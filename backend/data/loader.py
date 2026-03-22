"""
스마트팩토리 AI 플랫폼 - 데이터 로더
==============================
제조 AI 기반 스마트팩토리 시스템 개발 프로젝트

PKL 데이터 및 ML 모델 로딩
"""

import os
import time
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import joblib
import numpy as np
import pandas as pd

import state as st


def get_data_path(filename: str) -> Path:
    """데이터 파일 경로 반환"""
    return Path(st.BASE_DIR) / filename


def _optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame dtype 최적화 — state._optimize_df_memory 위임"""
    return st._optimize_df_memory(df)


def load_data_safe(filepath: Path) -> Optional[pd.DataFrame]:
    """안전한 PKL 데이터 로딩 (dtype 자동 최적화 포함)"""
    pkl_path = filepath.with_suffix(".pkl") if filepath.suffix != ".pkl" else filepath
    if not pkl_path.exists():
        st.logger.warning(f"데이터 파일 없음: {pkl_path}")
        return None
    try:
        df = pd.read_pickle(pkl_path)
        df = _optimize_dtypes(df)
        st.logger.info(f"PKL 로드 완료: {pkl_path.name} ({len(df)} rows, dtype 최적화 적용)")
        return df
    except Exception as e:
        st.logger.error(f"PKL 로드 실패: {pkl_path} - {e}")
        return None


# 하위 호환
load_csv_safe = load_data_safe


def load_model_safe(filepath: Path):
    """안전한 모델 로딩"""
    if not filepath.exists():
        st.logger.warning(f"모델 파일 없음: {filepath}")
        return None
    try:
        model = joblib.load(filepath)
        st.logger.info(f"모델 로드 완료: {filepath.name}")
        return model
    except Exception as e:
        st.logger.error(f"모델 로드 실패: {filepath} - {e}")
        return None


def load_all_data():
    """모든 데이터 로드 (H23/cross-2: ThreadPoolExecutor 병렬화)"""
    st.logger.info("=" * 50)
    st.logger.info("스마트팩토리 AI 플랫폼 데이터 로딩 시작 (PKL 병렬)")
    st.logger.info("=" * 50)

    _load_start = time.time()

    # ========================================
    # H23/cross-2: 데이터 병렬 로드
    # ========================================
    data_tasks = {
        "EQUIPMENT_DF": "equipment.pkl",
        "EQUIPMENT_TYPES_DF": "equipment_types.pkl",
        "MAINTENANCE_SERVICES_DF": "maintenance_services.pkl",
        "PRODUCTS_DF": "products.pkl",
        "PRODUCTION_LINES_DF": "production_lines.pkl",
        "LINE_ANALYTICS_DF": "line_analytics.pkl",
        "EQUIPMENT_PERFORMANCE_DF": "equipment_performance.pkl",
        "DAILY_PRODUCTION_DF": "daily_production.pkl",
        "MAINTENANCE_STATS_DF": "maintenance_stats.pkl",
        "WORK_ORDERS_DF": "work_orders.pkl",
        "DEFECT_DETAILS_DF": "defect_details.pkl",
        "EQUIPMENT_LIFECYCLE_DF": "equipment_lifecycle.pkl",
        "PRODUCTION_FUNNEL_DF": "production_funnel.pkl",
        "EQUIPMENT_ACTIVITY_DF": "equipment_activity.pkl",
    }

    def _load_data_task(attr_name, filename):
        return attr_name, load_data_safe(get_data_path(filename))

    # max_workers=4: 피크 메모리 감소 (Railway 512MB 제한 대응)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_load_data_task, attr, fname)
            for attr, fname in data_tasks.items()
        ]
        for future in as_completed(futures):
            try:
                attr_name, df = future.result()
                setattr(st, attr_name, df)
            except Exception as e:
                st.logger.error(f"PKL 병렬 로드 실패: {e}")

    # LINE_ANALYTICS_DF 후처리: equipment_grade_encoded → equipment_grade 디코딩
    # 구 데이터는 "equipment_grade_encoded", 신규 데이터는 "grade_encoded" 컬럼명을 사용할 수 있으므로
    # 두 컬럼명 모두 시도하는 fallback 처리
    if st.LINE_ANALYTICS_DF is not None:
        _la = st.LINE_ANALYTICS_DF
        # 신규 컬럼명 우선, 없으면 구 컬럼명 fallback
        _grade_enc_col = (
            "equipment_grade_encoded" if "equipment_grade_encoded" in _la.columns else
            "grade_encoded" if "grade_encoded" in _la.columns else
            None
        )
        if _grade_enc_col is not None:
            from core.constants import EQUIPMENT_GRADES
            st.LINE_ANALYTICS_DF["equipment_grade"] = (
                _la[_grade_enc_col]
                .map({i: t for i, t in enumerate(EQUIPMENT_GRADES)})
                .fillna("A")
            )
            st.logger.info(
                "LINE_ANALYTICS_DF: equipment_grade 컬럼 디코딩 완료 (소스 컬럼: %s)",
                _grade_enc_col,
            )

    # 운영 로그
    st.OPERATION_LOGS_DF = load_data_safe(get_data_path("operation_logs.pkl"))

    _data_elapsed = time.time() - _load_start
    st.logger.info("PKL 데이터 로드 완료: %.1f초", _data_elapsed)

    # ========================================
    # ML 모델 — Lazy Loading (Railway 메모리 최적화)
    # 시작 시 전체 로드 대신, 각 모델을 처음 사용할 때 로드
    # ========================================
    _model_start = time.time()

    model_tasks = {
        "MAINTENANCE_QUALITY_MODEL": "model_maintenance_quality.pkl",
        "FAULT_CLASSIFICATION_MODEL": "model_fault_classification.pkl",
        "EQUIPMENT_CLUSTER_MODEL": "model_equipment_cluster.pkl",
        "DEFECT_DETECTION_MODEL": "model_defect_detection.pkl",
        "EQUIPMENT_FAILURE_MODEL": "model_equipment_failure.pkl",
        "SHAP_EXPLAINER_FAILURE": "shap_explainer_failure.pkl",
        "YIELD_PREDICTION_MODEL": "model_yield_prediction.pkl",
        "EQUIPMENT_RUL_MODEL": "model_equipment_rul.pkl",
        "TFIDF_VECTORIZER": "tfidf_vectorizer.pkl",
        "SCALER_CLUSTER": "scaler_cluster.pkl",
    }

    def _load_model_task(attr_name, filename):
        return attr_name, load_model_safe(get_data_path(filename))

    # Lazy loading 모드: 파일 존재 여부만 확인, 실제 로드는 get_model()에서 수행
    st._LAZY_LOADING_ENABLED = True
    _available_models = []
    _missing_models = []
    for attr_name, filename in model_tasks.items():
        filepath = get_data_path(filename)
        if filepath.exists():
            _available_models.append(attr_name)
        else:
            _missing_models.append(attr_name)
            st._MODEL_LOAD_FAILED.add(attr_name)

    st.logger.info(
        "ML 모델 Lazy Loading 활성화: %d개 대기 (파일 있음), %d개 없음",
        len(_available_models), len(_missing_models),
    )

    # 고장 예측 모델 설정 (JSON) — 작은 파일이므로 즉시 로드
    failure_config_path = get_data_path("failure_model_config.json")
    if failure_config_path.exists():
        try:
            import json
            with open(failure_config_path, "r", encoding="utf-8") as f:
                st.FAILURE_MODEL_CONFIG = json.load(f)
            st.logger.info(f"고장 예측 모델 설정 로드 완료: {failure_config_path.name}")
        except Exception as e:
            st.logger.warning(f"고장 예측 모델 설정 로드 실패: {e}")
            st.FAILURE_MODEL_CONFIG = None

    _model_elapsed = time.time() - _model_start
    st.logger.info("ML 모델 Lazy Loading 설정 완료: %.1f초", _model_elapsed)

    # ========================================
    # 생산 최적화 모듈 확인
    # ========================================
    try:
        from ml.process_optimizer import MarketingOptimizer
        st.PRODUCTION_OPTIMIZER_AVAILABLE = True
        st.logger.info("생산 최적화 모듈 로드 완료")
    except ImportError as e:
        st.PRODUCTION_OPTIMIZER_AVAILABLE = False
        st.logger.warning(f"생산 최적화 모듈 로드 실패: {e}")

    # ========================================
    # 라벨 인코더 — Lazy Loading (get_model로 접근 시 자동 로드)
    # ========================================
    le_tasks = {
        "LE_WORK_ORDER_CATEGORY": "le_work_order_category.pkl",
        "LE_EQUIPMENT_GRADE": "le_equipment_grade.pkl",
        "LE_MAINTENANCE_PRIORITY": "le_maintenance_priority.pkl",
        "LE_FAULT_CATEGORY": "le_fault_category.pkl",
    }
    for attr_name, filename in le_tasks.items():
        filepath = get_data_path(filename)
        if not filepath.exists():
            st._MODEL_LOAD_FAILED.add(attr_name)
    # _MODEL_FILE_MAP에 라벨 인코더도 등록 (get_model에서 찾을 수 있도록)
    for attr_name, filename in le_tasks.items():
        st._MODEL_FILE_MAP[attr_name] = filename
    st.logger.info("라벨 인코더 Lazy Loading 설정 완료 (%d개)", len(le_tasks))

    # ========================================
    # 수율 예측 모델 초기화 (학습 필요 시 백그라운드)
    # ========================================
    try:
        from ml.yield_model import get_predictor, train_and_save
        predictor = get_predictor()

        if not predictor.is_fitted and st.EQUIPMENT_PERFORMANCE_DF is not None:
            def _train_yield_bg():
                try:
                    result = train_and_save(st.EQUIPMENT_PERFORMANCE_DF)
                    st.logger.info(f"수율 예측 모델 학습 완료: R2={result['cv_r2_mean']:.3f}")
                except Exception as ex:
                    st.logger.warning(f"수율 예측 모델 백그라운드 학습 실패: {ex}")
            st.logger.info("수율 예측 모델 백그라운드 학습 시작...")
            import threading
            threading.Thread(target=_train_yield_bg, daemon=True).start()
        elif predictor.is_fitted:
            st.logger.info("수율 예측 모델 로드 완료")
        else:
            st.logger.warning("수율 예측 모델 학습 불가 (equipment_performance.pkl 없음)")
    except Exception as e:
        st.logger.warning(f"수율 예측 모델 초기화 실패: {e}")

    # ========================================
    # 캐시 구성
    # ========================================
    build_caches()

    # ========================================
    # 시스템 상태 업데이트
    # ========================================
    st.SYSTEM_STATUS["data_loaded"] = True
    # lazy loading 모드에서는 파일 존재 여부로 모델 로드 가능 상태 판단
    st.SYSTEM_STATUS["models_loaded"] = (
        len(_available_models) > 0 or st.PRODUCTION_OPTIMIZER_AVAILABLE
    )

    st.logger.info("=" * 50)
    st.logger.info("데이터 로딩 완료")
    st.logger.info(f"  [기본 데이터]")
    st.logger.info(f"  - 설비: {len(st.EQUIPMENT_DF) if st.EQUIPMENT_DF is not None else 0}대")
    st.logger.info(f"  - 설비유형: {len(st.EQUIPMENT_TYPES_DF) if st.EQUIPMENT_TYPES_DF is not None else 0}개")
    st.logger.info(f"  - 부품/자재: {len(st.PRODUCTS_DF) if st.PRODUCTS_DF is not None else 0}개")
    st.logger.info(f"  - 생산라인: {len(st.PRODUCTION_LINES_DF) if st.PRODUCTION_LINES_DF is not None else 0}개")
    st.logger.info(f"  - 운영 로그: {len(st.OPERATION_LOGS_DF) if st.OPERATION_LOGS_DF is not None else 0}건")
    st.logger.info(f"  [분석용 데이터]")
    st.logger.info(f"  - 설비 성과: {len(st.EQUIPMENT_PERFORMANCE_DF) if st.EQUIPMENT_PERFORMANCE_DF is not None else 0}개")
    st.logger.info(f"  - 일별 생산: {len(st.DAILY_PRODUCTION_DF) if st.DAILY_PRODUCTION_DF is not None else 0}일")
    st.logger.info(f"  - 정비 통계: {len(st.MAINTENANCE_STATS_DF) if st.MAINTENANCE_STATS_DF is not None else 0}개")
    st.logger.info(f"  - 라이프사이클: {len(st.EQUIPMENT_LIFECYCLE_DF) if st.EQUIPMENT_LIFECYCLE_DF is not None else 0}개")
    # Lazy loading 모드에서는 파일 존재=대기(L), 파일 없음=X로 표시
    _model_status = lambda name: 'L(lazy)' if name in _available_models else 'X'
    st.logger.info(f"  [ML 모델 (Lazy Loading, 7개)]")
    st.logger.info(f"  - 설비 고장 예측: {_model_status('EQUIPMENT_FAILURE_MODEL')}")
    st.logger.info(f"  - 불량 탐지: {_model_status('DEFECT_DETECTION_MODEL')}")
    st.logger.info(f"  - 고장 자동 분류: {_model_status('FAULT_CLASSIFICATION_MODEL')}")
    st.logger.info(f"  - 설비 클러스터: {_model_status('EQUIPMENT_CLUSTER_MODEL')}")
    st.logger.info(f"  - 수율 예측: {_model_status('YIELD_PREDICTION_MODEL')}")
    st.logger.info(f"  - 정비 응답 품질: {_model_status('MAINTENANCE_QUALITY_MODEL')}")
    st.logger.info(f"  - 설비 RUL: {_model_status('EQUIPMENT_RUL_MODEL')}")
    st.logger.info(f"  - 생산 최적화: {'O' if st.PRODUCTION_OPTIMIZER_AVAILABLE else 'X'}")
    st.logger.info("=" * 50)

    # ========================================
    # 저장된 모델 선택 상태 로드 및 MLflow 모델 로드
    # ========================================
    load_selected_mlflow_models()


# MLflow 모델 경로 캐시 (version meta YAML → model_pkl_path)
_mlflow_path_cache: dict = {}


def load_selected_mlflow_models():
    """
    서버 시작 시 저장된 모델 선택 상태를 읽어서 MLflow 모델을 로드
    관리자가 선택한 모델이 서버 재시작 후에도 유지됨
    """
    import platform
    import yaml

    selected = st.load_selected_models()

    if not selected:
        st.logger.info("저장된 모델 선택 상태 없음 - 기본 pkl 모델 사용")
        return

    st.logger.info(f"저장된 모델 선택 상태 로드: {selected}")

    is_local = platform.system() == "Windows"
    st.logger.info(f"환경 감지: {'로컬(Windows)' if is_local else 'Docker(Linux)'}")

    # 모델 이름 → state 변수 매핑
    MODEL_STATE_MAP = {
        "설비고장예측": "EQUIPMENT_FAILURE_MODEL",
        "불량탐지": "DEFECT_DETECTION_MODEL",
        "고장자동분류": "FAULT_CLASSIFICATION_MODEL",
        "설비클러스터": "EQUIPMENT_CLUSTER_MODEL",
        "수율예측": "YIELD_PREDICTION_MODEL",
        "정비응답품질": "MAINTENANCE_QUALITY_MODEL",
        "설비RUL": "EQUIPMENT_RUL_MODEL",
    }

    ml_mlruns = os.path.join(st.BASE_DIR, "ml", "mlruns")
    if not os.path.exists(ml_mlruns):
        ml_mlruns = os.path.join(st.BASE_DIR, "mlruns")

    if not os.path.exists(ml_mlruns):
        st.logger.warning(f"MLflow 폴더 없음: {ml_mlruns}")
        return

    experiment_id = "660890565547137650"

    for model_name, version in selected.items():
        state_attr = MODEL_STATE_MAP.get(model_name)
        if not state_attr:
            st.logger.warning(f"알 수 없는 모델: {model_name}")
            continue

        loaded_model = None
        load_method = None

        # 1차 시도: MLflow API (Windows)
        if is_local:
            try:
                import mlflow
                mlflow.set_tracking_uri(f"file:///{ml_mlruns}")
                model_uri = f"models:/{model_name}/{version}"
                loaded_model = mlflow.pyfunc.load_model(model_uri)
                if hasattr(loaded_model, "_model_impl"):
                    loaded_model = loaded_model._model_impl.python_model
                    if hasattr(loaded_model, "model"):
                        loaded_model = loaded_model.model
                load_method = "MLflow API"
            except Exception as e:
                st.logger.debug(f"MLflow API 실패, fallback 시도: {e}")
                loaded_model = None

        # 2차 시도: joblib 직접 로드 (경로 캐싱)
        if loaded_model is None:
            cache_key = f"{model_name}:{version}"
            try:
                # 캐시된 pkl 경로 확인
                model_pkl_path = _mlflow_path_cache.get(cache_key)
                if model_pkl_path is None:
                    version_meta_path = os.path.join(
                        ml_mlruns, "models", model_name, f"version-{version}", "meta.yaml"
                    )
                    if not os.path.exists(version_meta_path):
                        st.logger.warning(f"버전 메타 없음: {version_meta_path}")
                        continue

                    with open(version_meta_path, "r", encoding="utf-8") as f:
                        version_meta = yaml.safe_load(f)

                    model_id = version_meta.get("model_id")
                    if not model_id:
                        st.logger.warning(f"model_id 없음: {model_name} v{version}")
                        continue

                    model_pkl_path = os.path.join(
                        ml_mlruns, experiment_id, "models", model_id, "artifacts", "model.pkl"
                    )
                    # 경로 캐싱
                    _mlflow_path_cache[cache_key] = model_pkl_path

                if not os.path.exists(model_pkl_path):
                    st.logger.warning(f"모델 파일 없음: {model_pkl_path}")
                    continue

                loaded_model = joblib.load(model_pkl_path)
                load_method = "직접 로드"
            except Exception as e:
                st.logger.warning(f"모델 로드 실패: {model_name} v{version} - {e}")
                continue

        if loaded_model is not None:
            setattr(st, state_attr, loaded_model)
            st.logger.info(f"[{load_method}] 모델 로드 완료: {model_name} v{version} → st.{state_attr}")


def build_caches():
    """캐시 데이터 구성 (groupby 벡터화)"""
    # 설비별 정비 서비스 매핑 — iterrows → groupby
    # 구 데이터: service_name / service_type 컬럼 존재
    # 신규 데이터: 해당 컬럼이 없을 수 있음 → 시뮬레이션 데이터로 fallback
    if st.MAINTENANCE_SERVICES_DF is not None and st.EQUIPMENT_DF is not None:
        svc_df = st.MAINTENANCE_SERVICES_DF.dropna(subset=["equipment_id"])
        cols = ["service_name", "service_type", "status", "description"]
        avail_cols = [c for c in cols if c in svc_df.columns]

        # service_name / service_type 중 하나라도 없으면 컬럼 불일치 → 시뮬레이션 fallback
        _key_cols_missing = not ("service_name" in svc_df.columns and "service_type" in svc_df.columns)
        if _key_cols_missing:
            st.logger.warning(
                "MAINTENANCE_SERVICES_DF에 service_name/service_type 컬럼 없음 "
                "(신규 스키마 불일치) — 시뮬레이션 서비스 데이터로 fallback"
            )
            _sim_services = [
                {"service_name": "예방정비", "service_type": "PM", "status": "완료", "description": "정기 예방 정비"},
                {"service_name": "긴급정비", "service_type": "EM", "status": "대기", "description": "긴급 고장 수리"},
                {"service_name": "정기점검", "service_type": "IM", "status": "완료", "description": "주기적 설비 점검"},
            ]
            # 모든 설비에 동일한 시뮬레이션 서비스 매핑
            for equipment_id in st.EQUIPMENT_DF["equipment_id"] if "equipment_id" in st.EQUIPMENT_DF.columns else []:
                st.EQUIPMENT_SERVICE_MAP[equipment_id] = _sim_services
        else:
            for equipment_id, group in svc_df.groupby("equipment_id"):
                st.EQUIPMENT_SERVICE_MAP[equipment_id] = group[avail_cols].to_dict("records")
        st.logger.info(f"설비 정비 서비스 캐시 구성: {len(st.EQUIPMENT_SERVICE_MAP)}개")

    # 설비별 성과 KPI 캐시 (O(1) 조회용)
    if st.EQUIPMENT_PERFORMANCE_DF is not None and "equipment_id" in st.EQUIPMENT_PERFORMANCE_DF.columns:
        st.EQUIPMENT_PERF_MAP = st.EQUIPMENT_PERFORMANCE_DF.set_index("equipment_id").to_dict("index")
        st.logger.info(f"설비 성과 캐시 구성: {len(st.EQUIPMENT_PERF_MAP)}개")


def get_data_summary() -> dict:
    """데이터 요약 정보 반환"""
    return {
        "equipment": {
            "count": len(st.EQUIPMENT_DF) if st.EQUIPMENT_DF is not None else 0,
            "loaded": st.EQUIPMENT_DF is not None,
        },
        "equipment_types": {
            "count": len(st.EQUIPMENT_TYPES_DF) if st.EQUIPMENT_TYPES_DF is not None else 0,
            "loaded": st.EQUIPMENT_TYPES_DF is not None,
        },
        "maintenance_services": {
            "count": len(st.MAINTENANCE_SERVICES_DF) if st.MAINTENANCE_SERVICES_DF is not None else 0,
            "loaded": st.MAINTENANCE_SERVICES_DF is not None,
        },
        "products": {
            "count": len(st.PRODUCTS_DF) if st.PRODUCTS_DF is not None else 0,
            "loaded": st.PRODUCTS_DF is not None,
        },
        "production_lines": {
            "count": len(st.PRODUCTION_LINES_DF) if st.PRODUCTION_LINES_DF is not None else 0,
            "loaded": st.PRODUCTION_LINES_DF is not None,
        },
        "operation_logs": {
            "count": len(st.OPERATION_LOGS_DF) if st.OPERATION_LOGS_DF is not None else 0,
            "loaded": st.OPERATION_LOGS_DF is not None,
        },
        "line_analytics": {
            "count": len(st.LINE_ANALYTICS_DF) if st.LINE_ANALYTICS_DF is not None else 0,
            "loaded": st.LINE_ANALYTICS_DF is not None,
        },
        "equipment_performance": {
            "count": len(st.EQUIPMENT_PERFORMANCE_DF) if st.EQUIPMENT_PERFORMANCE_DF is not None else 0,
            "loaded": st.EQUIPMENT_PERFORMANCE_DF is not None,
        },
        "daily_production": {
            "count": len(st.DAILY_PRODUCTION_DF) if st.DAILY_PRODUCTION_DF is not None else 0,
            "loaded": st.DAILY_PRODUCTION_DF is not None,
        },
        "maintenance_stats": {
            "count": len(st.MAINTENANCE_STATS_DF) if st.MAINTENANCE_STATS_DF is not None else 0,
            "loaded": st.MAINTENANCE_STATS_DF is not None,
        },
        "equipment_lifecycle": {
            "count": len(st.EQUIPMENT_LIFECYCLE_DF) if st.EQUIPMENT_LIFECYCLE_DF is not None else 0,
            "loaded": st.EQUIPMENT_LIFECYCLE_DF is not None,
        },
        "models": {
            "equipment_failure": st.EQUIPMENT_FAILURE_MODEL is not None or "EQUIPMENT_FAILURE_MODEL" not in st._MODEL_LOAD_FAILED,
            "defect_detection": st.DEFECT_DETECTION_MODEL is not None or "DEFECT_DETECTION_MODEL" not in st._MODEL_LOAD_FAILED,
            "fault_classification": st.FAULT_CLASSIFICATION_MODEL is not None or "FAULT_CLASSIFICATION_MODEL" not in st._MODEL_LOAD_FAILED,
            "equipment_cluster": st.EQUIPMENT_CLUSTER_MODEL is not None or "EQUIPMENT_CLUSTER_MODEL" not in st._MODEL_LOAD_FAILED,
            "yield_prediction": st.YIELD_PREDICTION_MODEL is not None or "YIELD_PREDICTION_MODEL" not in st._MODEL_LOAD_FAILED,
            "maintenance_quality": st.MAINTENANCE_QUALITY_MODEL is not None or "MAINTENANCE_QUALITY_MODEL" not in st._MODEL_LOAD_FAILED,
            "equipment_rul": st.EQUIPMENT_RUL_MODEL is not None or "EQUIPMENT_RUL_MODEL" not in st._MODEL_LOAD_FAILED,
            "production_optimizer": st.PRODUCTION_OPTIMIZER_AVAILABLE,
        },
    }


# 기존 함수 호환성을 위한 alias
def init_data_models():
    """데이터 로드 및 모델 초기화 (startup 시 호출)"""
    if st.SYSTEM_STATUS.get("data_loaded"):
        st.logger.info("데이터 이미 로드됨 - 스킵")
        return
    load_all_data()
