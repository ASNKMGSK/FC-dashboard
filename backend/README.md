# 🏭 FMCS 사상압연 제어 시스템 — 백엔드

> **스마트팩토리 AI 플랫폼** | 설비 예지보전 · ML 예측 · LLM 에이전트 · 실시간 압연 시뮬레이션

![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-005571?style=flat-square&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3+-F7931E?style=flat-square&logo=scikit-learn)
![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-0081B4?style=flat-square)
![LightGBM](https://img.shields.io/badge/LightGBM-4.0+-A8B400?style=flat-square)
![MLflow](https://img.shields.io/badge/MLflow-2.10+-0194E2?style=flat-square&logo=mlflow)
![SHAP](https://img.shields.io/badge/SHAP-0.44+-FF6F61?style=flat-square)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=flat-square&logo=openai)

---

## 📁 디렉토리 구조

```
backend/
├── main.py                          # FastAPI 앱 진입점 (lifespan, 미들웨어, 라우터)
├── state.py                         # 전역 상태 싱글톤 (DataFrame 15개, ML 모델 7개)
├── requirements.txt
│
├── api/                             # REST API 라우터
│   ├── routes.py                    # 라우터 통합 (7개 도메인)
│   ├── routes_admin.py              # 인증, 사용자, 설정, 내보내기, 헬스체크
│   ├── routes_equipment.py          # 설비, 설비유형, 대시보드, 분석, SPC
│   ├── routes_production.py         # 생산라인 분석, 세그먼트, 불량탐지
│   ├── routes_maintenance.py        # 정비 자동배정, 파이프라인, SSE 스트리밍
│   ├── routes_ml.py                 # MLflow 실험/모델 관리, 드리프트, A/B 테스트
│   ├── routes_automation.py         # 자동화 엔진 4종 API
│   ├── routes_stands.py             # StandSimulator (사상압연 9스탠드 실시간)
│   └── common.py                    # 공통 Pydantic 모델, 인증 유틸
│
├── agent/                           # LLM 에이전트 시스템
│   ├── __init__.py
│   ├── router.py                    # 키워드 기반 의도 분류 (IntentCategory 9종)
│   ├── intent.py                    # frozenset 키워드 사전, 카테고리 매핑
│   └── tools.py                     # dual-layer 도구 (~30개 @tool 래퍼 + implementation)
│
├── ml/                              # ML 모델 학습
│   ├── train_models.py              # 7종 모델 학습 + 합성 데이터 생성 + MLflow 추적 + CSV→PKL 자동 변환 (15개 PKL 생성)
│   ├── yield_model.py               # 수율 예측 보조 모듈
│   └── process_optimizer.py         # P-PSO 공정 최적화
│
├── automation/                      # 자동화 엔진
│   ├── predictive_maintenance_engine.py  # ML→SHAP→LLM 예지보전
│   ├── troubleshooting_engine.py         # TF-IDF→클러스터→LLM 트러블슈팅 가이드
│   ├── production_report_engine.py       # KPI 집계→LLM 리포트 생성
│   ├── optimization_engine.py            # 규칙기반 공정 최적화 추천
│   └── action_logger.py                  # 파이프라인 이력 기록
│
├── core/                            # 핵심 공통 모듈
│   ├── constants.py                 # 설비 등급/유형, ML 피처 컬럼, 제조 용어집
│   ├── memory.py                    # 사용자별 대화 메모리 관리
│   └── utils.py                     # 타입 안전 변환, JSON 직렬화
│
├── data/
│   └── loader.py                    # 서버 시작 시 CSV/PKL 일괄 로드 → state.py 주입
│
├── logs/                            # RotatingFileHandler 로그 (최대 5MB × 3개)
├── mlruns/                          # MLflow 로컬 추적 저장소
└── model_*.pkl                      # 학습된 ML 모델 (lazy loading)
```

---

## ⚙️ 서버 설정 (`main.py`)

| 항목 | 값 |
|------|----|
| 포트 | `8001` |
| 호스트 | `0.0.0.0` |
| 앱 제목 | 스마트팩토리 AI 플랫폼 v2.0.0 |
| CORS | `allow_origins=["*"]` |
| GZip 압축 | 응답 1,000 bytes 이상 자동 압축 |
| 요청/응답 로깅 | HTTP 미들웨어 — 메서드, 경로, 상태코드 기록 |
| 전역 예외 핸들러 | 스택 트레이스 노출 없이 500 반환 |
| Lifespan | 시작 시 `init_data_models()` 호출 → DataFrame + 모델 적재 |

```bash
# 개발 서버 실행
cd backend
python main.py        # http://0.0.0.0:8001
```

---

## 🔌 API 엔드포인트 목록

> 전체 ~80개 엔드포인트. 모든 엔드포인트는 HTTP Basic Auth 필요 (공개 엔드포인트 제외).
> SSE 스트리밍 엔드포인트 7개: maintenance/pipeline/answer, maintenance/stream, models/retrain, predictive-maintenance/stream, production-report/stream, optimization/stream, automation/stream

### 인증 방식

- **HTTP Basic Auth**: `Authorization: Basic base64(username:password)`
- `verify_credentials()` — `state.USERS` dict에서 검증, 실패 시 401
- n8n 콜백 전용: `X-Callback-Token` 헤더 API 키 인증

### Admin (`/api`)

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/health` | 헬스체크 (모델/데이터 준비 상태 포함) |
| `POST` | `/api/login` | 로그인 (Basic Auth, 세션 메모리 초기화) |
| `GET` | `/api/users` | 사용자 목록 (관리자 전용) |
| `POST` | `/api/users` | 사용자 추가 (관리자 전용) |
| `GET` | `/api/settings/default` | LLM 기본 설정 조회 |
| `GET` | `/api/export/csv` | 운영 로그 CSV 다운로드 |
| `GET` | `/api/export/excel` | 운영 로그 Excel 다운로드 |

### Equipment (`/api`)

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/equipment` | 설비 목록 (usage/OEE/CVR/reliability 성과 포함) |
| `GET` | `/api/equipment/{equipment_id}` | 설비 상세 |
| `GET` | `/api/equipment/{equipment_id}/services` | 설비 서비스/작업이력 |
| `GET` | `/api/equipment-types` | 설비유형 목록 |
| `GET` | `/api/equipment-types/{type_id}` | 설비유형 상세 |
| `GET` | `/api/work-orders/statistics` | 작업지시/운영 통계 |
| `POST` | `/api/classify/fault` | 결함 텍스트 자동 분류 |
| `GET` | `/api/dashboard/summary` | 대시보드 요약 (OEE, MTBF, MTTR, 불량률, 생산량, 설비상태 그리드) |
| `GET` | `/api/spc/xbar-chart` | SPC X-bar/R 관리도 (H형강 두께) |
| `GET` | `/api/spc/capability` | 공정 능력 지수 (Cp, Cpk, Pp, Ppk) |
| `GET` | `/api/dashboard/insights` | AI 인사이트 (60초 캐싱) |
| `GET` | `/api/dashboard/alerts` | 실시간 알림 목록 |
| `GET` | `/api/analysis/anomaly` | 설비 이상탐지 분석 (days=7/30/90) |
| `GET` | `/api/analysis/prediction/failure` | 설비 고장 예측 (ML+SHAP, days=7/30/90) |
| `GET` | `/api/analysis/prediction/failure/equipment/{user_id}` | 개별 설비 고장 예측 + SHAP |
| `GET` | `/api/analysis/equipment/lifecycle` | 설비 수명주기 분석 (가동률 코호트, RUL, 공정흐름) |
| `GET` | `/api/analysis/trend/kpis` | 트렌드 KPI 분석 (가동설비, OEE, 신규등록 등) |

### Production (`/api`)

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/production-lines/autocomplete` | 생산라인 자동완성 검색 |
| `GET` | `/api/production-lines/analyze/{line_id}` | 생산라인 분석 |
| `POST` | `/api/production-lines/segment` | 생산라인 클러스터 분류 |
| `POST` | `/api/production-lines/defect` | 불량 탐지 |
| `GET` | `/api/production-lines/segments/statistics` | 세그먼트 통계 |
| `GET` | `/api/users/segments/{segment_name}/details` | 세그먼트 상세 |
| `GET` | `/api/production-lines/{line_id}/activity` | 생산라인 활동 리포트 |
| `GET` | `/api/production-lines/performance` | 생산라인 성과 목록 (상위 100개) |

### Maintenance (`/api`)

| 메서드 | URL | 설명 |
|--------|-----|------|
| `POST` | `/api/maintenance/reply` | 정비 자동배정 응답 생성 |
| `POST` | `/api/maintenance/quality` | 정비 품질 평가 |
| `GET` | `/api/maintenance/glossary` | 제조 용어 사전 |
| `GET` | `/api/maintenance/statistics` | 정비 통계 |
| `POST` | `/api/maintenance/pipeline` | 정비 자동화 파이프라인 (분류→우선순위→지시→통계 병렬) |
| `POST` | `/api/maintenance/pipeline/answer` | 정비 지시서 초안 SSE 스트리밍 |
| `POST` | `/api/maintenance/send-reply` | n8n 워크플로우 트리거 (job_id 반환) |
| `GET` | `/api/maintenance/stream` | SSE 스트림 (job_id 기반, n8n 단계별 이벤트) |
| `POST` | `/api/maintenance/callback` | n8n 콜백 수신 (API 키 인증) |

### ML (`/api`)

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/mlflow/experiments` | MLflow 실험 목록 |
| `GET` | `/api/mlflow/models` | 등록 모델 목록 (제조 시뮬레이션 fallback) |
| `GET` | `/api/mlflow/models/selected` | 현재 선택된 모델 조회 |
| `POST` | `/api/mlflow/models/select` | 모델 선택 및 state 반영 |
| `GET` | `/api/process/production-line/{line_id}` | 공정 생산라인 정보 |
| `POST` | `/api/process/optimize` | 공정 파라미터 최적화 (P-PSO) |
| `GET` | `/api/process/status` | 공정 최적화기 상태 |
| `GET` | `/api/models/drift` | 모델 드리프트 모니터링 (RMSE 추이, PSI, 에러분포) |
| `POST` | `/api/models/retrain` | 모델 재학습 시뮬레이션 (SSE, 진행률 전송) |
| `GET` | `/api/models/versions` | 모델 버전 이력 |
| `POST` | `/api/models/ensemble` | 앙상블 가중치 설정 |
| `POST` | `/api/models/ab-test` | A/B 모델 비교 |

### Automation (`/api/automation`)

**예방정비 자동 조치**

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/automation/predictive-maintenance/at-risk` | 고장 위험 설비 목록 |
| `POST` | `/api/automation/predictive-maintenance/message` | 예방정비 메시지 생성 |
| `POST` | `/api/automation/predictive-maintenance/execute` | 예방정비 조치 실행 |
| `GET` | `/api/automation/predictive-maintenance/history` | 예방정비 조치 이력 |
| `POST` | `/api/automation/predictive-maintenance/execute-bulk` | 다중 설비 일괄 조치 |
| `POST` | `/api/automation/predictive-maintenance/stream` | 예방정비 파이프라인 SSE |

**트러블슈팅 가이드**

| 메서드 | URL | 설명 |
|--------|-----|------|
| `POST` | `/api/automation/troubleshooting/analyze` | 결함 패턴 분석 (kmeans/llm 모드) |
| `POST` | `/api/automation/troubleshooting/generate` | 트러블슈팅 가이드 자동 생성 |
| `GET` | `/api/automation/troubleshooting/list` | 가이드 목록 |
| `PUT` | `/api/automation/troubleshooting/{faq_id}/approve` | 가이드 승인 |
| `PUT` | `/api/automation/troubleshooting/{faq_id}` | 가이드 수정 |
| `DELETE` | `/api/automation/troubleshooting/{faq_id}` | 가이드 삭제 |

**생산 리포트**

| 메서드 | URL | 설명 |
|--------|-----|------|
| `POST` | `/api/automation/production-report/generate` | 생산 리포트 생성 (daily/weekly/monthly) |
| `GET` | `/api/automation/production-report/history` | 리포트 생성 이력 |
| `POST` | `/api/automation/production-report/stream` | 리포트 생성 SSE |

**공정 최적화 추천**

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/automation/optimization/candidates` | 최적화 대상 설비 목록 |
| `POST` | `/api/automation/optimization/message` | 최적화 추천 메시지 생성 |
| `POST` | `/api/automation/optimization/execute` | 최적화 조치 실행 |
| `POST` | `/api/automation/optimization/stream` | 최적화 대상 설비 SSE |

**공통**

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/automation/actions/log` | 자동화 액션 로그 |
| `GET` | `/api/automation/actions/stats` | 자동화 액션 통계 |
| `GET` | `/api/automation/categories` | 결함 카테고리 목록 |
| `GET` | `/api/automation/pipeline/{run_id}` | 파이프라인 실행 상태 |

### Stands (`/api/stands`)

| 메서드 | URL | 설명 |
|--------|-----|------|
| `GET` | `/api/stands/equipment-list` | 설비 목록 (FM-LINE1/2/3) |
| `GET` | `/api/stands/status` | 9개 스탠드 실시간 상태 (전류/속도/하중/온도/롤갭/AI보상값/알람) |
| `GET` | `/api/stands/control` | 스탠드 제어 현황 (피스 진행률, AI자동/수동 비율, 롤갭, HMD) |
| `POST` | `/api/stands/operation-mode` | 운전모드 변경 (`ai_auto` ↔ `manual`) |
| `GET` | `/api/stands/load-speed-chart` | Load vs Speed 시계열 차트 데이터 |
| `GET` | `/api/stands/production-lines` | 생산라인 목록 |
| `GET` | `/api/stands/production-lines/{line_id}/pieces` | 선택 라인 생산 본 목록 |
| `GET` | `/api/stands/production-lines/{line_id}/pieces/{piece_no}/spc` | 특정 본의 SPC 분석 |
| `GET` | `/api/stands/{stand_id}/detail` | 단일 스탠드 상세 + 시계열 (1~9) |

---

## 🤖 Agent 시스템

단일 LLM 에이전트 패턴 — 키워드 기반 의도 분류 후 해당 카테고리 도구만 GPT-4o에 노출합니다.

### 처리 흐름

```
사용자 질문
    │
    ▼
agent/router.py  ←  agent/intent.py (frozenset 키워드 사전)
    │  키워드 매칭 (우선순위: 진단 > 설비ID > 예지보전 > 분석 > ...)
    │  → IntentCategory 결정
    ▼
CATEGORY_TOOLS 매핑
    │  해당 카테고리 도구 이름 목록 반환
    ▼
agent/tools.py  ←  @tool 래퍼 (ALL_TOOLS)
    │  필터링된 도구만 GPT-4o에 바인딩
    ▼
GPT-4o (OpenAI)
    │  도구 호출 결정
    ▼
tool_* implementation 함수
    │  state.py DataFrame / ML 모델 접근
    ▼
결과 반환 (_llm_instruction 필드로 해석 지침 포함)
```

### 의도 카테고리 (IntentCategory)

| 카테고리 | 설명 | 주요 도구 |
|----------|------|-----------|
| `CONSULTING` | 설비 종합진단 (4단계 워크플로우) | `analyze_equipment`, `predict_equipment_failure`, `optimize_process`, `generate_maintenance_plan` |
| `ANALYSIS` | OEE·고장·가동률·트렌드 분석 | `get_failure_prediction`, `get_oee_prediction`, `get_trend_analysis`, `get_lifecycle_analysis` |
| `EQUIPMENT` | 설비 분석·클러스터·불량탐지 | `analyze_equipment`, `detect_defect`, `get_equipment_cluster`, `predict_production_yield` |
| `EQUIPMENT_LINE` | 설비 정보·라인·성과·공정 | `get_equipment_info`, `list_equipment`, `get_equipment_performance`, `get_dashboard_summary` |
| `CS` | 정비 자동배정·품질검사·고장분류 | `auto_assign_maintenance`, `check_maintenance_quality`, `classify_fault` |
| `MAINTENANCE` | 고장예방·예지보전·위험설비 관리 | `get_at_risk_equipment`, `generate_maintenance_plan`, `execute_maintenance_action` |
| `DASHBOARD` | 대시보드·전체 현황 | `get_dashboard_summary`, `get_maintenance_statistics`, `get_production_event_statistics` |
| `PLATFORM` | 플랫폼 정책·기능·제조 용어 | `get_manufacturing_glossary` |
| `GENERAL` | 일반 대화 | (도구 없음) |

### 전체 도구 목록 (ALL_TOOLS)

| 도구명 | 설명 |
|--------|------|
| `get_equipment_info` | 설비 ID/명칭으로 상세 정보 조회 |
| `list_equipment` | 카테고리·등급·위치 필터 목록 |
| `get_equipment_services` | 설비 연결 정비 서비스 |
| `get_process_type_info` | 공정 유형 상세 |
| `list_process_types` | 전체 공정 유형 목록 |
| `auto_assign_maintenance` | 정비 요청 자동 배정 |
| `check_maintenance_quality` | 정비 품질 평가 |
| `get_manufacturing_glossary` | 제조 용어집 검색 |
| `get_maintenance_statistics` | 정비 CS 통계 |
| `analyze_equipment` | 설비 운영 패턴 분석 (클러스터·KPI) |
| `get_equipment_cluster` | 설비 피처 기반 클러스터 분류 |
| `detect_defect` | 불량·결함 탐지 (Isolation Forest) |
| `get_equipment_cluster_statistics` | 클러스터별 통계 |
| `get_defect_statistics` | 불량 통계 |
| `get_equipment_activity_report` | 설비 활동 리포트 |
| `get_production_event_statistics` | 생산 이벤트 통계 |
| `classify_fault` | 고장 유형 자동 분류 |
| `get_dashboard_summary` | 전체 KPI 대시보드 집계 |
| `predict_equipment_failure` | 설비 고장 확률 예측 (RF+SHAP) |
| `predict_production_yield` | 수율 예측 (LightGBM) |
| `get_equipment_performance` | 설비 성과 KPI 조회 |
| `optimize_process` | 공정 파라미터 최적화 (P-PSO) |
| `get_failure_prediction` | 고장 위험 설비 목록 |
| `get_lifecycle_analysis` | 설비 라이프사이클 단계별 분석 |
| `get_production_trend` | 생산량·가동률 트렌드 |
| `get_oee_prediction` | OEE 예측 및 추이 분석 |
| `get_at_risk_equipment` | 위험 임계값 초과 설비 조회 |
| `generate_maintenance_plan` | LLM 기반 정비 계획 생성 |
| `execute_maintenance_action` | 정비 조치 실행 (우선도알림/일정/배정) |
| `analyze_data` | 범용 통계 분석 (집계·트렌드·상관) |

#### Dual-layer 패턴

```python
# 1. Implementation 함수 (순수 Python, state.py 접근)
def tool_predict_equipment_failure(line_id: str) -> dict:
    model = st.get_model("EQUIPMENT_FAILURE_MODEL")  # lazy load
    ...
    return {"failure_probability": 0.82, "_llm_instruction": "..."}

# 2. @tool 래퍼 (GPT-4o 바인딩용)
@tool
def predict_equipment_failure(line_id: str) -> dict:
    """설비 고장 확률을 예측합니다."""
    return tool_predict_equipment_failure(line_id)
```

---

## 🧠 ML 모델 7종

모든 모델은 **Lazy Loading** 방식으로 첫 접근 시 `.pkl` 파일에서 로드되어 메모리에 캐시됩니다 (`state.get_model()`).

| # | state 변수명 | 알고리즘 (하이퍼파라미터) | 타입 | 주요 피처 | 지표 |
|---|-------------|--------------------------|------|-----------|------|
| 1 | `EQUIPMENT_FAILURE_MODEL` | RandomForestClassifier (n=200, depth=8, balanced) + SHAP TreeExplainer | 이진분류 | operating_hours, fault_count, downtime_hours, vibration, temperature, pressure, current, days_since_install, grade_encoded | Accuracy, F1 |
| 2 | `DEFECT_DETECTION_MODEL` | IsolationForest + StandardScaler | 이상탐지 | operating_hours, vibration, temperature, pressure, current, fault_count | 이상 비율 |
| 3 | `FAULT_CLASSIFICATION_MODEL` | TfidfVectorizer(max=500) + RandomForestClassifier | 다중분류 | 고장 보고 텍스트 (TF-IDF) | Accuracy, F1(macro) |
| 4 | `EQUIPMENT_CLUSTER_MODEL` | KMeans(k=4, n_init=10) + StandardScaler | 클러스터링 | operating_hours, fault_count, downtime_hours, vibration, temperature, current | Silhouette Score |
| 5 | `YIELD_PREDICTION_MODEL` | LGBMRegressor (n=200, depth=6, lr=0.05, leaves=31) / fallback: GradientBoostingRegressor | 회귀 | equipment_type_encoded, operating_hours, vibration, temperature, pressure, current, oee | MAE, R² |
| 6 | `MAINTENANCE_QUALITY_MODEL` | RandomForestClassifier (n=150, depth=10, balanced) | 다중분류 | fault_type_encoded, severity_encoded, response_time, repair_time, is_repeat_issue, technician_experience | Accuracy, F1(macro) |
| 7 | `EQUIPMENT_RUL_MODEL` | GradientBoostingRegressor (n=200, depth=5, lr=0.05) | 회귀 | operating_hours, vibration, temperature, pressure, current, fault_count | MAE, R² |

> `model_sensor_anomaly.pkl` (IsolationForest) 은 Guardian 전용으로 별도 관리됩니다 (PART 4).

### Lazy Loading 동작 방식

```python
# state.py
_MODEL_FILE_MAP = {
    "EQUIPMENT_FAILURE_MODEL":    "model_equipment_failure.pkl",
    "SHAP_EXPLAINER_FAILURE":     "shap_explainer_failure.pkl",
    "DEFECT_DETECTION_MODEL":     "model_defect_detection.pkl",
    "FAULT_CLASSIFICATION_MODEL": "model_fault_classification.pkl",
    "EQUIPMENT_CLUSTER_MODEL":    "model_equipment_cluster.pkl",
    "YIELD_PREDICTION_MODEL":     "model_yield_prediction.pkl",
    "MAINTENANCE_QUALITY_MODEL":  "model_maintenance_quality.pkl",
    "EQUIPMENT_RUL_MODEL":        "model_equipment_rul.pkl",
    "TFIDF_VECTORIZER":           "tfidf_vectorizer.pkl",
    "SCALER_CLUSTER":             "scaler_cluster.pkl",
}

def get_model(attr_name: str) -> Optional[Any]:
    current = globals().get(attr_name)
    if current is not None:
        return current              # 이미 로드됨 → 즉시 반환
    if attr_name in _MODEL_LOAD_FAILED:
        return None                 # 이전 실패 → 재시도 없음
    with _MODEL_LOAD_LOCK:          # 스레드 안전 더블체크
        model = joblib.load(filepath)
        globals()[attr_name] = model
    return model
```

### 설비 군집 이름 (K-Means k=4)

고장 빈도 오름차순으로 자동 매핑됩니다.

| 순위 (고장 빈도) | 이름 |
|----------------|------|
| 최소 | 우수 설비 |
| 2위 | 정상 설비 |
| 3위 | 주의 설비 |
| 최대 | 위험 설비 |

---

## ⚡ 자동화 엔진 4종

### 1. 예지보전 엔진 (`predictive_maintenance_engine.py`)

```
설비 데이터 수집
    │
    ▼
ML 고장 예측 (RandomForest)
    │  failure_probability ≥ threshold
    ▼
SHAP 고장원인 분석 (배치 처리, 500건씩 분할)
    │  상위 5개 중요 피처 추출
    ▼
LLM 정비 계획 생성 (GPT-4o)
    │  SHAP 결과 + 설비 정보 컨텍스트
    ▼
정비 조치 실행
    │  priority_alert | maintenance_schedule | manager_assign | custom_message
    ▼
action_logger 파이프라인 이력 기록
```

### 2. 트러블슈팅 엔진 (`troubleshooting_engine.py`)

```
정비 이력 텍스트 수집
    │
    ▼
TF-IDF 벡터화 (max_features=500)
    │
    ▼
실루엣 계수 최적 K 탐색 (k_min=2, k_max=min(n//8, 10))
    │
    ▼
MiniBatchKMeans 클러스터링
    │  배치 사이즈 256, 메모리 효율 최적화
    ▼
PCA 2D 시각화 좌표 생성
    │
    ▼
LLM 고장대응 가이드 자동 생성 (GPT-4o)
    │  클러스터별 대표 텍스트 + 샘플 주입
    ▼
가이드 저장/조회/수정/삭제 (CRUD)
```

### 3. 생산 리포트 엔진 (`production_report_engine.py`)

```
생산 KPI 수집 (state.py DataFrame)
    │  생산량, 불량률, 가동률, OEE, MTBF, MTTR, 사이클타임
    │  7일/30일 평균, 전주 대비 트렌드
    ▼
LLM 리포트 자동 작성 (GPT-4o)
    │  일간 | 주간 | 월간 리포트 타입
    ▼
리포트 저장 및 이력 관리
```

### 4. 공정 최적화 엔진 (`optimization_engine.py`)

```
규칙 기반 후보 설비 선정
    │  생산량/가동시간 기준 임계값 초과 설비
    │  최적화 점수 = 생산량비율×0.6 + 가동시간비율×0.4 (0~100)
    ▼
최적 파라미터 추천 생성
    │  4가지 액션: upgrade_recommend | benefit_info
    │              consultation_request | custom_message
    ▼
추천 메시지 생성 및 실행 기록
```

**등급 업그레이드 임계값**:

| 현재 등급 | 추천 등급 | 생산량 기준 | 가동시간 기준 |
|----------|----------|-----------|-------------|
| Basic | Standard | 5,000,000 | 100h |
| Standard | Premium | 20,000,000 | 500h |
| Premium | Enterprise | 50,000,000 | 2,000h |

### 파이프라인 이력 (`action_logger.py`)

모든 자동화 엔진의 공통 저장소입니다.

| 함수 | 설명 |
|------|------|
| `log_action(action_type, equipment_id, result)` | 단건 액션 기록 |
| `save_retention_action(...)` | 예방정비 이력 저장 |
| `create_pipeline_run(pipeline_type)` | 파이프라인 실행 시작 (run_id 발급) |
| `update_pipeline_step(run_id, step, data)` | 단계별 진행 상태 갱신 |
| `complete_pipeline_run(run_id)` | 파이프라인 완료 처리 |
| `save_faq / get_faq / get_all_faqs` | 트러블슈팅 가이드 조회 |
| `delete_faq / update_faq_status` | 트러블슈팅 가이드 삭제/승인 |
| `save_report / get_report_history` | 생산 리포트 이력 |

---

## 🔩 StandSimulator (사상압연 시뮬레이터)

9개 스탠드의 **시간 기반 연속 시뮬레이션** 엔진. 3개 독립 라인을 각각 차별화된 파라미터로 운영합니다.

### 3라인 구성

| 라인 ID | 라인명 | 제품규격 | current_factor | speed_factor | temp_offset | AI자동 초기값 |
|---------|--------|----------|----------------|--------------|-------------|---------------|
| `FM-LINE1` | 사상압연 1라인 | H300x300 | 1.00 | 1.00 | 0 | 35본 |
| `FM-LINE2` | 사상압연 2라인 | H400x400 | 1.05 | 0.97 | 0 | 28본 |
| `FM-LINE3` | 사상압연 3라인 | H250x250 | 0.97 | 1.00 | +10℃ | 42본 |

### 스탠드 기본값 (`_BASE_RAW`)

| 스탠드 | 전류 (A) | 속도 (m/s) | 하중 (kN) | 온도 (℃) |
|--------|---------|-----------|---------|---------|
| S1 | 280 | 2.5 | 800 | 1080 |
| S2 | 320 | 3.2 | 1000 | 1060 |
| S3 | 380 | 4.0 | 1300 | 1040 |
| S4 | 420 | 4.8 | 1500 | 1020 |
| S5 | 480 | 5.6 | 1800 | 1000 |
| S6 | 530 | 6.5 | 2000 | 980 |
| S7 | 580 | 7.8 | 2200 | 960 |
| S8 | 640 | 9.2 | 2500 | 940 |
| S9 | 720 | 11.0 | 2800 | 920 |

### sin 룩업 테이블

```python
# 1024포인트 룩업 테이블 (0~2π 커버)
_SIN_TABLE_SIZE = 1024
_SIN_TABLE = [math.sin(i * _TWO_PI / _SIN_TABLE_SIZE) for i in range(_SIN_TABLE_SIZE)]

def _fast_sin(x: float) -> float:
    """룩업 테이블 기반 sin 근사 (정밀도 ~0.3%, 속도 ~3x)"""
    idx = int(x * _SIN_SCALE) % _SIN_TABLE_SIZE
    return _SIN_TABLE[idx]
```

### 물리 시뮬레이션 구조

- **1본당 처리 시간**: 45초 (`_piece_duration`), `piece_duration_inv=1/45.0` — 나눗셈→곱셈 최적화
- **히스토리 버퍼**: `deque(maxlen=120)` — 30초 × 4Hz
- **스탠드 값 계산**: `base_value × (1 + amp × fast_sin(freq×t + phase) + gauss(0, noise))`
  - 전류 주기: `2π / (8 + i×0.7)` 초, 진폭: `0.05 + i×0.005`
  - 롤갭 캐시: `ws_base=12+i×0.3`, `ds_base=11.8+i×0.3`, `h_base=300+i×5`
- **장입 효과**: 피스가 스탠드 통과 시 전류 ×1.3 (`load_factor`)
- **HMD**: 아직 장입 안 된 스탠드는 `hmd_loaded=False`
- **알람 시뮬레이션**: 180~300초 주기로 랜덤 스탠드 `alarm/warning`, 40초 유지
- **progress 캐시**: 동일 0.1초 내 재호출 시 캐시 반환 (CPU 절약)

### 운전모드 (`OPERATION_MODE`)

```python
# state.py
OPERATION_MODE: str = "ai_auto"  # "ai_auto" | "manual"
```

- `ai_auto`: 본 완료 시 90% 확률로 AI자동 카운트 증가
- `manual`: 무조건 수동 카운트 증가

---

## 🗄️ state.py — 전역 상태 싱글톤

모든 모듈이 `import state as st`로 참조하는 단일 공유 상태 모듈입니다.

### DataFrame 15개

| 변수명 | 설명 |
|--------|------|
| `EQUIPMENT_DF` | 설비 마스터 (ID, 유형, 등급, 위치, 상태) |
| `EQUIPMENT_TYPES_DF` | 설비유형 마스터 (8종: CNC, 프레스, 사출, 용접, 조립, 도장, 검사, 포장) |
| `MAINTENANCE_SERVICES_DF` | 정비 서비스 데이터 (신규 생성) |
| `PRODUCTS_DF` | 부품/자재 데이터 |
| `PRODUCTION_LINES_DF` | 생산라인 데이터 |
| `OPERATION_LOGS_DF` | 운영 로그 |
| `LINE_ANALYTICS_DF` | 생산라인 분석 (세그먼트명 포함) |
| `EQUIPMENT_PERFORMANCE_DF` | 설비별 성과 KPI (OEE, 가동률, 수율, 신뢰도 포함) |
| `DAILY_PRODUCTION_DF` | 일별 생산 지표 (OEE, 가동설비, 작업지시수) |
| `MAINTENANCE_STATS_DF` | 정비 통계 |
| `WORK_ORDERS_DF` | 작업지시 원문 (클러스터링용) |
| `DEFECT_DETAILS_DF` | 불량 상세 데이터 |
| `EQUIPMENT_LIFECYCLE_DF` | 설비 라이프사이클 |
| `PRODUCTION_FUNNEL_DF` | 생산 퍼널 데이터 |
| `EQUIPMENT_ACTIVITY_DF` | 설비 일별 활동 |

### ML 모델 (Lazy Loading)

| 변수명 | pkl 파일 |
|--------|---------|
| `EQUIPMENT_FAILURE_MODEL` | `model_equipment_failure.pkl` |
| `SHAP_EXPLAINER_FAILURE` | `shap_explainer_failure.pkl` |
| `DEFECT_DETECTION_MODEL` | `model_defect_detection.pkl` |
| `FAULT_CLASSIFICATION_MODEL` | `model_fault_classification.pkl` |
| `EQUIPMENT_CLUSTER_MODEL` | `model_equipment_cluster.pkl` |
| `YIELD_PREDICTION_MODEL` | `model_yield_prediction.pkl` |
| `MAINTENANCE_QUALITY_MODEL` | `model_maintenance_quality.pkl` |
| `EQUIPMENT_RUL_MODEL` | `model_equipment_rul.pkl` |
| `TFIDF_VECTORIZER` | `tfidf_vectorizer.pkl` |
| `SCALER_CLUSTER` | `scaler_cluster.pkl` |

### 메모리 최적화

```python
def _optimize_df_memory(df: pd.DataFrame) -> pd.DataFrame:
    """object → category (유니크 비율 50% 미만)
       int64  → int32
       float64 → float32"""
```

### 앙상블 가중치

```python
ENSEMBLE_WEIGHTS: Dict[str, float] = {
    "xgboost": 0.40,
    "lightgbm": 0.35,
    "rf": 0.25,
}
```

### 사용자 DB (인메모리)

| 아이디 | 역할 |
|--------|------|
| `admin` | 관리자 |
| `user` | 사용자 |
| `operator` | 운영자 |
| `analyst` | 분석가 |

---

## 🚀 설치 및 실행

```bash
# 의존성 설치
cd backend
pip install -r requirements.txt

# 개발 서버
python main.py
# → http://0.0.0.0:8001

# ML 모델 학습 (최초 1회)
python ml/train_models.py
```

### 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 (또는 `openai_api_key.txt` 파일) | — |
| `CS_CALLBACK_SECRET` | 정비 콜백 엔드포인트 인증 토큰 | `""` (개발 모드 무인증) |
| `KMP_DUPLICATE_LIB_OK` | OpenMP 충돌 방지 | `TRUE` (자동 설정) |

```bash
# .env 파일 예시
OPENAI_API_KEY=sk-...
CS_CALLBACK_SECRET=your-secret-token
```

### Docker

```bash
docker build -f docker/Dockerfile -t fmcs-backend .
docker run -p 8001:8001 -e OPENAI_API_KEY=sk-... fmcs-backend
```

---

## 📊 MLflow 실험 추적

```bash
# 로컬 MLflow UI
mlflow ui --backend-store-uri ./mlruns
# → http://localhost:5000
```

모델 학습 시 다음 항목이 자동 기록됩니다:
- 하이퍼파라미터 (`mlflow.log_params`)
- 성능 지표 (`mlflow.log_metrics`)
- 모델 아티팩트 (`mlflow.sklearn.log_model`)
- 실험명: `smart-factory-ai`
