"""
스마트팩토리 AI 플랫폼 - 전역 상태 관리
================================
제조 AI 기반 스마트팩토리 시스템 개발 프로젝트

모든 공유 가변 상태를 한 곳에서 관리합니다.
"""
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Any, Optional
from threading import Lock

import pandas as pd

# ============================================================
# DataFrame 메모리 최적화
# ============================================================
def _optimize_df_memory(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame 메모리 최적화 — object→category, int64→int32, float64→float32"""
    for col in df.columns:
        col_type = df[col].dtype
        if col_type == 'object':
            nunique = df[col].nunique()
            if nunique / len(df) < 0.5:  # 유니크 비율 50% 미만이면 category
                df[col] = df[col].astype('category')
        elif col_type == 'int64':
            if df[col].min() >= -2147483648 and df[col].max() <= 2147483647:
                df[col] = df[col].astype('int32')
        elif col_type == 'float64':
            df[col] = df[col].astype('float32')
    return df

# ============================================================
# 경로
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = Path(BASE_DIR)  # Path 객체 (routes.py에서 / 연산자 사용용)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "backend.log")

# ============================================================
# 로깅
# ============================================================
_logging_initialized = False

def setup_logging() -> logging.Logger:
    """로깅 초기화 (싱글톤 — 중복 호출 시 기존 로거 반환)"""
    global _logging_initialized
    lg = logging.getLogger("smartfactory-ai")
    if _logging_initialized:
        return lg
    _logging_initialized = True

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8", delay=True),
        ],
        force=True,
    )
    lg.setLevel(logging.INFO)
    lg.propagate = True
    for uvn in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        ul = logging.getLogger(uvn)
        ul.setLevel(logging.INFO)
        ul.propagate = True
    # pdfminer 경고 숨기기
    for pdflogger in ("pdfminer", "pdfminer.pdffont", "pdfminer.pdfinterp", "pdfminer.pdfpage"):
        logging.getLogger(pdflogger).setLevel(logging.ERROR)
    lg.info("LOGGER_READY log_file=%s", LOG_FILE)
    return lg

logger = setup_logging()

# ============================================================
# 사용자 DB (메모리)
# ============================================================
USERS: Dict[str, Dict[str, str]] = {
    "admin": {"password": "admin123", "role": "관리자", "name": "관리자"},
    "user": {"password": "user123", "role": "사용자", "name": "사용자"},
    "operator": {"password": "oper123", "role": "운영자", "name": "운영자"},
    "analyst": {"password": "analyst123", "role": "분석가", "name": "분석가"},
}

# ============================================================
# 스마트팩토리 제조 데이터프레임
# ============================================================
# 설비 데이터
EQUIPMENT_DF: Optional[pd.DataFrame] = None

# 설비 유형 데이터
EQUIPMENT_TYPES_DF: Optional[pd.DataFrame] = None

# 정비 서비스 데이터
MAINTENANCE_SERVICES_DF: Optional[pd.DataFrame] = None

# 부품/자재 데이터
PRODUCTS_DF: Optional[pd.DataFrame] = None

# 생산라인 데이터
PRODUCTION_LINES_DF: Optional[pd.DataFrame] = None

# 운영 로그 데이터
OPERATION_LOGS_DF: Optional[pd.DataFrame] = None

# 생산라인 분석 데이터
LINE_ANALYTICS_DF: Optional[pd.DataFrame] = None

# ============================================================
# 분석용 추가 데이터프레임
# ============================================================
# 설비별 성과 KPI
EQUIPMENT_PERFORMANCE_DF: Optional[pd.DataFrame] = None

# 일별 생산 지표 (OEE, 가동설비, 작업지시수 등)
DAILY_PRODUCTION_DF: Optional[pd.DataFrame] = None

# 정비 통계
MAINTENANCE_STATS_DF: Optional[pd.DataFrame] = None

# 작업지시 원문 (임베딩/클러스터링용)
WORK_ORDERS_DF: Optional[pd.DataFrame] = None

# 불량 상세 데이터
DEFECT_DETAILS_DF: Optional[pd.DataFrame] = None

# 설비 라이프사이클 데이터
EQUIPMENT_LIFECYCLE_DF: Optional[pd.DataFrame] = None

# 생산 퍼널 데이터
PRODUCTION_FUNNEL_DF: Optional[pd.DataFrame] = None

# 설비 일별 활동 데이터
EQUIPMENT_ACTIVITY_DF: Optional[pd.DataFrame] = None

# ============================================================
# ML 모델
# ============================================================
SELECTED_MODELS_FILE = os.path.join(BASE_DIR, "selected_models.json")
SELECTED_MODELS: Dict[str, str] = {}

def save_selected_models() -> bool:
    """선택된 모델 상태를 JSON 파일에 저장"""
    try:
        with open(SELECTED_MODELS_FILE, "w", encoding="utf-8") as f:
            json.dump(SELECTED_MODELS, f, ensure_ascii=False, indent=2)
        logger.info(f"선택된 모델 상태 저장 완료: {SELECTED_MODELS}")
        return True
    except Exception as e:
        logger.error(f"선택된 모델 상태 저장 실패: {e}")
        return False

_selected_models_loaded = False

def load_selected_models() -> Dict[str, str]:
    """저장된 모델 선택 상태 로드 (1회 캐시 — 이미 로드된 경우 디스크 I/O 스킵)"""
    global SELECTED_MODELS, _selected_models_loaded
    if _selected_models_loaded and SELECTED_MODELS:
        return SELECTED_MODELS
    try:
        if os.path.exists(SELECTED_MODELS_FILE):
            with open(SELECTED_MODELS_FILE, "r", encoding="utf-8") as f:
                SELECTED_MODELS = json.load(f)
                _selected_models_loaded = True
                logger.info(f"선택된 모델 상태 로드 완료: {SELECTED_MODELS}")
                return SELECTED_MODELS
    except Exception as e:
        logger.warning(f"선택된 모델 상태 로드 실패: {e}")
    _selected_models_loaded = True
    return {}

# ── 핵심 6개 모델 (리팩토링) ──
# 정비 응답 품질 예측 모델
MAINTENANCE_QUALITY_MODEL: Optional[Any] = None

# 고장 자동 분류 모델 (TF-IDF + RF)
FAULT_CLASSIFICATION_MODEL: Optional[Any] = None

# 설비 클러스터 모델 (K-Means)
EQUIPMENT_CLUSTER_MODEL: Optional[Any] = None

# 불량 탐지 모델 (Isolation Forest)
DEFECT_DETECTION_MODEL: Optional[Any] = None

# 설비 고장 예측 모델 (RandomForest + SHAP)
EQUIPMENT_FAILURE_MODEL: Optional[Any] = None

# SHAP Explainer (고장 예측용)
SHAP_EXPLAINER_FAILURE: Optional[Any] = None

# 고장 예측 모델 설정
FAILURE_MODEL_CONFIG: Optional[Dict[str, Any]] = None

# ── 신규 2개 모델 ──
# 수율 예측 모델 (LightGBM)
YIELD_PREDICTION_MODEL: Optional[Any] = None

# 설비 RUL 예측 모델 (GradientBoosting)
EQUIPMENT_RUL_MODEL: Optional[Any] = None

# ── 공용 모델 도구 ──
# TF-IDF 벡터라이저 (고장 분류용)
TFIDF_VECTORIZER: Optional[Any] = None

# 스케일러 (설비 클러스터용)
SCALER_CLUSTER: Optional[Any] = None

# 생산 최적화 모듈 사용 가능 여부
PRODUCTION_OPTIMIZER_AVAILABLE: bool = False

# ============================================================
# ML 모델 Lazy Loading (Railway 메모리 최적화)
# ============================================================
# 모델 이름 → pkl 파일 매핑 (lazy loading에 사용)
_MODEL_FILE_MAP: Dict[str, str] = {
    "MAINTENANCE_QUALITY_MODEL": "model_maintenance_quality.pkl",
    "FAULT_CLASSIFICATION_MODEL": "model_fault_classification.pkl",
    "EQUIPMENT_CLUSTER_MODEL": "model_equipment_cluster.pkl",
    "DEFECT_DETECTION_MODEL": "model_defect_detection.pkl",
    "EQUIPMENT_FAILURE_MODEL": "model_equipment_failure.pkl",
    "SHAP_EXPLAINER_FAILURE": "shap_explainer_failure.pkl",
    "YIELD_PREDICTION_MODEL": "model_yield_prediction.pkl",
    "EQUIPMENT_RUL_MODEL": "model_equipment_rul.pkl",
    "TFIDF_VECTORIZER": "tfidf_vectorizer.pkl",
    "SCALER_CLUSTER": "scaler_cluster.pkl",
}

# lazy loading 활성화 여부 (load_all_data가 모델을 로드했으면 False)
_LAZY_LOADING_ENABLED: bool = True
_MODEL_LOAD_LOCK = Lock()

# 로드 시도 실패 기록 (반복 로드 방지)
_MODEL_LOAD_FAILED: set = set()


def get_model(attr_name: str) -> Optional[Any]:
    """ML 모델 lazy getter — 첫 접근 시 디스크에서 로드

    이미 로드된 모델(setattr로 세팅된 경우)이 있으면 그대로 반환.
    아직 로드되지 않았으면 pkl 파일에서 로드 후 전역 변수에 캐시.
    """
    # 이미 로드된 모델이 있으면 반환
    current = globals().get(attr_name)
    if current is not None:
        return current

    # lazy loading 비활성화 상태면 None 반환 (이미 시도 완료)
    if not _LAZY_LOADING_ENABLED:
        return None

    # 로드 실패 기록이 있으면 재시도하지 않음
    if attr_name in _MODEL_LOAD_FAILED:
        return None

    filename = _MODEL_FILE_MAP.get(attr_name)
    if not filename:
        return None

    with _MODEL_LOAD_LOCK:
        # 더블체크 (다른 스레드가 이미 로드했을 수 있음)
        current = globals().get(attr_name)
        if current is not None:
            return current

        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            logger.warning("LAZY_LOAD 파일 없음: %s", filepath)
            _MODEL_LOAD_FAILED.add(attr_name)
            return None

        try:
            import joblib
            model = joblib.load(filepath)
            globals()[attr_name] = model
            logger.info("LAZY_LOAD 모델 로드 완료: %s ← %s", attr_name, filename)
            return model
        except Exception as e:
            logger.error("LAZY_LOAD 모델 로드 실패: %s - %s", attr_name, e)
            _MODEL_LOAD_FAILED.add(attr_name)
            return None

# ============================================================
# 라벨 인코더
# ============================================================
LE_WORK_ORDER_CATEGORY: Optional[Any] = None   # 작업지시 카테고리
LE_EQUIPMENT_GRADE: Optional[Any] = None        # 설비 등급
LE_MAINTENANCE_PRIORITY: Optional[Any] = None   # 정비 우선순위
LE_FAULT_CATEGORY: Optional[Any] = None         # 고장 분류 카테고리

# ============================================================
# 캐시
# ============================================================
# 설비별 정비 서비스 매핑
EQUIPMENT_SERVICE_MAP: Dict[str, Dict[str, Any]] = {}

# 설비별 성과 KPI 캐시 (equipment_id → {col: val, ...})
EQUIPMENT_PERF_MAP: Dict[str, Dict] = {}

# ============================================================
# 정비 작업 큐
# ============================================================
MAINTENANCE_QUEUE: List[Dict[str, Any]] = []
MAINTENANCE_LOCK = Lock()

# ============================================================
# 시스템 상태
# ============================================================
SYSTEM_STATUS = {
    "initialized": False,
    "data_loaded": False,
    "models_loaded": False,
    "startup_time": 0.0,
    "last_error": "",
}

# ============================================================
# FMCS 스탠드 제어
# ============================================================
OPERATION_MODE: str = "ai_auto"  # "ai_auto" | "manual"

# 앙상블 가중치 (모델 관리용)
ENSEMBLE_WEIGHTS: Dict[str, float] = {"xgboost": 0.4, "lightgbm": 0.35, "rf": 0.25}
