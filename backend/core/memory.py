"""
core/memory.py - 대화 메모리 관리 (#9: TTL/세션 제한 적용)
"""
import time
from collections import deque
from threading import Lock
from typing import Dict, List

# Settings
MAX_MEMORY_TURNS = 10
MAX_SESSIONS = 200            # 최대 동시 세션 수 (Railway 메모리 최적화, 1000→200)
SESSION_TTL_SEC = 30 * 60     # 30분 비활성 시 만료
_CLEANUP_INTERVAL_SEC = 60    # cleanup 최소 간격 (초)

# Store
MEMORY_STORE: Dict[str, deque] = {}
MEMORY_TIMESTAMPS: Dict[str, float] = {}  # 세션별 마지막 접근 시간
MEMORY_LOCK = Lock()
_last_cleanup_time: float = 0.0


def _cleanup_expired() -> None:
    """만료된 세션 정리 (lock 내부에서 호출, 스로틀 적용)"""
    global _last_cleanup_time
    now = time.time()

    # 스로틀: 마지막 cleanup으로부터 일정 시간 미경과 시 스킵
    if now - _last_cleanup_time < _CLEANUP_INTERVAL_SEC:
        return
    _last_cleanup_time = now

    expired = [k for k, ts in MEMORY_TIMESTAMPS.items() if now - ts > SESSION_TTL_SEC]
    for k in expired:
        MEMORY_STORE.pop(k, None)
        MEMORY_TIMESTAMPS.pop(k, None)

    # 세션 수 초과 시 가장 오래된 세션부터 제거
    if len(MEMORY_STORE) > MAX_SESSIONS:
        sorted_sessions = sorted(MEMORY_TIMESTAMPS.items(), key=lambda x: x[1])
        to_remove = len(MEMORY_STORE) - MAX_SESSIONS
        for k, _ in sorted_sessions[:to_remove]:
            MEMORY_STORE.pop(k, None)
            MEMORY_TIMESTAMPS.pop(k, None)


def get_user_memory(username: str) -> deque:
    """사용자별 메모리 deque 반환"""
    if username not in MEMORY_STORE:
        MEMORY_STORE[username] = deque(maxlen=MAX_MEMORY_TURNS * 2)
    MEMORY_TIMESTAMPS[username] = time.time()
    return MEMORY_STORE[username]


def memory_messages(username: str) -> List[Dict[str, str]]:
    """사용자의 대화 히스토리 반환"""
    with MEMORY_LOCK:
        _cleanup_expired()
        return list(get_user_memory(username))


def append_memory(username: str, user_input: str, assistant_output: str) -> None:
    """대화 내용을 메모리에 추가"""
    with MEMORY_LOCK:
        _cleanup_expired()
        mem = get_user_memory(username)
        mem.append({"role": "user", "content": user_input})
        mem.append({"role": "assistant", "content": assistant_output})


def clear_memory(username: str) -> None:
    """사용자의 메모리 초기화"""
    with MEMORY_LOCK:
        MEMORY_STORE[username] = deque(maxlen=MAX_MEMORY_TURNS * 2)
        MEMORY_TIMESTAMPS[username] = time.time()
