"""
스마트팩토리 AI 플랫폼 - 에이전트 도구 모음
==========================================
스마트팩토리 AI 기반 설비 관리 시스템

주요 기능:
1. 설비/생산라인/공정 데이터 조회 및 분석
2. 정비 자동배정 및 품질 예측
3. 불량/결함 탐지 및 설비 고장 예측
4. OEE/생산량 예측 및 공정 최적화
"""

from typing import Optional, List, Dict, Any
import json
import numpy as np
import pandas as pd

from core.constants import (
    EQUIPMENT_GRADES,
    EQUIPMENT_TYPES,
    EQUIPMENT_LOCATIONS,
    MAINTENANCE_TYPES,
    WORK_ORDER_STATUSES,
    MANUFACTURING_GLOSSARY,
    FEATURE_COLS_MAINTENANCE_QUALITY,
    FEATURE_COLS_EQUIPMENT_CLUSTER,
    FEATURE_COLS_FAILURE,
    FEATURE_LABELS,
    ML_MODEL_INFO,
    EQUIPMENT_CLUSTER_NAMES,
    WORK_ORDER_CATEGORIES,
    MAINTENANCE_PRIORITY_GRADES,
)
from core.utils import safe_str, safe_int, safe_float
import state as st


# ============================================================
# 1. 설비 정보 조회
# ============================================================
def tool_get_equipment_info(equipment_id: str) -> dict:
    """설비 정보를 조회합니다. equipment_id 또는 설비명으로 검색 가능합니다."""
    if st.EQUIPMENT_DF is None:
        return {"status": "error", "message": "설비 데이터가 로드되지 않았습니다."}

    # shop_id / equipment_id 컬럼 호환
    id_col = "equipment_id" if "equipment_id" in st.EQUIPMENT_DF.columns else "shop_id"
    equip = st.EQUIPMENT_DF[st.EQUIPMENT_DF[id_col] == equipment_id]
    if equip.empty:
        # 이름으로도 검색 시도
        name_col = "equipment_name" if "equipment_name" in st.EQUIPMENT_DF.columns else ("shop_name" if "shop_name" in st.EQUIPMENT_DF.columns else "name")
        equip = st.EQUIPMENT_DF[st.EQUIPMENT_DF[name_col].str.contains(equipment_id, na=False)]

    if equip.empty:
        return {"status": "error", "message": f"설비 '{equipment_id}'를 찾을 수 없습니다."}

    row = equip.iloc[0]

    # EQUIPMENT_PERF_MAP 캐시에서 성과 데이터 O(1) 조회
    perf = st.EQUIPMENT_PERF_MAP.get(safe_str(row.get(id_col))) if st.EQUIPMENT_PERF_MAP else None

    name_col = "equipment_name" if "equipment_name" in row.index else ("shop_name" if "shop_name" in row.index else "name")
    return {
        "status": "success",
        "equipment_id": safe_str(row.get(id_col)),
        "name": safe_str(row.get(name_col)),
        "plan_tier": safe_str(row.get("plan_tier")),
        "category": safe_str(row.get("category")),
        "region": safe_str(row.get("region")),
        "open_date": safe_str(row.get("open_date")),
        "monthly_production_volume": safe_int(perf.get("monthly_production_volume")) if perf is not None else 0,
        "product_count": safe_int(row.get("product_count", 0)),
        "monthly_orders": safe_int(perf.get("monthly_orders")) if perf is not None else 0,
        "avg_yield_rate": safe_int(perf.get("avg_yield_rate")) if perf is not None else 0,
        "oee_rate": safe_float(perf.get("oee_rate")) if perf is not None else 0.0,
        "defect_rate": safe_float(perf.get("defect_rate", perf.get("return_rate", 0))) if perf is not None else 0.0,
        "equipment_uptime_rate": safe_float(perf.get("equipment_uptime_rate")) if perf is not None else 0.0,
        "equipment_status": safe_str(row.get("status")),
    }


# 세그먼트명 캐시 (DataFrame 반복 조회 방지)
_segment_name_cache: dict = {}


def _sum_order_amount_from_json(series) -> int:
    """details_json 시리즈에서 order_amount 합산 (중복 파싱 로직 통합)"""
    total = 0
    for val in series.dropna():
        try:
            parsed = json.loads(val) if isinstance(val, str) else val
            if isinstance(parsed, dict) and "order_amount" in parsed:
                total += int(parsed["order_amount"])
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    return total


def _get_segment_name(cluster: int) -> str:
    """CSV segment_name 컬럼에서 클러스터 번호에 해당하는 이름 반환 (캐시)"""
    if cluster in _segment_name_cache:
        return _segment_name_cache[cluster]

    if st.LINE_ANALYTICS_DF is not None and "segment_name" in st.LINE_ANALYTICS_DF.columns:
        match = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF["cluster"] == cluster]
        if not match.empty:
            name = str(match.iloc[0]["segment_name"])
            _segment_name_cache[cluster] = name
            return name

    name = EQUIPMENT_CLUSTER_NAMES.get(cluster, f"세그먼트 {cluster}")
    _segment_name_cache[cluster] = name
    return name


def tool_list_equipment(
    category: Optional[str] = None,
    plan_tier: Optional[str] = None,
    tier: Optional[str] = None,
    region: Optional[str] = None,
) -> dict:
    """설비 목록을 조회합니다. 유형/등급/위치로 필터링 가능합니다."""
    if st.EQUIPMENT_DF is None:
        return {"status": "error", "message": "설비 데이터가 로드되지 않았습니다."}

    # tier와 plan_tier 둘 다 지원
    effective_tier = plan_tier or tier

    df = st.EQUIPMENT_DF

    if category:
        df = df[df["category"].str.contains(category, na=False, case=False)]
    if effective_tier:
        df = df[df["plan_tier"].str.contains(effective_tier, na=False, case=False)]
    if region:
        df = df[df["region"].str.contains(region, na=False, case=False)]

    # EQUIPMENT_PERF_MAP 캐시 활용
    perf_map = st.EQUIPMENT_PERF_MAP or {}

    id_col = "equipment_id" if "equipment_id" in df.columns else "shop_id"
    name_col = "equipment_name" if "equipment_name" in df.columns else ("shop_name" if "shop_name" in df.columns else "name")
    equip_cols = [id_col, name_col, "plan_tier", "category", "region", "status"]
    equip_cols = [c for c in equip_cols if c in df.columns]
    raw_records = df[equip_cols].to_dict("records")
    equipment_list = []
    for rec in raw_records:
        eid = safe_str(rec.get(id_col))
        perf = perf_map.get(eid)
        equipment_list.append({
            "equipment_id": eid,
            "name": safe_str(rec.get(name_col)),
            "plan_tier": safe_str(rec.get("plan_tier")),
            "category": safe_str(rec.get("category")),
            "region": safe_str(rec.get("region")),
            "monthly_production_volume": safe_int(perf.get("monthly_production_volume")) if perf is not None else 0,
            "monthly_orders": safe_int(perf.get("monthly_orders")) if perf is not None else 0,
            "equipment_status": safe_str(rec.get("status")),
        })

    return {
        "status": "success",
        "total": len(equipment_list),
        "filters": {"category": category, "plan_tier": effective_tier, "region": region},
        "equipment": equipment_list,
    }


def tool_get_equipment_services(equipment_id: str) -> dict:
    """설비에 연결된 정비 서비스/모듈 목록을 조회합니다."""
    if st.MAINTENANCE_SERVICES_DF is None:
        return {"status": "error", "message": "정비 서비스 데이터가 로드되지 않았습니다."}

    id_col = "equipment_id" if "equipment_id" in st.MAINTENANCE_SERVICES_DF.columns else "shop_id"
    services = st.MAINTENANCE_SERVICES_DF[st.MAINTENANCE_SERVICES_DF[id_col] == equipment_id]
    if services.empty:
        return {"status": "error", "message": f"설비 '{equipment_id}'의 정비 서비스 정보를 찾을 수 없습니다."}

    svc_cols = ["service_id", "service_name", "service_type", "status", "description"]
    svc_cols = [c for c in svc_cols if c in services.columns]
    service_list = []
    for rec in services[svc_cols].to_dict("records"):
        service_list.append({
            "service_id": safe_str(rec.get("service_id")),
            "service_name": safe_str(rec.get("service_name")),
            "service_type": safe_str(rec.get("service_type")),
            "service_status": safe_str(rec.get("status")),
            "description": safe_str(rec.get("description")),
        })

    return {
        "status": "success",
        "equipment_id": equipment_id,
        "total_services": len(service_list),
        "services": service_list,
    }


# ============================================================
# 2. 공정유형 카테고리 정보 조회
# ============================================================
def tool_get_category_info(category_id: str) -> dict:
    """공정유형 카테고리 정보를 조회합니다."""
    if st.EQUIPMENT_TYPES_DF is None:
        return {"status": "error", "message": "카테고리 데이터가 로드되지 않았습니다."}

    # cat_id 또는 category_id 컬럼 지원
    id_col = "cat_id" if "cat_id" in st.EQUIPMENT_TYPES_DF.columns else "category_id"
    name_col = "name_ko" if "name_ko" in st.EQUIPMENT_TYPES_DF.columns else "name"

    category = st.EQUIPMENT_TYPES_DF[st.EQUIPMENT_TYPES_DF[id_col] == category_id]
    if category.empty:
        # 이름으로도 검색 시도
        category = st.EQUIPMENT_TYPES_DF[st.EQUIPMENT_TYPES_DF[name_col].str.contains(category_id, na=False, case=False)]

    if category.empty:
        return {"status": "error", "message": f"카테고리 '{category_id}'를 찾을 수 없습니다."}

    row = category.iloc[0]
    parent_col = "parent_cat" if "parent_cat" in row.index else "parent_id"
    desc_col = "description_ko" if "description_ko" in row.index else "description"

    return {
        "status": "success",
        "category_id": safe_str(row.get(id_col)),
        "name": safe_str(row.get(name_col)),
        "name_en": safe_str(row.get("name_en", "")),
        "parent_id": safe_str(row.get(parent_col)),
        "description": safe_str(row.get(desc_col)),
        "description_en": safe_str(row.get("description_en", "")),
    }


def tool_list_categories() -> dict:
    """모든 공정유형 카테고리 목록을 조회합니다."""
    if st.EQUIPMENT_TYPES_DF is None:
        return {"status": "error", "message": "카테고리 데이터가 로드되지 않았습니다."}

    id_col = "cat_id" if "cat_id" in st.EQUIPMENT_TYPES_DF.columns else "category_id"
    name_col = "name_ko" if "name_ko" in st.EQUIPMENT_TYPES_DF.columns else "name"
    parent_col = "parent_cat" if "parent_cat" in st.EQUIPMENT_TYPES_DF.columns else "parent_id"
    desc_col = "description_ko" if "description_ko" in st.EQUIPMENT_TYPES_DF.columns else "description"

    cat_cols = [id_col, name_col, "name_en", parent_col, desc_col]
    cat_cols = [c for c in cat_cols if c in st.EQUIPMENT_TYPES_DF.columns]
    categories = []
    for rec in st.EQUIPMENT_TYPES_DF[cat_cols].to_dict("records"):
        categories.append({
            "category_id": safe_str(rec.get(id_col)),
            "name": safe_str(rec.get(name_col)),
            "name_en": safe_str(rec.get("name_en", "")),
            "parent_id": safe_str(rec.get(parent_col)),
            "description": safe_str(rec.get(desc_col)),
        })

    return {
        "status": "success",
        "total": len(categories),
        "categories": categories,
    }


# ============================================================
# 3. 정비 자동배정/품질 도구
# ============================================================
def tool_auto_assign_maintenance(
    inquiry_text: str,
    inquiry_category: str = "기타",
    grade: str = "Basic",
    order_id: Optional[str] = None,
) -> dict:
    """
    정비 요청에 대한 자동 배정 초안을 생성합니다.
    LLM을 사용하여 스마트팩토리 플랫폼 정책에 맞는 정비 배정을 작성합니다.
    """
    if inquiry_category not in WORK_ORDER_CATEGORIES:
        # 가장 유사한 카테고리 매칭 시도
        matched = False
        for cat in WORK_ORDER_CATEGORIES:
            if cat in inquiry_category or inquiry_category in cat:
                inquiry_category = cat
                matched = True
                break
        if not matched:
            inquiry_category = "기타"

    # CS 응답 컨텍스트 생성 (실제 LLM 호출은 agent/runner.py에서 처리)
    cs_context = {
        "inquiry_text": inquiry_text,
        "inquiry_category": inquiry_category,
        "grade": grade,
        "order_id": order_id,
        "platform": "SMART_FACTORY",
        "priority_guide": MAINTENANCE_PRIORITY_GRADES,
        "category_guide": WORK_ORDER_CATEGORIES,
    }

    return {
        "status": "success",
        "action": "CS_AUTO_REPLY",
        "context": cs_context,
        "message": f"'{inquiry_text[:50]}...' 문의에 대한 자동 응답을 생성합니다. 카테고리: {inquiry_category}, 설비 등급: {grade}.",
    }


def tool_check_maintenance_quality(
    ticket_category: str,
    grade: str,
    sentiment_score: float,
    order_value: float,
    is_repeat_issue: bool = False,
    text_length: int = 100,
) -> dict:
    """정비 작업의 우선순위/긴급도를 예측합니다."""
    # lazy loading: 모델이 아직 로드되지 않았으면 디스크에서 로드 시도
    st.get_model("MAINTENANCE_QUALITY_MODEL")
    if st.MAINTENANCE_QUALITY_MODEL is None:
        return {"status": "error", "message": "정비 품질 예측 모델이 로드되지 않았습니다."}

    # 피처 인코딩 (lazy loading)
    st.get_model("LE_FAULT_CATEGORY")
    st.get_model("LE_MAINTENANCE_PRIORITY")
    try:
        category_encoded = st.LE_FAULT_CATEGORY.transform([ticket_category])[0] if st.LE_FAULT_CATEGORY else 0
    except (ValueError, AttributeError):
        category_encoded = 0

    try:
        tier_encoded = st.LE_MAINTENANCE_PRIORITY.transform([grade])[0] if st.LE_MAINTENANCE_PRIORITY else 0
    except (ValueError, AttributeError):
        tier_encoded = 0

    features = {
        "work_order_category_encoded": category_encoded,
        "equipment_grade_encoded": tier_encoded,
        "severity_score": sentiment_score,
        "production_volume": order_value,
        "is_repeat_fault": int(is_repeat_issue),
        "description_length": text_length,
    }

    # 모델 예측
    try:
        X = pd.DataFrame([features])[FEATURE_COLS_MAINTENANCE_QUALITY]
        pred = st.MAINTENANCE_QUALITY_MODEL.predict(X)[0]
        proba = st.MAINTENANCE_QUALITY_MODEL.predict_proba(X)[0]

        priority_grade = st.LE_MAINTENANCE_PRIORITY.inverse_transform([pred])[0] if st.LE_MAINTENANCE_PRIORITY else "normal"

        grade_info = MAINTENANCE_PRIORITY_GRADES.get(priority_grade, {})

        return {
            "status": "success",
            "ticket_category": ticket_category,
            "grade": grade,
            "predicted_priority": priority_grade,
            "priority_description": grade_info.get("description", ""),
            "confidence": float(max(proba)),
            "is_repeat_issue": is_repeat_issue,
            "recommendations": _get_cs_recommendations(priority_grade, is_repeat_issue, ticket_category),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _get_cs_recommendations(priority: str, is_repeat: bool, category: str) -> List[str]:
    """CS 우선순위에 따른 권장사항을 반환합니다."""
    recommendations = []

    if priority == "urgent":
        recommendations.append("즉시 담당자 배정이 필요합니다.")
        recommendations.append("담당 엔지니어에게 1시간 이내 초기 응답을 보내주세요.")
    elif priority == "high":
        recommendations.append("우선 처리 대상입니다. 4시간 이내 응답을 권장합니다.")
    elif priority == "normal":
        recommendations.append("일반 처리 흐름을 따릅니다.")
    elif priority == "low":
        recommendations.append("낮은 우선순위입니다. FAQ 자동 답변을 활용하세요.")

    if is_repeat:
        recommendations.append("반복 문의입니다. 근본 원인 해결이 필요합니다. 이전 티켓 히스토리를 확인하세요.")

    if category == "품질불량":
        recommendations.append("불량 원인 분석 및 시정 조치 기간을 명확히 안내하세요.")
    elif category == "설비고장":
        recommendations.append("설비 상태 이력을 확인하고 예상 복구 시간을 안내하세요.")
    elif category == "자재":
        recommendations.append("자재 재고 현황을 확인하고 대체 자재를 안내하세요.")

    return recommendations


def tool_get_manufacturing_glossary(term: Optional[str] = None) -> dict:
    """제조 용어집을 조회합니다. 특정 용어를 검색하거나 전체 목록을 반환합니다."""
    terms = []

    if term:
        # 특정 용어 검색
        term_upper = term.upper()
        if term_upper in MANUFACTURING_GLOSSARY:
            info = MANUFACTURING_GLOSSARY[term_upper]
            terms.append({
                "term": term_upper,
                "english": info.get("en", ""),
                "description": info.get("desc", ""),
            })
        elif term in MANUFACTURING_GLOSSARY:
            info = MANUFACTURING_GLOSSARY[term]
            terms.append({
                "term": term,
                "english": info.get("en", ""),
                "description": info.get("desc", ""),
            })
        else:
            # 부분 매칭 시도
            for key, info in MANUFACTURING_GLOSSARY.items():
                if term.lower() in key.lower() or term.lower() in info.get("desc", "").lower():
                    terms.append({
                        "term": key,
                        "english": info.get("en", ""),
                        "description": info.get("desc", ""),
                    })
    else:
        # 전체 용어집
        for key, info in MANUFACTURING_GLOSSARY.items():
            terms.append({
                "term": key,
                "english": info.get("en", ""),
                "description": info.get("desc", ""),
            })

    if not terms:
        return {"status": "error", "message": f"'{term}' 관련 용어를 찾을 수 없습니다."}

    return {
        "status": "success",
        "total": len(terms),
        "search_term": term,
        "terms": terms,
    }


# ============================================================
# 4. 설비 분석 도구
# ============================================================
def tool_analyze_equipment(line_id: str) -> dict:
    """설비의 운영 데이터 및 성과를 분석합니다."""
    if st.LINE_ANALYTICS_DF is None:
        return {"status": "error", "message": "라인 분석 데이터가 로드되지 않았습니다."}

    _id_col = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
    row_match = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[_id_col] == line_id]
    if row_match.empty:
        return {"status": "error", "message": f"설비/라인 '{line_id}'를 찾을 수 없습니다."}

    row = row_match.iloc[0]

    total_work_orders = safe_int(row.get("total_work_orders"))
    total_production_volume = safe_int(row.get("total_production_volume"))

    # avg_yield_rate: 원본이 0이면 total_production_volume / total_work_orders로 계산
    avg_yield_rate = safe_int(row.get("avg_yield_rate"))
    if avg_yield_rate == 0 and total_work_orders > 0 and total_production_volume > 0:
        avg_yield_rate = round(total_production_volume / total_work_orders)

    oee_rate = safe_float(row.get("oee_rate"))
    equipment_reuse_rate = safe_float(row.get("equipment_reuse_rate"))
    monthly_growth_rate = safe_float(row.get("monthly_growth_rate"))

    # 데이터 정합성 경고 (LLM이 잘못된 해석을 하지 않도록 가이드)
    data_warnings = []
    if total_work_orders > 0 and oee_rate == 0.0:
        data_warnings.append("OEE 0%: 가동 데이터가 집계되지 않아 산출 불가")
    if total_work_orders > 100 and equipment_reuse_rate == 0.0:
        data_warnings.append("재가동률 0%: 설비별 재가동 집계가 반영되지 않았을 가능성")
    if monthly_growth_rate == 0.0:
        data_warnings.append("월간 성장률 0%: 월별 시계열 데이터 부재로 산출 불가")
    if safe_int(row.get("maintenance_cost")) == 0:
        data_warnings.append("정비비 0원: 외부 정비 비용 미연동 또는 자체 정비 중심 가능성 — 정비 미실시로 단정 불가")

    defect_return_rate = safe_float(row.get("defect_return_rate"))
    plan_tier = safe_str(row.get("plan_tier"))

    result = {
        "status": "success",
        "line_id": line_id,
        "performance": {
            "total_work_orders": total_work_orders,
            "total_production_volume": total_production_volume,
            "product_count": safe_int(row.get("product_count")),
            "avg_yield_rate": avg_yield_rate,
            "oee_rate": oee_rate,
            "equipment_reuse_rate": equipment_reuse_rate,
            "monthly_growth_rate": monthly_growth_rate,
        },
        "operations": {
            "cs_tickets": safe_int(row.get("cs_tickets")),
            "cs_ticket_rate_pct": round(safe_int(row.get("cs_tickets")) / max(total_work_orders, 1) * 100, 2),
            "defect_return_rate": defect_return_rate,
            "defect_return_rate_pct": round(defect_return_rate * 100, 2) if defect_return_rate < 1 else round(defect_return_rate, 2),
            "avg_response_time": safe_float(row.get("avg_response_time")),
            "days_since_last_login": safe_int(row.get("days_since_last_login")),
            "days_since_register": safe_int(row.get("days_since_register")),
        },
        "maintenance": {
            "maintenance_cost": safe_int(row.get("maintenance_cost")),
            "maintenance_roi": safe_float(row.get("maintenance_roi")),
        },
        "plan_tier": plan_tier,
    }

    # 세그먼트 정보 포함
    if "cluster" in row.index:
        cluster = safe_int(row.get("cluster"))
        result["segment"] = {
            "cluster": cluster,
            "segment_name": _get_segment_name(cluster),
        }

    # 전체 설비 대비 비교 데이터 (LLM이 맥락 있는 해석을 할 수 있도록)
    df = st.LINE_ANALYTICS_DF
    try:
        total_equipment = len(df)
        platform_avg_revenue = float(df["total_production_volume"].mean())
        platform_avg_orders = float(df["total_work_orders"].mean())
        platform_avg_refund = float(df["defect_return_rate"].mean())

        platform_avg_cs = float(df["cs_tickets"].mean()) if "cs_tickets" in df.columns else 0
        platform_cs_rate = round(platform_avg_cs / max(platform_avg_orders, 1) * 100, 2)

        result["comparison"] = {
            "platform_avg": {
                "total_work_orders": round(platform_avg_orders, 1),
                "total_production_volume": round(platform_avg_revenue),
                "avg_yield_rate": round(df["total_production_volume"].sum() / max(df["total_work_orders"].sum(), 1)),
                "defect_return_rate": round(platform_avg_refund, 4),
                "defect_return_rate_pct": round(platform_avg_refund * 100, 2) if platform_avg_refund < 1 else round(platform_avg_refund, 2),
                "cs_tickets": round(platform_avg_cs, 1),
                "cs_ticket_rate_pct": platform_cs_rate,
                "equipment_count": total_equipment,
            },
        }

        # 동일 등급(plan_tier) 평균
        if plan_tier:
            tier_df = df[df["plan_tier"] == plan_tier]
            if len(tier_df) > 1:
                tier_avg_refund = float(tier_df["defect_return_rate"].mean())
                result["comparison"]["tier_avg"] = {
                    "plan_tier": plan_tier,
                    "equipment_count": len(tier_df),
                    "total_work_orders": round(float(tier_df["total_work_orders"].mean()), 1),
                    "total_production_volume": round(float(tier_df["total_production_volume"].mean())),
                    "defect_return_rate_pct": round(tier_avg_refund * 100, 2) if tier_avg_refund < 1 else round(tier_avg_refund, 2),
                }

        # 백분위 순위 (이 설비가 전체 중 상위 몇%인지)
        if total_work_orders > 0:
            result["comparison"]["percentile"] = {
                "total_work_orders": round(float((df["total_work_orders"] <= total_work_orders).mean()) * 100, 1),
                "total_production_volume": round(float((df["total_production_volume"] <= total_production_volume).mean()) * 100, 1),
            }
    except Exception:
        pass

    if data_warnings:
        result["data_warnings"] = data_warnings

    return result


def tool_get_equipment_cluster(line_id_or_features) -> dict:
    """설비 ID 또는 피처 딕셔너리를 기반으로 클러스터를 분류합니다 (K-Means 클러스터링)."""

    # line_id(str)로 호출된 경우 → LINE_ANALYTICS_DF에서 조회
    if isinstance(line_id_or_features, str):
        line_id = line_id_or_features
        if st.LINE_ANALYTICS_DF is None:
            return {"status": "error", "message": "라인 분석 데이터가 로드되지 않았습니다."}

        _id_col = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
        row_match = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[_id_col] == line_id]
        if row_match.empty:
            return {"status": "error", "message": f"설비/라인 '{line_id}'를 찾을 수 없습니다."}

        row = row_match.iloc[0]

        # 이미 cluster 컬럼이 있으면 바로 반환
        if "cluster" in row.index and pd.notna(row.get("cluster")):
            cluster = int(row["cluster"])
            segment_name = safe_str(row.get("segment_name", "")) or _get_segment_name(cluster)
            return {
                "status": "success",
                "line_id": line_id,
                "segment": {
                    "cluster": cluster,
                    "name": segment_name,
                },
            }

        # cluster가 없으면 모델로 예측
        equipment_features = {col: float(row.get(col, 0)) for col in FEATURE_COLS_EQUIPMENT_CLUSTER if col in row.index}
    else:
        equipment_features = line_id_or_features
        line_id = None

    # lazy loading: 모델이 아직 로드되지 않았으면 디스크에서 로드 시도
    st.get_model("EQUIPMENT_CLUSTER_MODEL")
    st.get_model("SCALER_CLUSTER")
    if st.EQUIPMENT_CLUSTER_MODEL is None:
        return {"status": "error", "message": "설비 클러스터 모델이 로드되지 않았습니다."}

    try:
        X = pd.DataFrame([equipment_features])[FEATURE_COLS_EQUIPMENT_CLUSTER].fillna(0)
        X_scaled = st.SCALER_CLUSTER.transform(X) if st.SCALER_CLUSTER else X
        cluster = int(st.EQUIPMENT_CLUSTER_MODEL.predict(X_scaled)[0])

        result = {
            "status": "success",
            "segment": {
                "cluster": cluster,
                "name": _get_segment_name(cluster),
            },
        }
        if line_id:
            result["line_id"] = line_id
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_detect_defect(line_id: Optional[str] = None, transaction_features: Optional[dict] = None) -> dict:
    """결함/불량을 탐지합니다. 설비 ID 또는 센서 피처를 기반으로 분석합니다."""
    try:
        # 설비 ID로 기존 결함 데이터 조회 (ML 모델 불필요)
        if line_id:
            if st.DEFECT_DETAILS_DF is None:
                return {"status": "error", "message": f"결함 탐지 데이터(DEFECT_DETAILS_DF)가 로드되지 않았습니다. 설비 {line_id}의 결함 조사를 수행할 수 없습니다. 다른 도구를 사용하세요."}
            _id_col = "line_id" if "line_id" in st.DEFECT_DETAILS_DF.columns else "line_id"
            defect_records = st.DEFECT_DETAILS_DF[st.DEFECT_DETAILS_DF[_id_col] == line_id]
            if defect_records.empty:
                return {"status": "success", "line_id": line_id, "defect_records": [], "total_flags": 0, "risk_level": "NONE", "message": f"설비 {line_id}에 대한 결함 기록이 없습니다. 정상입니다."}
            else:
                defect_cols = [_id_col, "anomaly_score", "anomaly_type", "detected_date", "details"]
                defect_cols = [c for c in defect_cols if c in defect_records.columns]
                records = []
                for rec in defect_records[defect_cols].to_dict("records"):
                    score = safe_float(rec.get("anomaly_score", 0))
                    records.append({
                        "line_id": safe_str(rec.get(_id_col)),
                        "anomaly_score": score,
                        "anomaly_type": safe_str(rec.get("anomaly_type")),
                        "detected_date": safe_str(rec.get("detected_date")),
                        "details": safe_str(rec.get("details")),
                    })
                max_score = max(r["anomaly_score"] for r in records)
                return {
                    "status": "success",
                    "line_id": line_id,
                    "defect_records": records,
                    "total_flags": len(records),
                    "risk_level": "HIGH" if max_score >= 0.9 else "MEDIUM" if max_score >= 0.7 else "LOW",
                }

        # 거래 피처로 실시간 탐지 (ML 모델 필요)
        if transaction_features:
            # lazy loading: 모델이 아직 로드되지 않았으면 디스크에서 로드 시도
            st.get_model("DEFECT_DETECTION_MODEL")
            if st.DEFECT_DETECTION_MODEL is None:
                return {"status": "error", "message": "결함 탐지 ML 모델이 로드되지 않았습니다. line_id로 기록 조회는 가능합니다."}
            feature_cols = ["production_volume", "production_frequency", "defect_return_rate",
                            "quality_anomaly_score", "equipment_error_rate"]
            X = pd.DataFrame([transaction_features])[feature_cols].fillna(0)

            pred = int(st.DEFECT_DETECTION_MODEL.predict(X)[0])
            score = float(st.DEFECT_DETECTION_MODEL.decision_function(X)[0])

            is_defect = pred == -1

            return {
                "status": "success",
                "is_defect": is_defect,
                "anomaly_score": score,
                "risk_level": "HIGH" if is_defect and score < -0.2 else "MEDIUM" if is_defect else "LOW",
                "recommendation": "비정상 패턴이 감지되었습니다. 해당 설비의 센서 데이터를 상세 조사하세요." if is_defect else "정상적인 패턴입니다.",
            }

        return {"status": "error", "message": "line_id 또는 transaction_features를 제공해주세요."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_get_cluster_statistics() -> dict:
    """설비 클러스터별 통계를 조회합니다."""
    if st.LINE_ANALYTICS_DF is None:
        return {"status": "error", "message": "라인 분석 데이터가 로드되지 않았습니다."}

    try:
        df = st.LINE_ANALYTICS_DF

        # 세그먼트 분류가 되어 있는 경우
        if "cluster" in df.columns or "segment" in df.columns:
            cluster_col = "cluster" if "cluster" in df.columns else "segment"
            stats = []
            for cluster in sorted(df[cluster_col].unique()):
                cluster_equipment = df[df[cluster_col] == cluster]
                if cluster_equipment.empty:
                    continue
                name = _get_segment_name(int(cluster))
                stats.append({
                    "cluster": int(cluster),
                    "name": name,
                    "equipment_count": len(cluster_equipment),
                    "avg_revenue": safe_float(cluster_equipment["total_production_volume"].mean()),
                    "avg_orders": safe_float(cluster_equipment["total_work_orders"].mean()),
                    "avg_products": safe_float(cluster_equipment["product_count"].mean()),
                    "avg_defect_return_rate": safe_float(cluster_equipment["defect_return_rate"].mean()),
                })

            return {
                "status": "success",
                "total_equipment": len(df),
                "segments": stats,
            }

        # 세그먼트 분류가 안 되어 있으면 모델로 분류 (원본 변경 방지를 위해 copy)
        # lazy loading: 모델 로드 시도
        st.get_model("EQUIPMENT_CLUSTER_MODEL")
        st.get_model("SCALER_CLUSTER")
        if st.EQUIPMENT_CLUSTER_MODEL is not None and st.SCALER_CLUSTER is not None:
            df = df.copy()
            X = df[FEATURE_COLS_EQUIPMENT_CLUSTER].fillna(0)
            X_scaled = st.SCALER_CLUSTER.transform(X)
            df["cluster"] = st.EQUIPMENT_CLUSTER_MODEL.predict(X_scaled)

            stats = []
            for cluster in sorted(df["cluster"].unique()):
                cluster_equipment = df[df["cluster"] == cluster]
                if cluster_equipment.empty:
                    continue
                name = _get_segment_name(int(cluster))
                stats.append({
                    "cluster": int(cluster),
                    "name": name,
                    "equipment_count": len(cluster_equipment),
                    "avg_revenue": safe_float(cluster_equipment["total_production_volume"].mean()),
                    "avg_orders": safe_float(cluster_equipment["total_work_orders"].mean()),
                    "avg_products": safe_float(cluster_equipment["product_count"].mean()),
                    "avg_defect_return_rate": safe_float(cluster_equipment["defect_return_rate"].mean()),
                })

            return {
                "status": "success",
                "total_equipment": len(df),
                "segments": stats,
            }

        return {"status": "error", "message": "세그먼트 분류 데이터 또는 모델이 없습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_get_defect_statistics() -> dict:
    """전체 결함/불량 통계를 조회합니다."""
    if st.DEFECT_DETAILS_DF is None:
        return {"status": "error", "message": "결함 탐지 데이터가 로드되지 않았습니다."}

    df = st.DEFECT_DETAILS_DF
    total_records = len(df)

    # defect_details.csv 컬럼: line_id, anomaly_score, anomaly_type, detected_date, details

    # 이상 유형별 분포
    anomaly_type_dist = {}
    if "anomaly_type" in df.columns:
        anomaly_type_dist = df["anomaly_type"].value_counts().to_dict()

    # 이상 점수 통계
    avg_score = safe_float(df["anomaly_score"].mean()) if "anomaly_score" in df.columns else 0
    max_score = safe_float(df["anomaly_score"].max()) if "anomaly_score" in df.columns else 0
    min_score = safe_float(df["anomaly_score"].min()) if "anomaly_score" in df.columns else 0

    # 고위험 (anomaly_score >= 0.9)
    high_risk_count = len(df[df["anomaly_score"] >= 0.9]) if "anomaly_score" in df.columns else 0
    _id_col = "line_id" if "line_id" in df.columns else "line_id"
    unique_equipment = df[_id_col].nunique() if _id_col in df.columns else 0

    # 위험도 높은 순 샘플 (최대 10건)
    sorted_df = df.sort_values("anomaly_score", ascending=False) if "anomaly_score" in df.columns else df
    sample_cols = [_id_col, "anomaly_score", "anomaly_type", "detected_date", "details"]
    sample_cols = [c for c in sample_cols if c in sorted_df.columns]
    defect_samples = []
    for rec in sorted_df.head(10)[sample_cols].to_dict("records"):
        defect_samples.append({
            "line_id": safe_str(rec.get(_id_col)),
            "anomaly_score": safe_float(rec.get("anomaly_score")),
            "anomaly_type": safe_str(rec.get("anomaly_type")),
            "detected_date": safe_str(rec.get("detected_date")),
            "details": safe_str(rec.get("details")),
        })

    return {
        "status": "success",
        "total_anomalies": total_records,
        "unique_equipment": unique_equipment,
        "high_risk_count": high_risk_count,
        "high_risk_rate": round(high_risk_count / total_records * 100, 1) if total_records > 0 else 0,
        "anomaly_type_distribution": anomaly_type_dist,
        "anomaly_score_stats": {"avg": avg_score, "max": max_score, "min": min_score},
        "top_anomalies": defect_samples,
    }


# ============================================================
# 5. 생산/운영 로그 분석 도구
# ============================================================
def tool_get_order_statistics(event_type: Optional[str] = None, days: int = 30) -> dict:
    """작업지시/운영 이벤트 통계를 조회합니다."""
    if st.OPERATION_LOGS_DF is None:
        return {"status": "error", "message": "운영 로그 데이터가 로드되지 않았습니다."}

    df = st.OPERATION_LOGS_DF.copy()
    # CSV 컬럼: log_id, line_id, event_type, event_date, details_json
    date_col = "event_date" if "event_date" in df.columns else "timestamp"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # 최근 N일 필터
    cutoff = df[date_col].max() - pd.Timedelta(days=days)
    df = df[df[date_col] >= cutoff]

    # event_type 별칭 매핑 (LLM이 축약형으로 보내는 경우 처리)
    _EVENT_TYPE_ALIAS = {
        "order": "work_order_created",
        "payment": "work_completed",
        "completion": "work_completed",
        "refund": "rework_processed",
        "delivery": "work_order_created",
        "cancel": "rework_processed",
        "cs": "cs_ticket",
        "marketing": "maintenance_campaign",
        "product": "product_listed",
    }
    if event_type:
        event_type = _EVENT_TYPE_ALIAS.get(event_type.lower(), event_type)
        df = df[df["event_type"] == event_type]

    # 이벤트 타입별 집계
    event_counts = df["event_type"].value_counts().to_dict()

    # 일별 추이
    daily_counts = df.groupby(df[date_col].dt.date).size().to_dict()
    daily_counts = {str(k): v for k, v in daily_counts.items()}

    # details_json에서 작업 금액 합산
    total_amount = _sum_order_amount_from_json(df["details_json"]) if "details_json" in df.columns else 0

    # 설비별 이벤트 수
    _id_col = "line_id" if "line_id" in df.columns else "line_id"
    line_event_counts = df[_id_col].value_counts().head(10).to_dict() if _id_col in df.columns else {}

    # 마크다운 표 생성 (LLM 라벨 보존용)
    md_lines = [
        f"## 운영 이벤트 통계 (최근 {days}일)",
        "",
        f"- 총 이벤트: **{len(df):,}건**",
        f"- 총 금액: **₩{total_amount:,}**" if total_amount else "",
        "",
        "| 이벤트 유형 | 건수 |",
        "|-------------|------|",
    ]
    for etype, cnt in event_counts.items():
        md_lines.append(f"| {etype} | {cnt:,} |")
    if line_event_counts:
        md_lines += ["", "### 이벤트 상위 설비", "| 라인 ID | 이벤트 수 |", "|---------|----------|"]
        for sid, cnt in line_event_counts.items():
            md_lines.append(f"| {sid} | {cnt:,} |")

    return {
        "status": "success",
        "period": f"최근 {days}일",
        "total_events": len(df),
        "total_amount": total_amount,
        "event_type_filter": event_type,
        "_markdown": "\n".join([l for l in md_lines if l != "" or True]),
        "event_counts": event_counts,
        "top_equipment_by_events": line_event_counts,
        "daily_trend": daily_counts,
    }


def tool_get_equipment_activity_report(line_id: str, days: int = 30) -> dict:
    """특정 설비의 활동 리포트를 생성합니다."""
    if st.EQUIPMENT_ACTIVITY_DF is None and st.OPERATION_LOGS_DF is None:
        return {"status": "error", "message": "설비 활동 데이터가 로드되지 않았습니다."}

    # EQUIPMENT_ACTIVITY_DF 우선 사용
    # CSV 컬럼: line_id, date, orders_processed, products_updated, cs_handled, revenue
    if st.EQUIPMENT_ACTIVITY_DF is not None:
        _id_col = "line_id" if "line_id" in st.EQUIPMENT_ACTIVITY_DF.columns else "line_id"
        df = st.EQUIPMENT_ACTIVITY_DF[st.EQUIPMENT_ACTIVITY_DF[_id_col] == line_id].copy()
        if df.empty:
            return {"status": "error", "message": f"설비 '{line_id}'의 활동 로그를 찾을 수 없습니다."}

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        cutoff = df["date"].max() - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff]

        active_days = df["date"].dt.date.nunique()
        total_work_orders = safe_int(df["orders_processed"].sum()) if "orders_processed" in df.columns else 0
        total_production_volume = safe_int(df["revenue"].sum()) if "revenue" in df.columns else 0
        total_cs = safe_int(df["cs_handled"].sum()) if "cs_handled" in df.columns else 0

        total_products = safe_int(df["products_updated"].sum()) if "products_updated" in df.columns else 0
        total_all_events = total_work_orders + total_products + total_cs

        event_summary = {
            "작업지시처리": total_work_orders,
            "제품업데이트": total_products,
            "CS처리": total_cs,
        }

        return {
            "status": "success",
            "line_id": line_id,
            "period": f"최근 {days}일",
            "total_events": total_all_events,
            "total_production_volume": total_production_volume,
            "active_days": active_days,
            "event_summary": event_summary,
            "avg_events_per_day": round(total_all_events / max(active_days, 1), 2),
        }

    # OPERATION_LOGS_DF 폴백
    # CSV 컬럼: log_id, line_id, event_type, event_date, details_json
    _id_col = "line_id" if "line_id" in st.OPERATION_LOGS_DF.columns else "line_id"
    df = st.OPERATION_LOGS_DF[st.OPERATION_LOGS_DF[_id_col] == line_id].copy()
    if df.empty:
        return {"status": "error", "message": f"설비 '{line_id}'의 활동 로그를 찾을 수 없습니다."}

    date_col = "event_date" if "event_date" in df.columns else "timestamp"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    cutoff = df[date_col].max() - pd.Timedelta(days=days)
    df = df[df[date_col] >= cutoff]

    event_summary = df["event_type"].value_counts().to_dict()
    active_days = df[date_col].dt.date.nunique()

    # details_json에서 작업 금액 합산
    total_amount = _sum_order_amount_from_json(df["details_json"]) if "details_json" in df.columns else 0

    return {
        "status": "success",
        "line_id": line_id,
        "period": f"최근 {days}일",
        "total_events": len(df),
        "total_amount": total_amount,
        "active_days": active_days,
        "event_summary": event_summary,
        "avg_events_per_day": round(len(df) / max(active_days, 1), 2),
    }


# ============================================================
# 6. 문의 분류 도구
# ============================================================
def tool_classify_inquiry(text: str) -> dict:
    """고장 보고서 텍스트를 카테고리별로 자동 분류합니다 (TF-IDF + RandomForest)."""
    # lazy loading: 모델이 아직 로드되지 않았으면 디스크에서 로드 시도
    st.get_model("FAULT_CLASSIFICATION_MODEL")
    st.get_model("TFIDF_VECTORIZER")
    st.get_model("LE_FAULT_CATEGORY")
    if st.FAULT_CLASSIFICATION_MODEL is None or st.TFIDF_VECTORIZER is None:
        return {"status": "error", "message": "고장 분류 모델이 로드되지 않았습니다."}

    try:
        X = st.TFIDF_VECTORIZER.transform([text])
        pred = st.FAULT_CLASSIFICATION_MODEL.predict(X)[0]
        proba = st.FAULT_CLASSIFICATION_MODEL.predict_proba(X)[0]

        category = st.LE_FAULT_CATEGORY.inverse_transform([pred])[0] if st.LE_FAULT_CATEGORY else "기타"

        # 상위 3개 카테고리 확률
        top_indices = np.argsort(proba)[::-1][:3]
        categories = st.LE_FAULT_CATEGORY.classes_ if st.LE_FAULT_CATEGORY else []

        top_categories = []
        for idx in top_indices:
            if idx < len(categories):
                top_categories.append({
                    "category": categories[idx],
                    "probability": float(proba[idx]),
                })

        return {
            "status": "success",
            "text": text[:100] + "..." if len(text) > 100 else text,
            "predicted_category": category,
            "confidence": float(max(proba)),
            "top_categories": top_categories,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# 7. CS 통계 도구
# ============================================================
def tool_get_cs_statistics() -> dict:
    """CS 문의 통계를 조회합니다."""
    if st.MAINTENANCE_STATS_DF is None:
        return {"status": "error", "message": "CS 통계 데이터가 로드되지 않았습니다."}

    df = st.MAINTENANCE_STATS_DF
    # CSV 컬럼: category, total_tickets, avg_resolution_hours, satisfaction_score

    # 전체 티켓 수 합산
    total_tickets = int(df["total_tickets"].sum()) if "total_tickets" in df.columns else len(df)

    # 카테고리별 통계
    cat_col = "category" if "category" in df.columns else "ticket_category"
    by_category = {}
    if cat_col in df.columns and "total_tickets" in df.columns:
        cs_cols = [cat_col, "total_tickets", "avg_resolution_hours", "satisfaction_score"]
        cs_cols = [c for c in cs_cols if c in df.columns]
        for rec in df[cs_cols].to_dict("records"):
            by_category[str(rec[cat_col])] = {
                "total_tickets": int(rec["total_tickets"]),
                "avg_resolution_hours": round(safe_float(rec.get("avg_resolution_hours", 0)), 1),
                "satisfaction_score": round(safe_float(rec.get("satisfaction_score", 0)), 2),
            }
    elif cat_col in df.columns:
        by_category = df[cat_col].value_counts().to_dict()

    # 티켓 수 기반 가중평균 (카테고리별 단순 평균이 아닌 전체 티켓 가중평균)
    if "satisfaction_score" in df.columns and "total_tickets" in df.columns:
        weights = pd.to_numeric(df["total_tickets"], errors="coerce").fillna(0)
        scores = pd.to_numeric(df["satisfaction_score"], errors="coerce").fillna(0)
        avg_satisfaction = safe_float((scores * weights).sum() / max(weights.sum(), 1))
    elif "satisfaction_score" in df.columns:
        avg_satisfaction = safe_float(df["satisfaction_score"].mean())
    else:
        avg_satisfaction = 0

    if "avg_resolution_hours" in df.columns and "total_tickets" in df.columns:
        weights = pd.to_numeric(df["total_tickets"], errors="coerce").fillna(0)
        hours = pd.to_numeric(df["avg_resolution_hours"], errors="coerce").fillna(0)
        avg_resolution = safe_float((hours * weights).sum() / max(weights.sum(), 1))
    elif "avg_resolution_hours" in df.columns:
        avg_resolution = safe_float(df["avg_resolution_hours"].mean())
    else:
        avg_resolution = 0

    # 마크다운 표 생성 (LLM 라벨 보존용)
    md_lines = [
        "## CS 문의 통계",
        "",
        f"- 총 티켓 수: **{total_tickets:,}**",
        f"- 평균 만족도: **{round(avg_satisfaction, 2)}**",
        f"- 평균 해결 시간: **{round(avg_resolution, 1)}시간**",
        "",
        "| 카테고리 | 티켓 수 | 평균 해결 시간(h) | 만족도 |",
        "|----------|---------|-------------------|--------|",
    ]
    for cat_name, cat_data in by_category.items():
        if isinstance(cat_data, dict):
            md_lines.append(
                f"| {cat_name} | {cat_data.get('total_tickets', 0)} "
                f"| {cat_data.get('avg_resolution_hours', 0)} "
                f"| {cat_data.get('satisfaction_score', 0)} |"
            )
        else:
            md_lines.append(f"| {cat_name} | {cat_data} | - | - |")

    return {
        "status": "success",
        "total_tickets": total_tickets,
        "avg_satisfaction_score": round(avg_satisfaction, 2),
        "avg_resolution_hours": round(avg_resolution, 1),
        "_markdown": "\n".join(md_lines),
        "_llm_instruction": "⚠️ 이 정비 통계는 **스마트팩토리 플랫폼 전체** 집계입니다. 특정 설비의 정비 품질이 아닙니다! 설비별 정비 점검 시 반드시 '플랫폼 전체 정비 통계 기준'임을 명시하세요.",
        "by_category": by_category,
    }


# ============================================================
# 9. 고장 예측 분석
# ============================================================
def tool_get_failure_prediction(risk_level: str = None, limit: int = None) -> dict:
    """설비 고장 예측 분석을 조회합니다. 고위험/중위험/저위험 고장 설비 수와 주요 고장 요인을 반환합니다.

    Args:
        risk_level: 특정 위험 등급만 필터 ("high", "medium", "low")
        limit: 상세 설비 목록 반환 시 최대 개수 (기본값: 10)
    """
    if st.LINE_ANALYTICS_DF is None:
        return {"status": "error", "message": "라인 분석 데이터가 없습니다."}

    try:
        df = st.LINE_ANALYTICS_DF
        original_total = len(df)

        # 특정 위험 등급 필터링
        filtered_equipment = []
        if risk_level:
            risk_level = risk_level.lower()
            if risk_level not in ['high', 'medium', 'low']:
                return {"status": "error", "message": "risk_level은 'high', 'medium', 'low' 중 하나여야 합니다."}

            if 'failure_risk_level' in df.columns:
                if risk_level == 'medium' and 'failure_probability' in df.columns:
                    df = df[(df['failure_probability'] > 0.3) & (df['failure_probability'] <= 0.7)]
                else:
                    df = df[df['failure_risk_level'] == risk_level]
            elif 'is_failed' in df.columns:
                if risk_level == 'high':
                    df = df[df['is_failed'] == 1]
                elif risk_level == 'low':
                    df = df[df['is_failed'] == 0]

            # 상세 설비 목록 (limit 적용)
            max_equipment = limit if limit and limit > 0 else 10
            _id_col = "line_id" if "line_id" in df.columns else "line_id"
            if _id_col in df.columns:
                failure_cols = [_id_col]
                if 'failure_probability' in df.columns:
                    failure_cols.append('failure_probability')
                if 'total_production_volume' in df.columns:
                    failure_cols.append('total_production_volume')
                for rec in df.head(max_equipment)[failure_cols].to_dict("records"):
                    equipment_info = {"line_id": rec[_id_col]}
                    if 'failure_probability' in rec:
                        equipment_info['failure_probability'] = f"{rec['failure_probability'] * 100:.1f}%"
                    if 'total_production_volume' in rec:
                        equipment_info['total_production_volume'] = safe_int(rec['total_production_volume'])
                    filtered_equipment.append(equipment_info)

        total = len(df) if not risk_level else original_total

        # 실제 데이터에서 고장 위험 분류
        full_df = st.LINE_ANALYTICS_DF
        if 'failure_risk_level' in full_df.columns:
            high_risk = len(full_df[full_df['failure_risk_level'] == 'high'])
            low_risk = len(full_df[full_df['failure_risk_level'] == 'low'])
            if 'failure_probability' in full_df.columns:
                medium_mask = (full_df['failure_probability'] > 0.3) & (full_df['failure_probability'] <= 0.7)
                medium_risk = len(full_df[medium_mask])
            else:
                medium_risk = 0
        elif 'is_failed' in full_df.columns:
            high_risk = len(full_df[full_df['is_failed'] == 1])
            low_risk = len(full_df[full_df['is_failed'] == 0])
            medium_risk = 0
        else:
            high_risk = int(total * 0.085)
            medium_risk = int(total * 0.142)
            low_risk = total - high_risk - medium_risk

        # SHAP 기반 고장 요인 분석
        shap_cols = [c for c in df.columns if c.startswith('shap_')]
        top_factors = []
        if shap_cols:
            factor_names = {
                'shap_total_work_orders': '작업지시 수 감소',
                'shap_total_production_volume': '생산량 하락',
                'shap_product_count': '제품 등록 감소',
                'shap_cs_tickets': 'CS 문의 증가',
                'shap_defect_return_rate': '불량률 증가',
                'shap_avg_response_time': '응답 시간 지연',
                'shap_days_since_last_login': '장기 미접속',
                'shap_days_since_register': '가입 후 경과 일수',
                'shap_plan_tier_encoded': '플랜 등급',
            }
            shap_importance = {col: df[col].abs().mean() for col in shap_cols}
            sorted_factors = sorted(shap_importance.items(), key=lambda x: x[1], reverse=True)[:5]
            total_importance = sum(v for _, v in sorted_factors) or 1
            for col, val in sorted_factors:
                pct = round(val / total_importance * 100)
                factor_name = factor_names.get(col, col.replace('shap_', ''))
                top_factors.append({"factor": factor_name, "importance": f"{pct}%"})
        else:
            top_factors = [
                {"factor": "장기 미접속", "importance": "32%"},
                {"factor": "생산량 하락", "importance": "25%"},
                {"factor": "제품 등록 감소", "importance": "18%"},
                {"factor": "CS 문의 급증", "importance": "15%"},
                {"factor": "불량률 상승", "importance": "10%"},
            ]

        failure_rate = round(high_risk / original_total * 100, 1) if original_total > 0 else 0
        top_factor_name = top_factors[0]['factor'] if top_factors else '활동 감소'

        result = {
            "status": "success",
            "prediction_type": "설비 고장 예측",
            "summary": {
                "total_equipment": original_total,
                "high_risk_count": high_risk,
                "medium_risk_count": medium_risk,
                "low_risk_count": low_risk,
                "predicted_failure_rate": failure_rate,
            },
            "top_factors": top_factors,
        }

        # 특정 위험 등급 필터 적용 시 상세 정보 추가
        if risk_level and filtered_equipment:
            level_names = {'high': '고위험', 'medium': '중위험', 'low': '저위험'}
            result["filtered"] = {
                "risk_level": risk_level,
                "count": len(df),
                "equipment": filtered_equipment
            }

        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_get_lifecycle_analysis(lifecycle_period: str = None, month: str = None) -> dict:
    """설비 라이프사이클 분석을 조회합니다. 주간 가동율과 트렌드를 반환합니다.

    CSV 형식: lifecycle_month, week1, week2, week4, week8, week12 (와이드 포맷)

    Args:
        lifecycle_period: 사용하지 않음 (호환성 유지)
        month: 특정 월 필터 (예: "2024-11", "2025-01")
    """
    if st.EQUIPMENT_LIFECYCLE_DF is None:
        return {"status": "error", "message": "라이프사이클 데이터가 없습니다."}

    try:
        df = st.EQUIPMENT_LIFECYCLE_DF

        # 월 필터링 (lifecycle_period 또는 month 사용)
        filter_month = month or lifecycle_period
        if filter_month:
            # "2024-11 W1" 같은 형식에서 월만 추출
            import re
            m = re.search(r'(\d{4}-\d{2})', filter_month)
            if m:
                filter_month = m.group(1)
            filtered = df[df['lifecycle_month'].astype(str).str.contains(filter_month, case=False, na=False)]
            if len(filtered) == 0:
                # 요청한 월이 없으면 전체 라이프사이클 반환 (폴백)
                available = st.EQUIPMENT_LIFECYCLE_DF['lifecycle_month'].tolist()
                st.logger.warning("라이프사이클 '%s' 없음 → 전체 반환. 사용 가능: %s", filter_month, available)
            else:
                df = filtered

        # 와이드 포맷(week1,week2,week4,...) 컬럼 감지
        week_cols = [c for c in df.columns if c.startswith("week")]

        # 라이프사이클별 리텐션 데이터 구성
        lifecycle_cols = ["lifecycle_month"] + week_cols
        lifecycle_cols = [c for c in lifecycle_cols if c in df.columns]
        retention = {}
        for rec in df[lifecycle_cols].to_dict("records"):
            lifecycle_name = safe_str(rec.get("lifecycle_month"))
            weeks = {}
            for wc in week_cols:
                val = safe_float(rec.get(wc))
                weeks[wc] = f"{val:.1f}%"
            retention[lifecycle_name] = {"weeks": weeks}

        # 전체 평균 리텐션 계산
        avg_retention = {}
        for wc in week_cols:
            vals = pd.to_numeric(df[wc], errors="coerce").dropna()
            avg_retention[wc] = round(vals.mean(), 1) if len(vals) > 0 else 0

        return {
            "status": "success",
            "analysis_type": "설비 라이프사이클 가동률 분석",
            "_llm_instruction": "⚠️ 이 라이프사이클 분석은 **스마트팩토리 플랫폼 전체** 설비 기준입니다. 특정 설비/라인의 라이프사이클이 아닙니다! 개별 설비 분석과 함께 제시할 때 반드시 '플랫폼 전체 라이프사이클 기준'임을 명시하세요.",
            "total_lifecycles": len(retention),
            "retention": retention,
            "avg_retention": {k: f"{v}%" for k, v in avg_retention.items()},
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_get_production_trend(start_date: str = None, end_date: str = None, days: int = None) -> dict:
    """생산 트렌드 KPI 분석을 조회합니다. OEE, 생산량, 가동 설비 등 주요 지표의 변화율을 반환합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)
        days: 최근 N일 분석 (start_date/end_date 대신 사용 가능)
    """
    if st.DAILY_PRODUCTION_DF is None:
        return {"status": "error", "message": "일별 지표 데이터가 없습니다."}

    try:
        # 원본 DF를 수정하지 않고 조회만 수행 (copy 제거로 메모리/시간 절약)
        df = st.DAILY_PRODUCTION_DF

        # 날짜 컬럼이 아직 datetime이 아닌 경우에만 변환 (지역 변수로 처리)
        if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
            date_col = pd.to_datetime(df['date'])
        elif 'date' in df.columns:
            date_col = df['date']
        else:
            date_col = None

        # 날짜 필터링
        full_df = df  # fallback용 원본 참조
        if start_date and end_date:
            try:
                start = pd.to_datetime(start_date)
                end = pd.to_datetime(end_date)
                if date_col is not None:
                    df = df[(date_col >= start) & (date_col <= end)]
                    # 날짜 필터링 결과가 부족하면 전체 데이터로 fallback
                    if len(df) < 2:
                        df = full_df
            except Exception:
                pass
        elif days and days > 0:
            df = df.tail(days * 2)  # 비교를 위해 2배 기간 가져오기

        # 최근 기간 vs 이전 기간 비교
        compare_days = days if days and days > 0 else 7
        if len(df) >= compare_days * 2:
            recent = df.tail(compare_days)
            previous = df.iloc[-(compare_days * 2):-compare_days]
        elif len(df) >= 2:
            mid = len(df) // 2
            recent = df.tail(mid)
            previous = df.head(mid)
        else:
            return {"status": "error", "message": "데이터가 충분하지 않습니다."}

        def calc_change(curr, prev):
            if prev == 0:
                return 0
            return round((curr - prev) / prev * 100, 1)

        def format_change(val):
            if val > 0:
                return f"+{val}%"
            return f"{val}%"

        # 컬럼명 호환 (daily_metrics.csv: total_gmv, active_shops, new_signups, cs_tickets_open 등)
        def _col(df_, name, fallbacks=None):
            if name in df_.columns:
                return name
            for fb in (fallbacks or []):
                if fb in df_.columns:
                    return fb
            return None

        gmv_col = _col(recent, 'total_gmv', ['gmv'])
        shops_col = _col(recent, 'active_shops', ['active_equipment'])
        orders_col = _col(recent, 'total_work_orders')
        signups_col = _col(recent, 'new_signups', ['new_equipment'])
        cs_open_col = _col(recent, 'cs_tickets_open', ['cs_tickets'])
        cs_resolved_col = _col(recent, 'cs_tickets_resolved')
        repair_time_col = _col(recent, 'avg_repair_time', ['avg_settlement_time'])
        sessions_col = _col(recent, 'total_sessions')

        # KPI 계산 - 총생산량
        gmv_curr = int(recent[gmv_col].mean()) if gmv_col else 0
        gmv_prev = int(previous[gmv_col].mean()) if gmv_col else 0
        gmv_change = calc_change(gmv_curr, gmv_prev)

        # 활성 설비 수
        shops_curr = int(recent[shops_col].mean()) if shops_col else 0
        shops_prev = int(previous[shops_col].mean()) if shops_col else 0
        shops_change = calc_change(shops_curr, shops_prev)

        # 총 작업지시수
        orders_curr = int(recent[orders_col].mean()) if orders_col else 0
        orders_prev = int(previous[orders_col].mean()) if orders_col else 0
        orders_change = calc_change(orders_curr, orders_prev)

        # 신규 등록
        signups_curr = int(recent[signups_col].mean()) if signups_col else 0
        signups_prev = int(previous[signups_col].mean()) if signups_col else 0
        signups_change = calc_change(signups_curr, signups_prev)

        # 평균 수리 시간
        repair_curr = round(recent[repair_time_col].mean(), 1) if repair_time_col else 0
        repair_prev = round(previous[repair_time_col].mean(), 1) if repair_time_col else 0
        repair_change = calc_change(repair_curr, repair_prev)

        # CS 티켓 (open)
        cs_curr = int(recent[cs_open_col].mean()) if cs_open_col else 0
        cs_prev = int(previous[cs_open_col].mean()) if cs_open_col else 0
        cs_change = calc_change(cs_curr, cs_prev)

        # CS 해결률
        cs_resolved_curr = int(recent[cs_resolved_col].sum()) if cs_resolved_col else 0
        cs_open_sum_curr = int(recent[cs_open_col].sum()) if cs_open_col else 1
        cs_rate_curr = round(cs_resolved_curr / max(cs_open_sum_curr, 1) * 100, 1)

        cs_resolved_prev = int(previous[cs_resolved_col].sum()) if cs_resolved_col else 0
        cs_open_sum_prev = int(previous[cs_open_col].sum()) if cs_open_col else 1
        cs_rate_prev = round(cs_resolved_prev / max(cs_open_sum_prev, 1) * 100, 1)
        cs_rate_change = calc_change(cs_rate_curr, cs_rate_prev)

        # 세션
        sessions_curr = int(recent[sessions_col].mean()) if sessions_col else 0
        sessions_prev = int(previous[sessions_col].mean()) if sessions_col else 0
        sessions_change = calc_change(sessions_curr, sessions_prev)

        # 상관관계 계산
        correlations = []
        if len(df) >= 7 and shops_col and gmv_col and orders_col:
            corr_shops_gmv = df[shops_col].corr(df[gmv_col])
            corr_orders_gmv = df[orders_col].corr(df[gmv_col])
            correlations = [
                {"var1": "활성 설비", "var2": "총생산량", "correlation": round(corr_shops_gmv, 2),
                 "strength": "강함" if abs(corr_shops_gmv) > 0.7 else "중간"},
                {"var1": "작업지시수", "var2": "총생산량", "correlation": round(corr_orders_gmv, 2),
                 "strength": "강함" if abs(corr_orders_gmv) > 0.7 else "중간"},
            ]

        # 생산량 포맷팅
        def format_production(val):
            if val >= 100000000:
                return f"₩{val / 100000000:.1f}억"
            elif val >= 10000:
                return f"₩{val / 10000:.0f}만"
            else:
                return f"₩{val:,}"

        insight_parts = [f"일평균 총생산량 {format_production(gmv_curr)}으로 전기간 대비 {format_change(gmv_change)} 변화."]
        if signups_change < 0:
            insight_parts.append(f"신규 등록 {format_change(signups_change)} 감소 주의.")
        if cs_rate_change > 0:
            insight_parts.append(f"CS 해결률 {format_change(cs_rate_change)} 개선.")

        # 마크다운 표 생성 (LLM 라벨 보존용)
        md_lines = [
            f"## 플랫폼 트렌드 분석 (최근 {len(recent)}일 vs 이전 {len(previous)}일)",
            "",
            "| 지표 | 현재 | 이전 | 변화율 |",
            "|------|------|------|--------|",
            f"| 총생산량 | {format_production(gmv_curr)} | {format_production(gmv_prev)} | {format_change(gmv_change)} |",
            f"| 활성설비 | {shops_curr} | {shops_prev} | {format_change(shops_change)} |",
            f"| 작업지시수 | {orders_curr} | {orders_prev} | {format_change(orders_change)} |",
            f"| 신규등록 | {signups_curr} | {signups_prev} | {format_change(signups_change)} |",
            f"| 평균수리시간 | {repair_curr:.1f}일 | {repair_prev:.1f}일 | {format_change(repair_change)} |",
            f"| CS해결률 | {cs_rate_curr}% | {cs_rate_prev}% | {format_change(cs_rate_change)} |",
            f"| CS티켓 | {cs_curr} | {cs_prev} | {format_change(cs_change)} |",
            f"| 세션수 | {sessions_curr} | {sessions_prev} | {format_change(sessions_change)} |",
        ]
        if correlations:
            md_lines += ["", "### 상관관계", "| 변수1 | 변수2 | 상관계수 | 강도 |", "|-------|-------|----------|------|"]
            for c in correlations:
                md_lines.append(f"| {c['var1']} | {c['var2']} | {c['correlation']} | {c['strength']} |")

        return {
            "status": "success",
            "analysis_type": "플랫폼 트렌드 분석",
            "_llm_instruction": "⚠️ 이 데이터는 스마트팩토리 **플랫폼 전체** 집계입니다. 특정 설비/라인 데이터가 아닙니다! 특정 설비 분석에는 get_equipment_performance를 사용하세요.",
            "period": f"최근 {len(recent)}일 vs 이전 {len(previous)}일",
            "_markdown": "\n".join(md_lines),
            "kpis": {
                "총생산량": {"current": format_production(gmv_curr), "previous": format_production(gmv_prev), "change": format_change(gmv_change)},
                "활성설비": {"current": shops_curr, "previous": shops_prev, "change": format_change(shops_change)},
                "작업지시수": {"current": orders_curr, "previous": orders_prev, "change": format_change(orders_change)},
                "신규등록": {"current": signups_curr, "previous": signups_prev, "change": format_change(signups_change)},
                "평균수리시간": {"current": f"{repair_curr:.1f}일", "previous": f"{repair_prev:.1f}일", "change": format_change(repair_change)},
                "CS해결률": {"current": f"{cs_rate_curr}%", "previous": f"{cs_rate_prev}%", "change": format_change(cs_rate_change)},
                "CS티켓": {"current": cs_curr, "previous": cs_prev, "change": format_change(cs_change)},
                "세션수": {"current": sessions_curr, "previous": sessions_prev, "change": format_change(sessions_change)},
            },
            "correlations": correlations,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_get_oee_prediction(days: int = None, start_date: str = None, end_date: str = None) -> dict:
    """OEE(종합설비효율) 예측 분석을 조회합니다. 예상 OEE, 생산 트렌드, 설비 생산성 분포를 반환합니다.

    Args:
        days: 최근 N일 기준 분석 (기본값: 30일)
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)
    """
    if st.DAILY_PRODUCTION_DF is None:
        return {"status": "error", "message": "일별 지표 데이터가 없습니다."}

    try:
        # 원본 DF를 수정하지 않고 조회만 수행 (copy 제거로 메모리/시간 절약)
        metrics_df = st.DAILY_PRODUCTION_DF

        # 날짜 컬럼이 아직 datetime이 아닌 경우에만 변환 (지역 변수로 처리)
        if 'date' in metrics_df.columns and not pd.api.types.is_datetime64_any_dtype(metrics_df['date']):
            date_col = pd.to_datetime(metrics_df['date'])
        elif 'date' in metrics_df.columns:
            date_col = metrics_df['date']
        else:
            date_col = None

        # 날짜 필터링
        if start_date and end_date:
            try:
                start = pd.to_datetime(start_date)
                end = pd.to_datetime(end_date)
                if date_col is not None:
                    metrics_df = metrics_df[(date_col >= start) & (date_col <= end)]
            except Exception:
                pass

        # 분석 기간 설정 (기본 30일)
        analyze_days = days if days and days > 0 else 30

        # 최근 N일 vs 이전 N일
        if len(metrics_df) >= analyze_days * 2:
            recent = metrics_df.tail(analyze_days)
            previous = metrics_df.iloc[-(analyze_days * 2):-analyze_days]
        elif len(metrics_df) >= 14:
            mid = len(metrics_df) // 2
            recent = metrics_df.tail(mid)
            previous = metrics_df.head(mid)
        else:
            recent = metrics_df
            previous = metrics_df

        # 컬럼명 호환
        gmv_col = 'total_gmv' if 'total_gmv' in recent.columns else 'gmv'
        shops_col = 'active_shops' if 'active_shops' in recent.columns else 'active_equipment'

        # 월 총생산량 예측 (최근 일평균 * 30)
        daily_avg_gmv = recent[gmv_col].mean() if gmv_col in recent.columns else 0
        monthly_gmv = int(daily_avg_gmv * 30)
        prev_monthly = int(previous[gmv_col].mean() * 30) if gmv_col in previous.columns else 0
        growth_rate = round((monthly_gmv - prev_monthly) / prev_monthly * 100, 1) if prev_monthly > 0 else 0

        # 평균 수율 - daily_metrics에 없으면 총생산량/작업지시수로 계산
        if 'avg_yield_rate' in recent.columns:
            avg_yield_rate = int(recent['avg_yield_rate'].mean())
        elif 'total_work_orders' in recent.columns and gmv_col in recent.columns:
            total_work_orders_sum = recent['total_work_orders'].sum()
            avg_yield_rate = int(recent[gmv_col].sum() / max(total_work_orders_sum, 1))
        else:
            avg_yield_rate = 0

        # 총 작업지시수
        total_work_orders = int(recent['total_work_orders'].sum()) if 'total_work_orders' in recent.columns else 0

        # 활성 설비
        avg_active_equipment = int(recent[shops_col].mean()) if shops_col in recent.columns else 0

        # 설비 등급별 생산 분포 (LINE_ANALYTICS_DF 기반)
        tier_distribution = {}
        if st.LINE_ANALYTICS_DF is not None and 'plan_tier' in st.LINE_ANALYTICS_DF.columns:
            equipment_df = st.LINE_ANALYTICS_DF
            for tier in EQUIPMENT_GRADES:
                tier_equipment = equipment_df[equipment_df['plan_tier'] == tier]
                if len(tier_equipment) > 0:
                    tier_distribution[tier] = {
                        "equipment_count": len(tier_equipment),
                        "avg_revenue": safe_int(tier_equipment['total_production_volume'].mean()),
                        "total_production_volume": safe_int(tier_equipment['total_production_volume'].sum()),
                    }

        # OEE (daily_metrics에 없을 수 있음)
        avg_conversion = round(recent['oee_rate'].mean(), 2) if 'oee_rate' in recent.columns else 0.0

        # 생산량 포맷팅
        def format_production(val):
            if val >= 100000000:
                return f"₩{val / 100000000:.1f}억"
            elif val >= 10000:
                return f"₩{val / 10000:.0f}만"
            else:
                return f"₩{val:,}"

        growth_str = f"+{growth_rate}%" if growth_rate > 0 else f"{growth_rate}%"

        return {
            "status": "success",
            "prediction_type": "총생산량 예측",
            "monthly_forecast": {
                "predicted_gmv": format_production(monthly_gmv),
                "growth_rate": growth_str,
                "daily_avg": format_production(int(daily_avg_gmv)),
            },
            "platform_metrics": {
                "avg_yield_rate": f"₩{avg_yield_rate:,}",
                "total_work_orders": total_work_orders,
                "active_equipment": avg_active_equipment,
                "oee_rate": f"{avg_conversion}%",
            },
            "tier_distribution": tier_distribution,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_get_dashboard_summary() -> dict:
    """대시보드 요약 정보를 조회합니다. 플랫폼 전체 운영 현황을 반환합니다."""

    summary = {
        "status": "success",
    }

    # 설비 통계 (프론트엔드: equipment_stats_overview)
    if st.EQUIPMENT_DF is not None:
        equip_df = st.EQUIPMENT_DF
        by_tier = equip_df["plan_tier"].value_counts().to_dict() if "plan_tier" in equip_df.columns else {}
        summary["shop_stats"] = {
            "total": len(equip_df),
            "by_tier": by_tier,
            "by_plan_tier": by_tier,
            "by_category": equip_df["category"].value_counts().to_dict() if "category" in equip_df.columns else {},
            "by_region": equip_df["region"].value_counts().to_dict() if "region" in equip_df.columns else {},
        }

    # 설비 세그먼트 통계 (프론트엔드: equipment_stats.total, .anomaly_count, .segments)
    if st.LINE_ANALYTICS_DF is not None:
        equipment_df = st.LINE_ANALYTICS_DF
        anomaly_count = int(equipment_df["is_anomaly"].sum()) if "is_anomaly" in equipment_df.columns else 0
        equipment_stats = {
            "total": len(equipment_df),
            "anomaly_count": anomaly_count,
        }

        if "cluster" in equipment_df.columns:
            raw_segments = equipment_df["cluster"].value_counts().to_dict()
            equipment_stats["segments"] = {
                _get_segment_name(k): v for k, v in raw_segments.items()
            }
        elif "plan_tier" in equipment_df.columns:
            equipment_stats["by_plan_tier"] = equipment_df["plan_tier"].value_counts().to_dict()

        summary["equipment_stats"] = equipment_stats
    elif st.PRODUCTION_LINES_DF is not None:
        lines_df = st.PRODUCTION_LINES_DF
        summary["equipment_stats"] = {
            "total": len(lines_df),
            "by_plan_tier": lines_df["plan_tier"].value_counts().to_dict() if "plan_tier" in lines_df.columns else {},
            "by_region": lines_df["region"].value_counts().to_dict() if "region" in lines_df.columns else {},
        }

    # CS 통계 (프론트엔드: cs_stats.total, .avg_satisfaction, .by_category)
    # CSV 컬럼: category, total_tickets, avg_resolution_hours, satisfaction_score
    if st.MAINTENANCE_STATS_DF is not None:
        cs_df = st.MAINTENANCE_STATS_DF
        cat_col = "category" if "category" in cs_df.columns else "ticket_category"
        total_tickets = int(cs_df["total_tickets"].sum()) if "total_tickets" in cs_df.columns else len(cs_df)
        avg_satisfaction = round(float(cs_df["satisfaction_score"].mean()), 1) if "satisfaction_score" in cs_df.columns else 0
        avg_resolution = round(float(cs_df["avg_resolution_hours"].mean()), 1) if "avg_resolution_hours" in cs_df.columns else 0

        # by_category: {카테고리: 건수} 형태
        by_category = {}
        if cat_col in cs_df.columns and "total_tickets" in cs_df.columns:
            for rec in cs_df[[cat_col, "total_tickets"]].to_dict("records"):
                by_category[str(rec[cat_col])] = int(rec["total_tickets"])
        elif cat_col in cs_df.columns:
            by_category = cs_df[cat_col].value_counts().to_dict()

        summary["cs_stats"] = {
            "total": total_tickets,
            "total_tickets": total_tickets,
            "avg_satisfaction": avg_satisfaction,
            "avg_resolution_hours": avg_resolution,
            "by_category": by_category,
        }

    # 작업지시/이벤트 통계 (프론트엔드: order_stats.total, .by_type)
    # CSV 컬럼: log_id, line_id, event_type, event_date, details_json
    if st.OPERATION_LOGS_DF is not None and "event_type" in st.OPERATION_LOGS_DF.columns:
        logs_df = st.OPERATION_LOGS_DF
        event_counts = logs_df["event_type"].value_counts().to_dict()
        summary["order_stats"] = {
            "total": len(logs_df),
            "total_events": len(logs_df),
            "by_type": event_counts,
        }

    # 이상 탐지 통계
    # CSV 컬럼: line_id, anomaly_score, anomaly_type, detected_date, details
    if st.DEFECT_DETAILS_DF is not None:
        defect_df = st.DEFECT_DETAILS_DF
        high_risk_count = len(defect_df[defect_df["anomaly_score"] >= 0.9]) if "anomaly_score" in defect_df.columns else 0
        by_type = defect_df["anomaly_type"].value_counts().to_dict() if "anomaly_type" in defect_df.columns else {}
        summary["defect_stats"] = {
            "total_records": len(defect_df),
            "high_risk_count": high_risk_count,
            "defect_rate": round(high_risk_count / len(defect_df) * 100, 1) if len(defect_df) > 0 else 0,
            "by_type": by_type,
        }

    # 일별 플랫폼 지표 (최근 14일)
    # CSV 컬럼: date, active_shops, total_gmv, new_signups, total_work_orders, avg_repair_time, cs_tickets_open, cs_tickets_resolved, defect_alerts
    if st.DAILY_PRODUCTION_DF is not None and len(st.DAILY_PRODUCTION_DF) > 0:
        recent_df = st.DAILY_PRODUCTION_DF.tail(14)
        daily_cols = ["date", "total_gmv", "gmv", "active_shops", "active_equipment",
                      "total_work_orders", "new_signups", "new_equipment"]
        daily_cols = [c for c in daily_cols if c in recent_df.columns]
        daily_list = []
        for rec in recent_df[daily_cols].to_dict("records"):
            date_val = safe_str(rec.get("date"))
            # 날짜를 MM/DD 형식으로 변환
            try:
                date_display = pd.to_datetime(date_val).strftime("%m/%d")
            except Exception:
                date_display = date_val
            daily_list.append({
                "date": date_display,
                "gmv": safe_int(rec.get("total_gmv", rec.get("gmv", 0))),
                "active_equipment": safe_int(rec.get("active_shops", rec.get("active_equipment", 0))),
                "total_work_orders": safe_int(rec.get("total_work_orders", 0)),
                "new_equipment": safe_int(rec.get("new_signups", rec.get("new_equipment", 0))),
            })
        summary["daily_metrics"] = daily_list
        # 프론트엔드 총생산량 차트용: daily_gmv 배열 (date, gmv)
        summary["daily_gmv"] = [{"date": d["date"], "gmv": d["gmv"]} for d in daily_list]
    else:
        summary["daily_metrics"] = []
        summary["daily_gmv"] = []

    # 마크다운 표 생성 (LLM 라벨 보존용)
    md_sections = ["## 플랫폼 전체 운영 현황 대시보드"]

    # 설비 분포
    if "shop_stats" in summary:
        ss = summary["shop_stats"]
        md_sections.append(f"\n### 설비 현황\n- 총 설비 수: **{ss['total']}**")
        if ss.get("by_tier"):
            md_sections.append("\n**티어별 분포**\n| 티어 | 수 |\n|------|-------|")
            for tier, cnt in ss["by_tier"].items():
                md_sections.append(f"| {tier} | {cnt} |")
        if ss.get("by_category"):
            md_sections.append("\n**카테고리별 분포**\n| 카테고리 | 수 |\n|----------|-------|")
            for cat, cnt in ss["by_category"].items():
                md_sections.append(f"| {cat} | {cnt} |")
        if ss.get("by_region"):
            md_sections.append("\n**지역별 분포**\n| 지역 | 수 |\n|------|-------|")
            for region, cnt in ss["by_region"].items():
                md_sections.append(f"| {region} | {cnt} |")

    # 설비 현황
    if "equipment_stats" in summary:
        sl = summary["equipment_stats"]
        md_sections.append(f"\n### 설비 현황\n- 총 설비 수: **{sl['total']}**")
        if sl.get("anomaly_count"):
            md_sections.append(f"- 이상 징후 설비: **{sl['anomaly_count']}**")
        if sl.get("segments"):
            md_sections.append("\n**세그먼트별 분포**\n| 세그먼트 | 수 |\n|----------|-------|")
            for seg, cnt in sl["segments"].items():
                md_sections.append(f"| {seg} | {cnt} |")

    # CS 통계
    if "cs_stats" in summary:
        cs = summary["cs_stats"]
        md_sections.append(f"\n### CS 통계\n- 총 티켓 수: **{cs.get('total', 0):,}**")
        md_sections.append(f"- 평균 만족도: **{cs.get('avg_satisfaction', 0)}**")
        md_sections.append(f"- 평균 해결 시간: **{cs.get('avg_resolution_hours', 0)}시간**")
        if cs.get("by_category"):
            md_sections.append("\n| 카테고리 | 티켓 수 |\n|----------|---------|")
            for cat, cnt in cs["by_category"].items():
                md_sections.append(f"| {cat} | {cnt} |")

    # 운영 이벤트
    if "order_stats" in summary:
        os_ = summary["order_stats"]
        md_sections.append(f"\n### 운영 이벤트\n- 총 이벤트: **{os_.get('total', 0):,}**")
        if os_.get("by_type"):
            md_sections.append("\n| 이벤트 유형 | 건수 |\n|-------------|------|")
            for etype, cnt in os_["by_type"].items():
                md_sections.append(f"| {etype} | {cnt:,} |")

    # 이상 탐지
    if "defect_stats" in summary:
        fs = summary["defect_stats"]
        md_sections.append(f"\n### 이상 탐지 현황\n- 총 기록: **{fs.get('total_records', 0)}**")
        md_sections.append(f"- 고위험: **{fs.get('high_risk_count', 0)}**")
        md_sections.append(f"- 불량 비율: **{fs.get('defect_rate', 0)}%**")
        if fs.get("by_type"):
            md_sections.append("\n| 유형 | 건수 |\n|------|------|")
            for ftype, cnt in fs["by_type"].items():
                md_sections.append(f"| {ftype} | {cnt} |")

    summary["_markdown"] = "\n".join(md_sections)
    return summary


# ============================================================
# 10. ML 모델 예측 도구
# ============================================================
def tool_predict_equipment_failure(line_id: str) -> dict:
    """
    특정 설비의 고장 확률을 예측합니다.
    EQUIPMENT_FAILURE_MODEL(RandomForest)과 SHAP Explainer를 사용하여 예측 및 설명을 제공합니다.
    """
    if st.LINE_ANALYTICS_DF is None:
        return {"status": "error", "message": "라인 분석 데이터가 로드되지 않았습니다."}

    # 설비 데이터 조회
    _id_col = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
    row_match = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[_id_col] == line_id]
    if row_match.empty:
        return {"status": "error", "message": f"설비/라인 '{line_id}'를 찾을 수 없습니다."}

    row = row_match.iloc[0]

    # lazy loading: 고장 예측 모델 로드 시도
    st.get_model("EQUIPMENT_FAILURE_MODEL")
    # 고장 예측 모델이 없으면 휴리스틱 사용
    if st.EQUIPMENT_FAILURE_MODEL is None:
        total_work_orders = safe_int(row.get("total_work_orders", 0))
        total_production_volume = safe_int(row.get("total_production_volume", 0))
        days_since_last = safe_int(row.get("days_since_last_login", 0))
        defect_return_rate = safe_float(row.get("defect_return_rate", 0))
        cs_tickets = safe_int(row.get("cs_tickets", 0))

        # 고장 위험 점수 계산
        failure_score = 0.3  # 기본값
        if days_since_last > 14:
            failure_score += 0.25
        elif days_since_last > 7:
            failure_score += 0.15
        if total_work_orders < 10:
            failure_score += 0.1
        if total_production_volume < 100000:
            failure_score += 0.1
        if defect_return_rate > 10:
            failure_score += 0.1
        if cs_tickets > 20:
            failure_score += 0.05

        failure_score = min(max(failure_score, 0.05), 0.95)
        risk_level = "HIGH" if failure_score > 0.6 else "MEDIUM" if failure_score > 0.3 else "LOW"
        heuristic_pct = round(failure_score * 100, 2)

        return {
            "status": "success",
            "line_id": line_id,
            "failure_probability_pct": heuristic_pct,
            "failure_probability_display": f"{heuristic_pct}%",
            "risk_level": risk_level,
            "risk_thresholds": "LOW: 0~30%, MEDIUM: 30~60%, HIGH: 60%+",
            "model_used": "heuristic",
            "top_factors": [
                {"factor": f"마지막 접속 {days_since_last}일 전", "importance": 30},
                {"factor": f"총 작업지시 수 {total_work_orders}건", "importance": 25},
                {"factor": f"총 생산량 ₩{total_production_volume:,}", "importance": 20},
                {"factor": f"불량률 {defect_return_rate}%", "importance": 15},
                {"factor": f"CS 문의 {cs_tickets}건", "importance": 10},
            ],
            "recommendation": _get_equipment_failure_recommendation(risk_level, days_since_last, total_production_volume),
        }

    # 실제 모델 사용
    try:
        # 피처 준비
        feature_cols = FEATURE_COLS_FAILURE
        X = pd.DataFrame([{col: safe_float(row.get(col, 0)) for col in feature_cols}])

        # plan_tier 인코딩 처리
        if "plan_tier_encoded" in feature_cols and "plan_tier" in row.index:
            tier_map = {tier: i for i, tier in enumerate(EQUIPMENT_GRADES)}
            X["plan_tier_encoded"] = tier_map.get(row.get("plan_tier", "Basic"), 0)

        # 예측
        failure_prob = st.EQUIPMENT_FAILURE_MODEL.predict_proba(X)[0][1]  # 고장 확률
        failure_pred = st.EQUIPMENT_FAILURE_MODEL.predict(X)[0]

        risk_level = "HIGH" if failure_prob > 0.6 else "MEDIUM" if failure_prob > 0.3 else "LOW"

        # 모델 내장 feature_importances_ 사용 (SHAP 대비 수백ms 절약)
        top_factors = []
        if hasattr(st.EQUIPMENT_FAILURE_MODEL, 'feature_importances_'):
            try:
                importances = st.EQUIPMENT_FAILURE_MODEL.feature_importances_
                feature_importance = list(zip(feature_cols, importances))
                feature_importance.sort(key=lambda x: x[1], reverse=True)

                for feat, imp in feature_importance[:5]:
                    top_factors.append({
                        "factor": FEATURE_LABELS.get(feat, feat),
                        "importance": round(float(imp) * 100, 1),
                    })
            except Exception as e:
                print(f"[FeatureImportance Error] {type(e).__name__}: {e}")

        if not top_factors:
            top_factors = [
                {"factor": "마지막 접속 후 일수", "importance": 30},
                {"factor": "총 생산량", "importance": 25},
                {"factor": "작업지시 수", "importance": 20},
                {"factor": "불량률", "importance": 15},
                {"factor": "플랜 등급", "importance": 10},
            ]

        days_since_last = safe_int(row.get("days_since_last_login", 0))
        total_production_volume = safe_int(row.get("total_production_volume", 0))

        # 모델 확률 0.0% → 최소 0.5%로 표시 (모델 보정 한계, 과신 방지)
        failure_pct = round(failure_prob * 100, 2)
        if failure_pct < 1.0:
            failure_pct = max(failure_pct, 0.5)

        return {
            "status": "success",
            "line_id": line_id,
            "failure_probability_pct": failure_pct,
            "failure_probability_display": f"{failure_pct}%",
            "risk_level": risk_level,
            "risk_thresholds": "LOW: 0~30%, MEDIUM: 30~60%, HIGH: 60%+",
            "will_fail": bool(failure_pred),
            "model_used": "random_forest",
            "top_factors": top_factors,
            "importance_note": "모델 전체 학습 데이터 기준 변수 중요도이며, 해당 설비 개별 원인 분석은 아닙니다",
            "recommendation": _get_equipment_failure_recommendation(risk_level, days_since_last, total_production_volume),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def _get_equipment_failure_recommendation(risk_level: str, days_since_last: int, total_production_volume: int) -> str:
    """설비 고장 위험에 따른 권장사항"""
    if risk_level == "HIGH":
        if days_since_last > 14:
            return "긴급! 14일 이상 미가동 설비입니다. 전담 엔지니어 배정 및 긴급 점검을 권장합니다."
        return "높은 고장 위험. 정밀 진단 및 예방 정비 일정 수립을 권장합니다."
    elif risk_level == "MEDIUM":
        if total_production_volume < 500000:
            return "중간 고장 위험. 수율 저하 설비입니다. 공정 파라미터 점검 및 정비 일정 조정을 권장합니다."
        return "중간 고장 위험. 정기적인 상태 모니터링 및 예방 정비를 권장합니다."
    return "현재 기준 저위험. 주요 운영 지표가 양호한 편이나, 정기적인 모니터링을 권장합니다."


def tool_predict_production_yield(equipment_id: str) -> dict:
    """
    설비/라인의 다음달 생산량을 예측합니다.
    YIELD_PREDICTION_MODEL(LightGBM)을 사용합니다.
    """
    if st.EQUIPMENT_PERFORMANCE_DF is None:
        return {"status": "error", "message": "설비 성과 데이터가 로드되지 않았습니다."}

    # 설비 검색 (equipment_id / shop_id 컬럼 호환)
    id_col = "equipment_id" if "equipment_id" in st.EQUIPMENT_PERFORMANCE_DF.columns else "shop_id"
    equip = st.EQUIPMENT_PERFORMANCE_DF[st.EQUIPMENT_PERFORMANCE_DF[id_col] == equipment_id]
    if equip.empty:
        equip = st.EQUIPMENT_PERFORMANCE_DF[st.EQUIPMENT_PERFORMANCE_DF["name"].str.contains(equipment_id, na=False)]

    if equip.empty:
        return {"status": "error", "message": f"설비 '{equipment_id}'를 찾을 수 없습니다."}

    row = equip.iloc[0]

    # 실제 다음달 생산량 (데이터에 있는 경우)
    actual_next_production = safe_int(row.get("next_month_production", row.get("next_month_revenue", 0)))

    # 현재 성과 지표
    total_production_volume = safe_int(row.get("total_production_volume"))
    total_work_orders = safe_int(row.get("total_work_orders"))
    active_equipment_count = safe_int(row.get("active_equipment_count"))
    avg_yield_rate = safe_int(row.get("avg_yield_rate"))
    production_growth = safe_float(row.get("production_growth", row.get("revenue_growth", 0)))
    oee_rate = safe_float(row.get("oee_rate"))
    defect_return_rate = safe_float(row.get("defect_return_rate"))

    # 모델 예측 (lazy loading)
    st.get_model("YIELD_PREDICTION_MODEL")
    predicted_production = actual_next_production
    if st.YIELD_PREDICTION_MODEL is not None:
        try:
            feature_dict = {
                "total_production_volume": total_production_volume,
                "total_work_orders": total_work_orders,
                "active_equipment_count": active_equipment_count,
                "avg_yield_rate": avg_yield_rate,
                "production_growth": production_growth,
                "oee_rate": oee_rate,
                "defect_return_rate": defect_return_rate,
            }
            X = pd.DataFrame([feature_dict])
            predicted_production = int(st.YIELD_PREDICTION_MODEL.predict(X)[0])
        except Exception:
            predicted_production = actual_next_production if actual_next_production > 0 else int(total_production_volume * (1 + production_growth / 100))

    # 생산량 등급
    production_tier = _get_production_tier(predicted_production)

    # 생산량 포맷팅
    def format_production(val):
        if val >= 100000000:
            return f"₩{val / 100000000:.1f}억"
        elif val >= 10000:
            return f"₩{val / 10000:.0f}만"
        else:
            return f"₩{val:,}"

    return {
        "status": "success",
        "equipment_id": safe_str(row.get(id_col)),
        "name": safe_str(row.get("name")),
        "category": safe_str(row.get("category")),
        "region": safe_str(row.get("region")),
        "predicted_production": format_production(predicted_production),
        "predicted_production_raw": predicted_production,
        "production_tier": production_tier,
        "current_performance": {
            "total_production_volume": format_production(total_production_volume),
            "total_work_orders": total_work_orders,
            "active_equipment_count": active_equipment_count,
            "avg_yield_rate": f"₩{avg_yield_rate:,}",
            "production_growth": f"{production_growth}%",
            "oee_rate": f"{oee_rate}%",
            "defect_return_rate": f"{defect_return_rate}%",
        },
        "analysis": _analyze_equipment_performance(row, predicted_production),
    }


def _get_production_tier(production: int) -> str:
    """생산량 규모에 따른 등급 반환"""
    if production >= 50000000:
        return "S (최상위 생산량)"
    elif production >= 20000000:
        return "A (상위 생산량)"
    elif production >= 10000000:
        return "B (평균 생산량)"
    elif production >= 5000000:
        return "C (하위 생산량)"
    return "D (최하위 생산량)"

# 하위 호환 별칭
_get_revenue_tier = _get_production_tier


def _analyze_equipment_performance(row, predicted_production: int) -> str:
    """설비 성과 분석"""
    analysis = []

    oee_rate = safe_float(row.get("oee_rate"))
    defect_return_rate = safe_float(row.get("defect_return_rate"))
    production_growth = safe_float(row.get("production_growth", row.get("revenue_growth", 0)))

    if oee_rate > 3:
        analysis.append("OEE가 우수하여 가동률 확대가 효과적일 수 있습니다")
    elif oee_rate < 1:
        analysis.append("OEE 개선이 필요합니다. 공정 파라미터 최적화를 권장합니다")

    if defect_return_rate > 5:
        analysis.append("불량률이 높습니다. 공정 파라미터 및 원자재 품질 점검을 권장합니다")

    if production_growth > 10:
        analysis.append("높은 생산량 성장률을 보이고 있습니다")
    elif production_growth < -5:
        analysis.append("생산량이 감소 추세입니다. 공정 전략 재검토가 필요합니다")

    if not analysis:
        analysis.append("전반적으로 안정적인 운영 상태입니다")

    return ". ".join(analysis) + "."


def tool_get_equipment_performance(equipment_id: str) -> dict:
    """
    특정 설비의 성과 KPI를 조회합니다.
    """
    if st.EQUIPMENT_PERFORMANCE_DF is None:
        return {"status": "error", "message": "설비 성과 데이터가 로드되지 않았습니다."}

    # 설비 검색 (equipment_id / shop_id 컬럼 호환)
    id_col = "equipment_id" if "equipment_id" in st.EQUIPMENT_PERFORMANCE_DF.columns else "shop_id"
    equip = st.EQUIPMENT_PERFORMANCE_DF[st.EQUIPMENT_PERFORMANCE_DF[id_col] == equipment_id]
    if equip.empty:
        equip = st.EQUIPMENT_PERFORMANCE_DF[st.EQUIPMENT_PERFORMANCE_DF["name"].str.contains(equipment_id, na=False)]

    if equip.empty:
        return {"status": "error", "message": f"설비 '{equipment_id}'를 찾을 수 없습니다."}

    row = equip.iloc[0]

    # 컬럼명 호환: monthly_production_volume/total_production_volume 둘 다 지원
    total_production_volume = safe_int(row.get("monthly_production_volume", row.get("total_production_volume")))

    def format_production(val):
        if val >= 100000000:
            return f"₩{val / 100000000:.1f}억"
        elif val >= 10000:
            return f"₩{val / 10000:.0f}만"
        else:
            return f"₩{val:,}"

    total_work_orders = safe_int(row.get("monthly_orders", row.get("total_work_orders")))
    # avg_yield_rate: 생산량/작업지시수에서 재계산 (데이터 정합성 보장)
    avg_yield_rate = round(total_production_volume / total_work_orders) if total_work_orders > 0 else 0
    defect_return_rate = safe_float(row.get("defect_rate", row.get("defect_return_rate", row.get("return_rate", 0))))
    uptime_rate = safe_float(row.get("equipment_uptime_rate"))

    # 설비 DF에서 이름/카테고리/지역 보완
    equip_name = safe_str(row.get("equipment_name", row.get("shop_name", row.get("name"))))
    equip_category = safe_str(row.get("category"))
    equip_region = safe_str(row.get("region"))
    if (not equip_name or not equip_category) and st.EQUIPMENT_DF is not None:
        eq_id_col = "equipment_id" if "equipment_id" in st.EQUIPMENT_DF.columns else "shop_id"
        eq_row = st.EQUIPMENT_DF[st.EQUIPMENT_DF[eq_id_col] == equipment_id]
        if not eq_row.empty:
            r2 = eq_row.iloc[0]
            equip_name = equip_name or safe_str(r2.get("equipment_name", r2.get("shop_name", r2.get("name"))))
            equip_category = equip_category or safe_str(r2.get("category"))
            equip_region = equip_region or safe_str(r2.get("region"))

    # 데이터 정합성 경고
    data_warnings = []
    if total_work_orders == 0 and safe_float(row.get("oee_rate")) > 0:
        data_warnings.append("작업지시 수 0인데 OEE가 0보다 큼 — 데이터 미집계 가능성")
    if total_production_volume == 0 and total_work_orders > 0:
        data_warnings.append("생산량 0인데 작업지시 수가 0보다 큼 — 생산량 미집계 가능성")

    result = {
        "status": "success",
        "equipment_id": safe_str(row.get(id_col)),
        "name": equip_name,
        "category": equip_category,
        "region": equip_region,
        "performance": {
            "total_production_volume": format_production(total_production_volume),
            "total_production_volume_raw": total_production_volume,
            "total_work_orders": total_work_orders,
            "avg_yield_rate": avg_yield_rate,
            "oee_rate": safe_float(row.get("oee_rate")),
            "defect_return_rate": defect_return_rate,
            "equipment_uptime_rate": uptime_rate,
        },
        "production_tier": _get_production_tier(total_production_volume),
    }
    if data_warnings:
        result["data_warnings"] = data_warnings
        result["_llm_instruction"] = "⚠️ data_warnings를 반드시 사용자에게 전달하세요. 0값 지표는 '데이터 미집계 가능성'을 먼저 언급하세요."
    return result


def tool_optimize_process(
    line_id: str,
    goal: str = "maximize_oee",
    total_budget: float = None,
) -> dict:
    """
    설비/라인의 공정 파라미터를 분석하여 최적의 운영 전략을 제안합니다.
    P-PSO(Phasor Particle Swarm Optimization) 알고리즘 사용.

    Args:
        line_id: 라인 ID
        goal: 최적화 목표 ('maximize_oee', 'maximize_production', 'balanced')
        total_budget: 총 정비 예산 (None이면 라인 수율의 10%로 자동 산정)

    Returns:
        공정별 정비 예산 배분 추천, 예상 ROI, 생산량 예측 (프론트엔드 호환 포맷)
    """
    # 공정 유형 매핑
    PROCESS_TYPE_MAP = {
        "preventive_maintenance": "예방정비",
        "calibration": "교정점검",
        "parts_replacement": "부품교체",
        "lubrication": "윤활급유",
        "sensor_tuning": "센서조정",
        "process_optimization": "공정최적화",
    }

    try:
        # 라인 수율 기반 예산 산정
        if total_budget is None:
            equipment_revenue = 0
            if st.PRODUCTION_LINES_DF is not None:
                _id_col = "line_id" if "line_id" in st.PRODUCTION_LINES_DF.columns else "line_id"
                row = st.PRODUCTION_LINES_DF[st.PRODUCTION_LINES_DF[_id_col] == line_id]
                if not row.empty:
                    equipment_revenue = float(row.iloc[0].get("total_production_volume", 0))
            if st.LINE_ANALYTICS_DF is not None and equipment_revenue == 0:
                _id_col2 = "line_id" if "line_id" in st.LINE_ANALYTICS_DF.columns else "line_id"
                row = st.LINE_ANALYTICS_DF[st.LINE_ANALYTICS_DF[_id_col2] == line_id]
                if not row.empty:
                    equipment_revenue = float(row.iloc[0].get("total_production_volume", 0))
            total_budget = max(500_000, equipment_revenue * 0.1)

        if st.PRODUCTION_OPTIMIZER_AVAILABLE:
            from ml.process_optimizer import ProcessOptimizer
            optimizer = ProcessOptimizer(line_id, total_budget=total_budget, goal=goal)
            result = optimizer.optimize(max_iterations=200)

            if "error" in result:
                return {"status": "error", "message": result["error"]}

            # optimizer allocation → 프론트엔드 recommendations 변환
            recommendations = []
            total_efficiency_gain = 0.0
            for rec in result.get("allocation", []):
                process = rec.get("channel", rec.get("process", ""))
                process_type = PROCESS_TYPE_MAP.get(process, process)
                budget_val = rec.get("budget", 0)
                uplift = rec.get("expected_revenue_uplift", rec.get("expected_production_uplift", 0))
                eff_gain = round(uplift * 100, 1)
                total_efficiency_gain += eff_gain
                eff = rec.get("efficiency_score", 0)
                max_eff = max(r.get("efficiency_score", 1) for r in result.get("allocation", [{"efficiency_score": 1}]))
                norm_eff = eff / max_eff if max_eff > 0 else 0

                recommendations.append({
                    "process": process,
                    "process_name": rec.get("channel_name", process_type),
                    "process_type": process_type,
                    "from_budget": f"₩{int(budget_val * 0.7):,}",
                    "to_budget": f"₩{int(budget_val):,}",
                    "efficiency_gain": eff_gain,
                    "efficiency": round(norm_eff, 3),
                    "cost": {"maintenance_cost": int(budget_val)},
                    "expected_roi": rec.get("expected_roas", rec.get("expected_roi", 0)),
                    "expected_production": rec.get("expected_revenue", rec.get("expected_production", 0)),
                })

            return {
                "status": "success",
                "line_id": line_id,
                "goal": goal,
                "total_efficiency_gain": round(total_efficiency_gain, 1),
                "optimization_method": result.get("optimization_method", "P-PSO"),
                "recommendations": sorted(recommendations, key=lambda x: x["efficiency_gain"], reverse=True),
                "summary": {
                    "total_budget": int(total_budget),
                    "total_expected_production": result.get("total_expected_revenue", result.get("total_expected_production", 0)),
                    "overall_roi": result.get("overall_roas", result.get("overall_roi", 0)),
                },
                "budget_usage": result.get("budget_usage", {}),
            }
        else:
            return {"status": "error", "message": "공정 최적화 모듈이 로드되지 않았습니다."}

    except Exception as e:
        st.logger.exception("공정 최적화 실패")
        return {"status": "error", "message": str(e)}


# ============================================================
# 16. 예지보전(고장 예방) 도구
# ============================================================
def tool_get_at_risk_equipment(threshold: float = 0.6, limit: int = 5) -> dict:
    """고장 위험 설비 목록을 조회합니다."""
    try:
        from automation.predictive_maintenance_engine import get_at_risk_equipment
        results = get_at_risk_equipment(threshold=threshold, limit=limit)
        return {
            "status": "success",
            "total": len(results),
            "threshold": threshold,
            "equipment": results,
        }
    except Exception as e:
        st.logger.exception("고장 위험 설비 조회 실패")
        return {"status": "error", "message": str(e)}


def tool_generate_maintenance_plan(line_id: str, api_key: str = "") -> dict:
    """특정 설비에 대한 정비 계획을 생성합니다."""
    try:
        from automation.predictive_maintenance_engine import generate_maintenance_plan
        result = generate_maintenance_plan(equipment_id=line_id, api_key=api_key)
        if result.get("error"):
            return {"status": "error", "message": result["error"]}
        return {"status": "success", **result}
    except Exception as e:
        st.logger.exception("정비 계획 생성 실패")
        return {"status": "error", "message": str(e)}


def tool_execute_maintenance_action(line_id: str, action_type: str, api_key: str = "") -> dict:
    """정비 조치를 실행합니다 (priority_alert, maintenance_schedule, manager_assign, custom_message)."""
    try:
        from automation.predictive_maintenance_engine import execute_maintenance_action
        result = execute_maintenance_action(equipment_id=line_id, action_type=action_type, api_key=api_key)
        return result
    except Exception as e:
        st.logger.exception("정비 조치 실행 실패")
        return {"status": "error", "message": str(e)}


# ============================================================
# cross-3: @tool 래핑 (LLM Tool Calling용)
# ============================================================
# plain 함수(tool_*)는 routes_*.py에서 직접 호출하므로 그대로 유지.
# 아래 @tool 래핑 버전은 LLM에 바인딩할 때 사용.

import functools
import inspect

def tool(func):
    """OpenAI function-calling 호환 @tool 데코레이터"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)
        return result
    wrapper.name = func.__name__
    wrapper.description = (func.__doc__ or "").strip()
    wrapper._is_tool = True
    # OpenAI function schema 생성
    sig = inspect.signature(func)
    params = {}
    for pname, p in sig.parameters.items():
        ptype = "string"
        if p.annotation == int:
            ptype = "integer"
        elif p.annotation == float:
            ptype = "number"
        elif p.annotation == bool:
            ptype = "boolean"
        params[pname] = {"type": ptype}
    wrapper.openai_schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": wrapper.description,
            "parameters": {
                "type": "object",
                "properties": params,
            },
        },
    }
    return wrapper


# -- 설비 도구 --
@tool
def get_equipment_info(equipment_id: str) -> dict:
    """
    특정 설비의 상세 정보를 조회합니다.

    Args:
        equipment_id: 설비 ID (예: EQP0001, EQP0042)

    Returns:
        설비의 이름, 카테고리, 등급, 지역, 생산 현황 등 상세 정보
    """
    return tool_get_equipment_info(equipment_id)


@tool
def list_equipment(
    category: Optional[str] = None,
    tier: Optional[str] = None,
    region: Optional[str] = None,
) -> dict:
    """
    설비 목록을 조회합니다. 카테고리, 등급, 위치로 필터링할 수 있습니다.

    Args:
        category: 카테고리 필터 (예: CNC, 사출, 프레스, 조립, 용접, 도장)
        tier: 티어 필터 (예: 프리미엄, 스탠다드, 베이직, 엔터프라이즈)
        region: 지역 필터 (예: 국내, 해외, 글로벌)

    Returns:
        필터링된 설비 목록
    """
    return tool_list_equipment(category=category, tier=tier, region=region)


@tool
def get_equipment_services(equipment_id: str) -> dict:
    """
    특정 설비의 연결된 정비 서비스/모듈 정보를 조회합니다.

    Args:
        equipment_id: 설비 ID (예: EQP0001)

    Returns:
        설비에 적용된 정비 서비스, 모듈 목록
    """
    return tool_get_equipment_services(equipment_id)


# -- 카테고리/업종 도구 --
@tool
def get_category_info(category_id: str) -> dict:
    """
    특정 카테고리(업종)의 상세 정보를 조회합니다.

    Args:
        category_id: 카테고리 ID 또는 이름 (예: CAT001, CNC)

    Returns:
        카테고리의 이름, 설명, 소속 설비 수 등
    """
    return tool_get_category_info(category_id)


@tool
def list_categories() -> dict:
    """
    모든 카테고리(업종) 목록을 조회합니다.

    Returns:
        카테고리 목록과 기본 정보
    """
    return tool_list_categories()


# -- 정비 자동배정/품질 도구 --
@tool
def auto_assign_maintenance(
    inquiry_text: str,
    category: str = "general",
) -> dict:
    """
    정비 요청에 대한 자동 배정을 생성합니다.
    스마트팩토리 플랫폼 정책과 제조 용어를 반영합니다.

    Args:
        inquiry_text: 정비 요청 텍스트
        category: 문의 카테고리 (general, equipment, process, quality, maintenance, safety 등)

    Returns:
        자동 생성된 CS 응답 텍스트 및 관련 정책 안내
    """
    return tool_auto_assign_maintenance(inquiry_text, category)


@tool
def check_maintenance_quality(
    ticket_category: str,
    grade: str,
    sentiment_score: float,
    order_value: float,
    is_repeat: bool = False,
    text_length: int = 0,
) -> dict:
    """
    정비 작업 품질을 평가합니다.

    Args:
        ticket_category: 문의 카테고리 (equipment, process, quality, maintenance 등)
        grade: 설비 등급 (프리미엄, 스탠다드, 베이직)
        sentiment_score: 정비 품질 점수 (-1.0 ~ 1.0)
        order_value: 작업 규모
        is_repeat: 반복 문의 여부
        text_length: 응답 텍스트 길이

    Returns:
        품질 등급 (excellent/good/acceptable/needs_review), 우선순위, 권장사항
    """
    return tool_check_maintenance_quality(ticket_category, grade, sentiment_score, order_value, is_repeat, text_length)


@tool
def get_manufacturing_glossary(term: Optional[str] = None) -> dict:
    """
    스마트팩토리 제조 용어집을 조회합니다.

    Args:
        term: 검색할 용어 (선택사항, 예: OEE, MTBF, 예지보전, 불량률 등)
              지정하지 않으면 전체 용어 목록을 반환합니다.

    Returns:
        제조 플랫폼 용어와 설명
    """
    return tool_get_manufacturing_glossary(term=term)


@tool
def get_cs_statistics() -> dict:
    """
    CS 상담 데이터 통계를 조회합니다.

    Returns:
        카테고리별/채널별 CS 통계, 응답 품질 분포, 평균 처리 시간
    """
    return tool_get_cs_statistics()


# -- 설비 분석 도구 --
@tool
def analyze_equipment(line_id: str) -> dict:
    """
    특정 설비의 운영 패턴을 분석합니다.

    Args:
        line_id: 라인 ID (예: FM-LINE1, FM-LINE2)

    Returns:
        설비 클러스터, 운영 지표(작업량, 수율, 불량률, 정비 건수), 이상 여부
    """
    return tool_analyze_equipment(line_id)


@tool
def get_equipment_cluster(line_id: str) -> dict:
    """
    설비 피처를 기반으로 클러스터를 분류합니다.

    Args:
        line_id: 라인 ID (예: FM-LINE1)

    Returns:
        클러스터 분류 결과
    """
    return tool_get_equipment_cluster(line_id)


@tool
def detect_defect(line_id: str) -> dict:
    """
    설비 또는 공정의 결함/불량 여부를 탐지합니다.

    Args:
        line_id: 라인 ID (예: FM-LINE1)

    Returns:
        이상 여부, 이상 점수, 위험 수준, 결함 유형
    """
    return tool_detect_defect(line_id)


@tool
def get_cluster_statistics() -> dict:
    """
    설비 클러스터별 통계를 조회합니다.

    Returns:
        클러스터별 설비 수, 평균 생산량, 평균 가동률, 불량 비율
    """
    return tool_get_cluster_statistics()


@tool
def get_defect_statistics() -> dict:
    """
    전체 결함/불량 탐지 통계를 조회합니다.

    Returns:
        결함 설비 수, 불량 비율, 유형별 분포, 결함 설비 샘플
    """
    return tool_get_defect_statistics()


@tool
def get_equipment_activity_report(line_id: str, days: int = 30) -> dict:
    """
    특정 설비의 활동 리포트를 생성합니다.

    Args:
        line_id: 라인 ID
        days: 조회할 기간 (기본값: 30일)

    Returns:
        활동 요약, 생산/정비/가동 집계
    """
    return tool_get_equipment_activity_report(line_id, days)


# -- 작업지시/운영 도구 --
@tool
def get_order_statistics(event_type: Optional[str] = None, days: int = 30) -> dict:
    """
    운영 이벤트 통계를 조회합니다.

    Args:
        event_type: 이벤트 타입 필터. 가능한 값: work_order_created(작업지시), work_completed(작업완료), rework_processed(재작업), cs_ticket(CS문의), login(로그인), maintenance_campaign(정비캠페인), product_listed(제품등록), product_updated(제품수정). None이면 전체 이벤트.
        days: 조회할 기간 (기본값: 30일)

    Returns:
        이벤트 타입별 집계, 일별 추이
    """
    return tool_get_order_statistics(event_type, days)


# -- 문의 분류 도구 --
@tool
def classify_inquiry(text: str) -> dict:
    """
    CS 문의 텍스트의 카테고리를 분류합니다.

    Args:
        text: 분류할 문의 텍스트

    Returns:
        예측 카테고리 (설비, 공정, 품질, 정비, 안전, 기타 등), 신뢰도, 상위 3개 카테고리
    """
    return tool_classify_inquiry(text)


# -- 대시보드 도구 --
@tool
def get_dashboard_summary() -> dict:
    """
    대시보드 요약 정보를 조회합니다.

    Returns:
        설비/라인/정비/생산/품질 통계 요약
    """
    return tool_get_dashboard_summary()


# -- ML 모델 예측 도구 --
@tool
def predict_equipment_failure(line_id: str) -> dict:
    """
    특정 설비의 고장 확률을 예측합니다.
    ML 모델(LightGBM)과 SHAP Explainer를 사용하여 예측 및 주요 고장 요인을 분석합니다.

    Args:
        line_id: 라인 ID (예: FM-LINE1)

    Returns:
        고장 확률(%), 위험 수준(HIGH/MEDIUM/LOW), 주요 고장 요인, 권장 조치
    """
    return tool_predict_equipment_failure(line_id)


@tool
def predict_production_yield(equipment_id: str) -> dict:
    """
    설비/라인의 운영 데이터를 기반으로 예상 생산량을 예측합니다.
    LightGBM 회귀 모델을 사용합니다.

    Args:
        equipment_id: 설비 ID (예: EQP0001)

    Returns:
        예측 월생산량, 성장률, 주요 생산량 기여 요인 분석
    """
    return tool_predict_production_yield(equipment_id)


@tool
def get_equipment_performance(equipment_id: str) -> dict:
    """
    특정 설비의 현재 운영 데이터를 기반으로 성과를 분석합니다.

    Args:
        equipment_id: 설비 ID (예: EQP0001, EQP0042)

    Returns:
        설비 정보, 실제 생산량, 예측 생산량, 성과 등급, 주요 지표
    """
    return tool_get_equipment_performance(equipment_id)


@tool
def optimize_process(
    line_id: str,
    budget: Optional[float] = None,
    goal: str = "maximize_production",
) -> dict:
    """
    설비/라인의 데이터를 분석하여 최적의 공정 파라미터 전략을 제안합니다.
    P-PSO(Phasor Particle Swarm Optimization) 알고리즘을 사용합니다.

    Args:
        line_id: 라인 ID (예: FM-LINE1)
        budget: 정비 예산 (선택사항, 없으면 현재 예산 기준)
        goal: 최적화 목표
            - maximize_production: 생산량 최대화 (기본값)
            - maximize_oee: OEE 최대화
            - balanced: 균형 잡힌 최적화

    Returns:
        공정 파라미터별 최적화 추천 (최대 10개), 예상 총생산량 증가, 예상 ROI, 필요 예산
    """
    return tool_optimize_process(line_id, goal=goal, total_budget=budget)


# -- 분석 도구 --
@tool
def get_failure_prediction(risk_level: str = None, limit: int = None) -> dict:
    """
    전체 설비의 고장 예측 분석을 조회합니다.
    고위험/중위험/저위험 고장 설비 수와 주요 고장 요인을 반환합니다.

    Args:
        risk_level: 특정 위험 등급만 필터 ("high", "medium", "low")
        limit: 상세 설비 목록 반환 시 최대 개수 (기본값: 10)

    Returns:
        고위험/중위험/저위험 설비 수, 예상 고장률, 주요 고장 요인 5개, 인사이트
    """
    return tool_get_failure_prediction(risk_level=risk_level, limit=limit)


@tool
def get_lifecycle_analysis(month: str = None) -> dict:
    """
    설비 라이프사이클 분석을 조회합니다.
    월별 코호트의 Week1/Week2/Week4/Week8/Week12 가동율을 반환합니다.

    Args:
        month: 특정 월 필터 (예: "2024-11", "2024-07"). 미지정 시 전체 코호트 반환.

    Returns:
        코호트별 주차 리텐션율, 전체 평균 리텐션, 인사이트
    """
    return tool_get_lifecycle_analysis(month=month)


@tool
def get_production_trend(start_date: str = None, end_date: str = None, days: int = None) -> dict:
    """
    **플랫폼 전체** 생산 트렌드 KPI 분석을 조회합니다. (특정 설비가 아닌 스마트팩토리 플랫폼 전체 데이터)
    주요 지표(활성 설비 수, OEE, 신규 도입, 생산량 등)의 변화율과 상관관계를 반환합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)
        days: 최근 N일 분석 (기본값: 7일)

    Returns:
        KPI별 현재/이전 값, 변화율, 주요 상관관계, 인사이트
    """
    return tool_get_production_trend(start_date=start_date, end_date=end_date, days=days)


@tool
def get_oee_prediction(days: int = None, start_date: str = None, end_date: str = None) -> dict:
    """
    OEE(종합설비효율) 예측 분석을 조회합니다.
    예상 OEE, 생산성 지표, 설비 등급별 생산 분포를 반환합니다.

    Args:
        days: 최근 N일 기준 분석 (기본값: 30일)
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)

    Returns:
        예상 월간 생산량, 성장률, 설비별 출력, 등급별 생산 분포, 인사이트
    """
    return tool_get_oee_prediction(days=days, start_date=start_date, end_date=end_date)


# -- 예지보전(고장 예방) 도구 --
@tool
def get_at_risk_equipment(threshold: float = 0.6, limit: int = 5) -> dict:
    """
    고장 위험이 높은 설비 목록을 조회합니다.
    ML 고장 예측 모델과 SHAP 분석으로 위험 설비를 탐지합니다.

    Args:
        threshold: 고장 확률 임계값 (0.0~1.0, 기본값 0.6)
        limit: 최대 반환 설비 수 (기본값 5)

    Returns:
        고장 위험 설비 목록 (고장 확률, 위험 등급, 주요 고장 요인)
    """
    return tool_get_at_risk_equipment(threshold=threshold, limit=limit)


@tool
def generate_maintenance_plan(line_id: str, api_key: str = "") -> dict:
    """
    특정 설비에 대한 정비 계획을 LLM으로 생성합니다.
    예방 정비, 부품 교체, 전담 엔지니어 배정 등 추천 포함.

    Args:
        line_id: 라인 ID (예: FM-LINE1)
        api_key: OpenAI API 키 (선택사항, 미지정 시 환경변수 사용)

    Returns:
        정비 계획, 추천 조치 목록, 긴급도
    """
    return tool_generate_maintenance_plan(line_id=line_id, api_key=api_key)


@tool
def execute_maintenance_action(line_id: str, action_type: str, api_key: str = "") -> dict:
    """
    정비 조치를 실행합니다.

    Args:
        line_id: 라인 ID (예: FM-LINE1)
        action_type: 조치 유형 ("priority_alert", "maintenance_schedule", "manager_assign", "custom_message")
        api_key: OpenAI API 키 (선택사항, custom_message 시 필요)

    Returns:
        조치 실행 결과 (action_id, 상세 내역)
    """
    return tool_execute_maintenance_action(line_id=line_id, action_type=action_type, api_key=api_key)


# ============================================================
# 데이터 통계 분석 도구
# ============================================================

# 분석 가능한 DataFrame 매핑
_ANALYSIS_DF_MAP = {
    "equipment": "EQUIPMENT_DF",
    "equipment_types": "EQUIPMENT_TYPES_DF",
    "production_lines": "PRODUCTION_LINES_DF",
    "line_analytics": "LINE_ANALYTICS_DF",
    "products": "PRODUCTS_DF",
    "operation_logs": "OPERATION_LOGS_DF",
    "maintenance_stats": "MAINTENANCE_STATS_DF",
    "daily_production": "DAILY_PRODUCTION_DF",
    "equipment_performance": "EQUIPMENT_PERFORMANCE_DF",
    "equipment_activity": "EQUIPMENT_ACTIVITY_DF",
    "defect_details": "DEFECT_DETAILS_DF",
    "equipment_lifecycle": "EQUIPMENT_LIFECYCLE_DF",
    "production_funnel": "PRODUCTION_FUNNEL_DF",
}


def _get_analysis_df(name: str):
    """DataFrame 이름으로 실제 객체 반환"""
    attr = _ANALYSIS_DF_MAP.get(name)
    if not attr:
        return None
    return getattr(st, attr, None)


def tool_analyze_data(
    dataframe: str,
    operation: str,
    column: str = "",
    group_by: str = "",
    filter_column: str = "",
    filter_value: str = "",
    top_n: int = 10,
    ascending: bool = False,
) -> dict:
    """데이터프레임에 대해 통계 분석을 수행합니다."""

    df = _get_analysis_df(dataframe)
    if df is None:
        available = [k for k, v in _ANALYSIS_DF_MAP.items() if getattr(st, v, None) is not None]
        return {"status": "error", "message": f"'{dataframe}' 없음. 사용 가능: {available}"}

    # 필터 적용
    if filter_column and filter_value and filter_column in df.columns:
        df = df[df[filter_column].astype(str).str.contains(filter_value, case=False, na=False)]
        if df.empty:
            return {"status": "error", "message": f"필터 결과 없음: {filter_column}='{filter_value}'"}

    try:
        # describe: 기술 통계
        if operation == "describe":
            if column and column in df.columns:
                desc = df[column].describe()
            else:
                desc = df.describe(include="all")
            result = {str(k): round(v, 4) if isinstance(v, float) else v for k, v in desc.to_dict().items()} if isinstance(desc, pd.Series) else {col: {str(k): round(v, 4) if isinstance(v, float) else v for k, v in vals.items()} for col, vals in desc.to_dict().items()}
            return {"status": "success", "operation": "describe", "dataframe": dataframe, "rows": len(df), "columns": list(df.columns), "result": result}

        # value_counts: 고유값 빈도 (상위 top_n개)
        elif operation == "value_counts":
            if not column or column not in df.columns:
                return {"status": "error", "message": f"column 필요. 사용 가능: {list(df.columns)}"}
            vc = df[column].value_counts().head(top_n)
            total = len(df)
            result = [{"value": str(k), "count": int(v), "ratio": f"{v/total*100:.1f}%"} for k, v in vc.items()]
            return {"status": "success", "operation": "value_counts", "column": column, "total_rows": total, "unique_count": df[column].nunique(), "top_n": result}

        # groupby_agg: 그룹별 집계 (mean, sum, count, min, max)
        elif operation.startswith("groupby_"):
            agg_func = operation.replace("groupby_", "")
            if agg_func not in ("mean", "sum", "count", "min", "max", "median"):
                return {"status": "error", "message": f"지원 집계: mean, sum, count, min, max, median"}
            if not group_by or group_by not in df.columns:
                return {"status": "error", "message": f"group_by 필요. 사용 가능: {list(df.columns)}"}
            if not column or column not in df.columns:
                # count는 column 없어도 가능
                if agg_func == "count":
                    grp = df.groupby(group_by).size().reset_index(name="count")
                else:
                    return {"status": "error", "message": f"column 필요. 사용 가능: {list(df.columns)}"}
            else:
                grp = df.groupby(group_by)[column].agg(agg_func).reset_index()
                grp.columns = [group_by, f"{column}_{agg_func}"]

            grp = grp.sort_values(grp.columns[-1], ascending=ascending).head(top_n)
            result = grp.to_dict("records")
            # float 반올림
            for r in result:
                for k, v in r.items():
                    if isinstance(v, float):
                        r[k] = round(v, 2)
            return {"status": "success", "operation": operation, "group_by": group_by, "column": column, "result": result}

        # top_n / bottom_n: 상위/하위 N개
        elif operation in ("top_n", "bottom_n"):
            if not column or column not in df.columns:
                return {"status": "error", "message": f"column 필요. 사용 가능: {list(df.columns)}"}
            numeric_col = pd.to_numeric(df[column], errors="coerce")
            if operation == "top_n":
                idx = numeric_col.nlargest(top_n).index
            else:
                idx = numeric_col.nsmallest(top_n).index
            # 핵심 컬럼만 반환 (최대 6개)
            display_cols = [c for c in df.columns if c != column][:5]
            display_cols = [column] + display_cols
            result = df.loc[idx, display_cols].to_dict("records")
            for r in result:
                for k, v in r.items():
                    if isinstance(v, float):
                        r[k] = round(v, 2)
            return {"status": "success", "operation": operation, "column": column, "count": len(result), "result": result}

        # correlation: 수치형 컬럼 간 상관관계
        elif operation == "correlation":
            numeric_df = df.select_dtypes(include="number")
            if column and column in numeric_df.columns:
                corr = numeric_df.corr()[column].drop(column).sort_values(key=abs, ascending=False).head(top_n)
                result = [{"column": k, "correlation": round(v, 3)} for k, v in corr.items()]
            else:
                corr = numeric_df.corr()
                # 상위 상관관계 쌍 추출
                pairs = []
                for i, c1 in enumerate(corr.columns):
                    for c2 in corr.columns[i+1:]:
                        pairs.append({"col1": c1, "col2": c2, "correlation": round(corr.loc[c1, c2], 3)})
                pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
                result = pairs[:top_n]
            return {"status": "success", "operation": "correlation", "result": result}

        # percentile: 분위수 분포
        elif operation == "percentile":
            if not column or column not in df.columns:
                return {"status": "error", "message": f"column 필요. 사용 가능: {list(df.columns)}"}
            numeric_col = pd.to_numeric(df[column], errors="coerce").dropna()
            result = {
                "count": int(len(numeric_col)),
                "mean": round(float(numeric_col.mean()), 2),
                "std": round(float(numeric_col.std()), 2),
                "min": round(float(numeric_col.min()), 2),
                "25%": round(float(numeric_col.quantile(0.25)), 2),
                "50%": round(float(numeric_col.quantile(0.50)), 2),
                "75%": round(float(numeric_col.quantile(0.75)), 2),
                "max": round(float(numeric_col.max()), 2),
            }
            return {"status": "success", "operation": "percentile", "column": column, "result": result}

        # trend: 시계열 추세 요약
        elif operation == "trend":
            date_col = None
            for c in ["date", "created_at", "timestamp", "event_date"]:
                if c in df.columns:
                    date_col = c
                    break
            if not date_col:
                return {"status": "error", "message": "날짜 컬럼을 찾을 수 없음"}
            df_copy = df.copy()
            df_copy[date_col] = pd.to_datetime(df_copy[date_col], errors="coerce")
            df_copy = df_copy.dropna(subset=[date_col]).sort_values(date_col)

            if column and column in df_copy.columns:
                # 수치 컬럼의 일별 집계
                daily = df_copy.groupby(df_copy[date_col].dt.date)[column].mean()
            else:
                # 일별 건수
                daily = df_copy.groupby(df_copy[date_col].dt.date).size()

            if len(daily) < 2:
                return {"status": "error", "message": "추세 분석에 충분한 데이터 없음"}

            half = len(daily) // 2
            first_half = daily.iloc[:half].mean()
            second_half = daily.iloc[half:].mean()
            change_pct = ((second_half - first_half) / first_half * 100) if first_half != 0 else 0

            result = {
                "period": f"{daily.index[0]} ~ {daily.index[-1]}",
                "total_days": len(daily),
                "daily_mean": round(float(daily.mean()), 2),
                "daily_min": {"date": str(daily.idxmin()), "value": round(float(daily.min()), 2)},
                "daily_max": {"date": str(daily.idxmax()), "value": round(float(daily.max()), 2)},
                "first_half_avg": round(float(first_half), 2),
                "second_half_avg": round(float(second_half), 2),
                "trend_change": f"{change_pct:+.1f}%",
                "trend_direction": "상승" if change_pct > 5 else "하락" if change_pct < -5 else "안정",
                "recent_7": [{"date": str(d), "value": round(float(v), 2)} for d, v in daily.tail(7).items()],
            }
            return {"status": "success", "operation": "trend", "column": column or "건수", "result": result}

        # compare: 두 그룹 비교
        elif operation == "compare":
            if not group_by or group_by not in df.columns:
                return {"status": "error", "message": f"group_by 필요. 사용 가능: {list(df.columns)}"}
            numeric_cols = [c for c in df.select_dtypes(include="number").columns if c != group_by][:8]
            comparison = []
            for grp_val, grp_df in df.groupby(group_by):
                stats = {"group": str(grp_val), "count": len(grp_df)}
                for c in numeric_cols:
                    stats[f"{c}_mean"] = round(float(grp_df[c].mean()), 2)
                comparison.append(stats)
            comparison.sort(key=lambda x: x["count"], reverse=True)
            return {"status": "success", "operation": "compare", "group_by": group_by, "groups": len(comparison), "result": comparison[:top_n]}

        # columns: 컬럼 목록 조회
        elif operation == "columns":
            col_info = []
            for c in df.columns:
                info = {"name": c, "dtype": str(df[c].dtype), "non_null": int(df[c].notna().sum()), "unique": int(df[c].nunique())}
                if df[c].dtype in ("int32", "int64", "float32", "float64"):
                    info["min"] = round(float(df[c].min()), 2)
                    info["max"] = round(float(df[c].max()), 2)
                elif df[c].dtype == "object" or str(df[c].dtype) == "category":
                    info["sample_values"] = [str(v) for v in df[c].dropna().unique()[:5]]
                col_info.append(info)
            return {"status": "success", "operation": "columns", "dataframe": dataframe, "rows": len(df), "columns": col_info}

        else:
            return {"status": "error", "message": f"지원 operation: describe, value_counts, groupby_mean, groupby_sum, groupby_count, top_n, bottom_n, correlation, percentile, trend, compare, columns"}

    except Exception as e:
        return {"status": "error", "message": f"분석 실패: {str(e)}"}


@tool
def analyze_data(
    dataframe: str,
    operation: str,
    column: str = "",
    group_by: str = "",
    filter_column: str = "",
    filter_value: str = "",
    top_n: int = 10,
    ascending: bool = False,
) -> str:
    """데이터프레임에 대해 통계 분석(정렬·필터·집계·비교·추세)을 수행합니다.
    직접 수치를 계산하므로 정확한 통계 결과를 얻을 수 있습니다.

    Args:
        dataframe: 분석할 데이터 (equipment, equipment_types, production_lines, line_analytics, products, operation_logs, maintenance_stats, daily_production, equipment_performance, equipment_activity, defect_details, equipment_lifecycle, production_funnel)
        operation: 분석 유형
            - columns: 컬럼 목록·타입·샘플값 조회
            - describe: 기술 통계 (평균, 표준편차, 최소, 최대 등)
            - value_counts: 고유값 빈도 및 비율
            - groupby_mean / groupby_sum / groupby_count / groupby_max / groupby_min: 그룹별 집계
            - top_n / bottom_n: 상위/하위 N개 추출
            - correlation: 수치형 컬럼 간 상관관계
            - percentile: 분위수 분포 (25%, 50%, 75%)
            - trend: 시계열 추세 요약 (일별 평균, 최고/최저일, 추세 방향)
            - compare: 그룹 간 수치 비교
        column: 분석 대상 컬럼
        group_by: 그룹화 기준 컬럼
        filter_column: 필터링할 컬럼
        filter_value: 필터 값 (부분 일치)
        top_n: 결과 개수 (기본 10)
        ascending: 오름차순 정렬 여부 (기본 False = 내림차순)

    Returns:
        계산된 통계 결과 (정확한 수치)
    """
    return json.dumps(
        tool_analyze_data(
            dataframe=dataframe,
            operation=operation,
            column=column,
            group_by=group_by,
            filter_column=filter_column,
            filter_value=filter_value,
            top_n=top_n,
            ascending=ascending,
        ),
        ensure_ascii=False,
    )


# ============================================================
# 추가 별칭 (다른 도메인 이름으로도 접근 가능)
# ============================================================

# @tool 래핑 함수 별칭 (다른 모듈에서 대체 이름으로 import 시)
get_process_type_info = get_category_info
list_process_types = list_categories
get_maintenance_statistics = get_cs_statistics
get_equipment_cluster_statistics = get_cluster_statistics
get_production_event_statistics = get_order_statistics
classify_fault = classify_inquiry
# plain 함수 별칭 (하위 호환)

# ============================================================
# 에이전트별 도구 분류
# ============================================================

# 예지보전 에이전트 도구: 고장 예방, 정비 계획, 자동 조치
MAINTENANCE_AGENT_TOOLS = [
    get_at_risk_equipment,
    get_maintenance_statistics,
    generate_maintenance_plan,    # 정비 계획 생성
    execute_maintenance_action,   # 정비 자동 조치 실행
]

# 하위 호환성 유지
RETENTION_AGENT_TOOLS = MAINTENANCE_AGENT_TOOLS

# ============================================================
# 모든 도구 리스트 (LLM에 바인딩할 때 사용)
# ============================================================
ALL_TOOLS = [
    # 설비 정보
    get_equipment_info,
    list_equipment,
    get_equipment_services,
    # 공정유형 정보
    get_process_type_info,
    list_process_types,
    # 정비 (자동배정/품질)
    auto_assign_maintenance,
    check_maintenance_quality,
    get_manufacturing_glossary,
    get_maintenance_statistics,
    # 설비 분석
    analyze_equipment,
    get_equipment_cluster,
    detect_defect,
    get_equipment_cluster_statistics,
    get_defect_statistics,
    get_equipment_activity_report,
    # 생산/운영 이벤트
    get_production_event_statistics,
    # 고장 분류
    classify_fault,
    # 대시보드
    get_dashboard_summary,
    # ML 모델 예측
    predict_equipment_failure,
    predict_production_yield,
    get_equipment_performance,
    optimize_process,
    # 분석 도구
    get_failure_prediction,
    get_lifecycle_analysis,
    get_production_trend,
    get_oee_prediction,
    # 예지보전(고장 예방) 도구
    get_at_risk_equipment,
    generate_maintenance_plan,
    execute_maintenance_action,
    # 통계 분석 도구
    analyze_data,
]
