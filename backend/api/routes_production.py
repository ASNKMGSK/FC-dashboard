"""
api/routes_production.py - 생산라인/작업자 관련 API
"""
import pandas as pd
from fastapi import APIRouter, Depends

from core.utils import safe_str, json_sanitize
from agent.tools import (
    tool_analyze_equipment,
    tool_get_equipment_cluster,
    tool_detect_defect,
    tool_get_cluster_statistics,
    tool_get_equipment_activity_report,
)
import state as st
from api.common import verify_credentials, error_response


router = APIRouter(prefix="/api", tags=["production"])


@router.get("/production-lines/autocomplete")
def production_lines_autocomplete(q: str = "", limit: int = 8, user: dict = Depends(verify_credentials)):
    if st.PRODUCTION_LINES_DF is None:
        return error_response("생산라인 데이터 없음")
    q = q.strip().upper()
    if not q:
        return {"status": "success", "users": []}
    df = st.PRODUCTION_LINES_DF
    id_col = "line_id" if "line_id" in df.columns else "line_id"
    mask = df[id_col].str.upper().str.contains(q, na=False)
    _name_col = "line_name" if "line_name" in df.columns else ("equipment_name" if "equipment_name" in df.columns else ("shop_name" if "shop_name" in df.columns else None))
    if _name_col:
        mask |= df[_name_col].str.upper().str.contains(q, na=False)
    matched = df[mask].head(limit)
    users = [{"id": r[id_col], "name": r[id_col]} for r in matched[[id_col]].to_dict("records")]
    return {"status": "success", "users": users}


@router.get("/production-lines/analyze/{line_id}")
def analyze_production_line(line_id: str, user: dict = Depends(verify_credentials)):
    return tool_analyze_equipment(line_id)


@router.post("/production-lines/segment")
def get_production_line_segment(equipment_features: dict, user: dict = Depends(verify_credentials)):
    return tool_get_equipment_cluster(equipment_features)


@router.post("/production-lines/defect")
def detect_production_defect(equipment_features: dict, user: dict = Depends(verify_credentials)):
    return tool_detect_defect(transaction_features=equipment_features)


@router.get("/production-lines/segments/statistics")
def get_segment_stats(user: dict = Depends(verify_credentials)):
    return tool_get_cluster_statistics()


@router.get("/users/segments/{segment_name}/details")
def get_segment_details(segment_name: str, user: dict = Depends(verify_credentials)):
    try:
        if st.LINE_ANALYTICS_DF is None:
            return error_response("생산라인 분석 데이터 없음")
        df = st.LINE_ANALYTICS_DF
        if "segment_name" in df.columns:
            seg = df[df["segment_name"] == segment_name]
        else:
            return error_response(f"알 수 없는 세그먼트: {segment_name}")
        total = len(df)
        count = len(seg)
        return json_sanitize({
            "status": "success", "segment": segment_name, "count": count,
            "percentage": round(count / max(total, 1) * 100, 1),
            "avg_monthly_yield": int(seg["total_revenue"].mean()) if "total_revenue" in seg.columns else 0,
            "avg_equipment_count": int(seg["product_count"].mean()) if "product_count" in seg.columns else 0,
            "avg_work_order_count": int(seg["total_orders"].mean()) if "total_orders" in seg.columns else 0,
            "top_activities": [], "uptime_rate": None,
        })
    except Exception as e:
        return error_response(safe_str(e))


@router.get("/production-lines/{line_id}/activity")
def get_production_line_activity(line_id: str, days: int = 30, user: dict = Depends(verify_credentials)):
    return tool_get_equipment_activity_report(line_id, days)


@router.get("/production-lines/performance")
def get_production_lines_performance(user: dict = Depends(verify_credentials)):
    try:
        if st.PRODUCTION_LINES_DF is None or st.PRODUCTION_LINES_DF.empty:
            return error_response("생산라인 데이터 없음")
        _id_col = "line_id" if "line_id" in st.PRODUCTION_LINES_DF.columns else "line_id"
        cols = [_id_col, "grade" if "grade" in st.PRODUCTION_LINES_DF.columns else "plan_tier", "segment"]
        available_cols = [c for c in cols if c in st.PRODUCTION_LINES_DF.columns]
        top100 = st.PRODUCTION_LINES_DF.head(100)
        lines = [
            {"id": r.get(_id_col, ""), "name": r.get(_id_col, ""), "grade": r.get("grade", r.get("plan_tier", "Standard")), "segment": r.get("segment", "알 수 없음")}
            for r in top100[available_cols].to_dict("records")
        ]
        return {"status": "success", "equipment": lines}
    except Exception as e:
        st.logger.error(f"생산라인 목록 조회 오류: {e}")
        return error_response(str(e))
