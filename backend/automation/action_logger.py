"""
automation/action_logger.py - 자동화 조치 로깅
==============================================
모든 자동 조치(예지보전, 고장대응, 생산리포트, 공정최적화)의 실행 기록을 관리합니다.
"""
import time
import uuid
from typing import Dict, List, Any, Optional
from threading import Lock

import state as st


# 전역 액션 로그 저장소 (크기 제한)
_ACTION_LOG: List[Dict[str, Any]] = []
_ACTION_LOCK = Lock()
_ACTION_LOG_MAX_SIZE = 5000

# FAQ 저장소 (크기 제한)
_FAQ_STORE: Dict[str, Dict[str, Any]] = {}
_FAQ_LOCK = Lock()
_FAQ_STORE_MAX_SIZE = 1000

# 리포트 히스토리 (크기 제한)
_REPORT_HISTORY: List[Dict[str, Any]] = []
_REPORT_LOCK = Lock()
_REPORT_HISTORY_MAX_SIZE = 500

# 리텐션 메시지 히스토리 (크기 제한)
_RETENTION_HISTORY: List[Dict[str, Any]] = []
_RETENTION_LOCK = Lock()
_RETENTION_HISTORY_MAX_SIZE = 1000

# 파이프라인 실행 추적 (크기 제한)
_PIPELINE_RUNS: Dict[str, Dict[str, Any]] = {}
_PIPELINE_LOCK = Lock()
_PIPELINE_RUNS_MAX_SIZE = 500


def log_action(
    action_type: str,
    target_id: str,
    detail: Dict[str, Any],
    status: str = "success",
) -> Dict[str, Any]:
    """자동화 조치를 로깅합니다."""
    entry = {
        "id": str(uuid.uuid4())[:8],
        "action_type": action_type,
        "target_id": target_id,
        "detail": detail,
        "status": status,
        "timestamp": time.time(),
    }
    with _ACTION_LOCK:
        _ACTION_LOG.append(entry)
        # 크기 제한: 오래된 항목 제거
        if len(_ACTION_LOG) > _ACTION_LOG_MAX_SIZE:
            del _ACTION_LOG[:len(_ACTION_LOG) - _ACTION_LOG_MAX_SIZE]
    st.logger.info("ACTION_LOG type=%s target=%s status=%s", action_type, target_id, status)
    return entry


def get_action_log(
    action_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """액션 로그를 조회합니다."""
    with _ACTION_LOCK:
        logs = list(_ACTION_LOG)
    if action_type:
        logs = [l for l in logs if l["action_type"] == action_type]
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs[:limit]


def get_action_stats() -> Dict[str, Any]:
    """액션 통계를 반환합니다."""
    with _ACTION_LOCK:
        logs = list(_ACTION_LOG)
    total = len(logs)
    by_type: Dict[str, int] = {}
    for l in logs:
        t = l["action_type"]
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "total_actions": total,
        "by_type": by_type,
    }


# ── FAQ 저장소 ──
def save_faq(faq_id: str, faq_data: Dict[str, Any]) -> None:
    with _FAQ_LOCK:
        # 크기 제한: 가장 오래된 항목 제거
        if len(_FAQ_STORE) >= _FAQ_STORE_MAX_SIZE and faq_id not in _FAQ_STORE:
            oldest_key = next(iter(_FAQ_STORE))
            del _FAQ_STORE[oldest_key]
        _FAQ_STORE[faq_id] = faq_data


def get_faq(faq_id: str) -> Optional[Dict[str, Any]]:
    with _FAQ_LOCK:
        return _FAQ_STORE.get(faq_id)


def get_all_faqs() -> List[Dict[str, Any]]:
    with _FAQ_LOCK:
        return list(_FAQ_STORE.values())


def delete_faq(faq_id: str) -> bool:
    with _FAQ_LOCK:
        if faq_id in _FAQ_STORE:
            del _FAQ_STORE[faq_id]
            return True
        return False


def update_faq_status(faq_id: str, status: str) -> bool:
    with _FAQ_LOCK:
        if faq_id in _FAQ_STORE:
            _FAQ_STORE[faq_id]["status"] = status
            _FAQ_STORE[faq_id]["updated_at"] = time.time()
            return True
        return False


# ── 리포트 히스토리 ──
def save_report(report: Dict[str, Any]) -> None:
    with _REPORT_LOCK:
        _REPORT_HISTORY.append(report)
        if len(_REPORT_HISTORY) > _REPORT_HISTORY_MAX_SIZE:
            del _REPORT_HISTORY[:len(_REPORT_HISTORY) - _REPORT_HISTORY_MAX_SIZE]


def get_report_history(limit: int = 20) -> List[Dict[str, Any]]:
    with _REPORT_LOCK:
        return sorted(_REPORT_HISTORY, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]


# ── 리텐션 히스토리 ──
def save_retention_action(action: Dict[str, Any]) -> None:
    with _RETENTION_LOCK:
        _RETENTION_HISTORY.append(action)
        if len(_RETENTION_HISTORY) > _RETENTION_HISTORY_MAX_SIZE:
            del _RETENTION_HISTORY[:len(_RETENTION_HISTORY) - _RETENTION_HISTORY_MAX_SIZE]


def get_retention_history(limit: int = 50) -> List[Dict[str, Any]]:
    with _RETENTION_LOCK:
        return sorted(_RETENTION_HISTORY, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]


# ── 파이프라인 실행 추적 ──
def create_pipeline_run(pipeline_type: str, steps: List[str]) -> str:
    """파이프라인 실행을 생성하고 run_id를 반환합니다."""
    run_id = str(uuid.uuid4())[:8]
    run = {
        "run_id": run_id,
        "pipeline_type": pipeline_type,
        "steps": {
            s: {"status": "pending", "started_at": None, "completed_at": None, "result": None}
            for s in steps
        },
        "current_step": None,
        "status": "running",
        "created_at": time.time(),
    }
    with _PIPELINE_LOCK:
        # 크기 제한: 완료된 오래된 파이프라인 제거
        if len(_PIPELINE_RUNS) >= _PIPELINE_RUNS_MAX_SIZE:
            completed = [
                (rid, r) for rid, r in _PIPELINE_RUNS.items()
                if r.get("status") in ("complete", "error")
            ]
            completed.sort(key=lambda x: x[1].get("created_at", 0))
            for rid, _ in completed[:len(_PIPELINE_RUNS) - _PIPELINE_RUNS_MAX_SIZE + 1]:
                del _PIPELINE_RUNS[rid]
        _PIPELINE_RUNS[run_id] = run
    return run_id


def update_pipeline_step(
    run_id: str, step: str, status: str, result: Any = None,
) -> None:
    """파이프라인 스텝 상태를 업데이트합니다."""
    with _PIPELINE_LOCK:
        run = _PIPELINE_RUNS.get(run_id)
        if not run:
            return
        if step in run["steps"]:
            run["steps"][step]["status"] = status
            run["current_step"] = step
            if status == "processing":
                run["steps"][step]["started_at"] = time.time()
            elif status in ("complete", "error"):
                run["steps"][step]["completed_at"] = time.time()
                run["steps"][step]["result"] = result
        # 전체 파이프라인 상태 갱신
        all_statuses = [s["status"] for s in run["steps"].values()]
        if all(s == "complete" for s in all_statuses):
            run["status"] = "complete"
        elif any(s == "error" for s in all_statuses):
            run["status"] = "error"


def complete_pipeline_run(run_id: str) -> None:
    """파이프라인 실행을 완료 처리합니다."""
    with _PIPELINE_LOCK:
        run = _PIPELINE_RUNS.get(run_id)
        if run:
            run["status"] = "complete"


def get_pipeline_run(run_id: str) -> Optional[Dict[str, Any]]:
    """파이프라인 실행 상태를 조회합니다."""
    with _PIPELINE_LOCK:
        return _PIPELINE_RUNS.get(run_id)
