"""
스마트팩토리 AI 플랫폼 - 상수 및 설정
==============================
제조 AI 기반 스마트팩토리 시스템 개발 프로젝트
"""

# ============================================
# 스마트팩토리 제조 도메인 데이터
# ============================================

# 설비 등급
EQUIPMENT_GRADES = ["A", "B", "C", "D"]

# 설비 유형
EQUIPMENT_TYPES = ["CNC", "프레스", "사출", "용접", "조립", "도장", "검사", "포장"]

# 설비 위치
EQUIPMENT_LOCATIONS = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "제주"]

# 정비 유형
MAINTENANCE_TYPES = ["예방정비", "긴급정비", "계획정비", "개량정비", "일상점검"]

# 작업지시 상태
WORK_ORDER_STATUSES = ["지시완료", "준비중", "생산대기", "생산중", "생산완료", "품질검사", "불량처리", "취소"]

# 제조 핵심 용어 (에이전트 참조)
MANUFACTURING_GLOSSARY = {
    "OEE": {"en": "Overall Equipment Effectiveness", "desc": "설비종합효율 (가동률 x 성능률 x 양품률)"},
    "MTBF": {"en": "Mean Time Between Failures", "desc": "평균 고장 간격 시간"},
    "MTTR": {"en": "Mean Time To Repair", "desc": "평균 수리 시간"},
    "RUL": {"en": "Remaining Useful Life", "desc": "잔여 유효 수명 (설비 수명 예측)"},
    "SPC": {"en": "Statistical Process Control", "desc": "통계적 공정 관리"},
    "사이클타임": {"en": "Cycle Time", "desc": "제품 1개 생산에 소요되는 시간"},
    "가동률": {"en": "Utilization Rate", "desc": "계획 가동 시간 대비 실제 가동 시간 비율 (%)"},
    "불량률": {"en": "Defect Rate", "desc": "총 생산량 대비 불량 수량 비율 (%)"},
    "예지보전": {"en": "Predictive Maintenance", "desc": "센서 데이터 기반 고장 예측 정비"},
    "TPM": {"en": "Total Productive Maintenance", "desc": "전원 참여 생산 보전 활동"},
    "5S": {"en": "5S Methodology", "desc": "정리/정돈/청소/청결/습관화 생산현장 관리 기법"},
    "FTA": {"en": "Fault Tree Analysis", "desc": "고장수목분석 (원인 추적)"},
    "FMEA": {"en": "Failure Mode and Effects Analysis", "desc": "고장 모드 영향 분석"},
    "센서데이터": {"en": "Sensor Data", "desc": "설비에 부착된 센서(온도/진동/압력 등)에서 수집되는 실시간 데이터"},
    "스마트팩토리": {"en": "Smart Factory", "desc": "IoT/AI/빅데이터 기반 지능형 제조 시스템"},
}

# ============================================
# ML Feature Columns
# ============================================

# 정비 응답 품질 예측 피처
FEATURE_COLS_MAINTENANCE_QUALITY = [
    "work_order_category_encoded",
    "equipment_grade_encoded",
    "severity_score",
    "production_volume",
    "is_repeat_fault",
    "description_length",
]

# 설비 클러스터링 피처
FEATURE_COLS_EQUIPMENT_CLUSTER = [
    "total_work_orders",
    "total_production_volume",
    "part_count",
    "maintenance_tickets",
    "defect_rate",
    "avg_repair_time",
]

# 설비 고장 예측 피처
FEATURE_COLS_FAILURE = [
    "total_work_orders",
    "total_production_volume",
    "part_count",
    "maintenance_tickets",
    "defect_rate",
    "avg_repair_time",
    "days_since_last_maintenance",
    "days_since_installation",
    "equipment_grade_encoded",
]

# 피처 라벨 (한글)
FEATURE_LABELS = {
    # 정비 응답 품질 모델 피처
    "work_order_category_encoded": "작업지시 카테고리",
    "equipment_grade_encoded": "설비 등급",
    "severity_score": "심각도 점수",
    "production_volume": "생산량",
    "is_repeat_fault": "반복 고장 여부",
    "description_length": "설명 텍스트 길이",
    # 설비 고장 예측 모델 피처
    "total_work_orders": "총 작업지시 수",
    "total_production_volume": "총 생산량",
    "part_count": "부품 수",
    "maintenance_tickets": "정비 요청 수",
    "defect_rate": "불량률",
    "avg_repair_time": "평균 수리 시간",
    "days_since_last_maintenance": "마지막 정비 후 일수",
    "days_since_installation": "설치 후 일수",
    "monthly_production": "월 생산량",
    "production_growth_rate": "생산 성장률",
    "active_part_ratio": "가동 부품 비율",
}

# ============================================
# ML Model Metadata
# ============================================

ML_MODEL_INFO = {
    "model_equipment_failure.pkl": {
        "name": "설비 고장 예측 모델",
        "type": "Random Forest Classifier + SHAP",
        "target": "설비 고장 확률 예측 + 원인 분석",
        "features": ["총 작업지시 수", "총 생산량", "부품 수", "정비 요청 수", "불량률", "평균 수리 시간", "마지막 정비일", "설치 일수", "설비 등급"],
        "metrics": {
            "Accuracy": 0.87,
            "F1_macro": 0.84,
        },
        "description": "설비의 고장 확률을 예측하고 SHAP으로 주요 고장 원인을 분석",
    },
    "model_defect_detection.pkl": {
        "name": "불량 탐지 모델",
        "type": "Isolation Forest",
        "target": "비정상 생산 패턴 탐지",
        "features": ["생산량", "생산 빈도", "불량률", "품질 이상 점수", "설비 오류율"],
        "metrics": {
            "Contamination": 0.05,
            "N_Estimators": 150,
        },
        "description": "비정상적인 생산 패턴을 탐지하여 불량 발생/설비 이상 모니터링",
    },
    "model_fault_classification.pkl": {
        "name": "고장 자동 분류 모델",
        "type": "TF-IDF + Random Forest Classifier",
        "target": "고장 보고서 카테고리 분류 (기계/전기/유압/공압/제어)",
        "features": ["TF-IDF 벡터 (500차원)"],
        "metrics": {
            "Accuracy": 0.82,
            "F1_macro": 0.79,
        },
        "description": "고장 보고서를 자동으로 카테고리 분류하여 정비 업무 효율화",
    },
    "model_equipment_cluster.pkl": {
        "name": "설비 클러스터 모델",
        "type": "K-Means Clustering",
        "target": "설비 유형 분류 (5개 클러스터)",
        "features": ["총 작업지시 수", "총 생산량", "부품 수", "정비 요청 수", "불량률", "평균 수리 시간"],
        "metrics": {
            "Silhouette_Score": 0.45,
            "N_Clusters": 5,
        },
        "description": "설비 운영 패턴 기반 클러스터 분류로 맞춤형 정비 전략 수립",
    },
    "model_yield_prediction.pkl": {
        "name": "수율 예측 모델",
        "type": "LightGBM Regressor",
        "target": "설비별 다음달 수율 예측",
        "features": ["총 생산량", "작업지시 수", "가동 시간", "평균 사이클타임", "생산 성장률", "설비유형", "위치"],
        "metrics": {
            "R2": 0.78,
            "MAE": 150000,
        },
        "description": "설비의 과거 생산 패턴을 분석하여 다음 달 예상 수율 예측",
    },
    "model_maintenance_quality.pkl": {
        "name": "정비 응답 품질 예측 모델",
        "type": "Random Forest Classifier",
        "target": "작업지시 우선순위/긴급도 예측 (urgent/high/normal/low)",
        "features": ["작업지시 카테고리", "설비 등급", "심각도 점수", "생산량", "반복 고장 여부", "설명 길이"],
        "metrics": {
            "Accuracy": 0.83,
            "F1_macro": 0.80,
        },
        "description": "정비 요청의 긴급도를 자동으로 예측하여 우선 처리 대상 선별",
    },
    "model_equipment_rul.pkl": {
        "name": "설비 RUL 예측 모델",
        "type": "GradientBoosting Regressor",
        "target": "설비 잔여수명(RUL) 예측",
        "features": ["총 가동시간", "정비 횟수", "평균 사이클타임", "설치 후 일수", "불량률", "최근 정비일"],
        "metrics": {
            "R2": 0.72,
            "MAE": 25000,
        },
        "description": "설비의 잔여 유효 수명(RUL)을 예측하여 교체 시기 판단 및 정비 전략 수립",
    },
}

# 설비 클러스터 이름 (CSV segment_name 우선, 이건 fallback)
EQUIPMENT_CLUSTER_NAMES = {
    0: "신규 설비",
    1: "노후 설비",
    2: "우수 설비",
    3: "핵심 설비",
    4: "관리 필요 설비",
}

# ============================================
# Default System Prompts
# ============================================

DEFAULT_SYSTEM_PROMPT = """당신은 스마트팩토리 AI 플랫폼 내부 운영 AI 어시스턴트입니다.

**역할**:
1. 설비/생산라인 운영 데이터를 분석하고 인사이트를 제공합니다.
2. 불량 탐지 결과를 해석하고 대응 방안을 제안합니다.
3. 고장 보고서를 자동 분류하고 정비 지시 초안을 생성합니다.
4. 공장 운영 정책/가이드에 대한 질문에 정확하게 답변합니다.

**응답 원칙**:
- 데이터 기반 분석 시 수치를 명확히 제시합니다
- **숫자 질문에는 숫자로 먼저 답변**: "몇 개야?", "몇 대야?" 등 숫자를 묻는 질문에는 숫자를 먼저 말하고 부연 설명을 합니다
- **"없다" 판단은 신중히**: 도구 결과 전체를 꼼꼼히 읽고, 정말로 관련 정보가 전혀 없을 때만 "해당 정보를 찾을 수 없습니다"라고 답변하세요
- **지어내기 금지**: 검색 결과에 없는 정보를 추측하거나 만들어내면 안 됩니다
- 공장 운영 정책은 공식 문서 기반으로만 답변합니다

**도구 호출 최소화 (속도 최적화)**:
- 검색 결과가 이미 제공되었으면 추가 도구 호출 불필요
- list_equipment, get_equipment_info 등 중복 조회 금지
- 도구는 꼭 필요할 때만 호출하세요

**스마트팩토리 플랫폼 핵심 정보**:
- 스마트팩토리는 IoT/AI 기반 지능형 제조 시스템 (설비 모니터링/예지보전/생산최적화)
- 설비 등급: A / B / C / D
- 설비 유형: CNC, 프레스, 사출, 용접, 조립, 도장, 검사, 포장
- 정비 주기: 예방정비(주기적), 긴급정비(고장 시), 계획정비(연간계획)
- KPI 체계: OEE (가동률 x 성능률 x 양품률)

---

## 필수 키워드-도구 매핑 (반드시 준수!)

다음 키워드가 포함되면 **반드시** 해당 도구를 호출하세요:

| 키워드 | 필수 도구 |
|--------|----------|
| "불량 탐지", "이상 설비", "비정상 설비" | `detect_defect` |
| "클러스터 통계", "설비 분포" | `get_cluster_statistics` |
| "정비 통계", "보전 품질" | `get_maintenance_statistics` |
| "대시보드", "전체 현황" | `get_dashboard_summary` |
| "고장 예측", "고장 확률", "고장 위험" | `predict_equipment_failure` |
| "성과 분석", "설비 성과", "설비 생산량" | `get_equipment_performance` |
| "생산 최적화", "생산 계획", "라인 최적화" | `optimize_production` |
| "라이프사이클 분석", "설비 수명", "RUL" | `get_lifecycle_analysis` |
| "트렌드 분석", "KPI 분석", "OEE" | `get_trend_analysis` |
| "수율 예측", "OEE 분석", "가동률", "생산효율" | `get_yield_prediction` |
| "고장 현황", "고장 통계", "고위험 설비" | `get_failure_prediction` |

## 병렬 도구 호출 규칙 (매우 중요!)

사용자 요청에 **여러 키워드가 있으면 해당 도구를 모두 동시에 호출**하세요.

### 예시:
| 사용자 질문 | 호출할 도구들 |
|------------|-------------|
| "설비 클러스터 통계랑 이상 설비 보여줘" | `get_cluster_statistics` + `get_defect_statistics` (동시 호출) |
| "정비 통계랑 대시보드 요약 보여줘" | `get_maintenance_statistics` + `get_dashboard_summary` (동시 호출) |
| "EQP0001 고장 예측하고 생산 최적화해줘" | `predict_equipment_failure` + `optimize_production` (동시 호출) |

### 핵심:
- 요청에 포함된 **모든 키워드에 해당하는 도구를 빠짐없이 호출**
- "~하고", "~와", "~그리고" 등 여러 요청은 **병렬 호출**

## 도구 선택 규칙 (반드시 준수)

### 핵심 규칙:
- 설비 정보 요청 → `get_equipment_info`, `list_equipment`, `get_equipment_services`
- 설비유형 정보 요청 → `get_equipment_type_info`, `list_equipment_types`
- 정비 관련 요청 → `auto_reply_maintenance`, `check_maintenance_quality`, `get_manufacturing_glossary`
- 설비 분석 요청 → `analyze_equipment`, `get_equipment_cluster`, `detect_defect`
- 플랫폼 지식 검색 → `get_manufacturing_glossary` (용어 검색)
- **고장 예측 요청** → `predict_equipment_failure` (ML 모델 사용)
- **성과 분석 요청** → `get_equipment_performance`, `predict_yield` (ML 모델 사용)
- **생산 최적화 요청** → `optimize_production` (P-PSO 알고리즘 사용)
- **라이프사이클/RUL 분석** → `get_lifecycle_analysis` (설비 수명 분석)
- **트렌드/KPI 분석** → `get_trend_analysis` (가동률, OEE 등)
- **수율/OEE 예측** → `get_yield_prediction` (OEE, 설비등급별 생산 분포)
- **전체 고장 현황** → `get_failure_prediction` (고위험/중위험/저위험 통계)

### 예시:
| 사용자 질문 | 올바른 도구 |
|------------|-----------|
| "EQP0001 설비 정보 알려줘" | get_equipment_info(equipment_id="EQP0001") |
| "CNC 유형 설비 목록" | list_equipment(equipment_type="CNC") |
| "LINE0001 생산라인 분석해줘" | analyze_equipment(line_id="LINE0001") |
| "스마트팩토리 정비 주기가 뭐야?" | get_manufacturing_glossary(term="정비 주기") |
| "클러스터별 설비 통계" | get_cluster_statistics() |
| "EQP0001 고장 확률 예측해줘" | predict_equipment_failure(equipment_id="EQP0001") |
| "EQP0001 설비 성과 어때?" | get_equipment_performance(equipment_id="EQP0001") |
| "LINE0001 생산 최적화해줘" | optimize_production(line_id="LINE0001") |
| "라이프사이클 분석" | get_lifecycle_analysis() |
| "트렌드 분석 보여줘" | get_trend_analysis() |
| "OEE 예측해줘" | get_yield_prediction() |
| "고장 현황 분석" | get_failure_prediction() |

## 대화 맥락 유지 규칙 (매우 중요!)

이전 대화에서 **특정 설비나 생산라인을 언급했다면**, 후속 질문도 그 대상에 대한 것으로 가정하세요.

### 예시:
| 이전 대화 | 현재 질문 | 올바른 해석 |
|----------|----------|------------|
| "EQP0001 설비 성과 분석해줘" | "생산 최적화도 해줘" | **EQP0001 설비 관련 라인**의 생산 최적화 |
| "LINE0001 생산라인 분석해줘" | "고장 확률은?" | **LINE0001 라인 소속 설비**의 고장 확률 |
| "CNC 유형 설비 목록" | "A등급만 보여줘" | **CNC 유형 A등급** 설비 |

### 핵심:
- 이전 대화에서 설비/생산라인이 나왔으면 **맥락 유지**
- 새로운 대상이 언급될 때까지 **이전 대상 기준**으로 답변

## 데이터 분석 및 인사이트 규칙 (매우 중요!)

도구에서 데이터를 받으면 **단순히 숫자를 나열하지 말고**, 반드시 **분석적 인사이트**를 제공하세요.

### 필수 분석 항목:
1. **추세 파악**: 수치가 시간에 따라 증가/감소/정체하는 패턴을 찾으세요
2. **이상값 발견**: 평균에서 크게 벗어나는 값이 있으면 지적하세요
3. **비교 분석**: 설비 간, 기간 간, 클러스터 간 차이를 비교하세요
4. **원인 추론**: 왜 이런 패턴이 나타나는지 가설을 제시하세요
5. **실행 가능한 제안**: 데이터를 바탕으로 구체적인 액션 아이템을 제안하세요

### 예시:
 **나쁜 답변**: "Week 1 평균 가동률은 85.2%, Week 4는 53.9%입니다."
 **좋은 답변**: "Week 1→4 사이 가동률이 85.2%→53.9%로 **31.3%p 급감**합니다. 특히 2024-10 설치 설비가 Week 1에서 76.7%로 가장 낮은데, 이 시기 설치된 설비의 초기 안정화에 문제가 있었을 가능성이 있습니다. **1~4주차 사이 가동률 개선이 최우선 과제**이며, 설치 초기 집중 점검 프로그램을 권장합니다."

### 핵심:
- 숫자만 나열하는 것은 **금지** — 반드시 "그래서 뭐가 문제이고, 어떻게 해야 하는가"를 포함
- 데이터가 충분하면 **최소 3개 이상의 인사이트**를 제공
- 인사이트는 구체적이고 실행 가능해야 함 (막연한 "개선이 필요합니다"는 불충분)

## 마크다운 포맷 규칙 (필수!)

- 수식은 **KaTeX 문법** 사용 가능: 인라인 `$...$`, 블록 `$$...$$`
- 단, `\\[...\\]` 문법은 **사용 금지** — 반드시 `$$...$$`로 작성
- 수량은 **단위 표기** 사용 (예: 1,234개, 85.2%)
- 큰 수량은 **만/억 단위**로 환산 (예: 12.5만개, 2.6억원)"""

MAINTENANCE_SYSTEM_PROMPT = """당신은 스마트팩토리 플랫폼의 정비 자동 응답 전문가입니다.

**정비 응답 원칙**:
1. 고장 보고 유형을 정확히 파악합니다 (기계/전기/유압/공압/제어)
2. 스마트팩토리 운영 정책에 맞는 정확한 답변을 제공합니다
3. 상황 인지 표현으로 시작하되 핵심 해결책을 명확히 전달합니다
4. 처리 절차와 예상 소요 시간을 구체적으로 안내합니다

**정비 카테고리별 가이드**:
- 기계 고장: 진동 분석, 마모 점검, 윤활 상태 확인 절차
- 전기 고장: 전원 점검, 센서 교정, 배선 확인 절차
- 유압 고장: 유압유 점검, 실린더 상태, 배관 누유 확인
- 공압 고장: 에어 압력 점검, 밸브 상태, 배관 점검
- 제어 고장: PLC 로그 확인, 파라미터 점검, 프로그램 리셋

**주의사항**:
- 안전 관련 사항은 반드시 강조 (LOTO 절차 등)
- 확인되지 않은 진단은 하지 않음
- 복잡한 건은 전문 정비팀 연결 안내"""


# ============================================
# Maintenance Work Order Settings
# ============================================

WORK_ORDER_CATEGORIES = [
    "기계고장",      # 기계적 고장/마모/파손
    "전기고장",      # 전기/전자 부품 고장
    "유압고장",      # 유압 시스템 이상
    "공압고장",      # 공압 시스템 이상
    "제어고장",      # PLC/제어 시스템 오류
    "품질이상",      # 생산 품질 관련 이슈
    "예방정비",      # 정기 예방 정비 요청
    "설비개선",      # 설비 개선/업그레이드 요청
    "기타",          # 기타 요청
]

MAINTENANCE_PRIORITY_GRADES = {
    "urgent": {"min_score": 0.9, "description": "긴급 처리 필요", "color": "#ef4444"},
    "high": {"min_score": 0.7, "description": "우선 처리 대상", "color": "#f59e0b"},
    "normal": {"min_score": 0.4, "description": "일반 처리", "color": "#3b82f6"},
    "low": {"min_score": 0.0, "description": "낮은 우선순위", "color": "#22c55e"},
}

# ============================================
# Memory Settings
# ============================================

MAX_MEMORY_TURNS = 10

# ============================================
# Ranking Settings
# ============================================

DEFAULT_TOPN = 10
MAX_TOPN = 50

# ============================================
# Summary Triggers
# ============================================

SUMMARY_TRIGGERS = [
    "요약", "정리", "요점", "핵심", "한줄", "한 줄", "간단히", "짧게",
    "요약해줘", "요약해 줘", "정리해줘", "정리해 줘",
    "summary", "summarize", "tl;dr", "tldr", "brief"
]

# ============================================
# File Upload Settings
# ============================================

MAX_UPLOAD_SIZE_MB = 10
ALLOWED_EXTENSIONS = [".txt", ".pdf", ".docx", ".csv", ".json", ".md"]
