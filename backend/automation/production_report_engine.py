"""
automation/production_report_engine.py - 생산/OEE 리포트 자동 생성 엔진
=====================================================
생산 데이터 집계 → LLM 리포트 자동 작성
KPI: 생산량, 불량률, 가동률, OEE, MTBF, MTTR, 사이클타임
"""
import time
import uuid
from typing import Dict, Any

import pandas as pd
from core.utils import safe_str, safe_int, safe_float
import state as st
from automation.action_logger import save_report, get_report_history, log_action, create_pipeline_run, update_pipeline_step, complete_pipeline_run


# -- 리포트 타입별 라벨 --
_REPORT_TYPE_LABELS = {
    "daily": "일간",
    "weekly": "주간",
    "monthly": "월간",
}


def collect_report_data() -> Dict[str, Any]:
    """모든 주요 DF에서 생산 KPI를 수집합니다."""
    kpi: Dict[str, Any] = {}
    trends: Dict[str, Any] = {}
    segments: Dict[str, Any] = {}
    maintenance_summary: Dict[str, Any] = {}

    # -- DAILY_METRICS_DF: 생산량, 가동률, OEE --
    df = st.DAILY_PRODUCTION_DF
    if df is not None and not df.empty:
        date_col = None
        for c in ("date", "날짜", "dt"):
            if c in df.columns:
                date_col = c
                break

        df_sorted = df.copy()
        if date_col:
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
            df_sorted = df_sorted.sort_values(date_col, ascending=False)

        recent_7 = df_sorted.head(7) if len(df_sorted) >= 7 else df_sorted
        recent_30 = df_sorted.head(30) if len(df_sorted) >= 30 else df_sorted

        for col in ("gmv", "active_equipment", "orders", "new_signups"):
            if col in df_sorted.columns:
                kpi[f"{col}_latest"] = safe_float(df_sorted[col].iloc[0]) if len(df_sorted) > 0 else 0
                kpi[f"{col}_7d_avg"] = round(safe_float(recent_7[col].mean()), 2)
                kpi[f"{col}_30d_avg"] = round(safe_float(recent_30[col].mean()), 2)

        # 트렌드: 7일 vs 이전 7일 비교
        if len(df_sorted) >= 14:
            prev_7 = df_sorted.iloc[7:14]
            for col in ("gmv", "active_equipment", "orders", "new_signups"):
                if col in df_sorted.columns:
                    cur = safe_float(recent_7[col].mean())
                    prev = safe_float(prev_7[col].mean())
                    if prev > 0:
                        trends[f"{col}_wow_change_pct"] = round((cur - prev) / prev * 100, 2)
                    else:
                        trends[f"{col}_wow_change_pct"] = 0.0

    # -- EQUIPMENT_DF: 총 설비 수, 라인별 분포 --
    df = st.EQUIPMENT_DF
    if df is not None and not df.empty:
        kpi["total_equipment"] = len(df)
        if "plan_tier" in df.columns:
            kpi["equipment_by_line"] = df["plan_tier"].value_counts().to_dict()

    # -- LINE_ANALYTICS_DF: 생산라인 수, 세그먼트 분포 --
    production_df = st.LINE_ANALYTICS_DF
    if production_df is not None and not production_df.empty:
        kpi["total_production_lines"] = len(production_df)
        if "cluster" in production_df.columns:
            segments["line_segments"] = production_df["cluster"].value_counts().to_dict()
        if "is_anomaly" in production_df.columns:
            kpi["anomaly_lines"] = int(production_df["is_anomaly"].sum())
    elif st.PRODUCTION_LINES_DF is not None and not st.PRODUCTION_LINES_DF.empty:
        kpi["total_production_lines"] = len(st.PRODUCTION_LINES_DF)
        if "plan_tier" in st.PRODUCTION_LINES_DF.columns:
            segments["lines_by_type"] = st.PRODUCTION_LINES_DF["plan_tier"].value_counts().to_dict()

    # -- CS_STATS_DF: 정비 요청 건수, 카테고리별 분포 --
    df = st.MAINTENANCE_STATS_DF
    if df is not None and not df.empty:
        if "total_tickets" in df.columns:
            maintenance_summary["total_maintenance_requests"] = safe_int(df["total_tickets"].sum())
        else:
            maintenance_summary["total_maintenance_requests"] = len(df)

        if "satisfaction_score" in df.columns:
            maintenance_summary["avg_completion_score"] = round(safe_float(df["satisfaction_score"].mean()), 2)

        if "avg_resolution_hours" in df.columns:
            maintenance_summary["avg_repair_hours"] = round(safe_float(df["avg_resolution_hours"].mean()), 1)

        cat_col = "category" if "category" in df.columns else "ticket_category"
        if cat_col in df.columns and "total_tickets" in df.columns:
            maintenance_summary["by_failure_type"] = {
                safe_str(row[cat_col]): safe_int(row["total_tickets"])
                for _, row in df.iterrows()
            }
        elif cat_col in df.columns:
            maintenance_summary["by_failure_type"] = df[cat_col].value_counts().to_dict()

    # -- DEFECT_DETAILS_DF: 불량 건수 --
    df = st.DEFECT_DETAILS_DF
    if df is not None and not df.empty:
        kpi["defect_total"] = len(df)
        if "defect_type" in df.columns:
            kpi["defect_by_type"] = df["defect_type"].value_counts().to_dict()
        elif "fraud_type" in df.columns:
            kpi["defect_by_type"] = df["fraud_type"].value_counts().to_dict()

    # -- EQUIPMENT_LIFECYCLE_DF: 설비 가동률 추이 --
    df = st.EQUIPMENT_LIFECYCLE_DF
    if df is not None and not df.empty:
        cohort_col = None
        for c in ("cohort", "cohort_month", "cohort_date"):
            if c in df.columns:
                cohort_col = c
                break
        if cohort_col:
            latest_cohort = df[cohort_col].max()
            latest_rows = df[df[cohort_col] == latest_cohort]
            availability_cols = [c for c in df.columns if c.startswith("month_") or c.startswith("m")]
            if availability_cols:
                kpi["latest_period"] = safe_str(latest_cohort)
                kpi["availability_trend"] = {
                    c: round(safe_float(latest_rows[c].mean()), 2) for c in availability_cols
                }

    return {
        "kpi": kpi,
        "trends": trends,
        "segments": segments,
        "maintenance_summary": maintenance_summary,
        "collected_at": time.time(),
    }


def _build_report_content(type_label: str, data: dict) -> str:
    """KPI 데이터를 기반으로 템플릿 리포트를 생성합니다."""
    kpi = data.get("kpi", {})
    trends = data.get("trends", {})
    segments = data.get("segments", {})
    maintenance = data.get("maintenance_summary", {})

    content = f"# {type_label} 생산/OEE 리포트\n\n"

    # 1. 핵심 지표 요약
    content += "## 핵심 지표 요약\n\n"
    if kpi.get("total_equipment"):
        content += f"- 총 설비 수: {kpi['total_equipment']:,}대\n"
    if kpi.get("total_production_lines"):
        content += f"- 생산라인 수: {kpi['total_production_lines']:,}개\n"
    if kpi.get("gmv_latest") is not None:
        content += f"- 최근 GMV: {kpi['gmv_latest']:,.0f}\n"
    if kpi.get("gmv_7d_avg") is not None:
        content += f"- 7일 평균 GMV: {kpi['gmv_7d_avg']:,.0f}\n"
    if kpi.get("active_equipment_latest") is not None:
        content += f"- 최근 가동 설비: {kpi['active_equipment_latest']:,.0f}대\n"
    if kpi.get("orders_latest") is not None:
        content += f"- 최근 주문: {kpi['orders_latest']:,.0f}건\n"
    if kpi.get("defect_total") is not None:
        content += f"- 불량 총건수: {kpi['defect_total']:,}건\n"
    if kpi.get("anomaly_lines") is not None:
        content += f"- 이상 감지 라인: {kpi['anomaly_lines']}개\n"
    content += "\n"

    # 2. 주요 변화 및 트렌드
    if trends:
        content += "## 주요 변화 및 트렌드\n\n"
        trend_labels = {
            "gmv_wow_change_pct": "GMV",
            "active_equipment_wow_change_pct": "가동 설비",
            "orders_wow_change_pct": "주문",
            "new_signups_wow_change_pct": "신규 등록",
        }
        for key, label in trend_labels.items():
            if key in trends:
                val = trends[key]
                direction = "증가" if val > 0 else "감소" if val < 0 else "변동 없음"
                content += f"- {label}: 전주 대비 {abs(val):.1f}% {direction}\n"
        content += "\n"

    # 3. 이슈 & 주의사항
    issues = []
    if kpi.get("anomaly_lines", 0) > 0:
        issues.append(f"이상 감지 라인 {kpi['anomaly_lines']}개 — 점검 필요")
    if kpi.get("defect_total", 0) > 0:
        issues.append(f"불량 {kpi['defect_total']:,}건 발생")
    for key in trends:
        if trends[key] < -10:
            label = key.replace("_wow_change_pct", "")
            issues.append(f"{label} 지표 {abs(trends[key]):.1f}% 하락 — 주의 필요")
    if maintenance.get("total_maintenance_requests", 0) > 0:
        issues.append(f"정비 요청 {maintenance['total_maintenance_requests']:,}건 접수")

    if issues:
        content += "## 이슈 & 주의사항\n\n"
        for issue in issues:
            content += f"- {issue}\n"
        content += "\n"

    # 4. 권장 조치사항
    content += "## 권장 조치사항\n\n"
    if kpi.get("anomaly_lines", 0) > 0:
        content += "- 이상 감지 라인에 대한 즉시 점검 및 원인 분석 실시\n"
    if kpi.get("defect_total", 0) > 50:
        content += "- 불량률 집중 관리 및 품질 개선 활동 강화\n"
    if maintenance.get("avg_repair_hours", 0) > 24:
        content += f"- 평균 수리 시간({maintenance['avg_repair_hours']:.1f}시간) 단축 방안 마련\n"
    content += "- 정기 설비 점검 스케줄 준수 확인\n"
    content += "- KPI 모니터링 대시보드 주기적 확인\n"

    return content


def generate_report(report_type: str = "daily") -> Dict[str, Any]:
    """KPI 데이터 기반 템플릿으로 생산/OEE 리포트를 자동 생성합니다."""
    report_id = str(uuid.uuid4())[:8]
    type_label = _REPORT_TYPE_LABELS.get(report_type, report_type)
    run_id = create_pipeline_run("production_report", ["collect", "aggregate", "write", "save"])
    update_pipeline_step(run_id, "collect", "processing")

    try:
        # 데이터 수집
        data = collect_report_data()

        update_pipeline_step(run_id, "collect", "complete", {"kpi_count": len(data.get("kpi", {}))})
        update_pipeline_step(run_id, "aggregate", "complete", {"trends": len(data.get("trends", {}))})
        update_pipeline_step(run_id, "write", "processing")

        # 템플릿 기반 리포트 생성
        content = _build_report_content(type_label, data)

        update_pipeline_step(run_id, "write", "complete")
        update_pipeline_step(run_id, "save", "processing")

        result = {
            "report_id": report_id,
            "report_type": report_type,
            "content": content,
            "data_summary": data,
            "timestamp": time.time(),
            "pipeline_run_id": run_id,
        }

        # 히스토리 저장
        save_report(result)
        log_action("production_report_generate", report_id, {
            "report_type": report_type,
            "kpi_keys": list(data.get("kpi", {}).keys()),
        })

        update_pipeline_step(run_id, "save", "complete")
        complete_pipeline_run(run_id)

        st.logger.info("PRODUCTION_REPORT_GENERATED id=%s type=%s", report_id, report_type)
        return result

    except Exception as e:
        if run_id:
            update_pipeline_step(run_id, "write", "error", {"error": safe_str(e)})
        st.logger.error("PRODUCTION_REPORT_FAIL id=%s err=%s", report_id, safe_str(e))
        log_action("production_report_generate", report_id, {
            "report_type": report_type,
            "error": safe_str(e),
        }, status="error")
        return {
            "report_id": report_id,
            "report_type": report_type,
            "content": f"# {type_label} 생산 리포트 생성 실패\n\n오류: {safe_str(e)}",
            "data_summary": {},
            "timestamp": time.time(),
            "error": safe_str(e),
        }


async def generate_report_stream(report_type: str = "daily"):
    """템플릿 기반 생산/OEE 리포트를 섹션별로 SSE 스트리밍합니다."""
    import asyncio

    report_id = str(uuid.uuid4())[:8]
    type_label = _REPORT_TYPE_LABELS.get(report_type, report_type)
    start_time = time.time()

    try:
        # 1단계: 데이터 수집
        yield {"event": "step_start", "data": {"step": "collect", "description": "생산 데이터 수집 시작", "timestamp": time.time()}}
        await asyncio.sleep(0)

        data = collect_report_data()

        collect_elapsed = int((time.time() - start_time) * 1000)
        yield {"event": "step_end", "data": {"step": "collect", "elapsed_ms": collect_elapsed, "result_count": len(data.get("kpi", {}))}}

        # 2단계: KPI 집계
        yield {"event": "step_start", "data": {"step": "aggregate", "description": "KPI 집계 및 트렌드 분석", "timestamp": time.time()}}
        await asyncio.sleep(0)

        aggregate_elapsed = int((time.time() - start_time) * 1000)
        yield {"event": "step_end", "data": {"step": "aggregate", "elapsed_ms": aggregate_elapsed, "result_count": len(data.get("trends", {}))}}

        # 3단계: 템플릿 기반 리포트 생성
        yield {"event": "step_start", "data": {"step": "write", "description": "리포트 섹션 생성 시작", "timestamp": time.time()}}
        await asyncio.sleep(0)

        full_content = _build_report_content(type_label, data)
        # 섹션별 분할하여 스트리밍
        sections_raw = full_content.split("\n## ")
        section_names = ["핵심 지표 요약", "주요 변화 및 트렌드", "이슈 & 주의사항", "권장 조치사항"]

        for i, section_name in enumerate(section_names):
            yield {"event": "step_progress", "data": {
                "step": "write", "current": i + 1, "total": len(section_names),
                "detail": f"'{section_name}' 섹션 생성 중",
            }}
            # 해당 섹션 내용 찾기
            section_content = ""
            for part in sections_raw:
                if section_name in part:
                    section_content = f"## {part}"
                    break
            if section_content:
                yield {"event": "report_section", "data": {"section": section_name, "content": section_content}}
            await asyncio.sleep(0)

        write_elapsed = int((time.time() - start_time) * 1000)
        yield {"event": "step_end", "data": {"step": "write", "elapsed_ms": write_elapsed, "result_count": len(section_names)}}

        # 4단계: 저장
        yield {"event": "step_start", "data": {"step": "save", "description": "리포트 저장", "timestamp": time.time()}}

        result = {
            "report_id": report_id,
            "report_type": report_type,
            "content": full_content,
            "data_summary": data,
            "timestamp": time.time(),
        }

        save_report(result)
        log_action("production_report_generate", report_id, {
            "report_type": report_type,
            "kpi_keys": list(data.get("kpi", {}).keys()),
        })

        save_elapsed = int((time.time() - start_time) * 1000)
        yield {"event": "step_end", "data": {"step": "save", "elapsed_ms": save_elapsed, "result_count": 1}}

        total_elapsed = int((time.time() - start_time) * 1000)
        yield {"event": "done", "data": {"ok": True, "report_id": report_id, "total_elapsed_ms": total_elapsed}}

        st.logger.info("PRODUCTION_REPORT_GENERATED_STREAM id=%s type=%s", report_id, report_type)

    except Exception as e:
        st.logger.error("PRODUCTION_REPORT_STREAM_FAIL id=%s err=%s", report_id, safe_str(e))
        yield {"event": "error", "data": {"message": safe_str(e)}}


def get_history(limit: int = 20) -> Dict[str, Any]:
    """리포트 히스토리를 조회합니다."""
    reports = get_report_history(limit)
    return {
        "total": len(reports),
        "reports": reports,
    }
