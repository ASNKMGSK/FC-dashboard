"""
api/routes_automation.py - 자동화 엔진 API 라우터
================================================
탐지 → 자동 실행 3대 기능:
  1. 설비 고장예방정비 자동 조치
  2. 트러블슈팅 가이드 자동 생성
  3. 생산 리포트 자동 생성
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.common import verify_credentials, sse_pack
from core.constants import WORK_ORDER_CATEGORIES
from core.utils import safe_str
import state as st

from automation import action_logger
from automation import predictive_maintenance_engine
from automation import troubleshooting_engine
from automation import production_report_engine
from automation.optimization_engine import get_optimization_candidates, generate_optimization_recommendation, execute_optimization_action

router = APIRouter(prefix="/api/automation", tags=["automation"])


# ============================================================
# Pydantic 요청 모델
# ============================================================
class MaintenancePlanRequest(BaseModel):
    equipment_id: str


class MaintenanceExecuteRequest(BaseModel):
    equipment_id: str
    action_type: str = Field("custom_message", description="priority_alert | maintenance_schedule | manager_assign | custom_message")


class TroubleshootingGenerateRequest(BaseModel):
    category: Optional[str] = None
    count: int = Field(5, ge=1, le=100)
    mode: str = "kmeans"
    selected_clusters: Optional[List[dict]] = Field(None, alias="selectedClusters",
        description="선택된 클러스터 목록 [{category, cluster_id, representative, samples}]")
    class Config:
        populate_by_name = True


class TroubleshootingUpdateRequest(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None


class MaintenanceBulkExecuteRequest(BaseModel):
    equipment_ids: List[str]
    action_type: str = Field("custom_message", description="priority_alert | maintenance_schedule | manager_assign | custom_message")


class OptimizationMessageRequest(BaseModel):
    equipment_id: str


class OptimizationExecuteRequest(BaseModel):
    equipment_id: str
    action_type: str = Field("upgrade_recommend", description="upgrade_recommend | benefit_info | consultation_request | custom_message")


class ReportGenerateRequest(BaseModel):
    report_type: str = Field("daily", description="daily | weekly | monthly")


# ── SSE 스트리밍 요청 모델 ──
class MaintenanceStreamRequest(BaseModel):
    threshold: float = Field(0.6, ge=0.0, le=1.0)
    limit: int = Field(20, ge=1, le=100)


class ReportStreamRequest(BaseModel):
    report_type: str = Field("daily", description="daily | weekly | monthly")


class OptimizationStreamRequest(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    use_ml_scoring: bool = Field(False, alias="useMlScoring", description="ML 설비 이상 위험도 스코어 반영 여부")
    class Config:
        populate_by_name = True


# ============================================================
# 1. 설비 고장예방정비 자동 조치
# ============================================================
@router.get("/predictive-maintenance/at-risk")
def get_at_risk_equipment(
    threshold: float = Query(0.6, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(verify_credentials),
):
    """고장 위험 설비 목록 조회"""
    try:
        equipment = predictive_maintenance_engine.get_at_risk_equipment(threshold=threshold, limit=limit)
        return {"status": "success", "equipment": equipment, "total": len(equipment)}
    except Exception as e:
        st.logger.error("MAINTENANCE_AT_RISK_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.post("/predictive-maintenance/message")
def generate_maintenance_message(
    req: MaintenancePlanRequest,
    user=Depends(verify_credentials),
):
    """예방정비 메시지 생성"""
    try:
        result = predictive_maintenance_engine.generate_maintenance_plan(
            equipment_id=req.equipment_id,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("MAINTENANCE_MESSAGE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.post("/predictive-maintenance/execute")
def execute_maintenance_action(
    req: MaintenanceExecuteRequest,
    user=Depends(verify_credentials),
):
    """예방정비 조치 실행"""
    try:
        result = predictive_maintenance_engine.execute_maintenance_action(
            equipment_id=req.equipment_id,
            action_type=req.action_type,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("MAINTENANCE_EXECUTE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.get("/predictive-maintenance/history")
def get_maintenance_history(
    limit: int = Query(50, ge=1, le=200),
    user=Depends(verify_credentials),
):
    """예방정비 조치 이력 조회"""
    try:
        history = action_logger.get_retention_history(limit=limit)
        return {"status": "success", "total": len(history), "history": history}
    except Exception as e:
        st.logger.error("MAINTENANCE_HISTORY_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


# ============================================================
# 2. 트러블슈팅 가이드 자동 생성
# ============================================================
class TroubleshootingAnalyzeRequest(BaseModel):
    mode: str = "kmeans"  # "kmeans" or "llm"
    category: Optional[str] = None

@router.post("/troubleshooting/analyze")
def analyze_fault_patterns(
    req: TroubleshootingAnalyzeRequest = TroubleshootingAnalyzeRequest(),
    user=Depends(verify_credentials),
):
    """결함 패턴 분석 (mode: kmeans / llm)"""
    try:
        result = troubleshooting_engine.analyze_maintenance_patterns(
            category=req.category,
            mode=req.mode,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("TROUBLESHOOTING_ANALYZE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.post("/troubleshooting/generate")
def generate_troubleshooting(
    req: TroubleshootingGenerateRequest,
    user=Depends(verify_credentials),
):
    """트러블슈팅 가이드 자동 생성"""
    try:
        result = troubleshooting_engine.generate_troubleshooting_guide(
            category=req.category,
            count=req.count,
            mode=req.mode,
            selected_clusters=req.selected_clusters,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("TROUBLESHOOTING_GENERATE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.get("/troubleshooting/list")
def list_troubleshooting(
    status: Optional[str] = Query(None, description="draft | approved | all"),
    user=Depends(verify_credentials),
):
    """트러블슈팅 가이드 목록 조회"""
    try:
        result = troubleshooting_engine.list_faqs(status=status)
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("TROUBLESHOOTING_LIST_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.put("/troubleshooting/{faq_id}/approve")
def approve_troubleshooting(
    faq_id: str,
    user=Depends(verify_credentials),
):
    """트러블슈팅 가이드 승인"""
    try:
        result = troubleshooting_engine.approve_faq(faq_id=faq_id)
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("TROUBLESHOOTING_APPROVE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.put("/troubleshooting/{faq_id}")
def update_troubleshooting(
    faq_id: str,
    req: TroubleshootingUpdateRequest,
    user=Depends(verify_credentials),
):
    """트러블슈팅 가이드 수정"""
    try:
        result = troubleshooting_engine.update_faq(
            faq_id=faq_id,
            question=req.question,
            answer=req.answer,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("TROUBLESHOOTING_UPDATE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.delete("/troubleshooting/{faq_id}")
def delete_troubleshooting(
    faq_id: str,
    user=Depends(verify_credentials),
):
    """트러블슈팅 가이드 삭제"""
    try:
        result = troubleshooting_engine.delete_faq_item(faq_id=faq_id)
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("TROUBLESHOOTING_DELETE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


# ============================================================
# 3. 생산 리포트 자동 생성
# ============================================================
@router.post("/production-report/generate")
def generate_production_report(
    req: ReportGenerateRequest,
    user=Depends(verify_credentials),
):
    """생산 리포트 자동 생성"""
    try:
        result = production_report_engine.generate_report(
            report_type=req.report_type,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("REPORT_GENERATE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.get("/production-report/history")
def get_production_report_history(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(verify_credentials),
):
    """생산 리포트 생성 이력 조회"""
    try:
        result = production_report_engine.get_history(limit=limit)
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("REPORT_HISTORY_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


# ============================================================
# 4. 공통 - 액션 로그
# ============================================================
@router.get("/actions/log")
def get_actions_log(
    action_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(verify_credentials),
):
    """자동화 액션 로그 조회"""
    try:
        logs = action_logger.get_action_log(action_type=action_type, limit=limit)
        return {"status": "success", "total": len(logs), "logs": logs}
    except Exception as e:
        st.logger.error("ACTION_LOG_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.get("/actions/stats")
def get_actions_stats(
    user=Depends(verify_credentials),
):
    """자동화 액션 통계"""
    try:
        stats = action_logger.get_action_stats()
        return {"status": "success", **stats}
    except Exception as e:
        st.logger.error("ACTION_STATS_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


# ============================================================
# 5. 공통 유틸리티
# ============================================================
@router.get("/categories")
def get_fault_categories(
    user=Depends(verify_credentials),
):
    """결함 카테고리 목록 조회"""
    return {"status": "success", "categories": WORK_ORDER_CATEGORIES}


@router.get("/pipeline/{run_id}")
def get_pipeline_status(
    run_id: str,
    user=Depends(verify_credentials),
):
    """파이프라인 실행 상태 조회"""
    run = action_logger.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="파이프라인 실행을 찾을 수 없습니다.")
    return {"status": "success", **run}


@router.post("/predictive-maintenance/execute-bulk")
def execute_maintenance_bulk(
    req: MaintenanceBulkExecuteRequest,
    user=Depends(verify_credentials),
):
    """예방정비 벌크 조치 실행"""
    try:
        results = []
        for equipment_id in req.equipment_ids:
            result = predictive_maintenance_engine.execute_maintenance_action(
                equipment_id=equipment_id,
                action_type=req.action_type,
            )
            results.append({"equipment_id": equipment_id, **result})
        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success",
            "total": len(results),
            "success_count": success_count,
            "results": results,
        }
    except Exception as e:
        st.logger.error("MAINTENANCE_BULK_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


# ============================================================
# 6. 설비 최적화 추천
# ============================================================
@router.get("/optimization/candidates")
def get_optimization_candidates_route(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(verify_credentials),
):
    """최적화 대상 설비 목록 조회"""
    try:
        candidates = get_optimization_candidates(limit=limit)
        return {"status": "success", "candidates": candidates, "total": len(candidates)}
    except Exception as e:
        st.logger.error("OPTIMIZATION_CANDIDATES_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.post("/optimization/message")
def generate_optimization_message_route(
    req: OptimizationMessageRequest,
    user=Depends(verify_credentials),
):
    """설비 최적화 추천 메시지 생성"""
    try:
        result = generate_optimization_recommendation(
            equipment_id=req.equipment_id,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("OPTIMIZATION_MESSAGE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


@router.post("/optimization/execute")
def execute_optimization_action_route(
    req: OptimizationExecuteRequest,
    user=Depends(verify_credentials),
):
    """설비 최적화 조치 실행"""
    try:
        result = execute_optimization_action(
            equipment_id=req.equipment_id,
            action_type=req.action_type,
        )
        return {"status": "success", **result}
    except Exception as e:
        st.logger.error("OPTIMIZATION_EXECUTE_ERROR: %s", safe_str(e))
        raise HTTPException(status_code=500, detail=safe_str(e))


# ============================================================
# 7. SSE 스트리밍 엔드포인트
# ============================================================
@router.post("/predictive-maintenance/stream")
async def predictive_maintenance_stream(
    req: MaintenanceStreamRequest,
    user=Depends(verify_credentials),
):
    """예방정비 파이프라인 SSE 스트리밍"""
    async def event_generator():
        try:
            async for event in predictive_maintenance_engine.get_at_risk_equipment_stream(
                threshold=req.threshold,
                limit=req.limit,
            ):
                yield sse_pack(event["event"], event["data"])
        except Exception as e:
            st.logger.error("MAINTENANCE_STREAM_ERROR: %s", safe_str(e))
            yield sse_pack("error", {"message": safe_str(e)})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/production-report/stream")
async def production_report_stream(
    req: ReportStreamRequest,
    user=Depends(verify_credentials),
):
    """생산 리포트 SSE 스트리밍"""
    async def event_generator():
        try:
            async for event in production_report_engine.generate_report_stream(
                report_type=req.report_type,
            ):
                yield sse_pack(event["event"], event["data"])
        except Exception as e:
            st.logger.error("REPORT_STREAM_ERROR: %s", safe_str(e))
            yield sse_pack("error", {"message": safe_str(e)})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/optimization/stream")
async def optimization_stream(
    req: OptimizationStreamRequest,
    user=Depends(verify_credentials),
):
    """최적화 대상 설비 SSE 스트리밍"""
    from automation.optimization_engine import get_optimization_candidates_stream

    async def event_generator():
        try:
            async for event in get_optimization_candidates_stream(
                limit=req.limit,
                use_ml_scoring=req.use_ml_scoring,
            ):
                yield sse_pack(event["event"], event["data"])
        except Exception as e:
            st.logger.error("OPTIMIZATION_STREAM_ERROR: %s", safe_str(e))
            yield sse_pack("error", {"message": safe_str(e)})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
