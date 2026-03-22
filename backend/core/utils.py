import math
import re
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def safe_str(x: Any, default: str = "") -> str:
    """안전한 문자열 변환"""
    try:
        if x is None:
            return default
        return str(x)
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    """안전한 float 변환 (네이티브 변환 우선, pandas fallback)"""
    if x is None:
        return float(default)
    if isinstance(x, (int, float)):
        return x if math.isfinite(x) else float(default)
    try:
        fv = float(x)
        return fv if math.isfinite(fv) else float(default)
    except (ValueError, TypeError):
        pass
    try:
        v = pd.to_numeric(x, errors="coerce")
        if pd.isna(v):
            return float(default)
        fv = float(v)
        return fv if math.isfinite(fv) else float(default)
    except Exception:
        return float(default)


def safe_int(x: Any, default: int = 0) -> int:
    """안전한 int 변환"""
    try:
        v = pd.to_numeric(x, errors="coerce")
        if pd.isna(v):
            return int(default)
        return int(round(float(v)))
    except Exception:
        return int(default)


def json_sanitize(obj: Any):
    """JSON 직렬화를 위한 객체 변환"""
    if obj is None:
        return None

    if isinstance(obj, (bool, int, str)):
        return obj

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    if isinstance(obj, (np.generic,)):
        try:
            return json_sanitize(obj.item())
        except Exception:
            return None

    if isinstance(obj, (pd.Timestamp,)):
        if pd.isna(obj):
            return None
        return obj.isoformat()

    if isinstance(obj, (np.ndarray,)):
        return [json_sanitize(x) for x in obj.tolist()]

    if isinstance(obj, pd.Series):
        return {str(k): json_sanitize(v) for k, v in obj.to_dict().items()}

    if isinstance(obj, pd.DataFrame):
        return [json_sanitize(x) for x in obj.to_dict("records")]

    if isinstance(obj, dict):
        return {str(k): json_sanitize(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [json_sanitize(x) for x in obj]

    try:
        return json_sanitize(vars(obj))
    except Exception:
        return str(obj)


def format_exception(e: Exception) -> Dict[str, Any]:
    """예외를 딕셔너리로 변환"""
    return {"type": type(e).__name__, "message": safe_str(e)}


def format_openai_error(e: Exception) -> Dict[str, Any]:
    """OpenAI 에러를 딕셔너리로 변환"""
    err = {"type": type(e).__name__, "message": str(e)}
    try:
        resp = getattr(e, "response", None)
        if resp is not None:
            err["status_code"] = getattr(resp, "status_code", None)
            err["response_text"] = getattr(resp, "text", None)
    except Exception:
        pass
    return err


def normalize_model_name(model_name: str) -> str:
    """모델명 정규화"""
    m = safe_str(model_name).strip()
    ml = m.lower().replace(" ", "")
    if ml in ("gpt4", "gpt-4", "gpt-4-turbo", "gpt-4turbo", "gpt-4.0", "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"):
        if ml in ("gpt4", "gpt-4", "gpt-4-turbo", "gpt-4turbo", "gpt-4.0"):
            return "gpt-4o-mini"
        return m
    if ml.startswith("gpt-4"):
        return m
    return "gpt-4o-mini"


# ============================================================
# ID 추출 유틸리티
# ============================================================
def extract_line_id(text: str) -> Optional[str]:
    """텍스트에서 생산라인 ID를 추출합니다 (LINE0001 ~ LINE000001 형식, 1~6자리)."""
    if not text:
        return None
    match = re.search(r'LINE\d{1,6}', text.upper())
    return match.group() if match else None


def extract_equipment_id(text: str) -> Optional[str]:
    """텍스트에서 설비 ID를 추출합니다 (EQP0001 형식, 4~6자리)."""
    if not text:
        return None
    match = re.search(r'EQP\d{4,6}', text.upper())
    return match.group() if match else None


def extract_work_order_id(text: str) -> Optional[str]:
    """텍스트에서 작업지시 ID를 추출합니다 (WO0001 형식, 4~8자리)."""
    if not text:
        return None
    match = re.search(r'WO\d{4,8}', text.upper())
    return match.group() if match else None


def get_yield_r2() -> Optional[float]:
    """수율 예측 모델 R2 스코어 반환 (yield_model_config.json)"""
    import json as _json
    from pathlib import Path
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "yield_model_config.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
            return cfg.get("r2_score")
    except Exception:
        pass
    return None
