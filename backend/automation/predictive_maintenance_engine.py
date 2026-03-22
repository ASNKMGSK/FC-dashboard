"""
automation/predictive_maintenance_engine.py - 설비 예지보전 자동 조치 엔진
=============================================================
ML 고장예측 → SHAP 고장원인분석 → LLM 정비계획 생성 → 정비실행
스마트팩토리 패턴: 센서 데이터 분석 → AI 판단 → 자동 정비 실행
"""
import time
import uuid
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from core.constants import FEATURE_COLS_FAILURE, FEATURE_LABELS, EQUIPMENT_GRADES
from core.utils import safe_str, safe_int, safe_float
from automation.action_logger import log_action, save_maintenance_action, create_pipeline_run, update_pipeline_step, complete_pipeline_run
import state as st


def _extract_shap_values(explainer, X, batch_size: int = 500) -> "np.ndarray | None":
    """SHAP 값 추출 공통 로직 (배치/단일 공용).
    대규모 데이터에서 메모리 폭발 방지를 위해 batch_size(기본 500)씩 분할 처리합니다.
    """
    try:
        n_samples = X.shape[0]
        # 배치 크기 이하면 한번에 처리
        if n_samples <= batch_size:
            return _extract_shap_values_single(explainer, X)

        # 배치 분할 처리 — 메모리 절감
        st.logger.info("PREDICTIVE_MAINTENANCE SHAP 배치 분할 처리: %d건 → %d개 배치 (배치당 %d건)",
                       n_samples, (n_samples + batch_size - 1) // batch_size, batch_size)
        chunks = []
        for start in range(0, n_samples, batch_size):
            end = min(start + batch_size, n_samples)
            chunk_result = _extract_shap_values_single(explainer, X[start:end])
            if chunk_result is None:
                return None
            chunks.append(chunk_result)
        return np.concatenate(chunks, axis=0)
    except (ValueError, TypeError, RuntimeError) as e:
        st.logger.error("PREDICTIVE_MAINTENANCE SHAP extraction error: %s", str(e))
        return None


def _extract_shap_values_single(explainer, X) -> "np.ndarray | None":
    """단일 배치에 대한 SHAP 값 추출 (내부용)"""
    try:
        if hasattr(explainer, "shap_values"):
            shap_result = explainer.shap_values(X)
            if isinstance(shap_result, list) and len(shap_result) == 2:
                return np.array(shap_result[1])
            elif isinstance(shap_result, np.ndarray):
                if shap_result.ndim == 3:
                    return shap_result[:, :, 1]
                return shap_result
            return np.array(shap_result)
        else:
            shap_result = explainer(X)
            if hasattr(shap_result, "values"):
                return shap_result.values
            return np.array(shap_result)
    except (ValueError, TypeError, RuntimeError) as e:
        st.logger.error("PREDICTIVE_MAINTENANCE SHAP extraction error: %s", str(e))
        return None


def _shap_top_factors(shap_vals_row: "np.ndarray", feature_cols, top_n: int = 5) -> List[Dict]:
    """SHAP 값에서 상위 N개 고장 원인 추출"""
    feat_imp = sorted(
        zip(feature_cols, np.abs(shap_vals_row)),
        key=lambda x: x[1], reverse=True
    )
    return [
        {"factor": FEATURE_LABELS.get(feat, feat), "importance": round(float(imp) * 100, 1)}
        for feat, imp in feat_imp[:top_n]
    ]


def _heuristic_score(row) -> float:
    """휴리스틱 고장 위험 점수 계산 (공통 로직)"""
    days_since_last = safe_int(row.get("days_since_last_maintenance", 0))  # 마지막 정비 이후 일수
    total_orders = safe_int(row.get("operating_hours", row.get("total_orders", 0)))  # 총 가동시간(시간)
    total_revenue = safe_int(row.get("production_volume", row.get("total_revenue", 0)))  # 총 생산량
    refund_rate = safe_float(row.get("defect_rate", row.get("refund_rate", 0)))  # 불량률
    cs_tickets = safe_int(row.get("cs_tickets", 0))  # 정비요청 건수

    score = 0.3
    if days_since_last > 14:
        score += 0.25
    elif days_since_last > 7:
        score += 0.15
    if total_orders < 10:
        score += 0.1
    if total_revenue < 100000:
        score += 0.1
    if refund_rate > 10:
        score += 0.1
    if cs_tickets > 20:
        score += 0.05
    return min(max(score, 0.05), 0.95)


def _build_feature_df(df, feature_cols) -> "pd.DataFrame":
    """고장 예측용 피처 DataFrame 구성 (벡터화)"""
    cols_no_tier = [c for c in feature_cols if c != "plan_tier_encoded"]
    present = [c for c in cols_no_tier if c in df.columns]
    missing = [c for c in cols_no_tier if c not in df.columns]

    X = df[present].copy() if present else pd.DataFrame(index=df.index)
    for col in missing:
        X[col] = 0.0
    X[present] = X[present].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    if "plan_tier_encoded" in feature_cols and "plan_tier" in df.columns:
        tier_map = {tier: i for i, tier in enumerate(EQUIPMENT_GRADES)}
        X["plan_tier_encoded"] = df["plan_tier"].map(tier_map).fillna(0).astype(int)

    return X[feature_cols]


def get_at_risk_equipment(threshold: float = 0.6, limit: int = 20) -> List[Dict]:
    """
    고장 위험 설비 목록을 반환합니다.
    ML 고장예측 모델로 예측하고 SHAP으로 고장 원인을 분석합니다.
    threshold 이상인 설비만 필터링, 고장확률 높은 순 정렬.
    """
    run_id = create_pipeline_run("predictive_maintenance", ["detect", "analyze"])
    update_pipeline_step(run_id, "detect", "processing")

    if st.LINE_ANALYTICS_DF is None:
        st.logger.warning("PREDICTIVE_MAINTENANCE get_at_risk_equipment: EQUIPMENT_DF is None")
        return []

    # 읽기 전용 — 원본 수정 없으므로 copy 생략 (메모리 절감)
    df = st.LINE_ANALYTICS_DF
    if df.empty:
        return []

    results = []

    # ML 모델이 있는 경우 (lazy loading)
    st.get_model("EQUIPMENT_FAILURE_MODEL")
    if st.EQUIPMENT_FAILURE_MODEL is not None:
        try:
            feature_cols = FEATURE_COLS_FAILURE
            X = _build_feature_df(df, feature_cols)

            # 고장 확률 예측
            proba = st.EQUIPMENT_FAILURE_MODEL.predict_proba(X)[:, 1]

            # SHAP 분석
            shap_values_all = None

            # threshold 필터링 후 해당 행만 순회 (벡터화 필터)
            mask = proba >= threshold
            filtered_indices = np.where(mask)[0]

            for idx in filtered_indices:
                prob = float(proba[idx])
                row = df.iloc[idx]

                # SHAP top factors
                top_factors = []
                if shap_values_all is not None:
                    top_factors = _shap_top_factors(shap_values_all[idx], feature_cols)

                if not top_factors:
                    top_factors = _default_factors(row)

                results.append({
                    "equipment_id": safe_str(row.get("line_id", "")),
                    "failure_probability": round(prob * 100, 1),
                    "risk_level": "high" if prob > 0.7 else "medium",
                    "top_factors": top_factors,
                    "equipment_info": {
                        "operating_hours": safe_int(row.get("operating_hours", row.get("total_orders", 0))),
                        "production_volume": safe_int(row.get("production_volume", row.get("total_revenue", 0))),
                        "days_since_last_maintenance": safe_int(row.get("days_since_last_maintenance", 0)),
                        "defect_rate": safe_float(row.get("defect_rate", row.get("refund_rate", 0))),
                        "component_count": safe_int(row.get("product_count", 0)),
                    },
                })

        except (ValueError, TypeError, RuntimeError) as e:
            st.logger.error("PREDICTIVE_MAINTENANCE ML prediction error: %s", str(e))
            results = _heuristic_at_risk(df, threshold)
    else:
        # 모델이 없으면 휴리스틱 사용
        results = _heuristic_at_risk(df, threshold)

    # 고장확률 높은 순 정렬 + limit
    results.sort(key=lambda x: x["failure_probability"], reverse=True)
    update_pipeline_step(run_id, "detect", "complete", {"count": len(results)})
    update_pipeline_step(run_id, "analyze", "complete")
    complete_pipeline_run(run_id)
    return results[:limit]




def _heuristic_at_risk(df: pd.DataFrame, threshold: float) -> List[Dict]:
    """ML 모델이 없을 때 휴리스틱으로 고장 위험 설비를 산출합니다 (벡터화)."""
    # 벡터화 휴리스틱 점수 계산
    _days_col = "days_since_last_maintenance" if "days_since_last_maintenance" in df.columns else "days_since_install"
    _hours_col = "operating_hours" if "operating_hours" in df.columns else "total_orders"
    _vol_col = "production_volume" if "production_volume" in df.columns else "total_revenue"
    _defect_col = "defect_rate" if "defect_rate" in df.columns else "refund_rate"
    days = pd.to_numeric(df.get(_days_col, 0), errors="coerce").fillna(0)
    orders = pd.to_numeric(df.get(_hours_col, 0), errors="coerce").fillna(0)
    revenue = pd.to_numeric(df.get(_vol_col, 0), errors="coerce").fillna(0)
    refund = pd.to_numeric(df.get(_defect_col, 0), errors="coerce").fillna(0)
    cs = pd.to_numeric(df.get("cs_tickets", 0), errors="coerce").fillna(0)

    scores = pd.Series(0.3, index=df.index)
    scores += np.where(days > 14, 0.25, np.where(days > 7, 0.15, 0.0))
    scores += np.where(orders < 10, 0.1, 0.0)
    scores += np.where(revenue < 100000, 0.1, 0.0)
    scores += np.where(refund > 10, 0.1, 0.0)
    scores += np.where(cs > 20, 0.05, 0.0)
    scores = scores.clip(0.05, 0.95)

    # threshold 필터링 후 해당 행만 순회
    mask = scores >= threshold
    results = []
    for idx in np.where(mask)[0]:
        row = df.iloc[idx]
        score = float(scores.iloc[idx])
        results.append({
            "equipment_id": safe_str(row.get("line_id", "")),
            "failure_probability": round(score * 100, 1),
            "risk_level": "high" if score > 0.7 else "medium",
            "top_factors": _default_factors(row),
            "equipment_info": {
                "operating_hours": safe_int(row.get("operating_hours", row.get("total_orders", 0))),
                "production_volume": safe_int(row.get("production_volume", row.get("total_revenue", 0))),
                "days_since_last_maintenance": safe_int(row.get("days_since_last_maintenance", 0)),
                "defect_rate": safe_float(row.get("defect_rate", row.get("refund_rate", 0))),
                "component_count": safe_int(row.get("product_count", 0)),
            },
        })
    return results


def _default_factors(row) -> List[Dict]:
    """기본 고장 원인 목록을 생성합니다."""
    return [
        {"factor": f"마지막 정비 {safe_int(row.get('days_since_last_maintenance', 0))}일 전", "importance": 30},
        {"factor": f"총 가동시간 {safe_int(row.get('operating_hours', row.get('total_orders', 0)))}시간", "importance": 25},
        {"factor": f"총 생산량 {safe_int(row.get('production_volume', row.get('total_revenue', 0))):,}개", "importance": 20},
        {"factor": f"불량률 {safe_float(row.get('defect_rate', row.get('refund_rate', 0)))}%", "importance": 15},
        {"factor": f"정비요청 {safe_int(row.get('cs_tickets', 0))}건", "importance": 10},
    ]


def generate_maintenance_plan(equipment_id: str) -> Dict:
    """
    특정 설비에 대한 맞춤 정비계획을 템플릿 기반으로 생성합니다.
    부품교체, 윤활, 정밀점검, 긴급수리 등 추천 포함.
    """
    if st.LINE_ANALYTICS_DF is None:
        return {"equipment_id": equipment_id, "message": "", "recommended_actions": [],
                "urgency": "unknown", "error": "설비 분석 데이터가 로드되지 않았습니다."}

    id_col = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
    equipment = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[id_col] == equipment_id]
    if equipment.empty:
        return {"equipment_id": equipment_id, "message": "", "recommended_actions": [],
                "urgency": "unknown", "error": f"설비 '{equipment_id}'를 찾을 수 없습니다."}

    row = equipment.iloc[0]

    # 고장 원인 분석
    failure_info = _analyze_single_equipment(row)

    # 위험 등급에 따라 분기
    risk = failure_info["risk_level"]
    prob = failure_info["failure_probability"]
    top_factors = [f["factor"] for f in failure_info["top_factors"][:3]]

    # LOW 위험: 즉시 "정비 불필요" 판단 반환
    if risk.upper() == "LOW":
        return {
            "equipment_id": equipment_id,
            "message": "",
            "recommended_actions": [],
            "urgency": "none",
            "risk_level": "LOW",
            "failure_probability": prob,
            "judgment": "정비 조치 불필요 — 고장 위험이 LOW입니다. 현재 상태를 유지하면서 정기 모니터링만 권장합니다.",
        }

    # MEDIUM/HIGH: 템플릿 기반 정비계획 생성
    operating_hours = safe_int(row.get("operating_hours", row.get("total_orders", 0)))
    days_since_maint = safe_int(row.get("days_since_last_maintenance", 0))
    defect_rate = safe_float(row.get("defect_rate", row.get("refund_rate", 0)))

    urgency = "high" if risk.upper() == "HIGH" else "medium"

    message = f"설비 {equipment_id}의 고장 확률이 {prob:.1f}%입니다.\n"
    message += f"주요 위험 요인: {', '.join(top_factors)}\n"
    message += f"권장 조치: {'긴급 점검 필요' if prob > 70 else '정기 점검 권장'}"

    recommended_actions = []
    if days_since_maint > 14:
        recommended_actions.append(f"정비 주기 초과({days_since_maint}일) — 즉시 정밀 점검 실시")
    if defect_rate > 5:
        recommended_actions.append(f"불량률 {defect_rate}% — 핵심 부품 교체 검토")
    if operating_hours > 500:
        recommended_actions.append(f"가동시간 {operating_hours}시간 — 베어링/기어 윤활 작업 필요")
    if prob > 70:
        recommended_actions.append("긴급 수리팀 배정 및 예비 부품 확보")
    if not recommended_actions:
        recommended_actions.append("정기 점검 스케줄에 따른 예방 정비 실시")

    return {
        "equipment_id": equipment_id,
        "message": message,
        "recommended_actions": recommended_actions,
        "urgency": urgency,
    }


# 하위 호환성 (구 카페24 네이밍)
generate_maintenance_plan_alias = generate_maintenance_plan


def _analyze_single_equipment(row) -> Dict:
    """단일 설비의 고장 분석 결과를 반환합니다."""
    # lazy loading
    st.get_model("EQUIPMENT_FAILURE_MODEL")
    if st.EQUIPMENT_FAILURE_MODEL is not None:
        try:
            feature_cols = FEATURE_COLS_FAILURE
            X = pd.DataFrame([{col: safe_float(row.get(col, 0)) for col in feature_cols}])

            if "plan_tier_encoded" in feature_cols and "plan_tier" in row.index:
                tier_map = {tier: i for i, tier in enumerate(EQUIPMENT_GRADES)}
                X["plan_tier_encoded"] = tier_map.get(row.get("plan_tier", "Basic"), 0)

            prob = float(st.EQUIPMENT_FAILURE_MODEL.predict_proba(X)[0][1])
            risk_level = "high" if prob > 0.7 else "medium" if prob > 0.3 else "low"

            top_factors = []
            if not top_factors:
                top_factors = _default_factors(row)

            return {
                "failure_probability": round(prob * 100, 1),
                "risk_level": risk_level,
                "top_factors": top_factors,
            }
        except (ValueError, TypeError, RuntimeError) as e:
            st.logger.error("PREDICTIVE_MAINTENANCE _analyze_single_equipment ML error: %s", str(e))

    # 휴리스틱 폴백
    score = _heuristic_score(row)

    return {
        "failure_probability": round(score * 100, 1),
        "risk_level": "high" if score > 0.7 else "medium" if score > 0.3 else "low",
        "top_factors": _default_factors(row),
    }




async def get_at_risk_equipment_stream(threshold: float = 0.6, limit: int = 20):
    """
    고장 위험 설비 목록을 SSE 스트리밍으로 반환하는 async generator.
    개별 설비 ML 예측 + SHAP 분석 시 yield로 진행 이벤트 방출.
    """
    import asyncio

    if st.LINE_ANALYTICS_DF is None:
        st.logger.warning("PREDICTIVE_MAINTENANCE get_at_risk_equipment_stream: EQUIPMENT_DF is None")
        yield {"event": "error", "data": {"message": "설비 분석 데이터가 로드되지 않았습니다."}}
        return

    df = st.LINE_ANALYTICS_DF
    if df.empty:
        yield {"event": "done", "data": {"ok": True, "equipment": [], "total": 0, "total_elapsed_ms": 0}}
        return

    start_time = time.time()

    yield {"event": "step_start", "data": {"step": "detect", "description": "ML 고장 예측 시작", "timestamp": time.time()}}
    await asyncio.sleep(0)

    results = []

    st.get_model("EQUIPMENT_FAILURE_MODEL")
    if st.EQUIPMENT_FAILURE_MODEL is not None:
        try:
            feature_cols = FEATURE_COLS_FAILURE
            X = _build_feature_df(df, feature_cols)

            proba = st.EQUIPMENT_FAILURE_MODEL.predict_proba(X)[:, 1]
            shap_values_all = None

            mask = proba >= threshold
            filtered_indices = np.where(mask)[0]
            total = min(len(filtered_indices), limit)

            for i, idx in enumerate(filtered_indices[:limit]):
                prob = float(proba[idx])
                row = df.iloc[idx]

                top_factors = []
                if shap_values_all is not None:
                    top_factors = _shap_top_factors(shap_values_all[idx], feature_cols)
                if not top_factors:
                    top_factors = _default_factors(row)

                equipment_result = {
                    "equipment_id": safe_str(row.get("line_id", "")),
                    "failure_probability": round(prob * 100, 1),
                    "risk_level": "high" if prob > 0.7 else "medium",
                    "top_factors": top_factors,
                    "equipment_info": {
                        "operating_hours": safe_int(row.get("operating_hours", row.get("total_orders", 0))),
                        "production_volume": safe_int(row.get("production_volume", row.get("total_revenue", 0))),
                        "days_since_last_maintenance": safe_int(row.get("days_since_last_maintenance", 0)),
                        "defect_rate": safe_float(row.get("defect_rate", row.get("refund_rate", 0))),
                        "component_count": safe_int(row.get("product_count", 0)),
                    },
                }
                results.append(equipment_result)

                yield {"event": "equipment_result", "data": equipment_result}
                yield {"event": "step_progress", "data": {
                    "step": "detect", "current": i + 1, "total": total,
                    "detail": f"{safe_str(row.get('line_id', ''))} 분석 완료",
                }}
                await asyncio.sleep(0)

        except (ValueError, TypeError, RuntimeError) as e:
            st.logger.error("PREDICTIVE_MAINTENANCE ML prediction error (stream): %s", str(e))
            heuristic_results = _heuristic_at_risk(df, threshold)
            total = min(len(heuristic_results), limit)
            for i, equipment_result in enumerate(heuristic_results[:limit]):
                results.append(equipment_result)
                yield {"event": "equipment_result", "data": equipment_result}
                yield {"event": "step_progress", "data": {
                    "step": "detect", "current": i + 1, "total": total,
                    "detail": f"{equipment_result['equipment_id']} 분석 완료 (휴리스틱)",
                }}
                await asyncio.sleep(0)
    else:
        heuristic_results = _heuristic_at_risk(df, threshold)
        total = min(len(heuristic_results), limit)
        for i, equipment_result in enumerate(heuristic_results[:limit]):
            results.append(equipment_result)
            yield {"event": "equipment_result", "data": equipment_result}
            yield {"event": "step_progress", "data": {
                "step": "detect", "current": i + 1, "total": total,
                "detail": f"{equipment_result['equipment_id']} 분석 완료 (휴리스틱)",
            }}
            await asyncio.sleep(0)

    results.sort(key=lambda x: x["failure_probability"], reverse=True)

    detect_elapsed = int((time.time() - start_time) * 1000)
    yield {"event": "step_end", "data": {"step": "detect", "elapsed_ms": detect_elapsed, "result_count": len(results)}}

    total_elapsed = int((time.time() - start_time) * 1000)
    yield {"event": "done", "data": {"ok": True, "equipment": results, "total": len(results), "total_elapsed_ms": total_elapsed}}




def execute_maintenance_action(equipment_id: str, action_type: str) -> Dict:
    """
    정비 조치를 실행합니다 (시뮬레이션).
    action_type: "part_replacement" | "lubrication" | "detailed_inspection" | "emergency_repair"
    """
    run_id = create_pipeline_run("maintenance_action", ["execute", "log"])
    update_pipeline_step(run_id, "execute", "processing")

    valid_actions = {"part_replacement", "lubrication", "detailed_inspection", "emergency_repair"}
    if action_type not in valid_actions:
        return {
            "status": "error",
            "message": f"지원하지 않는 조치 유형입니다: {action_type}. "
                       f"사용 가능: {', '.join(sorted(valid_actions))}",
        }

    action_id = str(uuid.uuid4())[:8]
    timestamp = time.time()

    # 조치별 상세 내용 시뮬레이션
    action_details = {
        "part_replacement": {
            "description": "부품 교체",
            "detail": f"설비 {equipment_id}의 마모 부품 교체 작업 지시 완료 (예상 소요: 4시간)",
            "part_code": f"PART-{action_id.upper()}",
            "estimated_hours": 4,
            "priority": "high",
        },
        "lubrication": {
            "description": "윤활 작업",
            "detail": f"설비 {equipment_id}의 베어링/기어 윤활 작업 지시 완료 (예상 소요: 1시간)",
            "lubricant_type": "ISO VG 68",
            "estimated_hours": 1,
        },
        "detailed_inspection": {
            "description": "정밀 점검",
            "detail": f"설비 {equipment_id}의 정밀 점검 스케줄 등록 완료 (24시간 내 실시 예정)",
            "inspector_id": f"INS-{str(uuid.uuid4())[:4].upper()}",
            "inspection_deadline_hours": 24,
        },
        "emergency_repair": {
            "description": "긴급 수리",
            "detail": f"설비 {equipment_id}의 긴급 수리 작업 지시 완료 (즉시 대응)",
            "repair_team": f"TEAM-{str(uuid.uuid4())[:4].upper()}",
            "response_time_minutes": 30,
        },
    }

    detail = action_details[action_type]

    # 액션 로깅
    log_entry = log_action(
        action_type=f"maintenance_{action_type}",
        target_id=equipment_id,
        detail=detail,
        status="success",
    )

    # 정비 히스토리 저장
    maintenance_record = {
        "action_id": action_id,
        "equipment_id": equipment_id,
        "action_type": action_type,
        "description": detail["description"],
        "detail": detail["detail"],
        "timestamp": timestamp,
        "log_id": log_entry.get("id", ""),
    }
    save_maintenance_action(maintenance_record)

    st.logger.info(
        "MAINTENANCE_ACTION executed action_id=%s type=%s equipment=%s",
        action_id, action_type, equipment_id,
    )

    update_pipeline_step(run_id, "execute", "complete", {"action_type": action_type})
    update_pipeline_step(run_id, "log", "complete")
    complete_pipeline_run(run_id)

    return {
        "status": "success",
        "action_id": action_id,
        "action_type": action_type,
        "equipment_id": equipment_id,
        "detail": detail["detail"],
        "pipeline_run_id": run_id,
    }


# 하위 호환성 (구 카페24 네이밍)
execute_maintenance_action_alias = execute_maintenance_action
