"""
api/routes_ml.py - MLflow/공정 파라미터 최적화/모델 드리프트/모델 관리 API
"""
import asyncio
import json
import os
import random
import time
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Optional

from core.utils import safe_str, json_sanitize
from agent.tools import tool_optimize_process
import state as st
from api.common import verify_credentials, ModelSelectRequest, ProcessOptimizeRequest, error_response, sse_pack


router = APIRouter(prefix="/api", tags=["ml"])

# 제조 도메인 모델명 (MODEL_STATE_MAP 키와 일치)
MANUFACTURING_MODEL_NAMES = [
    "정비품질평가", "결함분류", "설비클러스터", "불량탐지", "설비고장예측",
    "수율예측", "설비RUL",
]

# 카페24 모델명 (감지 시 제조 시뮬레이션 데이터로 대체)
_CAFE24_MODEL_NAMES = {
    "CS응답품질", "Guardian감사로그이상탐지", "고객LTV예측", "리뷰감성분석",
    "매출예측", "문의자동분류", "상품수요예측", "셀러세그먼트", "셀러이탈예측",
    "이상거래탐지", "정산이상탐지",
}

# 제조 모델별 설명
_MFG_MODEL_DESCRIPTIONS = {
    "정비품질평가": "정비 작업 품질을 자동 평가하는 분류 모델",
    "결함분류": "제품 결함 유형을 자동 분류하는 모델",
    "설비클러스터": "설비 상태 기반 군집 분석 모델",
    "불량탐지": "실시간 불량 탐지 이상 감지 모델",
    "설비고장예측": "설비 고장을 사전 예측하는 모델",
    "수율예측": "공정 파라미터 기반 수율 예측 회귀 모델",
    "설비RUL": "설비 잔존 수명(Remaining Useful Life) 예측 모델",
}

# 제조 모델별 하이퍼파라미터 튜닝 파라미터 (Optuna용)
_MFG_MODEL_TUNING_PARAMS = {
    "정비품질평가": {"n_estimators": [50, 300], "max_depth": [3, 10], "learning_rate": [0.01, 0.3]},
    "결함분류": {"n_estimators": [100, 500], "max_depth": [4, 12], "min_samples_split": [2, 20]},
    "설비클러스터": {"n_clusters": [3, 10], "eps": [0.1, 2.0], "min_samples": [3, 15]},
    "불량탐지": {"contamination": [0.01, 0.1], "n_estimators": [100, 500], "max_features": [0.5, 1.0]},
    "설비고장예측": {"n_estimators": [100, 400], "max_depth": [3, 8], "learning_rate": [0.01, 0.2]},
    "수율예측": {"n_estimators": [50, 300], "num_leaves": [10, 50], "learning_rate": [0.01, 0.3]},
    "설비RUL": {"n_estimators": [100, 500], "max_depth": [4, 10], "subsample": [0.6, 1.0]},
}



def _generate_manufacturing_models_data() -> list:
    """제조 도메인 모델 시뮬레이션 데이터 생성 (/api/mlflow/models용)"""
    rng = np.random.default_rng(777)
    now_ts = int(pd.Timestamp.now().timestamp() * 1000)
    result = []
    for idx, model_name in enumerate(MANUFACTURING_MODEL_NAMES):
        n_versions = rng.integers(1, 4)  # 1~3 버전
        versions = []
        for ver in range(n_versions, 0, -1):
            days_ago = (n_versions - ver) * rng.integers(5, 20)
            ts = now_ts - int(days_ago * 86400 * 1000)
            versions.append({
                "version": str(ver),
                "stage": "Production" if ver == n_versions else "Archived",
                "status": "READY",
                "run_id": f"run_{model_name}_{ver}",
                "source": f"mlruns/models/{model_name}/v{ver}",
                "creation_timestamp": ts,
            })
        created_ts = now_ts - int(rng.integers(30, 90) * 86400 * 1000)
        result.append({
            "name": model_name,
            "creation_timestamp": created_ts,
            "last_updated_timestamp": now_ts - int(rng.integers(1, 10) * 86400 * 1000),
            "description": _MFG_MODEL_DESCRIPTIONS.get(model_name, ""),
            "versions": versions,
            "model_type": "registry",
        })
    return result


def _generate_manufacturing_versions_data() -> list:
    """제조 도메인 모델 버전 시뮬레이션 데이터 생성 (/api/models/versions용)"""
    rng = np.random.default_rng(42)
    versions = []
    for model_name in MANUFACTURING_MODEL_NAMES:
        n_versions = rng.integers(2, 5)  # 2~4 버전
        for ver in range(n_versions, 0, -1):
            days_ago = (n_versions - ver) * rng.integers(3, 15)
            created = (pd.Timestamp.now() - pd.Timedelta(days=int(days_ago))).isoformat()
            versions.append({
                "model_name": model_name,
                "version": str(ver),
                "stage": "Production" if ver == n_versions else "Archived",
                "status": "READY",
                "run_id": f"run_{model_name.lower()}_{ver}",
                "created_at": created,
                "metrics": {
                    "rmse": round(float(rng.uniform(0.0015, 0.0035)), 4),
                    "r2": round(float(rng.uniform(0.90, 0.99)), 4),
                    "mae": round(float(rng.uniform(0.0010, 0.0028)), 4),
                },
                "description": f"{model_name} 모델 v{ver}",
                "tuning_params": _MFG_MODEL_TUNING_PARAMS.get(model_name, {}),
            })
    return versions


# ============================================================
# MLflow 싱글톤 클라이언트
# ============================================================
_mlflow_client = None
_mlflow_uri_cached = None


def _get_mlflow_client():
    """MLflow 클라이언트 싱글톤 (URI 변경 시 재생성)"""
    global _mlflow_client, _mlflow_uri_cached
    import mlflow
    from mlflow.tracking import MlflowClient
    uri = _get_mlflow_uri()
    if _mlflow_client is None or _mlflow_uri_cached != uri:
        mlflow.set_tracking_uri(uri)
        _mlflow_client = MlflowClient()
        _mlflow_uri_cached = uri
    return _mlflow_client


# ============================================================
# MLflow
# ============================================================
@router.get("/mlflow/experiments")
def get_mlflow_experiments(user: dict = Depends(verify_credentials)):
    try:
        client = _get_mlflow_client()
        experiments = client.search_experiments()
        result = []
        for exp in experiments:
            runs = client.search_runs(experiment_ids=[exp.experiment_id], order_by=["start_time DESC"], max_results=10)
            runs_data = [{"run_id": run.info.run_id, "run_name": run.info.run_name, "status": run.info.status, "start_time": run.info.start_time, "end_time": run.info.end_time, "params": dict(run.data.params), "metrics": {k: round(v, 4) for k, v in run.data.metrics.items()}, "tags": dict(run.data.tags)} for run in runs]
            result.append({"experiment_id": exp.experiment_id, "name": exp.name, "artifact_location": exp.artifact_location, "lifecycle_stage": exp.lifecycle_stage, "runs": runs_data})
        return {"status": "success", "data": result}
    except ImportError:
        return error_response("MLflow가 설치되지 않았습니다.", data=[])
    except Exception as e:
        st.logger.exception("MLflow 조회 실패")
        return error_response(safe_str(e), data=[])


@router.get("/mlflow/models")
def get_mlflow_registered_models(user: dict = Depends(verify_credentials)):
    try:
        client = _get_mlflow_client()
        registered_models = client.search_registered_models()

        # 빈 결과 → 제조 시뮬레이션 데이터 반환
        if not registered_models:
            return {"status": "success", "data": _generate_manufacturing_models_data()}

        # 비제조 모델(구 카페24 잔재 등) 필터링 후 반환
        result = []
        for rm in registered_models:
            if rm.name in _CAFE24_MODEL_NAMES:
                continue
            versions = []
            try:
                all_versions = client.search_model_versions(filter_string=f"name='{rm.name}'")
                for v in sorted(all_versions, key=lambda x: int(x.version), reverse=True):
                    versions.append({"version": v.version, "stage": v.current_stage, "status": v.status, "run_id": v.run_id, "source": v.source, "creation_timestamp": v.creation_timestamp})
            except Exception:
                for v in rm.latest_versions:
                    versions.append({"version": v.version, "stage": v.current_stage, "status": v.status, "run_id": v.run_id, "source": v.source, "creation_timestamp": v.creation_timestamp})
            result.append({"name": rm.name, "creation_timestamp": rm.creation_timestamp, "last_updated_timestamp": rm.last_updated_timestamp, "description": rm.description or "", "versions": versions, "model_type": "registry"})

        # 필터 후 빈 결과 → 제조 시뮬레이션 데이터 반환
        if not result:
            return {"status": "success", "data": _generate_manufacturing_models_data()}

        return {"status": "success", "data": result}
    except ImportError:
        return {"status": "success", "data": _generate_manufacturing_models_data()}
    except Exception as e:
        st.logger.warning(f"MLflow 모델 조회 실패, 시뮬레이션 데이터 반환: {e}")
        return {"status": "success", "data": _generate_manufacturing_models_data()}


@router.get("/mlflow/models/selected")
def get_selected_models(user: dict = Depends(verify_credentials)):
    st.load_selected_models()
    return {"status": "success", "data": st.SELECTED_MODELS, "message": f"{len(st.SELECTED_MODELS)}개 모델이 선택되어 있습니다"}


@router.post("/mlflow/models/select")
def select_mlflow_model(req: ModelSelectRequest, user: dict = Depends(verify_credentials)):
    MODEL_STATE_MAP = {"정비품질평가": "MAINTENANCE_QUALITY_MODEL", "결함분류": "FAULT_CLASSIFICATION_MODEL", "설비클러스터": "EQUIPMENT_CLUSTER_MODEL", "불량탐지": "DEFECT_DETECTION_MODEL", "설비고장예측": "EQUIPMENT_FAILURE_MODEL", "수율예측": "YIELD_PREDICTION_MODEL", "설비RUL": "EQUIPMENT_RUL_MODEL"}
    state_attr = MODEL_STATE_MAP.get(req.model_name)
    if not state_attr:
        return error_response(f"알 수 없는 모델: {req.model_name}. 지원 모델: {list(MODEL_STATE_MAP.keys())}")
    try:
        import mlflow
        client = _get_mlflow_client()
        try:
            model_version = client.get_model_version(req.model_name, req.version)
            model_uri = f"models:/{req.model_name}/{req.version}"
            st.logger.info(f"모델 로드 시작: {model_uri}")
            loaded_model = mlflow.sklearn.load_model(model_uri)
            setattr(st, state_attr, loaded_model)
            st.logger.info(f"모델 로드 완료: st.{state_attr} = {model_uri}")
            st.SELECTED_MODELS[req.model_name] = req.version
            st.save_selected_models()
            return {"status": "success", "message": f"{req.model_name} v{req.version} 모델이 로드되었습니다", "data": {"model_name": req.model_name, "version": req.version, "stage": model_version.current_stage, "run_id": model_version.run_id, "state_variable": f"st.{state_attr}", "loaded": True}}
        except Exception as e:
            st.logger.warning(f"MLflow 모델 로드 실패: {e}")
            return error_response(f"모델 로드 실패: {safe_str(e)}", data={"model_name": req.model_name, "version": req.version})
    except ImportError:
        return error_response("MLflow가 설치되지 않았습니다.")
    except Exception as e:
        st.logger.exception("MLflow 모델 선택 실패")
        return error_response(safe_str(e))


def _get_mlflow_uri():
    ml_mlruns = os.path.join(st.BASE_DIR, "ml", "mlruns")
    backend_mlruns = os.path.join(st.BASE_DIR, "mlruns")
    project_mlruns = os.path.abspath(os.path.join(st.BASE_DIR, "..", "mlruns"))
    if os.path.exists(ml_mlruns):
        return f"file:{ml_mlruns}"
    elif os.path.exists(backend_mlruns):
        return f"file:{backend_mlruns}"
    elif os.path.exists(project_mlruns):
        return f"file:{project_mlruns}"
    return os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")


# ============================================================
# 공정 파라미터 최적화
# ============================================================
@router.get("/process/production-line/{line_id}")
def get_process_line_info(line_id: str, user: dict = Depends(verify_credentials)):
    try:
        if st.PRODUCTION_LINES_DF is None:
            return error_response("생산라인 데이터 없음")
        sid = line_id.strip().upper()
        _id_col = "line_id" if "line_id" in st.PRODUCTION_LINES_DF.columns else st.PRODUCTION_LINES_DF.columns[0]
        row = st.PRODUCTION_LINES_DF[st.PRODUCTION_LINES_DF[_id_col].str.upper() == sid]
        if row.empty:
            return error_response(f"생산라인 {line_id}을(를) 찾을 수 없습니다")
        line = row.iloc[0]
        equipment = []
        if st.EQUIPMENT_DF is not None:
            _eq_id_col = "line_id" if "line_id" in st.EQUIPMENT_DF.columns else st.EQUIPMENT_DF.columns[0]
            line_equipment = st.EQUIPMENT_DF[st.EQUIPMENT_DF.get(_eq_id_col, pd.Series()).str.upper() == sid] if _eq_id_col in st.EQUIPMENT_DF.columns else pd.DataFrame()
            if line_equipment.empty and st.EQUIPMENT_PERFORMANCE_DF is not None:
                equipment = st.EQUIPMENT_PERFORMANCE_DF.head(5).to_dict("records")
            else:
                equipment = line_equipment.head(5).to_dict("records")
        # equipment에 oee 필드 추가 (프론트엔드 차트용)
        for s in equipment:
            if "oee_rate" in s and "oee" not in s:
                s["oee"] = float(s["oee_rate"])
        data = {
            "line_id": line.get("line_id", sid),
            "total_yield": float(line.get("total_revenue", 0)),
            "total_work_orders": int(line.get("total_orders", 0)),
            "equipment_count": int(line.get("product_count", 0)),
            "resources": {
                "maintenance_budget": int(float(line.get("total_revenue", 0)) * 0.1),
                "monthly_yield": float(line.get("total_revenue", 0)),
                "equipment_count": int(line.get("product_count", 0)),
                "work_order_count": int(line.get("total_orders", 0)),
            },
            "equipment": equipment,
        }
        return json_sanitize({"status": "success", "data": data})
    except Exception as e:
        st.logger.exception("공정 생산라인 정보 조회 실패")
        return error_response(safe_str(e))


@router.post("/process/optimize")
def optimize_process_params(req: ProcessOptimizeRequest, user: dict = Depends(verify_credentials)):
    try:
        total_budget = None
        if req.budget_constraints and "total" in req.budget_constraints:
            total_budget = float(req.budget_constraints["total"])
        result = tool_optimize_process(line_id=req.line_id or "FM-LINE1", goal="maximize_roas", total_budget=total_budget)
        if result.get("status") == "FAILED":
            return error_response(result.get("error", "최적화 실패"))
        return {"status": "success", "data": result}
    except Exception as e:
        st.logger.exception("공정 파라미터 최적화 실패")
        return error_response(f"공정 파라미터 최적화 중 오류: {safe_str(e)}")


@router.get("/process/status")
def get_process_optimizer_status(user: dict = Depends(verify_credentials)):
    return {"status": "success", "data": {"optimizer_available": st.PRODUCTION_OPTIMIZER_AVAILABLE, "equipment_loaded": st.EQUIPMENT_DF is not None, "equipment_count": len(st.EQUIPMENT_DF) if st.EQUIPMENT_DF is not None else 0, "optimization_method": "P-PSO (Phasor Particle Swarm Optimization)"}}


# ============================================================
# 모델 드리프트 모니터링
# ============================================================
@router.get("/models/drift")
def get_model_drift(user: dict = Depends(verify_credentials)):
    """모델 드리프트 모니터링 데이터 (시뮬레이션)"""
    try:
        rng = np.random.default_rng(123)

        # RMSE 추이 (30일, 0.0020~0.0028 범위, 가끔 0.0028~0.0030 근접)
        base_rmse = 0.0022
        rmse_trend = []
        for i in range(30):
            drift = i * 0.00002  # 미세한 상승 트렌드
            noise = rng.normal(0, 0.0002)
            rmse = round(float(np.clip(base_rmse + drift + noise, 0.0018, 0.0032)), 4)
            d = (pd.Timestamp.now() - pd.Timedelta(days=29 - i)).strftime("%Y-%m-%d")
            rmse_trend.append({"date": d, "rmse": rmse})

        # Feature PSI (Population Stability Index) - 사상압연 공정 피처
        feature_names = [
            "전류_MA_1s", "속도_diff_1", "하중_ratio", "온도_MA_2s", "롤갭_WS",
            "교호작용_전류x속도", "시계열_차분_3", "이동통계_MA_3s", "스탠드간_diff", "도메인_pre_entry"
        ]
        feature_psi = []
        for fname in feature_names:
            psi = round(float(rng.exponential(0.05)), 4)
            if psi > 0.2:
                psi_status = "CRITICAL"
            elif psi > 0.1:
                psi_status = "WARNING"
            else:
                psi_status = "OK"
            feature_psi.append({"feature": fname, "psi": psi, "status": psi_status})

        # 에러 분포 (정규분포 히스토그램)
        errors = rng.normal(0, 0.002, 1000)
        hist_counts, bin_edges = np.histogram(errors, bins=20)
        error_distribution = []
        for j in range(len(hist_counts)):
            bin_center = round(float((bin_edges[j] + bin_edges[j + 1]) / 2), 4)
            error_distribution.append({"bin": bin_center, "count": int(hist_counts[j])})

        data = {
            "rmse_trend": rmse_trend,
            "feature_psi": feature_psi,
            "threshold": 0.003,
            "error_distribution": error_distribution,
        }

        return {"status": "success", "data": data}
    except Exception as e:
        st.logger.exception("모델 드리프트 데이터 생성 실패")
        return error_response(safe_str(e))


# ============================================================
# Pydantic 모델 (모델 관리 API용)
# ============================================================
class EnsembleWeightsRequest(BaseModel):
    weights: Dict[str, float] = Field(..., description="앙상블 가중치 (예: {xgboost: 0.4, lightgbm: 0.35, rf: 0.25})")


class ABTestRequest(BaseModel):
    model_a: str = Field(..., description="비교 모델 A")
    model_b: str = Field(..., description="비교 모델 B")


# ============================================================
# POST /api/models/retrain - 재학습 시뮬레이션 (SSE 스트림)
# ============================================================
@router.post("/models/retrain")
async def retrain_model(user: dict = Depends(verify_credentials)):
    """모델 재학습 시뮬레이션 — SSE 스트림으로 진행률 전송"""
    async def _stream():
        start_time = time.time()
        stages = [
            ("data_prep", 0, 25, "데이터 전처리 중..."),
            ("training", 25, 70, "모델 학습 중..."),
            ("evaluation", 70, 90, "모델 평가 중..."),
            ("deploy", 90, 100, "배포 중..."),
        ]

        for stage_name, start_pct, end_pct, desc in stages:
            steps = random.randint(3, 6)
            for step in range(steps + 1):
                progress = start_pct + (end_pct - start_pct) * step / steps
                yield sse_pack("progress", {
                    "stage": stage_name,
                    "progress": round(progress, 1),
                    "description": desc,
                })
                await asyncio.sleep(random.uniform(0.3, 0.6))

        duration = round(time.time() - start_time, 1)
        version = f"v{random.randint(2, 5)}.{random.randint(0, 9)}.{random.randint(0, 99)}"
        yield sse_pack("done", {
            "status": "success",
            "metrics": {
                "rmse": round(random.uniform(0.0015, 0.0030), 4),
                "r2": round(random.uniform(0.92, 0.99), 4),
                "mae": round(random.uniform(0.0010, 0.0025), 4),
            },
            "duration_sec": duration,
            "version": version,
        })

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# GET /api/models/versions - 모델 버전 이력
# ============================================================
@router.get("/models/versions")
def get_model_versions(user: dict = Depends(verify_credentials)):
    """모델 버전 이력 조회 (MLflow 조회, 카페24 모델이면 제조 시뮬레이션 반환)"""
    try:
        # MLflow에서 조회 시도
        client = _get_mlflow_client()
        registered = client.search_registered_models()
        if registered:
            model_names = [rm.name for rm in registered]
            versions = []
            for rm in registered:
                if rm.name in _CAFE24_MODEL_NAMES:
                    continue
                all_v = client.search_model_versions(filter_string=f"name='{rm.name}'")
                for v in sorted(all_v, key=lambda x: int(x.version), reverse=True):
                    versions.append({
                        "model_name": rm.name,
                        "version": v.version,
                        "stage": v.current_stage,
                        "status": v.status,
                        "run_id": v.run_id,
                        "created_at": v.creation_timestamp,
                        "description": rm.description or "",
                    })
            if versions:
                return {"status": "success", "data": versions}
    except Exception:
        pass

    # 제조 도메인 시뮬레이션 데이터
    return {"status": "success", "data": _generate_manufacturing_versions_data()}


# ============================================================
# POST /api/models/ensemble - 앙상블 가중치 설정
# ============================================================
@router.post("/models/ensemble")
def set_ensemble_weights(req: EnsembleWeightsRequest, user: dict = Depends(verify_credentials)):
    """앙상블 가중치 설정 및 예상 성능 개선치 반환"""
    try:
        # 가중치 합 검증
        total = sum(req.weights.values())
        if abs(total - 1.0) > 0.01:
            return error_response(f"가중치 합이 1.0이어야 합니다 (현재: {total:.2f})")

        # state에 저장
        st.ENSEMBLE_WEIGHTS = dict(req.weights)
        st.logger.info(f"앙상블 가중치 업데이트: {st.ENSEMBLE_WEIGHTS}")

        # 가중합 기반 예상 성능 계산 (시뮬레이션)
        rng = np.random.default_rng()
        base_metrics = {
            "xgboost": {"rmse": 0.0022, "r2": 0.965, "mae": 0.0018},
            "lightgbm": {"rmse": 0.0024, "r2": 0.960, "mae": 0.0019},
            "rf": {"rmse": 0.0028, "r2": 0.950, "mae": 0.0022},
        }

        ensemble_rmse = 0.0
        ensemble_r2 = 0.0
        ensemble_mae = 0.0
        for model_key, weight in req.weights.items():
            key_lower = model_key.lower()
            metrics = base_metrics.get(key_lower, {"rmse": 0.0025, "r2": 0.955, "mae": 0.0020})
            ensemble_rmse += weight * metrics["rmse"]
            ensemble_r2 += weight * metrics["r2"]
            ensemble_mae += weight * metrics["mae"]

        # 앙상블 효과 (개별 모델 대비 5~10% 개선)
        improvement = round(float(rng.uniform(5, 10)), 1)

        return {
            "status": "success",
            "weights": st.ENSEMBLE_WEIGHTS,
            "ensemble_metrics": {
                "rmse": round(ensemble_rmse * 0.92, 4),
                "r2": round(min(ensemble_r2 * 1.02, 0.999), 4),
                "mae": round(ensemble_mae * 0.93, 4),
            },
            "improvement_pct": improvement,
            "updated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        st.logger.exception("앙상블 가중치 설정 실패")
        return error_response(safe_str(e))


# ============================================================
# POST /api/models/ab-test - A/B 비교
# ============================================================
@router.post("/models/ab-test")
def ab_test_models(req: ABTestRequest, user: dict = Depends(verify_credentials)):
    """두 모델 A/B 비교 테스트"""
    try:
        rng = np.random.default_rng()

        def _sim_metrics(model_name: str) -> dict:
            """모델별 시뮬레이션 메트릭 생성"""
            seed_val = sum(ord(c) for c in model_name)
            m_rng = np.random.default_rng(seed_val)
            return {
                "model": model_name,
                "rmse": round(float(m_rng.uniform(0.0015, 0.0035)), 4),
                "r2": round(float(m_rng.uniform(0.91, 0.99)), 4),
                "mae": round(float(m_rng.uniform(0.0010, 0.0028)), 4),
                "inference_ms": round(float(m_rng.uniform(2, 15)), 1),
            }

        metrics_a = _sim_metrics(req.model_a)
        metrics_b = _sim_metrics(req.model_b)

        # 추천 결정 (R2 높고 RMSE 낮은 모델)
        score_a = metrics_a["r2"] - metrics_a["rmse"] * 100
        score_b = metrics_b["r2"] - metrics_b["rmse"] * 100
        if score_a >= score_b:
            recommendation = req.model_a
            reason = f"{req.model_a}이(가) R2 {metrics_a['r2']:.4f}, RMSE {metrics_a['rmse']:.4f}로 더 우수합니다."
        else:
            recommendation = req.model_b
            reason = f"{req.model_b}이(가) R2 {metrics_b['r2']:.4f}, RMSE {metrics_b['rmse']:.4f}로 더 우수합니다."

        return {
            "status": "success",
            "model_a": metrics_a,
            "model_b": metrics_b,
            "recommendation": recommendation,
            "reason": reason,
            "test_samples": random.randint(500, 2000),
            "tested_at": datetime.now().isoformat(),
        }
    except Exception as e:
        st.logger.exception("A/B 테스트 실패")
        return error_response(safe_str(e))
