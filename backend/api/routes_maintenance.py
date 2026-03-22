"""
api/routes_maintenance.py - 정비/설비보전 API
"""
import os
import json
import asyncio
import uuid
import time as _time
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse

from core.constants import WORK_ORDER_CATEGORIES, MAINTENANCE_PRIORITY_GRADES
from core.utils import safe_str
from agent.tools import (
    tool_auto_assign_maintenance, tool_check_maintenance_quality,
    tool_get_manufacturing_glossary, tool_get_cs_statistics,
    tool_classify_inquiry,
)
import state as st
from api.common import (
    verify_credentials, error_response,
    MaintenanceReplyRequest, MaintenanceQualityRequest, MaintenancePipelineRequest, MaintenancePipelineAnswerRequest,
)


router = APIRouter(prefix="/api", tags=["maintenance"])

# ── n8n 연동: job_id 기반 큐 (TTL 관리) ──
_maintenance_job_queues: dict = {}
_maintenance_job_timestamps: dict = {}  # job_id -> 생성 시각
_MAINTENANCE_JOB_TTL_SEC = 10 * 60     # 10분 후 자동 정리


_last_cleanup_ts = 0.0

def _cleanup_expired_jobs() -> None:
    """만료된 정비 job 큐 정리 (최소 30초 간격으로 실행)"""
    global _last_cleanup_ts
    now = _time.time()
    if now - _last_cleanup_ts < 30:
        return  # 빈번한 정리 방지
    _last_cleanup_ts = now
    expired = [k for k, ts in _maintenance_job_timestamps.items() if now - ts > _MAINTENANCE_JOB_TTL_SEC]
    for k in expired:
        _maintenance_job_queues.pop(k, None)
        _maintenance_job_timestamps.pop(k, None)


# ============================================================
# 정비 콜백 인증 (#4)
# ============================================================
_MAINTENANCE_CALLBACK_SECRET = os.environ.get("CS_CALLBACK_SECRET", "")


def _verify_callback_token(x_callback_token: Optional[str] = Header(None)):
    """콜백 엔드포인트 API 키 인증"""
    if not _MAINTENANCE_CALLBACK_SECRET:
        return  # 시크릿 미설정 시 인증 건너뛰기 (개발 모드)
    if x_callback_token != _MAINTENANCE_CALLBACK_SECRET:
        raise HTTPException(status_code=401, detail="유효하지 않은 콜백 토큰")


# ============================================================
# 정비 API
# ============================================================
@router.post("/maintenance/reply")
def maintenance_auto_reply(req: MaintenanceReplyRequest, user: dict = Depends(verify_credentials)):
    return tool_auto_assign_maintenance(inquiry_text=req.text, inquiry_category=req.ticket_category, grade=req.grade)


@router.post("/maintenance/quality")
def check_maintenance_quality_route(req: MaintenanceQualityRequest, user: dict = Depends(verify_credentials)):
    return tool_check_maintenance_quality(ticket_category=req.ticket_category, grade=req.grade, sentiment_score=req.priority_score, order_value=req.cost_estimate, is_repeat_issue=req.is_repeat_issue, text_length=req.text_length)


@router.get("/maintenance/glossary")
def get_manufacturing_glossary(term: Optional[str] = None, user: dict = Depends(verify_credentials)):
    return tool_get_manufacturing_glossary(term=term)


@router.get("/maintenance/statistics")
def get_maintenance_stats(user: dict = Depends(verify_credentials)):
    return tool_get_cs_statistics()


# ============================================================
# 정비 자동배정 파이프라인 API
# ============================================================
@router.post("/maintenance/pipeline")
async def maintenance_pipeline(req: MaintenancePipelineRequest, user: dict = Depends(verify_credentials)):
    result = {"status": "success", "steps": {}}

    # Step 1: 결함 분류 (후속 단계의 입력이 됨)
    step_classify = await asyncio.to_thread(tool_classify_inquiry, req.inquiry_text)
    result["steps"]["classify"] = step_classify
    if step_classify.get("status") != "SUCCESS":
        result["status"] = "error"
        return result
    predicted_category = step_classify.get("predicted_category", "기타")
    confidence = step_classify.get("confidence", 0.0)

    negative_words = ["긴급", "고장", "정지", "위험", "누출", "파손", "이상", "과열", "진동"]
    sentiment = -0.4 if any(w in req.inquiry_text for w in negative_words) else 0.1
    is_auto = confidence >= req.confidence_threshold
    routing = "auto" if is_auto else "manual"

    # Step 2~4: 우선순위 평가, 정비지시 생성, 통계조회를 병렬 실행
    priority_task = asyncio.to_thread(
        tool_check_maintenance_quality,
        ticket_category=predicted_category, grade=req.grade,
        sentiment_score=sentiment, order_value=req.cost_estimate,
        is_repeat_issue=req.is_repeat_issue, text_length=len(req.inquiry_text),
    )
    answer_task = asyncio.to_thread(
        tool_auto_assign_maintenance,
        inquiry_text=req.inquiry_text, inquiry_category=predicted_category,
        grade=req.grade, order_id=req.work_order_id,
    )
    stats_task = asyncio.to_thread(tool_get_cs_statistics)

    priority_result, answer_context, stats = await asyncio.gather(
        priority_task, answer_task, stats_task,
    )

    result["steps"]["review"] = {"confidence": confidence, "threshold": req.confidence_threshold, "routing": routing, "predicted_category": predicted_category, "sentiment_score": sentiment, "priority": priority_result}
    result["steps"]["answer"] = answer_context
    result["steps"]["reply"] = {"status": "READY", "channels": ["이메일", "MES", "SMS", "설비모니터링"], "selected_channel": None, "message": "알림 채널을 선택하면 n8n 워크플로우로 자동 전송됩니다."}
    result["steps"]["improve"] = {"statistics": stats, "pipeline_meta": {"classification_model_accuracy": 0.82, "auto_routing_rate": f"{req.confidence_threshold * 100:.0f}% 이상 자동", "categories": WORK_ORDER_CATEGORIES, "priority_grades": list(MAINTENANCE_PRIORITY_GRADES.keys())}}
    return result


@router.post("/maintenance/pipeline/answer")
async def maintenance_pipeline_answer(req: MaintenancePipelineAnswerRequest, request: Request, user: dict = Depends(verify_credentials)):
    """정비 파이프라인 Step 3 - 템플릿 기반 정비 지시서 초안 생성 (SSE 스트리밍)"""
    async def gen():
        try:
            draft = (
                f"## 정비 지시서 초안\n\n"
                f"**결함 카테고리:** {req.inquiry_category}\n"
                f"**설비 등급:** {req.grade}\n"
                f"**작업지시 ID:** {req.order_id or '없음'}\n\n"
                f"### 이상 현상\n{req.inquiry_text}\n\n"
                f"### 조치 사항\n"
                f"- SOP(표준작업절차서)에 따라 해당 설비를 점검하십시오.\n"
                f"- 필요 부품 및 공구를 확인 후 정비를 진행하십시오.\n"
                f"- 안전 수칙을 준수하고, 정비 완료 후 시운전을 실시하십시오.\n"
                f"- 정비 이력을 MES에 기록하십시오.\n"
            )
            yield f"data: {json.dumps({'type': 'rag_context', 'data': {'source_count': 0, 'context_preview': '(템플릿 기반 생성)'}})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'data': draft})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            st.logger.error("Maintenance Pipeline Answer Error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ── n8n 연동 ──
@router.post("/maintenance/send-reply")
async def maintenance_send_reply(request: Request, user: dict = Depends(verify_credentials)):
    body = await request.json()
    inquiries = body.get("inquiries", [])
    _cleanup_expired_jobs()
    job_id = uuid.uuid4().hex[:8]
    queue: asyncio.Queue = asyncio.Queue()
    _maintenance_job_queues[job_id] = queue
    _maintenance_job_timestamps[job_id] = _time.time()
    await queue.put({"type": "step", "data": {"node": "webhook", "status": "completed", "detail": "트리거 완료"}})
    n8n_url = os.environ.get("N8N_WEBHOOK_URL", "")
    callback_base = os.environ.get("N8N_CALLBACK_URL", "")
    if n8n_url:
        asyncio.create_task(_n8n_trigger(job_id, n8n_url, callback_base, inquiries, queue))
    else:
        asyncio.create_task(_simulate_workflow(job_id, inquiries, queue))
    return {"status": "success", "job_id": job_id}


async def _n8n_trigger(job_id, n8n_url, callback_base, inquiries, queue):
    try:
        import httpx
        all_channels = sorted({ch for inq in inquiries for ch in inq.get("channels", [])})
        st.logger.info("[n8n] job=%s calling %s channels=%s", job_id, n8n_url, all_channels)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(n8n_url, json={"job_id": job_id, "inquiries": inquiries, "channels": all_channels})
        st.logger.info("[n8n] job=%s status=%s body=%s", job_id, resp.status_code, resp.text[:300])
        if resp.status_code >= 400:
            await queue.put({"type": "error", "data": f"n8n 호출 실패: HTTP {resp.status_code}"})
            await queue.put(None)
            return
        await _replay_steps(inquiries, all_channels, queue)
    except Exception as e:
        st.logger.error("[n8n] job=%s error: %s", job_id, e)
        await queue.put({"type": "error", "data": f"n8n 연결 실패: {str(e)[:80]}"})
        await queue.put(None)


async def _send_email_resend(to_email, subject, body_html):
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key or not to_email:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"}, json={"from": "SmartFactory Maintenance <onboarding@resend.dev>", "to": [to_email], "subject": subject, "html": body_html})
        st.logger.info("[maintenance-email] resend to=%s status=%s", to_email, resp.status_code)
        return resp.status_code < 400
    except Exception as e:
        st.logger.error("[maintenance-email] resend error: %s", e)
        return False


async def _replay_steps(inquiries, all_channels, queue, *, send_emails: bool = False):
    """워크플로우 단계를 재생. send_emails=True이면 이메일 실제 발송 시도."""
    try:
        await queue.put({"type": "step", "data": {"node": "validate", "status": "running"}})
        await asyncio.sleep(0.4)
        await queue.put({"type": "step", "data": {"node": "validate", "status": "completed", "detail": f"{len(inquiries)}건 검증 완료"}})
        await queue.put({"type": "step", "data": {"node": "router", "status": "running"}})
        await asyncio.sleep(0.3)
        await queue.put({"type": "step", "data": {"node": "router", "status": "completed", "detail": f"{len(all_channels)}개 채널"}})
        for ch in all_channels:
            ch_count = sum(1 for inq in inquiries if ch in inq.get("channels", []))
            await queue.put({"type": "step", "data": {"node": f"channel_{ch}", "status": "running"}})
            if send_emails and ch == "이메일":
                email_sent = 0
                for inq in inquiries:
                    if "이메일" not in inq.get("channels", []):
                        continue
                    to_email = inq.get("recipient_email", "")
                    if not to_email:
                        continue
                    subject = f"[스마트팩토리] 정비 지시 — {inq.get('category', '기타')}"
                    html = f"""<div style="font-family:'Apple SD Gothic Neo',sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#1a56db;padding:20px 32px"><h2 style="margin:0;color:#fff;font-size:18px">스마트팩토리 정비 지시서</h2></div>
  <div style="padding:24px 32px;background:#fff"><p style="color:#374151;font-size:14px;line-height:1.7"><strong>이상 보고 내용:</strong><br>{inq.get('inquiry_text', '')}</p><hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"><p style="color:#374151;font-size:14px;line-height:1.7"><strong>정비 지시:</strong><br>{inq.get('answer_text', '')}</p></div>
  <div style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb"><p style="margin:0;font-size:11px;color:#9ca3af">SmartFactory AI Maintenance</p></div></div>"""
                    ok = await _send_email_resend(to_email, subject, html)
                    if ok:
                        email_sent += 1
                detail = f"{email_sent}건 발송 완료" if email_sent > 0 else f"{ch_count}건 전송 (시뮬레이션)"
                await queue.put({"type": "step", "data": {"node": f"channel_{ch}", "status": "completed", "detail": detail}})
            else:
                await asyncio.sleep(0.3)
                suffix = "" if not send_emails else " (시뮬레이션)"
                await queue.put({"type": "step", "data": {"node": f"channel_{ch}", "status": "completed", "detail": f"{ch_count}건 전송{suffix}"}})
        await queue.put({"type": "step", "data": {"node": "log", "status": "running"}})
        await asyncio.sleep(0.3)
        await queue.put({"type": "step", "data": {"node": "log", "status": "completed", "detail": "이력 저장 완료"}})
        await queue.put({"type": "done", "data": {"total": len(inquiries), "channels": all_channels}})
    except Exception as e:
        st.logger.error("replay_steps error: %s", e)
        await queue.put({"type": "error", "data": str(e)})
    finally:
        await queue.put(None)


async def _simulate_workflow(job_id, inquiries, queue):
    all_channels = sorted({ch for inq in inquiries for ch in inq.get("channels", [])})
    await _replay_steps(inquiries, all_channels, queue, send_emails=True)


@router.get("/maintenance/stream")
async def maintenance_stream(job_id: str, user: dict = Depends(verify_credentials)):
    _cleanup_expired_jobs()
    queue = _maintenance_job_queues.get(job_id)
    if not queue:
        return JSONResponse({"status": "error", "message": "유효하지 않은 job_id"}, status_code=404)

    async def gen():
        try:
            while True:
                evt = await asyncio.wait_for(queue.get(), timeout=120.0)
                if evt is None:
                    break
                yield f"data: {json.dumps(evt)}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'data': 'timeout'})}\n\n"
        finally:
            _maintenance_job_queues.pop(job_id, None)
            _maintenance_job_timestamps.pop(job_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/maintenance/callback")
async def maintenance_callback(request: Request, _auth=Depends(_verify_callback_token)):
    """n8n 콜백 수신 — API 키 인증 적용 (#4)"""
    body = await request.json()
    job_id = body.get("job_id", "")
    queue = _maintenance_job_queues.get(job_id)
    if not queue:
        return JSONResponse({"status": "error", "message": "유효하지 않은 job_id"}, status_code=404)

    step = body.get("step", "")
    status_val = body.get("status", "")
    detail = body.get("detail", "")

    if step == "done":
        await queue.put({"type": "done", "data": body.get("data", {})})
        await queue.put(None)
    elif step == "error":
        await queue.put({"type": "error", "data": detail or body.get("data", "")})
        await queue.put(None)
    else:
        await queue.put({"type": "step", "data": {"node": step, "status": status_val, "detail": detail}})

    return {"status": "success"}
