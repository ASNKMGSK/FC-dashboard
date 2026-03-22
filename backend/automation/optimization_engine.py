"""
automation/optimization_engine.py - 공정최적화 자동 추천 엔진
================================================================
규칙기반 후보설비 선정 → 최적 파라미터 추천 → 실행
4가지 액션: 파라미터조정, 설비업그레이드, 공정변경, 정비스케줄조정
"""
import json
import time
import uuid
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from core.constants import EQUIPMENT_GRADES
from core.utils import safe_str, safe_int, safe_float
from automation.action_logger import (
    log_action,
    create_pipeline_run,
    update_pipeline_step,
    complete_pipeline_run,
)
import state as st


# -- 공정 최적화 임계값 --
# {현재 등급: (추천 등급, 생산량 기준, 가동시간 기준)}
_OPTIMIZATION_THRESHOLDS = {
    "Basic": ("Standard", 5_000_000, 100),
    "Standard": ("Premium", 20_000_000, 500),
    "Premium": ("Enterprise", 50_000_000, 2000),
}


def _compute_optimization_score(
    row,
    production_threshold: int,
    hours_threshold: int,
) -> float:
    """
    최적화 점수 계산 (0~100).
    생산량과 가동시간을 각각 임계값 대비 비율로 환산하여 가중 합산.
    - 생산량 가중치 60%, 가동시간 가중치 40%
    """
    total_production = safe_int(row.get("production_volume", row.get("total_revenue", 0)))
    total_hours = safe_int(row.get("operating_hours", row.get("total_orders", 0)))

    production_ratio = min(total_production / max(production_threshold, 1), 2.0)
    hours_ratio = min(total_hours / max(hours_threshold, 1), 2.0)

    raw_score = (production_ratio * 0.6 + hours_ratio * 0.4) * 50
    return round(min(max(raw_score, 0), 100), 1)


def _build_reasons(row, production_threshold: int, hours_threshold: int) -> List[Dict]:
    """최적화 추천 사유 목록을 생성합니다."""
    reasons = []
    total_production = safe_int(row.get("production_volume", row.get("total_revenue", 0)))
    total_hours = safe_int(row.get("operating_hours", row.get("total_orders", 0)))

    if total_production >= production_threshold:
        reasons.append({
            "factor": "생산량 기준 달성",
            "value": f"{total_production:,}개 (기준: {production_threshold:,}개)",
        })
    if total_hours >= hours_threshold:
        reasons.append({
            "factor": "가동시간 기준 달성",
            "value": f"{total_hours:,}시간 (기준: {hours_threshold:,}시간)",
        })

    # 추가 성과 지표
    component_count = safe_int(row.get("product_count", 0))
    if component_count > 50:
        reasons.append({
            "factor": "부품 다양성 높음",
            "value": f"{component_count}종",
        })

    defect_rate = safe_float(row.get("defect_rate", row.get("refund_rate", 0)))
    if defect_rate < 3:
        reasons.append({
            "factor": "낮은 불량률",
            "value": f"{defect_rate}%",
        })

    days_since_last = safe_int(row.get("days_since_last_maintenance", row.get("days_since_last_login", 0)))
    if days_since_last <= 3:
        reasons.append({
            "factor": "활발한 가동 상태",
            "value": f"최근 정비 {days_since_last}일 전",
        })

    return reasons


def _apply_ml_failure_scoring(results: List[Dict]) -> List[Dict]:
    """
    ML 고장예측 모델로 고장 위험도를 스코어에 반영합니다.
    고장 위험이 높은 설비 → 최적화 우선순위 높임 (예방 효과).
    """
    from core.constants import FEATURE_COLS_FAILURE

    st.get_model("EQUIPMENT_FAILURE_MODEL")
    if st.EQUIPMENT_FAILURE_MODEL is None or st.LINE_ANALYTICS_DF is None:
        return results

    df = st.LINE_ANALYTICS_DF
    id_col = "line_id" if "line_id" in df.columns else "line_id"
    for item in results:
        equipment_id = item["equipment_id"]
        equipment = df[df[id_col] == equipment_id]
        if equipment.empty:
            continue

        try:
            row = equipment.iloc[0]
            feature_cols = FEATURE_COLS_FAILURE
            X = pd.DataFrame([{col: safe_float(row.get(col, 0)) for col in feature_cols}])

            if "plan_tier_encoded" in feature_cols and "plan_tier" in row.index:
                tier_map = {tier: i for i, tier in enumerate(EQUIPMENT_GRADES)}
                X["plan_tier_encoded"] = tier_map.get(row.get("plan_tier", "Basic"), 0)

            failure_prob = float(st.EQUIPMENT_FAILURE_MODEL.predict_proba(X)[0][1])

            # 고장 위험이 높을수록 최적화 점수 보너스 (최대 +20점)
            failure_bonus = round(failure_prob * 20, 1)
            item["optimization_score"] = round(min(item["optimization_score"] + failure_bonus, 100), 1)
            item["failure_probability"] = round(failure_prob * 100, 1)
            item["failure_risk_level"] = "high" if failure_prob > 0.7 else "medium" if failure_prob > 0.3 else "low"
        except (ValueError, TypeError, RuntimeError) as e:
            st.logger.warning("OPTIMIZATION ML failure scoring error equipment=%s: %s", equipment_id, str(e))

    return results


def get_optimization_candidates(limit: int = 20, use_ml_scoring: bool = False) -> List[Dict]:
    """
    규칙 기반으로 공정최적화 후보 설비를 탐지합니다.
    - Basic → Standard: 생산량 >= 5,000,000 or 가동시간 >= 100
    - Standard → Premium: 생산량 >= 20,000,000 or 가동시간 >= 500
    - Premium → Enterprise: 생산량 >= 50,000,000 or 가동시간 >= 2000
    - Enterprise는 최고 등급이므로 제외
    - use_ml_scoring=True 시 고장 위험도를 스코어에 반영
    """
    run_id = create_pipeline_run("optimization", ["detect", "analyze"])
    update_pipeline_step(run_id, "detect", "processing")

    if st.LINE_ANALYTICS_DF is None:
        st.logger.warning("OPTIMIZATION get_optimization_candidates: EQUIPMENT_DF is None")
        update_pipeline_step(run_id, "detect", "complete", {"count": 0})
        update_pipeline_step(run_id, "analyze", "complete")
        complete_pipeline_run(run_id)
        return []

    df = st.LINE_ANALYTICS_DF
    if df.empty:
        update_pipeline_step(run_id, "detect", "complete", {"count": 0})
        update_pipeline_step(run_id, "analyze", "complete")
        complete_pipeline_run(run_id)
        return []

    results = []

    _vol_col = "production_volume" if "production_volume" in df.columns else "total_revenue"
    _hrs_col = "operating_hours" if "operating_hours" in df.columns else "total_orders"
    production_col = pd.to_numeric(df.get(_vol_col, 0), errors="coerce").fillna(0)
    hours_col = pd.to_numeric(df.get(_hrs_col, 0), errors="coerce").fillna(0)

    for current_level, (next_level, prod_thresh, hrs_thresh) in _OPTIMIZATION_THRESHOLDS.items():
        _grade_col = "grade" if "grade" in df.columns else "plan_tier"
        plan_mask = df.get(_grade_col, pd.Series(dtype=str)) == current_level
        if not plan_mask.any():
            continue

        qualify_mask = plan_mask & (
            (production_col >= prod_thresh) | (hours_col >= hrs_thresh)
        )
        qualified_indices = np.where(qualify_mask)[0]

        for idx in qualified_indices:
            row = df.iloc[idx]
            score = _compute_optimization_score(row, prod_thresh, hrs_thresh)
            reasons = _build_reasons(row, prod_thresh, hrs_thresh)

            results.append({
                "equipment_id": safe_str(row.get("line_id", "")),
                "current_level": current_level,
                "recommended_level": next_level,
                "optimization_score": score,
                "reasons": reasons,
                "equipment_info": {
                    "operating_hours": safe_int(row.get("operating_hours", row.get("total_orders", 0))),
                    "production_volume": safe_int(row.get("production_volume", row.get("total_revenue", 0))),
                    "days_since_last_maintenance": safe_int(row.get("days_since_last_maintenance", row.get("days_since_last_login", 0))),
                    "defect_rate": safe_float(row.get("defect_rate", row.get("refund_rate", 0))),
                    "maintenance_requests": safe_int(row.get("cs_tickets", 0)),
                    "component_count": safe_int(row.get("product_count", 0)),
                },
            })

    # ML 고장 스코어링 적용
    if use_ml_scoring:
        results = _apply_ml_failure_scoring(results)

    # 점수 높은 순 정렬 + limit
    results.sort(key=lambda x: x["optimization_score"], reverse=True)

    update_pipeline_step(run_id, "detect", "complete", {"count": len(results)})
    update_pipeline_step(run_id, "analyze", "complete")
    complete_pipeline_run(run_id)

    st.logger.info("OPTIMIZATION get_optimization_candidates: %d대 탐지 (ml_scoring=%s)", len(results[:limit]), use_ml_scoring)
    return results[:limit]


# 하위 호환성
get_upgrade_candidates = get_optimization_candidates


async def get_optimization_candidates_stream(limit: int = 20, use_ml_scoring: bool = False):
    """
    최적화 후보 설비를 SSE 스트리밍으로 반환하는 async generator.
    """
    import asyncio

    if st.LINE_ANALYTICS_DF is None:
        st.logger.warning("OPTIMIZATION stream: EQUIPMENT_DF is None")
        yield {"event": "error", "data": {"message": "설비 분석 데이터가 로드되지 않았습니다."}}
        return

    df = st.LINE_ANALYTICS_DF
    if df.empty:
        yield {"event": "done", "data": {"ok": True, "candidates": [], "total": 0, "total_elapsed_ms": 0}}
        return

    start_time = time.time()

    yield {"event": "step_start", "data": {"step": "detect", "description": "최적화 후보 탐지 시작", "timestamp": time.time()}}
    await asyncio.sleep(0)

    results = []

    _vol_col2 = "production_volume" if "production_volume" in df.columns else "total_revenue"
    _hrs_col2 = "operating_hours" if "operating_hours" in df.columns else "total_orders"
    production_col = pd.to_numeric(df.get(_vol_col2, 0), errors="coerce").fillna(0)
    hours_col = pd.to_numeric(df.get(_hrs_col2, 0), errors="coerce").fillna(0)

    all_qualified = []
    for current_level, (next_level, prod_thresh, hrs_thresh) in _OPTIMIZATION_THRESHOLDS.items():
        _grade_col2 = "grade" if "grade" in df.columns else "plan_tier"
        plan_mask = df.get(_grade_col2, pd.Series(dtype=str)) == current_level
        if not plan_mask.any():
            continue
        qualify_mask = plan_mask & ((production_col >= prod_thresh) | (hours_col >= hrs_thresh))
        qualified_indices = np.where(qualify_mask)[0]
        for idx in qualified_indices:
            all_qualified.append((idx, current_level, next_level, prod_thresh, hrs_thresh))

    total = min(len(all_qualified), limit)

    for i, (idx, current_level, next_level, prod_thresh, hrs_thresh) in enumerate(all_qualified[:limit]):
        row = df.iloc[idx]
        score = _compute_optimization_score(row, prod_thresh, hrs_thresh)
        reasons = _build_reasons(row, prod_thresh, hrs_thresh)

        candidate = {
            "equipment_id": safe_str(row.get("line_id", "")),
            "current_level": current_level,
            "recommended_level": next_level,
            "optimization_score": score,
            "reasons": reasons,
            "equipment_info": {
                "operating_hours": safe_int(row.get("operating_hours", row.get("total_orders", 0))),
                "production_volume": safe_int(row.get("production_volume", row.get("total_revenue", 0))),
                "days_since_last_maintenance": safe_int(row.get("days_since_last_maintenance", row.get("days_since_last_login", 0))),
                "defect_rate": safe_float(row.get("defect_rate", row.get("refund_rate", 0))),
                "maintenance_requests": safe_int(row.get("cs_tickets", 0)),
                "component_count": safe_int(row.get("product_count", 0)),
            },
        }
        results.append(candidate)

        yield {"event": "equipment_result", "data": candidate}
        yield {"event": "step_progress", "data": {
            "step": "detect", "current": i + 1, "total": total,
            "detail": f"{safe_str(row.get('line_id', ''))} 분석 완료",
        }}
        await asyncio.sleep(0)

    # ML 고장 스코어링 적용 (lazy loading)
    st.get_model("EQUIPMENT_FAILURE_MODEL")
    if use_ml_scoring and st.EQUIPMENT_FAILURE_MODEL is not None:
        yield {"event": "step_start", "data": {"step": "ml_scoring", "description": "ML 고장 위험도 스코어링", "timestamp": time.time()}}
        await asyncio.sleep(0)

        results = _apply_ml_failure_scoring(results)

        ml_elapsed = int((time.time() - start_time) * 1000)
        yield {"event": "step_end", "data": {"step": "ml_scoring", "elapsed_ms": ml_elapsed, "result_count": len(results)}}

    results.sort(key=lambda x: x["optimization_score"], reverse=True)

    detect_elapsed = int((time.time() - start_time) * 1000)
    yield {"event": "step_end", "data": {"step": "detect", "elapsed_ms": detect_elapsed, "result_count": len(results)}}

    total_elapsed = int((time.time() - start_time) * 1000)
    yield {"event": "done", "data": {"ok": True, "candidates": results, "total": len(results), "total_elapsed_ms": total_elapsed}}


# 하위 호환성
get_upgrade_candidates_stream = get_optimization_candidates_stream


def generate_optimization_recommendation(equipment_id: str) -> Dict:
    """
    특정 설비에 대한 맞춤 공정최적화 추천을 템플릿 기반으로 생성합니다.
    파라미터 조정, 설비 업그레이드, 공정 변경, 정비 스케줄 조정 등.
    """
    run_id = create_pipeline_run("optimization", ["detect", "analyze", "generate"])
    update_pipeline_step(run_id, "detect", "processing")

    if st.LINE_ANALYTICS_DF is None:
        update_pipeline_step(run_id, "detect", "error")
        complete_pipeline_run(run_id)
        return {
            "equipment_id": equipment_id,
            "message": "",
            "benefits": [],
            "urgency": "unknown",
            "error": "설비 분석 데이터가 로드되지 않았습니다.",
        }

    _id_col = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
    equipment = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[_id_col] == equipment_id]
    if equipment.empty:
        update_pipeline_step(run_id, "detect", "error")
        complete_pipeline_run(run_id)
        return {
            "equipment_id": equipment_id,
            "message": "",
            "benefits": [],
            "urgency": "unknown",
            "error": f"설비 '{equipment_id}'를 찾을 수 없습니다.",
        }

    row = equipment.iloc[0]
    current_level = safe_str(row.get("grade", row.get("plan_tier", "Basic")))

    # 최적화 대상 분석
    threshold_info = _OPTIMIZATION_THRESHOLDS.get(current_level)
    if threshold_info is None:
        update_pipeline_step(run_id, "detect", "complete")
        update_pipeline_step(run_id, "analyze", "complete")
        update_pipeline_step(run_id, "generate", "complete")
        complete_pipeline_run(run_id)
        return {
            "equipment_id": equipment_id,
            "message": "",
            "benefits": [],
            "urgency": "low",
            "error": f"현재 등급({current_level})은 이미 최고 등급이거나 최적화 대상이 아닙니다.",
        }

    next_level, prod_thresh, hrs_thresh = threshold_info
    score = _compute_optimization_score(row, prod_thresh, hrs_thresh)

    update_pipeline_step(run_id, "detect", "complete")
    update_pipeline_step(run_id, "analyze", "complete")
    update_pipeline_step(run_id, "generate", "processing")

    # 템플릿 기반 추천 생성
    total_production = safe_int(row.get("production_volume", row.get("total_revenue", 0)))
    total_hours = safe_int(row.get("operating_hours", row.get("total_orders", 0)))
    defect_rate = safe_float(row.get("defect_rate", row.get("refund_rate", 0)))
    days_since_maint = safe_int(row.get("days_since_last_maintenance", row.get("days_since_last_login", 0)))

    urgency = "high" if score >= 70 else "medium" if score >= 40 else "low"

    message = (
        f"설비 {equipment_id}의 최적화 점수: {score}/100점\n"
        f"현재 등급 {current_level} → 추천 등급 {next_level}\n"
        f"생산량 {total_production:,}개 (기준 {prod_thresh:,}개), "
        f"가동시간 {total_hours:,}시간 (기준 {hrs_thresh:,}시간)"
    )

    benefits = []
    if total_production >= prod_thresh:
        benefits.append(f"생산량 기준 달성({total_production:,}개) — 등급 업그레이드로 생산 효율 향상 기대")
    if total_hours >= hrs_thresh:
        benefits.append(f"가동시간 기준 달성({total_hours:,}시간) — 공정 파라미터 최적화로 사이클타임 단축 가능")
    if defect_rate > 3:
        benefits.append(f"현재 불량률 {defect_rate}% — 파라미터 조정으로 불량률 개선 가능")
    else:
        benefits.append(f"낮은 불량률({defect_rate}%) 유지 — 등급 업그레이드 적합")
    if days_since_maint > 7:
        benefits.append(f"정비 주기({days_since_maint}일) 조정으로 예방 정비 효율 향상")

    result = {
        "equipment_id": equipment_id,
        "current_level": current_level,
        "recommended_level": next_level,
        "optimization_score": score,
        "message": message,
        "benefits": benefits,
        "urgency": urgency,
    }

    update_pipeline_step(run_id, "generate", "complete")
    complete_pipeline_run(run_id)
    return result


# 하위 호환성
generate_upgrade_message = generate_optimization_recommendation


def execute_optimization_action(
    equipment_id: str,
    action_type: str,
) -> Dict:
    """
    공정최적화 조치를 실행합니다 (시뮬레이션).
    action_type: "parameter_adjustment" | "equipment_upgrade" | "process_change" | "maintenance_schedule"
    """
    run_id = create_pipeline_run("optimization_action", ["execute", "log"])
    update_pipeline_step(run_id, "execute", "processing")

    valid_actions = {"parameter_adjustment", "equipment_upgrade", "process_change", "maintenance_schedule"}
    if action_type not in valid_actions:
        update_pipeline_step(run_id, "execute", "error")
        complete_pipeline_run(run_id)
        return {
            "status": "error",
            "message": f"지원하지 않는 조치 유형입니다: {action_type}. "
                       f"사용 가능: {', '.join(sorted(valid_actions))}",
        }

    action_id = str(uuid.uuid4())[:8]
    timestamp = time.time()

    # 설비 정보 조회
    current_level = "Unknown"
    recommended_level = "Unknown"
    if st.LINE_ANALYTICS_DF is not None:
        _id_col2 = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
        equipment = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[_id_col2] == equipment_id]
        if not equipment.empty:
            current_level = safe_str(equipment.iloc[0].get("grade", equipment.iloc[0].get("plan_tier", "Unknown")))
            threshold_info = _OPTIMIZATION_THRESHOLDS.get(current_level)
            if threshold_info:
                recommended_level = threshold_info[0]

    # 조치별 상세 내용 시뮬레이션
    action_details = {
        "parameter_adjustment": {
            "description": "공정 파라미터 조정",
            "detail": f"설비 {equipment_id}의 공정 파라미터(온도, 압력, 속도) 최적화 적용 완료",
            "parameters_adjusted": ["온도", "압력", "속도"],
            "expected_improvement": "불량률 15% 감소 예상",
        },
        "equipment_upgrade": {
            "description": "설비 업그레이드",
            "detail": f"설비 {equipment_id}의 {current_level} → {recommended_level} 등급 업그레이드 작업 지시 완료",
            "current_level": current_level,
            "recommended_level": recommended_level,
        },
        "process_change": {
            "description": "공정 변경",
            "detail": f"설비 {equipment_id}의 공정 시퀀스 최적화 변경 적용 완료",
            "process_optimized": True,
            "expected_improvement": "사이클타임 10% 단축 예상",
        },
        "maintenance_schedule": {
            "description": "정비 스케줄 조정",
            "detail": f"설비 {equipment_id}의 정비 스케줄 최적화 완료 (예지보전 기반 주기 조정)",
            "schedule_type": "predictive",
            "next_maintenance_days": 14,
        },
    }

    detail = action_details[action_type]

    # 액션 로깅
    log_entry = log_action(
        action_type=f"optimization_{action_type}",
        target_id=equipment_id,
        detail=detail,
        status="success",
    )

    st.logger.info(
        "OPTIMIZATION_ACTION executed action_id=%s type=%s equipment=%s",
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


# 하위 호환성
execute_upgrade_action = execute_optimization_action
