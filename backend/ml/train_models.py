"""
제조 AI 솔루션 - 데이터 생성 및 모델 학습
==========================================
스마트팩토리 AI 플랫폼

구조:
  PART 1: 설정 및 환경
  PART 2: 데이터 생성 (제조 도메인 CSV)
  PART 3: 모델 학습 (11개 ML 모델)
  PART 4: 저장 및 테스트
"""

# ============================================================================
# PART 1: 설정 및 환경
# ============================================================================
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import re
import logging

import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
    IsolationForest,
    GradientBoostingRegressor,
    GradientBoostingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    f1_score,
    silhouette_score,
    mean_absolute_error,
    r2_score,
)
from sklearn.cluster import KMeans, DBSCAN
import joblib
import warnings

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

np.random.seed(42)
rng = np.random.default_rng(42)

# MLflow 설정 (선택적) - 직접 실행 시에만 초기화
MLFLOW_AVAILABLE = False
try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    pass

if __name__ == "__main__" and MLFLOW_AVAILABLE:
    MLFLOW_TRACKING_URI = "file:./mlruns"
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    EXPERIMENT_NAME = "smart-factory-ai"
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        mlflow.create_experiment(EXPERIMENT_NAME)
    mlflow.set_experiment(EXPERIMENT_NAME)
    print(f"MLflow Tracking URI: {MLFLOW_TRACKING_URI}")
    print(f"MLflow Experiment: {EXPERIMENT_NAME}")
elif __name__ == "__main__" and not MLFLOW_AVAILABLE:
    print("MLflow 미설치 - 실험 추적을 건너뜁니다")

# LightGBM (수율 예측용)
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

# XGBoost (생산량 예측용)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

# SHAP
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

# 저장 경로
try:
    BACKEND_DIR = Path(__file__).parent.parent
except NameError:
    BACKEND_DIR = Path.cwd()
    if BACKEND_DIR.name == "ml":
        BACKEND_DIR = BACKEND_DIR.parent
    elif "backend" in str(BACKEND_DIR).lower():
        pass
    else:
        BACKEND_DIR = Path.cwd()

BACKEND_DIR.mkdir(parents=True, exist_ok=True)

reference_date = pd.to_datetime("2025-01-15")

# --------------------------------------------------------------------------
# 제조 도메인 상수 데이터
# --------------------------------------------------------------------------
# 설비 등급
EQUIPMENT_GRADES = ["A", "B", "C", "D"]
EQUIPMENT_GRADE_WEIGHTS = [0.25, 0.35, 0.30, 0.10]
EQUIPMENT_GRADE_ENCODE = {"A": 3, "B": 2, "C": 1, "D": 0}

# 설비 유형
EQUIPMENT_TYPES = ["CNC", "프레스", "사출", "용접", "조립", "도장", "검사", "포장"]
EQUIPMENT_TYPES_EN = ["CNC", "Press", "Injection", "Welding", "Assembly", "Painting", "Inspection", "Packaging"]

# 공장 위치 / 부서
LOCATIONS = ["A동", "B동", "C동", "D동", "E동", "F동", "G동", "H동"]
LOCATION_WEIGHTS = [0.20, 0.18, 0.15, 0.13, 0.10, 0.10, 0.08, 0.06]
DEPARTMENTS = ["생산1팀", "생산2팀", "생산3팀", "품질관리팀", "설비관리팀", "자동화팀"]

# 설비별 부품/자재
CNC_PARTS = [
    "스핀들 모터", "볼스크류", "리니어 가이드", "서보 드라이버", "쿨런트 펌프",
    "척 클램프", "터릿 유닛", "ATC 매거진", "방진 커버", "절삭유 필터",
    "인코더 센서", "유압 유닛", "칩 컨베이어", "주축 베어링", "이송축 커플링",
]
PRESS_PARTS = [
    "크랭크 샤프트", "슬라이드 가이드", "클러치 브레이크", "다이 쿠션", "볼스터 플레이트",
    "유압 실린더", "에어 밸브", "금형 클램프", "안전장치 센서", "슬라이드 조절기",
    "플라이휠 베어링", "커넥팅 로드", "기어 트레인", "오일 펌프", "백래시 보정기",
]
INJECTION_PARTS = [
    "사출 스크류", "가열 실린더", "노즐 히터", "금형 냉각채널", "이젝터 핀",
    "호퍼 드라이어", "유압 밸브", "형체력 실린더", "온도 센서", "사출 압력게이지",
    "체크 밸브", "배럴 히터밴드", "타이바 가이드", "형개폐 모터", "로봇 취출기",
]
WELDING_PARTS = [
    "용접 토치", "와이어 피더", "가스 레귤레이터", "냉각수 순환기", "전극 홀더",
    "지그 클램프", "아크 센서", "용접 변압기", "실드 가스 노즐", "접지 클램프",
    "용접 케이블", "와이어 교정기", "흄 집진기", "용접 로봇암", "시임 트래커",
]
GENERAL_PARTS = [
    "컨베이어 벨트", "모터 드라이버", "PLC 컨트롤러", "센서 모듈", "에어 컴프레서",
    "감속기 기어", "커플링 유닛", "베어링 유닛", "유압 호스", "전자 밸브",
    "터치 패널", "인버터", "서보 모터", "릴레이 모듈", "안전 스위치",
]

PARTS_MAP = {
    "CNC": CNC_PARTS,
    "프레스": PRESS_PARTS,
    "사출": INJECTION_PARTS,
    "용접": WELDING_PARTS,
    "조립": GENERAL_PARTS,
    "도장": GENERAL_PARTS,
    "검사": GENERAL_PARTS,
    "포장": GENERAL_PARTS,
}

# 설비 이름 생성용
EQUIPMENT_NAME_PREFIXES = {
    "CNC": ["정밀", "고속", "복합", "5축", "자동"],
    "프레스": ["유압", "서보", "기계식", "고속", "대형"],
    "사출": ["전동", "유압", "하이브리드", "정밀", "고속"],
    "용접": ["로봇", "자동", "레이저", "아크", "스팟"],
    "조립": ["자동", "반자동", "로봇", "정밀", "고속"],
    "도장": ["자동", "정전", "분체", "UV", "에어"],
    "검사": ["비전", "3D", "초음파", "X-ray", "레이저"],
    "포장": ["자동", "반자동", "진공", "수축", "라벨"],
}
EQUIPMENT_NAME_SUFFIXES = ["가공기", "성형기", "장치", "시스템", "머신", "유닛", "라인", "스테이션"]

# 고장 보고 텍스트 템플릿 (고장유형분류 모델용)
FAULT_REPORT_TEMPLATES = {
    "기계적": [
        "베어링에서 이상 소음이 발생합니다. 진동이 점점 심해지고 있어요.",
        "볼스크류 백래시가 커져서 가공 정밀도가 떨어집니다.",
        "스핀들 모터 회전 시 떨림이 심합니다. 밸런싱 조정이 필요합니다.",
        "기어 마모로 이송 속도가 불균일합니다. 교체 부탁드립니다.",
        "유압 실린더에서 오일 누유가 발생합니다. 씰 교체 필요.",
        "축 정렬이 틀어져서 제품 치수 불량이 발생합니다.",
        "체인 늘어남으로 컨베이어 속도가 불안정합니다.",
        "캠 마모로 프레스 타이밍이 어긋납니다.",
        "가이드 레일 손상으로 슬라이드 이동이 부드럽지 않습니다.",
        "크랭크 샤프트 베어링에서 고온이 감지됩니다.",
    ],
    "전기적": [
        "서보 드라이버 과전류 알람이 자주 발생합니다.",
        "전원 공급 장치에서 전압 불안정 현상이 있습니다.",
        "인코더 신호가 간헐적으로 끊깁니다. 케이블 확인 필요.",
        "PLC 통신 에러가 반복됩니다. 모듈 교체 필요한지 확인해주세요.",
        "모터 과열 경고가 자주 뜹니다. 냉각 팬 점검 필요.",
        "인버터에서 이상 알람이 발생하고 설비가 정지됩니다.",
        "접지 불량으로 노이즈가 발생하여 센서값이 불안정합니다.",
        "릴레이 접점 불량으로 간헐적 정지가 발생합니다.",
        "전선 피복이 손상되어 누전 위험이 있습니다.",
        "터치 패널 화면이 깜빡이고 입력이 안 됩니다.",
    ],
    "소프트웨어": [
        "NC 프로그램 로딩 에러가 발생합니다. 메모리 부족 의심.",
        "HMI 화면이 프리즈되어 조작이 불가합니다.",
        "자동 운전 중 원점 복귀 오류가 발생합니다.",
        "데이터 백업 실패 알람이 계속 뜹니다.",
        "레시피 변경 후 파라미터가 저장되지 않습니다.",
        "통신 프로토콜 에러로 상위 시스템 연결이 끊깁니다.",
        "소프트웨어 버전 충돌로 특정 기능이 작동하지 않습니다.",
        "로그 데이터가 기록되지 않아 이력 추적이 불가합니다.",
        "자동 보정 기능이 정상 작동하지 않습니다.",
        "알람 이력이 초기화되어 과거 데이터를 볼 수 없습니다.",
    ],
    "유압": [
        "유압 펌프 압력이 설정값까지 올라가지 않습니다.",
        "유압 호스에서 오일 누유가 심합니다. 즉시 교체 필요.",
        "어큐뮬레이터 압력이 자주 떨어집니다. 가스 충전 필요.",
        "유압 밸브 작동이 느려서 사이클 타임이 길어졌습니다.",
        "유압 오일 온도가 비정상적으로 높습니다. 쿨러 점검 필요.",
        "유압 필터 막힘 알람이 자주 발생합니다.",
        "형체력이 부족하여 금형이 벌어집니다.",
        "유압 실린더 속도가 불균일합니다. 유량 조절 밸브 확인.",
        "오일 탱크 유면이 낮아졌습니다. 누유 점검 필요.",
        "유압 모터에서 이상 소음이 발생합니다.",
    ],
    "공압": [
        "에어 실린더 작동이 느립니다. 에어 압력 확인 필요.",
        "공압 밸브에서 에어 누출이 발생합니다.",
        "에어 드라이어 수분 제거가 안 되어 라인에 물이 들어갑니다.",
        "레귤레이터 압력 설정이 자꾸 변합니다.",
        "에어 블로어 풍량이 부족합니다. 필터 청소 필요.",
        "공압 라인 이음부에서 에어 누출 소리가 납니다.",
        "실린더 쿠션 조절이 안 되어 충격이 큽니다.",
        "에어 호스가 노후되어 파열 위험이 있습니다.",
        "FRL 유닛 오일 보충이 필요합니다.",
        "공압 센서 오작동으로 부품 감지가 안 됩니다.",
    ],
}

# 작업자 피드백 텍스트 (감성분석 모델용)
FEEDBACK_TEMPLATES_POSITIVE = [
    "설비 상태가 좋아서 작업이 순조롭습니다. 가동률도 높아요.",
    "최근 정비 후 진동이 많이 줄었습니다. 잘 조치해주셨습니다.",
    "새로운 작업 표준서 덕분에 불량률이 크게 감소했습니다.",
    "안전 교육 후 작업 환경이 개선되었습니다. 감사합니다.",
    "자동화 라인 도입 후 생산성이 크게 향상되었습니다.",
    "공구 관리 시스템이 편리해져서 교체 시간이 단축되었습니다.",
    "설비 정비 일정이 잘 관리되어 고장이 줄었습니다.",
    "작업 환경 개선(조명, 환기)으로 집중도가 높아졌습니다.",
    "품질 검사 장비 교체 후 정확도가 향상되었습니다.",
    "신규 지그 도입으로 셋업 시간이 절반으로 줄었습니다.",
    "에어컨 설치 후 여름철 작업 환경이 좋아졌습니다.",
    "안전 보호구 교체 후 작업이 편해졌습니다.",
    "설비 이상 조기 경보 시스템이 매우 유용합니다.",
    "라인 밸런싱 조정으로 대기 시간이 줄었습니다.",
    "MES 시스템 도입으로 실적 입력이 간편해졌습니다.",
]

FEEDBACK_TEMPLATES_NEGATIVE = [
    "설비 고장이 잦아서 생산 목표 달성이 어렵습니다.",
    "부품 교체를 요청했는데 조달이 너무 늦습니다.",
    "안전 장치가 자주 오작동하여 작업이 중단됩니다.",
    "작업장 온도가 너무 높아 집중하기 어렵습니다.",
    "야간 교대 시 조명이 부족합니다. 개선 요청합니다.",
    "불량률이 높아서 재작업이 많습니다. 원인 분석 필요.",
    "정비 요청 후 응답이 너무 느립니다.",
    "공구 마모가 심한데 교체 주기가 너무 깁니다.",
    "소음이 너무 심해서 귀마개를 해도 힘듭니다.",
    "자재 입고가 지연되어 라인 가동이 중단됩니다.",
    "설비 매뉴얼이 구버전이라 참고하기 어렵습니다.",
    "쿨런트 관리가 안 되어 가공면이 거칠어졌습니다.",
    "측정 장비 교정이 안 되어 있어 품질 이슈가 있습니다.",
    "교대 인수인계가 부실하여 문제가 반복됩니다.",
    "안전 통로가 자재로 막혀있어 위험합니다.",
]

FEEDBACK_TEMPLATES_NEUTRAL = [
    "오늘도 정상 가동 중입니다. 특별한 이상 없습니다.",
    "생산 실적은 목표치와 비슷합니다. 평균적인 상태입니다.",
    "설비 상태 보통입니다. 큰 문제는 없으나 개선 여지 있습니다.",
    "작업 환경은 보통입니다. 특별히 좋지도 나쁘지도 않습니다.",
    "금일 교대 작업 평이하게 진행 중입니다.",
    "정기 점검 결과 특이사항 없습니다.",
    "생산 속도는 표준 수준입니다. 무난합니다.",
    "자재 입고 일정대로 진행 중입니다.",
    "품질 검사 합격률 정상 범위입니다.",
    "안전 점검 완료. 지적 사항 없습니다.",
]

# 플랫폼 문서 데이터 (용어집/가이드)
PLATFORM_DOCS_DATA = [
    {"doc_id": "DOC001", "title": "설비 예방정비 가이드", "category": "정비",
     "content_ko": "설비의 예방정비는 일상점검, 주간점검, 월간점검, 연간점검으로 구분됩니다. 일상점검은 매일 작업 시작 전 설비 외관, 이상 소음, 오일 레벨 등을 확인합니다."},
    {"doc_id": "DOC002", "title": "센서 데이터 수집 체계", "category": "센서",
     "content_ko": "설비에 부착된 진동, 온도, 압력, 전류, 습도 센서의 데이터는 실시간으로 수집됩니다. 이상 임계값 초과 시 자동 알람이 발생합니다."},
    {"doc_id": "DOC003", "title": "불량 관리 프로세스", "category": "품질",
     "content_ko": "불량 발생 시 즉시 라인 정지 후 원인 분석을 실시합니다. 불량 유형별 대응 매뉴얼에 따라 조치하고 재발 방지 대책을 수립합니다."},
    {"doc_id": "DOC004", "title": "고장 대응 절차", "category": "정비",
     "content_ko": "고장 발생 시 작업지시서를 발행하고 심각도에 따라 우선순위를 결정합니다. 경미한 고장은 현장 정비, 심각한 고장은 전문 정비팀이 대응합니다."},
    {"doc_id": "DOC005", "title": "OEE 산출 기준", "category": "생산",
     "content_ko": "OEE(종합설비효율)는 가동률 x 성능률 x 양품률로 계산됩니다. 목표 OEE는 85% 이상이며, 월별 추이를 모니터링합니다."},
    {"doc_id": "DOC006", "title": "공정 파라미터 관리", "category": "품질",
     "content_ko": "각 공정의 온도, 압력, 속도, 이송률 등 핵심 파라미터는 표준 범위 내에서 관리됩니다. 파라미터 변경 시 품질팀 승인이 필요합니다."},
    {"doc_id": "DOC007", "title": "자재 및 부품 관리", "category": "자재",
     "content_ko": "예비 부품은 A/B/C 등급으로 분류하여 관리합니다. A등급 부품은 안전 재고를 유지하고, 조달 리드타임을 고려하여 발주합니다."},
    {"doc_id": "DOC008", "title": "안전 작업 지침", "category": "안전",
     "content_ko": "설비 운전 중에는 반드시 안전 보호구를 착용합니다. LOTO(잠금/태그) 절차에 따라 정비 작업 시 에너지원을 차단합니다."},
    {"doc_id": "DOC009", "title": "설비 데이터 분석 가이드", "category": "분석",
     "content_ko": "설비 가동 데이터, 센서 데이터, 정비 이력을 종합 분석하여 설비 건강도를 평가합니다. AI 모델을 활용한 예지정비를 실시합니다."},
    {"doc_id": "DOC010", "title": "MES 연동 가이드", "category": "시스템",
     "content_ko": "MES(Manufacturing Execution System)와 연동하여 실시간 생산 현황, 품질 데이터, 설비 상태를 모니터링합니다."},
    {"doc_id": "DOC011", "title": "설비 등급 기준", "category": "설비",
     "content_ko": "A등급은 최신 설비(5년 이내), B등급은 정상 설비(5~10년), C등급은 노후 설비(10~15년), D등급은 교체 대상(15년 이상)입니다."},
    {"doc_id": "DOC012", "title": "에너지 관리 가이드", "category": "에너지",
     "content_ko": "설비별 에너지 사용량을 모니터링하고 비가동 시 대기전력을 줄입니다. 에너지 효율 목표를 설정하고 월별 달성률을 관리합니다."},
]

# 제조 용어 사전
MANUFACTURING_GLOSSARY = [
    {"term_ko": "OEE", "term_en": "Overall Equipment Effectiveness", "definition": "종합설비효율. 가동률 × 성능률 × 양품률로 산출", "category": "생산"},
    {"term_ko": "MTBF", "term_en": "Mean Time Between Failures", "definition": "평균고장간격. 고장과 고장 사이의 평균 가동 시간", "category": "정비"},
    {"term_ko": "MTTR", "term_en": "Mean Time To Repair", "definition": "평균수리시간. 고장 발생 후 복구까지 소요되는 평균 시간", "category": "정비"},
    {"term_ko": "RUL", "term_en": "Remaining Useful Life", "definition": "잔여수명. 설비가 고장 없이 가동 가능한 예상 잔여 시간", "category": "예지정비"},
    {"term_ko": "불량률", "term_en": "Defect Rate", "definition": "전체 생산량 대비 불량품 수의 비율", "category": "품질"},
    {"term_ko": "수율", "term_en": "Yield Rate", "definition": "양품 비율. 전체 생산량 대비 양품 수의 비율", "category": "품질"},
    {"term_ko": "사이클타임", "term_en": "Cycle Time", "definition": "한 개 제품을 생산하는 데 소요되는 시간", "category": "생산"},
    {"term_ko": "다운타임", "term_en": "Downtime", "definition": "설비가 정지되어 생산이 불가능한 시간", "category": "생산"},
    {"term_ko": "예지정비", "term_en": "Predictive Maintenance", "definition": "센서 데이터와 AI를 활용하여 고장을 사전에 예측하고 정비하는 방식", "category": "정비"},
    {"term_ko": "TPM", "term_en": "Total Productive Maintenance", "definition": "전원참여 생산보전. 모든 구성원이 참여하는 설비 관리 활동", "category": "정비"},
    {"term_ko": "FMEA", "term_en": "Failure Mode and Effects Analysis", "definition": "고장 모드 및 영향 분석. 잠재적 고장을 사전에 식별하고 대응", "category": "품질"},
    {"term_ko": "SPC", "term_en": "Statistical Process Control", "definition": "통계적 공정 관리. 공정 데이터를 통계적으로 분석하여 품질 관리", "category": "품질"},
    {"term_ko": "LOTO", "term_en": "Lock Out Tag Out", "definition": "잠금/태그 절차. 정비 작업 시 에너지원 차단 안전 절차", "category": "안전"},
    {"term_ko": "MES", "term_en": "Manufacturing Execution System", "definition": "제조실행시스템. 생산 현장의 실시간 모니터링 및 관리 시스템", "category": "시스템"},
]


def generate_equipment_name(eq_type, idx):
    """설비명 생성"""
    prefixes = EQUIPMENT_NAME_PREFIXES.get(eq_type, ["범용"])
    prefix = rng.choice(prefixes)
    suffix = rng.choice(EQUIPMENT_NAME_SUFFIXES)
    return f"{prefix} {suffix}"


# ============================================================================
# 가드: 직접 실행(python train_models.py)할 때만 데이터 생성/모델 학습 실행
# 상수(EQUIPMENT_TYPES, EQUIPMENT_GRADES 등)와 함수(generate_equipment_name)는
# import 시에도 사용 가능합니다.
# ============================================================================
assert __name__ == "__main__", (
    "train_models.py는 직접 실행 전용 스크립트입니다. "
    "import하지 마세요. 상수가 필요하면 별도 모듈로 분리하세요."
)

print("=" * 70)
print("PART 1: 설정 완료")
print(f"  BACKEND_DIR: {BACKEND_DIR}")
print("=" * 70)
print("\n" + "=" * 70)
print("PART 2: 데이터 생성 (제조 도메인)")
print("=" * 70)


# ============================================================================
# PART 2: 데이터 생성 (제조 도메인 CSV)
# ============================================================================

# --------------------------------------------------------------------------
# 2.1 설비 마스터 데이터 (equipment.csv) - 300개 설비
# --------------------------------------------------------------------------
print("\n[2.1] 설비 마스터 데이터 생성")

equipment_data = []
for i in range(300):
    eq_id = f"EQ{i+1:04d}"
    eq_type = rng.choice(EQUIPMENT_TYPES, p=[0.18, 0.15, 0.14, 0.12, 0.12, 0.10, 0.10, 0.09])
    location = rng.choice(LOCATIONS, p=LOCATION_WEIGHTS)
    department = rng.choice(DEPARTMENTS)
    grade = rng.choice(EQUIPMENT_GRADES, p=EQUIPMENT_GRADE_WEIGHTS)
    installation_date = reference_date - timedelta(days=int(rng.integers(180, 5400)))

    # 설비 상태: 가동중, 정지, 정비중
    status_prob = rng.random()
    if status_prob < 0.75:
        status = "running"
    elif status_prob < 0.90:
        status = "idle"
    else:
        status = "maintenance"

    eq_name = generate_equipment_name(eq_type, i)
    operating_hours = int(rng.integers(500, 50000))

    equipment_data.append({
        "equipment_id": eq_id,
        "equipment_name": eq_name,
        "equipment_type": eq_type,
        "grade": grade,
        "location": location,
        "department": department,
        "installation_date": installation_date.strftime("%Y-%m-%d"),
        "operating_hours": operating_hours,
        "status": status,
    })

equipment_df = pd.DataFrame(equipment_data)
print(f"  - 설비: {len(equipment_df)}개 (running: {(equipment_df['status']=='running').sum()}, "
      f"idle: {(equipment_df['status']=='idle').sum()}, maintenance: {(equipment_df['status']=='maintenance').sum()})")


# --------------------------------------------------------------------------
# 2.2 설비 유형 마스터 (equipment_types.csv)
# --------------------------------------------------------------------------
print("\n[2.2] 설비 유형 마스터 생성")

eq_types_data = []
for idx, (ko, en) in enumerate(zip(EQUIPMENT_TYPES, EQUIPMENT_TYPES_EN)):
    eq_types_data.append({
        "type_id": f"TYPE{idx+1:03d}",
        "name_ko": ko,
        "name_en": en,
        "description_ko": f"{ko} 공정 설비. 해당 유형의 설비를 관리합니다.",
        "description_en": f"Equipment for {en} process.",
    })
eq_types_df = pd.DataFrame(eq_types_data)
print(f"  - 설비 유형: {len(eq_types_df)}개")


# --------------------------------------------------------------------------
# 2.3 부품/자재 데이터 (parts.csv)
# --------------------------------------------------------------------------
print("\n[2.3] 부품/자재 데이터 생성")

parts_data = []
part_idx = 0
for _, eq in equipment_df.iterrows():
    eq_type = eq["equipment_type"]
    n_parts = rng.integers(5, 15)
    parts_pool = PARTS_MAP.get(eq_type, GENERAL_PARTS)
    for j in range(n_parts):
        part_idx += 1
        pname = rng.choice(parts_pool) + f" {rng.choice(['A', 'B', 'C', 'S', 'X', 'Pro', 'Std', ''])}{rng.integers(1, 99)}"
        lifespan_hours = int(rng.integers(1000, 30000))

        status_r = rng.random()
        if status_r < 0.80:
            p_status = "정상"
        elif status_r < 0.92:
            p_status = "마모"
        else:
            p_status = "교체필요"

        parts_data.append({
            "part_id": f"PT{part_idx:05d}",
            "equipment_id": eq["equipment_id"],
            "part_name": pname.strip(),
            "lifespan_hours": lifespan_hours,
            "status": p_status,
            "equipment_type": eq_type,
        })

parts_df = pd.DataFrame(parts_data)
print(f"  - 부품: {len(parts_df)}개")


# --------------------------------------------------------------------------
# 2.4 센서 데이터 (sensor_readings.csv) - 설비별 센서값
# --------------------------------------------------------------------------
print("\n[2.4] 센서 데이터 생성")

sensor_data = []
for _, eq in equipment_df.iterrows():
    # 설비 상태에 따른 센서값 범위 조정
    if eq["status"] == "running":
        vib_base, temp_base, press_base, curr_base = 2.5, 45, 5.0, 15
    elif eq["status"] == "idle":
        vib_base, temp_base, press_base, curr_base = 0.5, 25, 1.0, 2
    else:  # maintenance
        vib_base, temp_base, press_base, curr_base = 4.0, 55, 3.0, 18

    # 등급에 따른 상태 보정
    grade_mult = {"A": 0.8, "B": 1.0, "C": 1.2, "D": 1.5}.get(eq["grade"], 1.0)

    sensor_data.append({
        "equipment_id": eq["equipment_id"],
        "vibration": round(float(np.clip(rng.normal(vib_base * grade_mult, 0.8), 0.1, 15.0)), 2),
        "temperature": round(float(np.clip(rng.normal(temp_base * grade_mult, 8), 15, 120)), 1),
        "pressure": round(float(np.clip(rng.normal(press_base, 1.2), 0.5, 15.0)), 2),
        "current": round(float(np.clip(rng.normal(curr_base * grade_mult, 3), 0.5, 50)), 1),
        "humidity": round(float(np.clip(rng.normal(55, 10), 20, 95)), 1),
    })

sensor_df = pd.DataFrame(sensor_data)
print(f"  - 센서 데이터: {len(sensor_df)}건")


# --------------------------------------------------------------------------
# 2.5 설비 분석 데이터 (equipment_analytics.csv)
# --------------------------------------------------------------------------
print("\n[2.5] 설비 분석 데이터 생성")

equipment_analytics_data = []
for _, eq in equipment_df.iterrows():
    days_since_install = (reference_date - pd.to_datetime(eq["installation_date"])).days
    grade_encoded = EQUIPMENT_GRADE_ENCODE.get(eq["grade"], 0)

    # 센서값 가져오기
    sensor_row = sensor_df[sensor_df["equipment_id"] == eq["equipment_id"]].iloc[0]

    fault_count = int(rng.integers(0, max(1, eq["operating_hours"] // 2000)))
    downtime_hours = round(float(np.clip(
        rng.exponential(fault_count * 2) + 0.5, 0, 200
    )), 1)
    mtbf = round(eq["operating_hours"] / max(1, fault_count), 1)
    mttr = round(downtime_hours / max(1, fault_count), 1)

    equipment_analytics_data.append({
        "equipment_id": eq["equipment_id"],
        "equipment_type": eq["equipment_type"],
        "operating_hours": eq["operating_hours"],
        "fault_count": fault_count,
        "downtime_hours": downtime_hours,
        "mtbf": mtbf,
        "mttr": mttr,
        "vibration": sensor_row["vibration"],
        "temperature": sensor_row["temperature"],
        "pressure": sensor_row["pressure"],
        "current": sensor_row["current"],
        "days_since_install": days_since_install,
        "grade_encoded": grade_encoded,
        "cluster": -1,
        "failure_risk": -1,
        "failure_probability": -1.0,
    })

equipment_analytics_df = pd.DataFrame(equipment_analytics_data)
print(f"  - 설비 분석: {len(equipment_analytics_df)}개")


# --------------------------------------------------------------------------
# 2.6 생산 실적 데이터 (production.csv)
# --------------------------------------------------------------------------
print("\n[2.6] 생산 실적 데이터 생성")

production_data = []
for _, eq in equipment_df.iterrows():
    if eq["status"] == "running":
        daily_output = int(rng.integers(100, 500))
        defect_rate = round(float(rng.beta(2, 50)), 4)
    elif eq["status"] == "idle":
        daily_output = int(rng.integers(0, 50))
        defect_rate = round(float(rng.beta(2, 30)), 4)
    else:
        daily_output = 0
        defect_rate = 0.0

    defect_count = int(daily_output * defect_rate)
    cycle_time = round(float(np.clip(rng.normal(45, 10), 10, 120)), 1)
    oee = round(float(np.clip(rng.beta(8, 2) * 100, 30, 99)), 1)
    yield_rate = round(float(np.clip(1 - defect_rate, 0.80, 1.0) * 100), 1)

    production_data.append({
        "equipment_id": eq["equipment_id"],
        "line_id": f"LINE-{eq['location']}-{rng.integers(1, 5)}",
        "daily_output": daily_output,
        "defect_count": defect_count,
        "defect_rate": defect_rate,
        "cycle_time": cycle_time,
        "oee": oee,
        "yield_rate": yield_rate,
    })

production_df = pd.DataFrame(production_data)
print(f"  - 생산 실적: {len(production_df)}건")


# --------------------------------------------------------------------------
# 2.7 정비 이력 데이터 (maintenance.csv)
# --------------------------------------------------------------------------
print("\n[2.7] 정비 이력 데이터 생성")

FAULT_TYPES = ["기계적", "전기적", "소프트웨어", "유압", "공압"]
FAULT_TYPE_WEIGHTS = [0.30, 0.25, 0.15, 0.18, 0.12]
SEVERITIES = ["경미", "보통", "심각", "긴급"]
SEVERITY_WEIGHTS = [0.35, 0.35, 0.20, 0.10]

maintenance_data = []
maint_idx = 0
for _, eq in equipment_df.iterrows():
    n_records = rng.integers(2, 15)
    for _ in range(n_records):
        maint_idx += 1
        fault_type = rng.choice(FAULT_TYPES, p=FAULT_TYPE_WEIGHTS)
        severity = rng.choice(SEVERITIES, p=SEVERITY_WEIGHTS)

        response_time = round(float(np.clip(rng.exponential(2), 0.1, 24)), 1)
        repair_time = round(float(np.clip(rng.exponential(4), 0.5, 72)), 1)
        downtime = round(response_time + repair_time + rng.uniform(0, 2), 1)

        maint_date = reference_date - timedelta(days=int(rng.integers(0, 365)))

        maintenance_data.append({
            "work_order_id": f"WO{maint_idx:06d}",
            "equipment_id": eq["equipment_id"],
            "fault_type": fault_type,
            "severity": severity,
            "response_time": response_time,
            "repair_time": repair_time,
            "downtime": downtime,
            "maintenance_date": maint_date.strftime("%Y-%m-%d"),
            "technician_id": f"TECH{rng.integers(1, 20):03d}",
        })

maintenance_df = pd.DataFrame(maintenance_data)
print(f"  - 정비 이력: {len(maintenance_df)}건")


# --------------------------------------------------------------------------
# 2.8 운영 로그 데이터 (operation_logs.csv)
# --------------------------------------------------------------------------
print("\n[2.8] 운영 로그 데이터 생성")

OP_EVENT_TYPES = [
    "equipment_start", "equipment_stop", "alarm_triggered", "maintenance_request",
    "quality_check", "parameter_change", "shift_change", "material_loaded",
]
OP_EVENT_WEIGHTS = [0.20, 0.12, 0.18, 0.12, 0.15, 0.08, 0.08, 0.07]

op_logs_data = []
log_idx = 0
target_logs = 30000
logs_per_eq = target_logs // len(equipment_df)

for _, eq in equipment_df.iterrows():
    n_logs = min(logs_per_eq + rng.integers(-30, 30), 300)
    if eq["status"] == "maintenance":
        n_logs = max(20, n_logs // 3)
    elif eq["status"] == "idle":
        n_logs = max(30, n_logs // 2)

    install_d = pd.to_datetime(eq["installation_date"])
    active_span = max(1, (reference_date - install_d).days)

    for _ in range(n_logs):
        log_idx += 1
        evt = rng.choice(OP_EVENT_TYPES, p=OP_EVENT_WEIGHTS)
        evt_offset = int(rng.integers(0, min(active_span, 365)))
        evt_date = reference_date - timedelta(
            days=evt_offset,
            hours=int(rng.integers(0, 24)),
            minutes=int(rng.integers(0, 60)),
        )

        if evt == "alarm_triggered":
            detail = json.dumps({
                "alarm_type": rng.choice(["진동초과", "온도초과", "압력이상", "전류과부하", "비상정지"]),
                "severity": rng.choice(["warning", "critical", "info"]),
            }, ensure_ascii=False)
        elif evt == "maintenance_request":
            detail = json.dumps({
                "fault_type": rng.choice(FAULT_TYPES),
                "priority": rng.choice(["긴급", "높음", "보통", "낮음"]),
            }, ensure_ascii=False)
        elif evt == "quality_check":
            detail = json.dumps({
                "result": rng.choice(["합격", "불합격", "재검사"]),
                "defect_type": rng.choice(["치수불량", "외관불량", "기능불량", "없음"]),
            }, ensure_ascii=False)
        else:
            detail = "{}"

        op_logs_data.append({
            "log_id": f"LOG{log_idx:07d}",
            "equipment_id": eq["equipment_id"],
            "event_type": evt,
            "event_date": evt_date.strftime("%Y-%m-%d %H:%M:%S"),
            "details_json": detail,
        })
        if log_idx >= target_logs:
            break
    if log_idx >= target_logs:
        break

op_logs_df = pd.DataFrame(op_logs_data)
print(f"  - 운영 로그: {len(op_logs_df)}건")


# --------------------------------------------------------------------------
# 2.9 일별 공장 지표 (daily_metrics.csv) - 90일
# --------------------------------------------------------------------------
print("\n[2.9] 일별 공장 지표 생성")

daily_metrics_data = []
base_running = 225
base_output = 85000
for day in range(90):
    d = reference_date - timedelta(days=89 - day)
    weekend = 0.60 if d.weekday() >= 5 else 1.0  # 주말 가동률 감소
    running = int(base_running * weekend * rng.uniform(0.90, 1.05))
    total_output = int(base_output * weekend * rng.uniform(0.85, 1.15))
    total_defects = int(total_output * rng.uniform(0.01, 0.05))
    daily_metrics_data.append({
        "date": d.strftime("%Y-%m-%d"),
        "running_equipment": running,
        "total_output": total_output,
        "total_defects": total_defects,
        "avg_oee": round(float(rng.uniform(75, 95)), 1),
        "avg_cycle_time": round(float(rng.uniform(35, 55)), 1),
        "maintenance_requests": int(rng.integers(5, 30)),
        "maintenance_completed": int(rng.integers(3, 25)),
        "alarm_count": int(rng.integers(2, 20)),
        "energy_consumption_kwh": int(running * rng.uniform(50, 80)),
        "avg_yield_rate": round(float(rng.uniform(92, 99)), 1),
    })

daily_metrics_df = pd.DataFrame(daily_metrics_data)
print(f"  - 일별 지표: {len(daily_metrics_df)}일")


# --------------------------------------------------------------------------
# 2.10 정비 통계 (maintenance_stats.csv)
# --------------------------------------------------------------------------
print("\n[2.10] 정비 통계 데이터 생성")

maint_stats_data = []
for ft in FAULT_TYPES:
    maint_stats_data.append({
        "fault_type": ft,
        "total_cases": int(rng.integers(50, 500)),
        "avg_repair_hours": round(float(rng.uniform(1, 24)), 1),
        "avg_downtime_hours": round(float(rng.uniform(2, 48)), 1),
        "resolution_rate": round(float(np.clip(rng.normal(0.92, 0.05), 0.70, 1.0)), 4),
    })
maint_stats_df = pd.DataFrame(maint_stats_data)
print(f"  - 정비 통계: {len(maint_stats_df)}개 유형")


# --------------------------------------------------------------------------
# 2.11 이상 설비 상세 (anomaly_details.csv)
# --------------------------------------------------------------------------
print("\n[2.11] 이상 설비 상세 데이터 생성")

ANOMALY_TYPES = ["과진동", "과열", "압력이상", "전류과부하"]
anomaly_data = []
anomaly_equipment = rng.choice(
    equipment_df["equipment_id"].values, size=min(15, len(equipment_df)), replace=False
)
for eq_id in anomaly_equipment:
    anomaly_data.append({
        "equipment_id": eq_id,
        "anomaly_score": round(float(rng.uniform(0.6, 1.0)), 4),
        "anomaly_type": rng.choice(ANOMALY_TYPES),
        "detected_date": (reference_date - timedelta(days=int(rng.integers(0, 30)))).strftime("%Y-%m-%d"),
        "details": f"이상 패턴 감지: {rng.choice(['진동값 급증', '온도 이상 상승', '압력 불안정', '전류 과부하'])}",
    })
anomaly_detail_df = pd.DataFrame(anomaly_data)
print(f"  - 이상 설비 상세: {len(anomaly_detail_df)}건")


# --------------------------------------------------------------------------
# 2.12 설비 가동 추이 (equipment_uptime.csv)
# --------------------------------------------------------------------------
print("\n[2.12] 설비 가동 추이 데이터 생성")

uptime_months = ["2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"]
uptime_data = []
for m in uptime_months:
    w1 = round(float(np.clip(rng.normal(92, 3), 75, 99)), 1)
    w2 = round(float(np.clip(w1 * rng.uniform(0.95, 1.02), 75, 99)), 1)
    w4 = round(float(np.clip(w2 * rng.uniform(0.93, 1.01), 70, 99)), 1)
    oee_avg = round(float(np.clip(rng.normal(85, 5), 60, 98)), 1)
    uptime_data.append({
        "month": m,
        "week1_uptime": w1,
        "week2_uptime": w2,
        "week4_uptime": w4,
        "avg_oee": oee_avg,
    })
uptime_df = pd.DataFrame(uptime_data)
print(f"  - 설비 가동 추이: {len(uptime_df)}개월")

# 생산 퍼널 데이터 (월별)
production_funnel_data = []
for m in uptime_months:
    total_planned = int(rng.integers(80000, 120000))
    total_produced = int(total_planned * rng.uniform(0.85, 0.98))
    inspected = int(total_produced * rng.uniform(0.95, 1.0))
    passed = int(inspected * rng.uniform(0.92, 0.99))
    shipped = int(passed * rng.uniform(0.95, 1.0))
    production_funnel_data.append({
        "month": m,
        "planned": total_planned,
        "produced": total_produced,
        "inspected": inspected,
        "passed": passed,
        "shipped": shipped,
    })
production_funnel_df = pd.DataFrame(production_funnel_data)
print(f"  - 생산 퍼널: {len(production_funnel_df)}개월")


# --------------------------------------------------------------------------
# 2.13 설비 일별 가동 데이터 (equipment_daily.csv)
# --------------------------------------------------------------------------
print("\n[2.13] 설비 일별 가동 데이터 생성")

equipment_daily_data = []
for _, eq in equipment_df.iterrows():
    for day in range(90):
        d = reference_date - timedelta(days=89 - day)
        if eq["status"] == "maintenance" and rng.random() < 0.5:
            output = 0
            uptime_h = 0
            defects = 0
        elif eq["status"] == "idle":
            output = int(np.clip(rng.poisson(10), 0, 50))
            uptime_h = round(float(rng.uniform(0, 8)), 1)
            defects = int(rng.integers(0, max(1, output // 10)))
        else:
            activity_mult = 1.0 if d.weekday() < 5 else 0.3
            output = int(np.clip(rng.poisson(200 * activity_mult), 0, 600))
            uptime_h = round(float(np.clip(rng.normal(20 * activity_mult, 3), 0, 24)), 1)
            defects = int(rng.integers(0, max(1, int(output * 0.05))))

        equipment_daily_data.append({
            "equipment_id": eq["equipment_id"],
            "date": d.strftime("%Y-%m-%d"),
            "daily_output": output,
            "uptime_hours": uptime_h,
            "defect_count": defects,
            "energy_kwh": round(float(uptime_h * rng.uniform(3, 8)), 1),
        })

equipment_daily_df = pd.DataFrame(equipment_daily_data)
print(f"  - 설비 일별 가동: {len(equipment_daily_df)}건")


# --------------------------------------------------------------------------
# 2.14 플랫폼 문서 데이터
# --------------------------------------------------------------------------
print("\n[2.14] 플랫폼 문서 데이터 생성")

platform_docs_df = pd.DataFrame(PLATFORM_DOCS_DATA)
print(f"  - 플랫폼 문서: {len(platform_docs_df)}건")


# --------------------------------------------------------------------------
# 2.15 제조 용어 사전
# --------------------------------------------------------------------------
print("\n[2.15] 제조 용어 사전 생성")

glossary_df = pd.DataFrame(MANUFACTURING_GLOSSARY)
print(f"  - 용어 사전: {len(glossary_df)}건")


# --------------------------------------------------------------------------
# 2.16 설비-부품 매핑 데이터
# --------------------------------------------------------------------------
print("\n[2.16] 설비-부품 매핑 데이터 생성")

equipment_parts_data = []
for _, eq in equipment_df.iterrows():
    eq_parts = parts_df[parts_df["equipment_id"] == eq["equipment_id"]]
    for _, part in eq_parts.iterrows():
        equipment_parts_data.append({
            "equipment_id": eq["equipment_id"],
            "part_id": part["part_id"],
            "lifespan_hours": part["lifespan_hours"],
            "status": part["status"],
            "equipment_type": part["equipment_type"],
        })

equipment_parts_df = pd.DataFrame(equipment_parts_data)
print(f"  - 설비-부품 매핑: {len(equipment_parts_df)}건")


# --------------------------------------------------------------------------
# 2.17 설비 리소스 데이터 (에너지/소모품)
# --------------------------------------------------------------------------
print("\n[2.17] 설비 리소스 데이터 생성")

GRADE_ENERGY_QUOTA = {"A": 500, "B": 400, "C": 300, "D": 200}  # 월간 에너지 할당 (kWh)
equipment_resources_data = []
for _, eq in equipment_df.iterrows():
    quota = GRADE_ENERGY_QUOTA.get(eq["grade"], 300)
    used = round(float(np.clip(rng.uniform(0.3, 1.0) * quota, 10, quota * 0.95)), 2)
    equipment_resources_data.append({
        "equipment_id": eq["equipment_id"],
        "energy_quota_kwh": quota,
        "energy_used_kwh": used,
        "coolant_liters": round(float(rng.uniform(5, 200)), 1),
        "lubricant_liters": round(float(rng.uniform(1, 50)), 1),
        "spare_parts_cost": int(rng.integers(0, 5000000)),
    })

equipment_resources_df = pd.DataFrame(equipment_resources_data)
print(f"  - 설비 리소스: {len(equipment_resources_df)}건")

print("\n" + "=" * 70)
print("PART 2 완료: 모든 데이터 생성 완료")
print("=" * 70)


# ============================================================================
# PART 3: 모델 학습 (11개 ML 모델)
# ============================================================================
print("\n" + "=" * 70)
print("PART 3: 모델 학습 (11개)")
print("=" * 70)


# --------------------------------------------------------------------------
# 3.1 설비 고장 예측 (RandomForest + SHAP)
# --------------------------------------------------------------------------
print("\n[3.1] 설비 고장 예측 모델 (RandomForest + SHAP)")

FAILURE_FEATURES = [
    "operating_hours", "fault_count", "downtime_hours", "vibration",
    "temperature", "pressure", "current",
    "days_since_install", "grade_encoded",
]
FAILURE_FEATURE_NAMES_KR = {
    "operating_hours": "가동시간",
    "fault_count": "고장횟수",
    "downtime_hours": "다운타임(시간)",
    "vibration": "진동",
    "temperature": "온도",
    "pressure": "압력",
    "current": "전류",
    "days_since_install": "설치후경과일",
    "grade_encoded": "설비등급",
}

# 고장 여부 라벨링 (maintenance 상태 + 고장횟수 기반)
is_failure = ((equipment_df["status"] == "maintenance").astype(int) |
              (equipment_analytics_df["fault_count"] > equipment_analytics_df["fault_count"].quantile(0.85)).astype(int)).values
equipment_analytics_df["is_failure"] = is_failure

X_failure = equipment_analytics_df[FAILURE_FEATURES].fillna(0).copy()
y_failure = equipment_analytics_df["is_failure"].copy()

X_train_f, X_test_f, y_train_f, y_test_f = train_test_split(
    X_failure, y_failure, test_size=0.2, random_state=42, stratify=y_failure,
)

failure_params = {
    "n_estimators": 200, "max_depth": 8, "min_samples_split": 5,
    "min_samples_leaf": 2, "class_weight": "balanced", "random_state": 42,
}
rf_failure = RandomForestClassifier(**failure_params, n_jobs=-1)
rf_failure.fit(X_train_f, y_train_f)

y_pred_f = rf_failure.predict(X_test_f)
acc_failure = accuracy_score(y_test_f, y_pred_f)
f1_failure = f1_score(y_test_f, y_pred_f, zero_division=0)
print(f"  정확도: {acc_failure:.4f}, F1: {f1_failure:.4f}")

feature_importances_failure = dict(zip(FAILURE_FEATURES, rf_failure.feature_importances_))

# SHAP
shap_explainer = None
if SHAP_AVAILABLE:
    try:
        shap_explainer = shap.TreeExplainer(rf_failure)
        shap_values_raw = shap_explainer.shap_values(X_failure)
        if isinstance(shap_values_raw, list) and len(shap_values_raw) == 2:
            shap_vals = shap_values_raw[1]
        elif hasattr(shap_values_raw, "values"):
            shap_vals = shap_values_raw.values
        elif isinstance(shap_values_raw, np.ndarray) and shap_values_raw.ndim == 3:
            shap_vals = shap_values_raw[:, :, 1]
        else:
            shap_vals = np.array(shap_values_raw)
        for i, feat in enumerate(FAILURE_FEATURES):
            equipment_analytics_df[f"shap_{feat}"] = shap_vals[:, i]
        print("  SHAP 분석 완료")
    except Exception as e:
        print(f"  SHAP 분석 오류: {e}")
        SHAP_AVAILABLE = False

# 고장 확률 기록
failure_proba = rf_failure.predict_proba(X_failure)[:, 1]
equipment_analytics_df["failure_probability"] = np.round(failure_proba, 4)
equipment_analytics_df["failure_risk"] = (failure_proba >= 0.5).astype(int)

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="equipment_failure_model"):
        mlflow.set_tag("model_type", "classification")
        mlflow.log_params(failure_params)
        mlflow.log_metrics({"accuracy": acc_failure, "f1_score": f1_failure})
        mlflow.sklearn.log_model(rf_failure, "model", registered_model_name="설비고장예측")


# --------------------------------------------------------------------------
# 3.2 불량 감지 (Isolation Forest)
# --------------------------------------------------------------------------
print("\n[3.2] 불량 감지 모델 (Isolation Forest)")

defect_features = [
    "operating_hours", "vibration", "temperature", "pressure",
    "current", "fault_count",
]
X_defect = equipment_analytics_df[defect_features].fillna(0).copy()
scaler_defect = StandardScaler()
X_defect_scaled = scaler_defect.fit_transform(X_defect)

defect_params = {"n_estimators": 150, "contamination": 0.05, "random_state": 42}
iso_forest = IsolationForest(**defect_params)
defect_pred = iso_forest.fit_predict(X_defect_scaled)
defect_scores = iso_forest.decision_function(X_defect_scaled)

defect_count = int((defect_pred == -1).sum())
print(f"  불량 의심 설비: {defect_count}개 ({defect_count/len(defect_pred)*100:.1f}%)")

equipment_analytics_df["is_anomaly"] = (defect_pred == -1).astype(int)
raw_sc = -defect_scores
norm_sc = (raw_sc - raw_sc.min()) / (raw_sc.max() - raw_sc.min() + 1e-8)
equipment_analytics_df["anomaly_score"] = np.round(norm_sc, 4)

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="defect_detection_model"):
        mlflow.set_tag("model_type", "anomaly_detection")
        mlflow.log_params(defect_params)
        mlflow.log_metrics({
            "anomaly_count": defect_count,
            "anomaly_ratio": defect_count / len(defect_pred),
        })
        mlflow.sklearn.log_model(iso_forest, "model", registered_model_name="불량감지")


# --------------------------------------------------------------------------
# 3.3 고장 유형 분류 (TF-IDF + RandomForest)
# --------------------------------------------------------------------------
print("\n[3.3] 고장 유형 분류 모델 (TF-IDF + RandomForest)")

fault_texts = []
fault_labels = []
for fault_type, templates in FAULT_REPORT_TEMPLATES.items():
    for tpl in templates:
        for _ in range(20):
            text = tpl
            noise_words = rng.choice(
                ["", " 확인 부탁드립니다.", " 조치 필요합니다.", " 점검해주세요.", ""], size=1
            )[0]
            fault_texts.append(text + " " + noise_words)
            fault_labels.append(fault_type)

tfidf_fault = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
X_fault = tfidf_fault.fit_transform(fault_texts)
le_fault_type = LabelEncoder()
y_fault = le_fault_type.fit_transform(fault_labels)

X_tr_fault, X_te_fault, y_tr_fault, y_te_fault = train_test_split(
    X_fault, y_fault, test_size=0.2, random_state=42, stratify=y_fault,
)

fault_params = {
    "n_estimators": 150, "max_depth": 10,
    "random_state": 42, "class_weight": "balanced",
}
rf_fault = RandomForestClassifier(**fault_params, n_jobs=-1)
rf_fault.fit(X_tr_fault, y_tr_fault)

y_pred_fault = rf_fault.predict(X_te_fault)
acc_fault = accuracy_score(y_te_fault, y_pred_fault)
f1_fault = f1_score(y_te_fault, y_pred_fault, average="macro")
print(f"  정확도: {acc_fault:.4f}, F1(매크로): {f1_fault:.4f}")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="fault_classification_model"):
        mlflow.set_tag("model_type", "text_classification")
        mlflow.log_params(fault_params)
        mlflow.log_metrics({"accuracy": acc_fault, "f1_macro": f1_fault})
        mlflow.sklearn.log_model(rf_fault, "model", registered_model_name="고장유형분류")


# --------------------------------------------------------------------------
# 3.4 설비 군집화 (K-Means)
# --------------------------------------------------------------------------
print("\n[3.4] 설비 군집화 모델 (K-Means)")

cluster_features = [
    "operating_hours", "fault_count", "downtime_hours",
    "vibration", "temperature", "current",
]
X_cluster = equipment_analytics_df[cluster_features].fillna(0).copy()
scaler_cluster = StandardScaler()
X_cluster_scaled = scaler_cluster.fit_transform(X_cluster)

n_clusters = 4
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(X_cluster_scaled)
sil_score = silhouette_score(X_cluster_scaled, cluster_labels)
print(f"  실루엣 점수: {sil_score:.4f}")

equipment_analytics_df["cluster"] = cluster_labels

# 센트로이드 가동시간 기준으로 그룹 이름 자동 매핑
centroid_info = []
for c in range(n_clusters):
    mask = equipment_analytics_df["cluster"] == c
    avg_hours = equipment_analytics_df.loc[mask, "operating_hours"].mean() if mask.any() else 0
    avg_faults = equipment_analytics_df.loc[mask, "fault_count"].mean() if mask.any() else 0
    centroid_info.append((c, avg_hours, avg_faults))

# 고장 빈도 오름차순 정렬 (적은 → 많은)
centroid_info.sort(key=lambda x: x[2])

ORDERED_NAMES = ["우수 설비", "정상 설비", "주의 설비", "위험 설비"]
SEGMENT_NAMES = {}
for rank, (cid, avg_hours, avg_faults) in enumerate(centroid_info):
    SEGMENT_NAMES[cid] = ORDERED_NAMES[rank]
    print(f"  클러스터 {cid}: {ORDERED_NAMES[rank]} (평균 가동: {avg_hours:,.0f}h, 평균 고장: {avg_faults:,.1f}회)")

equipment_analytics_df["segment_name"] = equipment_analytics_df["cluster"].map(SEGMENT_NAMES)

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="equipment_cluster_model"):
        mlflow.set_tag("model_type", "clustering")
        mlflow.log_param("n_clusters", n_clusters)
        mlflow.log_metrics({"silhouette_score": sil_score})
        mlflow.sklearn.log_model(kmeans, "model", registered_model_name="설비군집화")


# --------------------------------------------------------------------------
# 3.5 수율 예측 (LightGBM / GradientBoosting)
# --------------------------------------------------------------------------
print("\n[3.5] 수율 예측 모델 (LightGBM / GradientBoosting)")

yield_data = []
for _, eq in equipment_df.iterrows():
    ea_row = equipment_analytics_df[
        equipment_analytics_df["equipment_id"] == eq["equipment_id"]
    ].iloc[0]
    prod_row = production_df[
        production_df["equipment_id"] == eq["equipment_id"]
    ]
    if len(prod_row) > 0:
        prod_row = prod_row.iloc[0]
        yield_rate = prod_row["yield_rate"]
        oee = prod_row["oee"]
    else:
        yield_rate = 95.0
        oee = 85.0

    eq_type_enc = EQUIPMENT_TYPES.index(eq["equipment_type"]) if eq["equipment_type"] in EQUIPMENT_TYPES else 0

    # 다음 기간 수율 예측 타겟
    growth = round(float(rng.normal(0.0, 0.02)), 4)
    target_yield = round(float(np.clip(yield_rate * (1 + growth), 80, 100)), 1)

    yield_data.append({
        "equipment_type_encoded": eq_type_enc,
        "operating_hours": eq["operating_hours"],
        "vibration": ea_row["vibration"],
        "temperature": ea_row["temperature"],
        "pressure": ea_row["pressure"],
        "current": ea_row["current"],
        "oee": oee,
        "target_yield": target_yield,
    })

yield_df = pd.DataFrame(yield_data)
X_yield = yield_df.drop(columns=["target_yield"]).copy()
y_yield = yield_df["target_yield"].copy()

X_tr_yield, X_te_yield, y_tr_yield, y_te_yield = train_test_split(
    X_yield, y_yield, test_size=0.2, random_state=42,
)

if LIGHTGBM_AVAILABLE:
    model_yield = lgb.LGBMRegressor(
        n_estimators=200, max_depth=6, learning_rate=0.05,
        num_leaves=31, random_state=42, verbose=-1,
    )
    algo_name_yield = "LightGBM"
else:
    model_yield = GradientBoostingRegressor(
        n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42,
    )
    algo_name_yield = "GradientBoosting"

model_yield.fit(X_tr_yield, y_tr_yield)
y_pred_yield = model_yield.predict(X_te_yield)
mae_yield = mean_absolute_error(y_te_yield, y_pred_yield)
r2_yield = r2_score(y_te_yield, y_pred_yield)
print(f"  알고리즘: {algo_name_yield}")
print(f"  MAE: {mae_yield:.2f}, R2: {r2_yield:.4f}")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="yield_prediction_model"):
        mlflow.set_tag("model_type", "regression")
        mlflow.set_tag("algorithm", algo_name_yield)
        mlflow.log_metrics({"mae": mae_yield, "r2": r2_yield})
        mlflow.sklearn.log_model(model_yield, "model", registered_model_name="수율예측")


# --------------------------------------------------------------------------
# 3.6 정비 품질 모델 (RandomForest Classifier)
# --------------------------------------------------------------------------
print("\n[3.6] 정비 품질 모델 (RandomForest Classifier)")

maint_quality_data = []
SEVERITY_LIST = ["경미", "보통", "심각", "긴급"]
PRIORITY_LABELS = ["긴급", "높음", "보통", "낮음"]
PRIORITY_WEIGHTS_MQ = [0.10, 0.20, 0.45, 0.25]

for _ in range(2000):
    fault_t = rng.choice(FAULT_TYPES)
    severity = rng.choice(SEVERITY_LIST)
    response_time = round(float(rng.exponential(2)), 1)
    repair_time = round(float(rng.exponential(4)), 1)
    is_repeat = int(rng.random() < 0.15)
    technician_exp = int(rng.integers(1, 20))  # 정비사 경력(년)

    fault_idx = FAULT_TYPES.index(fault_t)
    severity_idx = SEVERITY_LIST.index(severity)

    # 심각도 높고 응답 느리면 긴급/높음 우선순위
    if severity in ("심각", "긴급") and response_time > 4:
        priority = rng.choice(["긴급", "높음"], p=[0.6, 0.4])
    elif is_repeat:
        priority = rng.choice(["긴급", "높음", "보통"], p=[0.3, 0.4, 0.3])
    else:
        priority = rng.choice(PRIORITY_LABELS, p=PRIORITY_WEIGHTS_MQ)

    maint_quality_data.append({
        "fault_type_encoded": fault_idx,
        "severity_encoded": severity_idx,
        "response_time": response_time,
        "repair_time": repair_time,
        "is_repeat_issue": is_repeat,
        "technician_experience": technician_exp,
        "priority": priority,
    })

maint_quality_df = pd.DataFrame(maint_quality_data)
le_fault_cat = LabelEncoder()
le_severity = LabelEncoder()
le_maint_priority = LabelEncoder()

le_fault_cat.fit(FAULT_TYPES)
le_severity.fit(SEVERITY_LIST)
le_maint_priority.fit(PRIORITY_LABELS)

mq_feat_cols = [
    "fault_type_encoded", "severity_encoded", "response_time",
    "repair_time", "is_repeat_issue", "technician_experience",
]
X_mq = maint_quality_df[mq_feat_cols].copy()
y_mq = le_maint_priority.transform(maint_quality_df["priority"])

X_tr_mq, X_te_mq, y_tr_mq, y_te_mq = train_test_split(
    X_mq, y_mq, test_size=0.2, random_state=42, stratify=y_mq,
)

mq_params = {
    "n_estimators": 150, "max_depth": 10,
    "random_state": 42, "class_weight": "balanced",
}
rf_maint = RandomForestClassifier(**mq_params, n_jobs=-1)
rf_maint.fit(X_tr_mq, y_tr_mq)

y_pred_mq = rf_maint.predict(X_te_mq)
acc_mq = accuracy_score(y_te_mq, y_pred_mq)
f1_mq = f1_score(y_te_mq, y_pred_mq, average="macro")
print(f"  정확도: {acc_mq:.4f}, F1(매크로): {f1_mq:.4f}")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="maintenance_quality_model"):
        mlflow.set_tag("model_type", "classification")
        mlflow.log_params(mq_params)
        mlflow.log_metrics({"accuracy": acc_mq, "f1_macro": f1_mq})
        mlflow.sklearn.log_model(rf_maint, "model", registered_model_name="정비품질")


# --------------------------------------------------------------------------
# 3.7 설비 잔여수명(RUL) 예측 (GradientBoosting Regressor)
# --------------------------------------------------------------------------
print("\n[3.7] 설비 잔여수명(RUL) 예측 모델 (GradientBoosting Regressor)")

n_rul_samples = 3000
rul_data = []
for i in range(n_rul_samples):
    operating_hours = int(rng.integers(500, 50000))
    vibration = round(float(np.clip(rng.normal(3.0, 1.5), 0.1, 15)), 2)
    temperature = round(float(np.clip(rng.normal(50, 15), 15, 120)), 1)
    pressure = round(float(np.clip(rng.normal(5, 2), 0.5, 15)), 2)
    current = round(float(np.clip(rng.normal(15, 5), 0.5, 50)), 1)
    fault_count = int(np.clip(rng.poisson(operating_hours / 5000), 0, 30))

    # RUL = 설비 총 수명 - 현재 가동시간 (센서 열화 반영)
    total_life = int(rng.integers(30000, 80000))
    degradation = vibration * 100 + (temperature - 40) * 50 + fault_count * 500
    rul = max(0, int(total_life - operating_hours - degradation + rng.normal(0, 1000)))

    rul_data.append({
        "operating_hours": operating_hours,
        "vibration": vibration,
        "temperature": temperature,
        "pressure": pressure,
        "current": current,
        "fault_count": fault_count,
        "rul": rul,
    })

rul_df = pd.DataFrame(rul_data)
X_rul = rul_df.drop(columns=["rul"]).copy()
y_rul = rul_df["rul"].copy()

X_tr_rul, X_te_rul, y_tr_rul, y_te_rul = train_test_split(
    X_rul, y_rul, test_size=0.2, random_state=42,
)

model_rul = GradientBoostingRegressor(
    n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42,
)
model_rul.fit(X_tr_rul, y_tr_rul)

y_pred_rul = model_rul.predict(X_te_rul)
mae_rul = mean_absolute_error(y_te_rul, y_pred_rul)
r2_rul = r2_score(y_te_rul, y_pred_rul)
print(f"  MAE: {mae_rul:,.0f}, R2: {r2_rul:.4f}")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="equipment_rul_model"):
        mlflow.set_tag("model_type", "regression")
        mlflow.log_metrics({"mae": mae_rul, "r2": r2_rul})
        mlflow.sklearn.log_model(model_rul, "model", registered_model_name="설비잔여수명RUL")


# --------------------------------------------------------------------------
# 3.8 작업자 피드백 감성 분석 (TF-IDF + LogisticRegression)
# --------------------------------------------------------------------------
print("\n[3.8] 작업자 피드백 감성 분석 모델 (TF-IDF + LogisticRegression)")

feedback_texts = []
feedback_labels = []
for tpl in FEEDBACK_TEMPLATES_POSITIVE:
    for _ in range(30):
        noise = rng.choice(
            ["", " 감사합니다!", " 좋아요!", " 계속 유지해주세요!", " 만족합니다!"],
            p=[0.3, 0.2, 0.2, 0.15, 0.15],
        )
        feedback_texts.append(tpl + noise)
        feedback_labels.append("positive")

for tpl in FEEDBACK_TEMPLATES_NEGATIVE:
    for _ in range(30):
        noise = rng.choice(
            ["", " 개선해주세요.", " 문제입니다.", " 조치 바랍니다.", ""],
            p=[0.3, 0.2, 0.2, 0.15, 0.15],
        )
        feedback_texts.append(tpl + noise)
        feedback_labels.append("negative")

for tpl in FEEDBACK_TEMPLATES_NEUTRAL:
    for _ in range(30):
        noise = rng.choice(
            ["", " 보통입니다.", " 정상입니다.", ""],
            p=[0.3, 0.25, 0.25, 0.2],
        )
        feedback_texts.append(tpl + noise)
        feedback_labels.append("neutral")

tfidf_feedback = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
X_feedback = tfidf_feedback.fit_transform(feedback_texts)
le_feedback = LabelEncoder()
y_feedback = le_feedback.fit_transform(feedback_labels)

X_tr_fb, X_te_fb, y_tr_fb, y_te_fb = train_test_split(
    X_feedback, y_feedback, test_size=0.2, random_state=42, stratify=y_feedback,
)

model_feedback = LogisticRegression(
    max_iter=1000, random_state=42, class_weight="balanced",
)
model_feedback.fit(X_tr_fb, y_tr_fb)

y_pred_fb = model_feedback.predict(X_te_fb)
acc_fb = accuracy_score(y_te_fb, y_pred_fb)
f1_fb = f1_score(y_te_fb, y_pred_fb, average="macro")
print(f"  정확도: {acc_fb:.4f}, F1(매크로): {f1_fb:.4f}")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="operator_feedback_model"):
        mlflow.set_tag("model_type", "text_classification")
        mlflow.log_metrics({"accuracy": acc_fb, "f1_macro": f1_fb})
        mlflow.sklearn.log_model(
            model_feedback, "model", registered_model_name="작업자피드백분석",
        )


# --------------------------------------------------------------------------
# 3.9 생산량 예측 (XGBoost / GradientBoosting Ensemble)
# --------------------------------------------------------------------------
print("\n[3.9] 생산량 예측 모델 (XGBoost / GradientBoosting)")

forecast_data = []
for _ in range(2000):
    w1 = int(rng.poisson(200))
    w2 = int(rng.poisson(max(1, w1 + rng.integers(-30, 30))))
    w3 = int(rng.poisson(max(1, w2 + rng.integers(-30, 30))))
    w4 = int(rng.poisson(max(1, w3 + rng.integers(-30, 30))))
    eq_type_enc = int(rng.integers(0, len(EQUIPMENT_TYPES)))
    oee = round(float(rng.uniform(60, 98)), 1)
    cycle_time = round(float(rng.uniform(20, 80)), 1)
    is_overtime = int(rng.random() < 0.2)

    trend = (w4 - w1) / max(1, w1)
    base_output = (w1 + w2 + w3 + w4) / 4
    next_output = int(max(0, base_output * (1 + trend * 0.3 + is_overtime * 0.15) + rng.normal(0, 20)))

    forecast_data.append({
        "week1_output": w1, "week2_output": w2,
        "week3_output": w3, "week4_output": w4,
        "equipment_type_encoded": eq_type_enc,
        "oee": oee, "cycle_time": cycle_time,
        "is_overtime": is_overtime,
        "next_week_output": next_output,
    })

forecast_df = pd.DataFrame(forecast_data)
X_forecast = forecast_df.drop(columns=["next_week_output"]).copy()
y_forecast = forecast_df["next_week_output"].copy()

X_tr_fc, X_te_fc, y_tr_fc, y_te_fc = train_test_split(
    X_forecast, y_forecast, test_size=0.2, random_state=42,
)

if XGBOOST_AVAILABLE:
    model_forecast = xgb.XGBRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        random_state=42, verbosity=0,
    )
    algo_name_fc = "XGBoost"
else:
    model_forecast = GradientBoostingRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42,
    )
    algo_name_fc = "GradientBoosting"

model_forecast.fit(X_tr_fc, y_tr_fc)
y_pred_fc = model_forecast.predict(X_te_fc)
mae_fc = mean_absolute_error(y_te_fc, y_pred_fc)
r2_fc = r2_score(y_te_fc, y_pred_fc)
print(f"  알고리즘: {algo_name_fc}")
print(f"  MAE: {mae_fc:.2f}, R2: {r2_fc:.4f}")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="production_forecast_model"):
        mlflow.set_tag("model_type", "regression")
        mlflow.set_tag("algorithm", algo_name_fc)
        mlflow.log_metrics({"mae": mae_fc, "r2": r2_fc})
        mlflow.sklearn.log_model(
            model_forecast, "model", registered_model_name="생산량예측",
        )


# --------------------------------------------------------------------------
# 3.10 공정 이상 감지 (DBSCAN)
# --------------------------------------------------------------------------
print("\n[3.10] 공정 이상 감지 모델 (DBSCAN)")

# 설비당 3건 고정 (데모용 - 총 ~900건)
total_n = len(equipment_df) * 3
eq_ids_repeat = np.repeat(equipment_df["equipment_id"].values, 3)

normal_process_df = pd.DataFrame({
    "equipment_id": eq_ids_repeat,
    "temperature": np.round(rng.normal(50, 8, size=total_n), 1),
    "pressure": np.round(rng.normal(5, 1.2, size=total_n), 2),
    "vibration": np.round(rng.normal(2.5, 0.8, size=total_n), 2),
    "cycle_time": np.round(rng.normal(45, 8, size=total_n), 1),
    "defect_rate": np.round(rng.beta(2, 50, size=total_n), 4),
})

# 이상 공정 데이터 50건 고정
anomaly_process_df = pd.DataFrame({
    "equipment_id": rng.choice(equipment_df["equipment_id"].values, size=50),
    "temperature": np.round(rng.uniform(90, 130, size=50), 1),
    "pressure": np.round(rng.uniform(10, 18, size=50), 2),
    "vibration": np.round(rng.uniform(8, 15, size=50), 2),
    "cycle_time": np.round(rng.uniform(80, 150, size=50), 1),
    "defect_rate": np.round(rng.uniform(0.1, 0.5, size=50), 4),
})
process_df = pd.concat([normal_process_df, anomaly_process_df], ignore_index=True)
process_features = ["temperature", "pressure", "vibration", "cycle_time", "defect_rate"]
X_process = process_df[process_features].copy()
scaler_process = StandardScaler()
X_process_scaled = scaler_process.fit_transform(X_process)

dbscan = DBSCAN(eps=1.5, min_samples=5)
process_labels = dbscan.fit_predict(X_process_scaled)

n_noise = int((process_labels == -1).sum())
n_clusters_db = len(set(process_labels)) - (1 if -1 in process_labels else 0)
print(f"  클러스터 수: {n_clusters_db}, 이상(noise): {n_noise}건 ({n_noise/len(process_labels)*100:.1f}%)")

process_df["cluster_label"] = process_labels
process_df["is_anomaly"] = (process_labels == -1).astype(int)

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="process_anomaly_model"):
        mlflow.set_tag("model_type", "anomaly_detection")
        mlflow.log_param("eps", 1.5)
        mlflow.log_param("min_samples", 5)
        mlflow.log_metrics({"n_clusters": n_clusters_db, "n_noise": n_noise})
        mlflow.sklearn.log_model(dbscan, "model", registered_model_name="공정이상감지")

print("\n" + "=" * 70)
print("PART 3 완료: 모든 모델 학습 완료 (10개)")
print("=" * 70)


# ============================================================================
# PART 4: 저장 및 테스트
# ============================================================================
print("\n" + "=" * 70)
print("PART 4: 저장 및 테스트")
print("=" * 70)

# --------------------------------------------------------------------------
# 4.1 CSV 저장
# --------------------------------------------------------------------------
print("\n[4.1] CSV 파일 저장")

csv_enc = "utf-8-sig"
equipment_df.to_csv(BACKEND_DIR / "equipment.csv", index=False, encoding=csv_enc)
eq_types_df.to_csv(BACKEND_DIR / "equipment_types.csv", index=False, encoding=csv_enc)
parts_df.to_csv(BACKEND_DIR / "parts.csv", index=False, encoding=csv_enc)
sensor_df.to_csv(BACKEND_DIR / "sensor_readings.csv", index=False, encoding=csv_enc)
equipment_analytics_df.to_csv(BACKEND_DIR / "equipment_analytics.csv", index=False, encoding=csv_enc)
production_df.to_csv(BACKEND_DIR / "production.csv", index=False, encoding=csv_enc)
maintenance_df.to_csv(BACKEND_DIR / "maintenance.csv", index=False, encoding=csv_enc)
op_logs_df.to_csv(BACKEND_DIR / "operation_logs.csv", index=False, encoding=csv_enc)
daily_metrics_df.to_csv(BACKEND_DIR / "daily_metrics.csv", index=False, encoding=csv_enc)
maint_stats_df.to_csv(BACKEND_DIR / "maintenance_stats.csv", index=False, encoding=csv_enc)
anomaly_detail_df.to_csv(BACKEND_DIR / "anomaly_details.csv", index=False, encoding=csv_enc)
uptime_df.to_csv(BACKEND_DIR / "equipment_uptime.csv", index=False, encoding=csv_enc)
production_funnel_df.to_csv(BACKEND_DIR / "production_funnel.csv", index=False, encoding=csv_enc)
equipment_daily_df.to_csv(BACKEND_DIR / "equipment_daily.csv", index=False, encoding=csv_enc)
platform_docs_df.to_csv(BACKEND_DIR / "platform_docs.csv", index=False, encoding=csv_enc)
glossary_df.to_csv(BACKEND_DIR / "manufacturing_glossary.csv", index=False, encoding=csv_enc)
equipment_parts_df.to_csv(BACKEND_DIR / "equipment_parts.csv", index=False, encoding=csv_enc)
equipment_resources_df.to_csv(BACKEND_DIR / "equipment_resources.csv", index=False, encoding=csv_enc)
print("  18개 CSV 파일 저장 완료")


# --------------------------------------------------------------------------
# 4.2 모델 저장 (10개 + 보조 파일)
# --------------------------------------------------------------------------
print("\n[4.2] 모델 파일 저장")

# 1. 설비 고장 예측
joblib.dump(rf_failure, BACKEND_DIR / "model_equipment_failure.pkl")
if SHAP_AVAILABLE and shap_explainer is not None:
    joblib.dump(shap_explainer, BACKEND_DIR / "shap_explainer_failure.pkl")
    print("  - shap_explainer_failure.pkl 저장 완료")

failure_config = {
    "features": FAILURE_FEATURES,
    "feature_names_kr": FAILURE_FEATURE_NAMES_KR,
    "feature_importances": {k: float(v) for k, v in feature_importances_failure.items()},
    "shap_available": SHAP_AVAILABLE,
    "model_accuracy": float(acc_failure),
    "model_f1": float(f1_failure),
}
with open(BACKEND_DIR / "failure_model_config.json", "w", encoding="utf-8") as f:
    json.dump(failure_config, f, ensure_ascii=False, indent=2)

# 2. 불량 감지
joblib.dump(iso_forest, BACKEND_DIR / "model_defect_detection.pkl")

# 3. 고장 유형 분류
joblib.dump(rf_fault, BACKEND_DIR / "model_fault_classification.pkl")
joblib.dump(tfidf_fault, BACKEND_DIR / "tfidf_vectorizer.pkl")
joblib.dump(le_fault_type, BACKEND_DIR / "le_fault_type.pkl")

# 4. 설비 군집화
joblib.dump(kmeans, BACKEND_DIR / "model_equipment_cluster.pkl")
joblib.dump(scaler_cluster, BACKEND_DIR / "scaler_cluster.pkl")

# 5. 수율 예측
joblib.dump(model_yield, BACKEND_DIR / "model_yield_prediction.pkl")
yield_config = {
    "algorithm": algo_name_yield,
    "features": list(X_yield.columns),
    "mae": float(mae_yield),
    "r2_score": float(r2_yield),
}
with open(BACKEND_DIR / "yield_model_config.json", "w", encoding="utf-8") as f:
    json.dump(yield_config, f, ensure_ascii=False, indent=2)

# 6. 정비 품질
joblib.dump(rf_maint, BACKEND_DIR / "model_maintenance_quality.pkl")
joblib.dump(le_fault_cat, BACKEND_DIR / "le_fault_category.pkl")
joblib.dump(le_severity, BACKEND_DIR / "le_severity.pkl")
joblib.dump(le_maint_priority, BACKEND_DIR / "le_maint_priority.pkl")

# 7. 설비 잔여수명 RUL
joblib.dump(model_rul, BACKEND_DIR / "model_equipment_rul.pkl")

# 8. 작업자 피드백 감성 분석
joblib.dump(model_feedback, BACKEND_DIR / "model_operator_feedback.pkl")
joblib.dump(tfidf_feedback, BACKEND_DIR / "tfidf_vectorizer_feedback.pkl")

# 9. 생산량 예측
joblib.dump(model_forecast, BACKEND_DIR / "model_production_forecast.pkl")

# 10. 공정 이상 감지
joblib.dump(dbscan, BACKEND_DIR / "model_process_anomaly.pkl")

print("  10개 모델 + 보조 파일 저장 완료")


# --------------------------------------------------------------------------
# 4.2.1 센서 이상 감지 (Isolation Forest) 학습
# --------------------------------------------------------------------------
print("\n[4.2.1] 센서 이상 감지 IsolationForest 학습")

import sqlite3

GUARDIAN_DB_PATH = BACKEND_DIR / "guardian.db"
CORE_TABLES = {"equipment", "production", "maintenance", "sensor_readings", "work_orders"}

# (A) 감사 로그 DB 준비 (없으면 생성 + 시드 데이터)
def _prepare_guardian_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        row_count INTEGER DEFAULT 0,
        affected_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'executed',
        risk_level TEXT DEFAULT 'LOW',
        agent_reason TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        row_count INTEGER,
        was_mistake INTEGER DEFAULT 0,
        description TEXT
    )""")

    existing = c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    if existing < 200:
        from datetime import datetime, timedelta
        _now = datetime.now()
        _users = ["kim", "park", "lee", "choi", "jung"]
        _tables = ["equipment", "production", "maintenance", "sensor_readings", "work_orders", "logs", "temp_reports"]
        for _ in range(300):
            ts = (_now - timedelta(days=int(rng.integers(0, 60)), hours=int(rng.integers(0, 24)))).isoformat()
            u = rng.choice(_users)
            act = rng.choice(["INSERT", "UPDATE", "DELETE", "SELECT"])
            tbl = rng.choice(_tables)
            rc = int(rng.integers(1, 8)) if act == "DELETE" else int(rng.integers(1, 30))
            amt = rc * int(rng.integers(30000, 120000)) if tbl in ("production", "maintenance") else 0
            c.execute(
                "INSERT INTO audit_log (timestamp,user_id,action,table_name,row_count,affected_amount,status,risk_level) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (ts, u, act, tbl, rc, amt, "executed", "LOW")
            )
        # 이상 패턴 데이터 (야간 대량 DELETE 등)
        for _ in range(20):
            ts = (_now - timedelta(days=int(rng.integers(0, 30)))).replace(hour=int(rng.integers(22, 24))).isoformat()
            u = rng.choice(["unknown_admin", "temp_user", rng.choice(_users)])
            tbl = rng.choice(["equipment", "production", "sensor_readings"])
            rc = int(rng.integers(100, 5000))
            amt = rc * int(rng.integers(50000, 150000))
            c.execute(
                "INSERT INTO audit_log (timestamp,user_id,action,table_name,row_count,affected_amount,status,risk_level) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (ts, u, "DELETE", tbl, rc, amt, "executed", "HIGH")
            )
        # 과거 사건 데이터
        _incidents = [
            ("DELETE", "production", 250, 1, "신입 직원이 WHERE 없이 DELETE 실행, 전체 복구"),
            ("DELETE", "production", 180, 1, "테스트 DB와 혼동하여 프로덕션에서 삭제"),
            ("DELETE", "maintenance", 320, 1, "정비 데이터 삭제 실수, DBA가 백업에서 복구"),
            ("DELETE", "production", 150, 1, "퇴근 전 급하게 작업하다 실수"),
            ("DELETE", "sensor_readings", 500, 1, "센서 정리 스크립트 오류로 활성 데이터 삭제"),
            ("DELETE", "equipment", 200, 1, "설비 정리 중 실수로 전체 삭제"),
            ("DELETE", "production", 400, 1, "연말 정산 중 데이터 혼동"),
            ("DELETE", "logs", 10000, 0, "정기 로그 정리 (스케줄 작업)"),
            ("DELETE", "temp_reports", 5000, 0, "임시 리포트 정리"),
            ("UPDATE", "production", 300, 1, "수량 필드 일괄 0으로 업데이트 실수"),
            ("UPDATE", "equipment", 150, 1, "파라미터 일괄 변경 시 WHERE 조건 누락"),
            ("UPDATE", "sensor_readings", 1000, 1, "센서값 일괄 변경 실수"),
        ]
        for act, tbl, rc, mis, desc in _incidents:
            c.execute("INSERT INTO incidents (action,table_name,row_count,was_mistake,description) VALUES (?,?,?,?,?)",
                      (act, tbl, rc, mis, desc))
        conn.commit()
        print(f"  guardian.db 시드 데이터 생성 완료 (audit_log: {c.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]}건)")
    else:
        print(f"  guardian.db 기존 데이터 사용 ({existing}건)")
    return conn

guardian_conn = _prepare_guardian_db(GUARDIAN_DB_PATH)

# (B) 학습 데이터 로드
rows = guardian_conn.execute(
    "SELECT user_id, action, table_name, row_count, affected_amount, timestamp "
    "FROM audit_log WHERE status='executed'"
).fetchall()
guardian_conn.close()

ACTION_MAP = {"INSERT": 0, "SELECT": 0, "UPDATE": 1, "DELETE": 2,
              "ALTER": 3, "DROP": 4, "TRUNCATE": 4}
guardian_features = []
for r in rows:
    ts = r["timestamp"] or ""
    hour = int(ts[11:13]) if len(ts) > 13 else 12
    guardian_features.append([
        ACTION_MAP.get(r["action"], 0),
        1 if r["table_name"] in CORE_TABLES else 0,
        r["row_count"],
        np.log1p(r["row_count"]),
        r["affected_amount"],
        hour,
        1 if (hour >= 22 or hour < 6) else 0,
    ])

X_guardian = np.array(guardian_features)
scaler_guardian = StandardScaler()
X_guardian_scaled = scaler_guardian.fit_transform(X_guardian)

# (C) IsolationForest 학습
guardian_iso = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
guardian_iso.fit(X_guardian_scaled)

# 학습 결과 확인
guardian_pred = guardian_iso.predict(X_guardian_scaled)
guardian_anomaly_count = int((guardian_pred == -1).sum())
print(f"  학습 데이터: {len(rows)}건, 7 features")
print(f"  이상 탐지: {guardian_anomaly_count}건 ({guardian_anomaly_count/len(rows)*100:.1f}%)")

# (D) 모델 저장
joblib.dump(guardian_iso, BACKEND_DIR / "model_sensor_anomaly.pkl")
joblib.dump(scaler_guardian, BACKEND_DIR / "scaler_sensor_anomaly.pkl")
print("  model_sensor_anomaly.pkl, scaler_sensor_anomaly.pkl 저장 완료")

if MLFLOW_AVAILABLE:
    with mlflow.start_run(run_name="sensor_anomaly_model"):
        mlflow.set_tag("model_type", "anomaly_detection")
        mlflow.log_params({"n_estimators": 100, "contamination": 0.05, "random_state": 42})
        mlflow.log_metrics({
            "anomaly_count": guardian_anomaly_count,
            "anomaly_ratio": guardian_anomaly_count / len(rows),
            "n_samples": len(rows),
        })
        mlflow.sklearn.log_model(guardian_iso, "model", registered_model_name="센서이상감지")


# --------------------------------------------------------------------------
# 4.3 설비별 예측 결과 사전계산 → equipment_analytics.csv에 추가
# --------------------------------------------------------------------------
print("\n[4.3] 설비별 모델 예측 결과 사전계산")

# (A) 수율 예측: 전 설비에 대해 model_yield로 예측
yield_feat_cols = ["equipment_type_encoded", "operating_hours", "vibration",
                   "temperature", "pressure", "current", "oee"]
predicted_yields = []
yield_changes = []
for _, eq in equipment_df.iterrows():
    ea_row = equipment_analytics_df[
        equipment_analytics_df["equipment_id"] == eq["equipment_id"]
    ]
    if len(ea_row) == 0:
        predicted_yields.append(95.0)
        yield_changes.append(0.0)
        continue

    ea_row = ea_row.iloc[0]
    prod_row = production_df[production_df["equipment_id"] == eq["equipment_id"]]
    oee = prod_row.iloc[0]["oee"] if len(prod_row) > 0 else 85.0
    eq_type_enc = EQUIPMENT_TYPES.index(eq["equipment_type"]) if eq["equipment_type"] in EQUIPMENT_TYPES else 0

    X_pred = pd.DataFrame([{
        "equipment_type_encoded": eq_type_enc,
        "operating_hours": eq["operating_hours"],
        "vibration": ea_row["vibration"],
        "temperature": ea_row["temperature"],
        "pressure": ea_row["pressure"],
        "current": ea_row["current"],
        "oee": oee,
    }])
    pred_yield = float(model_yield.predict(X_pred)[0])
    pred_yield = max(80, min(100, pred_yield))
    predicted_yields.append(round(pred_yield, 1))
    current_yield = prod_row.iloc[0]["yield_rate"] if len(prod_row) > 0 else 95.0
    yield_change = round(pred_yield - current_yield, 1)
    yield_changes.append(yield_change)

equipment_analytics_df["predicted_yield"] = predicted_yields
equipment_analytics_df["yield_change"] = yield_changes
print(f"  수율 예측 완료: {len(predicted_yields)}개 설비")

# (B) 정비 품질: 설비별 대표 정비 기록 생성 후 모델 예측 → 품질 점수화
mq_scores = []
mq_grades = []
for _, eq in equipment_df.iterrows():
    ea_row = equipment_analytics_df[
        equipment_analytics_df["equipment_id"] == eq["equipment_id"]
    ].iloc[0]
    fault_count = ea_row["fault_count"]

    sample_tickets = []
    for ft_idx in range(min(5, len(FAULT_TYPES))):
        response_time = round(float(rng.exponential(2)), 1)
        repair_time = round(float(rng.exponential(4)), 1)
        is_repeat = 1 if fault_count > 5 else 0
        tech_exp = int(rng.integers(1, 20))
        sample_tickets.append({
            "fault_type_encoded": ft_idx,
            "severity_encoded": rng.integers(0, 4),
            "response_time": response_time,
            "repair_time": repair_time,
            "is_repeat_issue": is_repeat,
            "technician_experience": tech_exp,
        })
    X_mq_pred = pd.DataFrame(sample_tickets)
    preds = rf_maint.predict(X_mq_pred)
    probas = rf_maint.predict_proba(X_mq_pred)
    avg_proba = probas.mean(axis=0)
    priority_classes = le_maint_priority.classes_
    score_map = {"낮음": 100, "보통": 70, "높음": 40, "긴급": 10}
    mq_score = 0
    for i, cls in enumerate(priority_classes):
        mq_score += avg_proba[i] * score_map.get(cls, 50)
    mq_score = max(0, min(100, int(mq_score)))
    mq_scores.append(mq_score)
    mq_grades.append("우수" if mq_score >= 80 else "보통" if mq_score >= 50 else "개선필요")

equipment_analytics_df["maintenance_quality_score"] = mq_scores
equipment_analytics_df["maintenance_quality_grade"] = mq_grades
print(f"  정비 품질 예측 완료: {len(mq_scores)}개 설비")

# (C) 잔여수명(RUL) 예측: 설비별 RUL
rul_predictions = []
for _, eq in equipment_df.iterrows():
    ea_row = equipment_analytics_df[
        equipment_analytics_df["equipment_id"] == eq["equipment_id"]
    ].iloc[0]
    X_rul_pred = pd.DataFrame([{
        "operating_hours": eq["operating_hours"],
        "vibration": ea_row["vibration"],
        "temperature": ea_row["temperature"],
        "pressure": ea_row["pressure"],
        "current": ea_row["current"],
        "fault_count": ea_row["fault_count"],
    }])
    try:
        rul_pred = int(model_rul.predict(X_rul_pred)[0])
    except Exception:
        rul_pred = int(50000 - eq["operating_hours"])
    rul_predictions.append(max(0, rul_pred))

equipment_analytics_df["predicted_rul"] = rul_predictions
print(f"  RUL 예측 완료: {len(rul_predictions)}개 설비")

# CSV 다시 저장 (예측 결과 포함)
equipment_analytics_df.to_csv(BACKEND_DIR / "equipment_analytics.csv", index=False, encoding=csv_enc)
print("  equipment_analytics.csv 업데이트 완료 (예측 컬럼 추가)")


# --------------------------------------------------------------------------
# 4.4 예측 함수 테스트
# --------------------------------------------------------------------------
print("\n[4.4] 예측 함수 테스트")

# 고장 예측 테스트
sample_failure = {f: 0 for f in FAILURE_FEATURES}
sample_failure.update({
    "operating_hours": 15000, "fault_count": 3, "downtime_hours": 12.5,
    "vibration": 3.5, "temperature": 55, "pressure": 6.0,
    "current": 18, "days_since_install": 1200, "grade_encoded": 2,
})
X_sample_failure = pd.DataFrame([sample_failure])[FAILURE_FEATURES]
failure_pred = rf_failure.predict(X_sample_failure)[0]
failure_prob = rf_failure.predict_proba(X_sample_failure)[0]
print(f"  설비 고장 예측: {'고장위험' if failure_pred else '정상'} (확률: {failure_prob[1]:.2%})")

# 고장유형 분류 테스트
test_fault = "베어링에서 이상 소음이 발생하고 진동이 심합니다"
X_fault_test = tfidf_fault.transform([test_fault])
fault_pred = le_fault_type.inverse_transform(rf_fault.predict(X_fault_test))[0]
print(f"  고장유형 분류: '{test_fault}' -> {fault_pred}")

# 피드백 감성 분석 테스트
test_feedback = "설비 상태가 좋아서 작업이 순조롭습니다. 가동률도 높아요."
X_fb_test = tfidf_feedback.transform([test_feedback])
fb_pred = le_feedback.inverse_transform(model_feedback.predict(X_fb_test))[0]
print(f"  피드백 감성: '{test_feedback}' -> {fb_pred}")

# 설비 군집화 테스트
sample_cluster = {
    "operating_hours": 20000, "fault_count": 2, "downtime_hours": 8,
    "vibration": 2.0, "temperature": 45, "current": 12,
}
X_cluster_test = pd.DataFrame([sample_cluster])[cluster_features]
X_cluster_test_scaled = scaler_cluster.transform(X_cluster_test)
cluster_pred = int(kmeans.predict(X_cluster_test_scaled)[0])
print(f"  설비 군집: {SEGMENT_NAMES.get(cluster_pred, '알 수 없음')}")


# --------------------------------------------------------------------------
# 완료 요약
# --------------------------------------------------------------------------
print("\n" + "=" * 70)
print("완료! 제조 AI 솔루션 데이터 생성 및 모델 학습 성공")
print("=" * 70)
print(f"\n[요약]")
print(f"  데이터:")
print(f"    - 설비: {len(equipment_df)}개, 부품: {len(parts_df)}개")
print(f"    - 센서: {len(sensor_df)}건, 생산실적: {len(production_df)}건")
print(f"    - 정비이력: {len(maintenance_df)}건, 운영로그: {len(op_logs_df)}건")
print(f"    - 일별지표: {len(daily_metrics_df)}일, 설비일별: {len(equipment_daily_df)}건")
print(f"    - CSV 파일: 18개")
print(f"  모델 (11개):")
print(f"    1. 설비 고장 예측 (RandomForest + SHAP)")
print(f"    2. 불량 감지 (Isolation Forest)")
print(f"    3. 고장 유형 분류 (TF-IDF + RandomForest)")
print(f"    4. 설비 군집화 (K-Means)")
print(f"    5. 수율 예측 ({algo_name_yield})")
print(f"    6. 정비 품질 (RandomForest)")
print(f"    7. 설비 잔여수명 RUL (GradientBoosting)")
print(f"    8. 작업자 피드백 분석 (TF-IDF + LogisticRegression)")
print(f"    9. 생산량 예측 ({algo_name_fc})")
print(f"   10. 공정 이상 감지 (DBSCAN)")
print(f"   11. 센서 이상 감지 (IsolationForest, {len(rows)}건)")
print(f"  SHAP: {'활성화' if SHAP_AVAILABLE else '비활성화'}")
print(f"  MLflow: {'활성화' if MLFLOW_AVAILABLE else '비활성화'}")
print(f"\n백엔드 서버 시작: cd backend && python main.py")
