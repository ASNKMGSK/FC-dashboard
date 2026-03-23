# 🏭 FMCS 사상압연 제어 시스템 대시보드

> H형강 사상압연 공정의 **실시간 모니터링**, **AI 자동제어**, **예지보전**을 통합한 스마트팩토리 AI 플랫폼

---

## 🛠️ 기술 스택

**Backend**
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3+-F7931E?style=flat-square&logo=scikitlearn)
![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-FF6600?style=flat-square)
![LightGBM](https://img.shields.io/badge/LightGBM-4.0+-02B875?style=flat-square)
![MLflow](https://img.shields.io/badge/MLflow-2.10+-0194E2?style=flat-square&logo=mlflow)
![SHAP](https://img.shields.io/badge/SHAP-0.44+-FF6B6B?style=flat-square)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=flat-square&logo=openai)

**Frontend**
![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=nextdotjs)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4+-06B6D4?style=flat-square&logo=tailwindcss)
![Recharts](https://img.shields.io/badge/Recharts-3.7+-22B5BF?style=flat-square)
![framer-motion](https://img.shields.io/badge/framer--motion-11-0055FF?style=flat-square)
![React Flow](https://img.shields.io/badge/React_Flow-12-FF0072?style=flat-square)

**Infra**
![Railway](https://img.shields.io/badge/Railway-Backend-0B0D0E?style=flat-square&logo=railway)
![Vercel](https://img.shields.io/badge/Vercel-Frontend-000000?style=flat-square&logo=vercel)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker)

### 🔗 배포 주소

| 구분 | URL |
|------|-----|
| **Frontend (Vercel)** | https://nextjs-lyart-seven-75.vercel.app |
| **Backend (Railway)** | https://fc-dashboard-backend-production.up.railway.app |

<p align="center">
  <img src="portfolio/qr-webapp.png" alt="웹앱 QR" width="120"><br>
  <sub>웹앱 바로가기</sub>
</p>

---

## ✨ 주요 기능

### 📊 공정 모니터링 (대시보드)
- OEE(설비종합효율), 생산량, 가동률 KPI 실시간 집계
- 설비별 고장 예측 점수 및 상태 현황
- 생산 트렌드 차트, 불량률 추이 시각화
- 숫자 보간 애니메이션으로 부드러운 실시간 업데이트

### 🎛️ 스탠드 제어 (FMCS)
- 9개 압연 스탠드 실시간 상태 모니터링 (전류·속도·하중·온도)
- AI 자동제어 모드 ON/OFF 전환 및 적용률 표시
- Roll Gap·HMD 상태 시각화
- 빌렛 이동 애니메이션, Canvas 기반 실시간 Load/Speed 차트
- 시간 기반 연속 시뮬레이션 엔진 (현실적 데이터 생성)

### 📈 품질/SPC 분석
- SPC X-bar/R 관리도 (UCL/LCL 관리 한계선, 이탈점 강조)
- 5개 서브탭: 이상탐지 / 공정능력·예측 / 롤 수명 관리 / 생산 트렌드 / 정비 분석
- SPC 2단계 검색: 생산라인 → 본(piece) 선택, 기간 필터(7/30/90일)
- 설비 군집 분석, 수율 예측, 잔여수명(RUL) 예측
- SHAP 기반 AI 의사결정 근거 제공

### 🧠 AI 모델 / MLOps
- 7종 ML 모델 관리 (학습·평가·배포)
- 하이퍼파라미터 튜닝: Optuna 기반 자동 탐색 (파라미터 체크박스 선택 방식)
- AutoGluon 선택 시 앙상블 가중치 관리 비활성화
- 모델별 버전 관리 UI (모델별 그룹 카드 + Production 배포 선택)
- 모델별 정확도·F1 점수·MAE·R² 성능 지표 조회

### 🔧 자동화 엔진
- **예지보전 엔진**: 고장 위험 설비 자동 감지 및 정비 일정 추천
- **공정최적화 엔진**: 규칙 기반 후보 설비 선정 → 파라미터 자동 추천
- **생산 리포트 엔진**: 일간/주간 생산 보고서 자동 생성
- **트러블슈팅 엔진**: 고장 유형 자동 분류 및 조치 가이드

### 🤖 AI 어시스턴트
- OpenAI GPT-4o 기반 LLM 에이전트
- 키워드 기반 의도 분류(9종 IntentCategory) → 전문 도구 자동 라우팅
- 설비 종합진단 4단계 워크플로우 (분석→예측→최적화→정비계획)

### 👥 사용자 관리 (관리자 전용)
- Basic Auth 기반 인증, 역할별 탭 접근 제어 (RBAC)
- 사용자 등록·수정·삭제
- 역할: 관리자 / 운영자 / 분석가 / 사용자 (관리자만 스탠드 제어·MLOps·로그 탭 접근)

---

## 🏗️ 아키텍처 개요

```
Browser (3000)
    │
    ▼
Next.js 14 (Pages Router)
  /api/* → rewrite → FastAPI 8001
    │
    ▼
FastAPI (Python 3.13)
  ├── api/          # 도메인별 라우터 (8개)
  ├── agent/        # LLM 에이전트 (의도분류 → 도구 실행)
  ├── ml/           # ML 모델 학습·추론 (7종)
  ├── automation/   # 자동화 엔진 (4종)
  ├── data/         # 데이터 로더 (CSV·PKL)
  └── state.py      # 전역 싱글톤 (DataFrame, 모델, 설정)
```

**프록시 구조**: 브라우저는 항상 `localhost:3000` 오리진만 호출 → Next.js가 `/api/*` 요청을 백엔드(`localhost:8001`)로 리라이트

**인증**: Basic Auth (`lib/api.js`의 `makeBasicAuthHeader`)

---

## 📁 디렉토리 구조

```
제조AI솔루션/
├── backend/                    # FastAPI 백엔드
│   ├── main.py                 # 앱 진입점 (포트 8001)
│   ├── state.py                # 전역 상태 싱글톤
│   ├── requirements.txt
│   ├── api/
│   │   ├── routes.py           # 라우터 통합 (8개 도메인)
│   │   ├── routes_equipment.py # 설비 관리 API
│   │   ├── routes_production.py# 생산 현황 API
│   │   ├── routes_maintenance.py# 정비 관리 API
│   │   ├── routes_ml.py        # ML 모델·MLflow API
│   │   ├── routes_stands.py    # FMCS 스탠드 제어 API
│   │   ├── routes_automation.py# 자동화 엔진 API
│   │   └── routes_admin.py     # 관리자 API
│   ├── agent/
│   │   ├── router.py           # 의도 분류 (IntentCategory 9종)
│   │   ├── intent.py           # 키워드 사전 (frozenset 기반)
│   │   └── tools.py            # @tool 래퍼 + 구현 함수 (dual-layer)
│   ├── ml/
│   │   ├── train_models.py      # 7종 ML 모델 학습
│   │   ├── yield_model.py
│   │   └── process_optimizer.py
│   ├── automation/
│   │   ├── optimization_engine.py           # 공정 최적화
│   │   ├── predictive_maintenance_engine.py # 예지보전
│   │   ├── production_report_engine.py      # 리포트 생성
│   │   ├── troubleshooting_engine.py        # 트러블슈팅
│   │   └── action_logger.py                 # 파이프라인 이력
│   ├── core/
│   │   ├── constants.py
│   │   ├── memory.py
│   │   └── utils.py
│   └── data/
│       └── loader.py            # 시작 시 CSV·PKL 로드
│
├── nextjs/                     # Next.js 14 프론트엔드
│   ├── pages/
│   │   ├── app.js              # 메인 SPA (탭 기반)
│   │   ├── login.js            # 로그인 페이지
│   │   └── index.js            # 리다이렉트
│   ├── components/
│   │   ├── panels/
│   │   │   ├── DashboardPanel.js   # 공정 모니터링
│   │   │   ├── StandControlPanel.js# FMCS 스탠드 제어
│   │   │   ├── AnalysisPanel.js    # 품질/SPC 분석
│   │   │   ├── ModelsPanel.js      # AI 모델/MLOps
│   │   │   ├── UsersPanel.js       # 사용자 관리
│   │   │   └── LogsPanel.js        # 로그 조회
│   │   ├── RealtimeLineCanvas.js   # Canvas 실시간 차트
│   │   ├── KpiCard.js, Layout.js, Sidebar.js 등
│   │   └── common/             # 공통 컴포넌트
│   ├── lib/
│   │   ├── api.js               # Basic Auth + fetch 클라이언트
│   │   ├── storage.js           # 로컬/세션 스토리지 유틸
│   │   └── cn.js                # Tailwind 클래스 병합 유틸
│   ├── next.config.js           # 백엔드 프록시 rewrites
│   └── tailwind.config.js       # sf-* 커스텀 팔레트
│
├── portfolio/
│   └── PORTFOLIO_re.html        # 포트폴리오 페이지
├── docs/
│   └── index.html               # GitHub Pages
├── CLAUDE.md                    # 프로젝트 가이드
└── 실행 명령어.txt
```

---

## 🚀 설치 및 실행

### 사전 요구사항
- Python 3.13 (conda 환경 권장)
- Node.js 18+
- OpenAI API Key

### 1. 백엔드 실행

```bash
# conda 환경 활성화
conda activate 3.13

# 의존성 설치
cd backend
pip install -r requirements.txt

# 개발 서버 실행 (http://0.0.0.0:8001)
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 2. 프론트엔드 실행

```bash
cd nextjs

# 의존성 설치
npm install

# 개발 서버 실행 (http://localhost:3000)
npm run dev -- -H 0.0.0.0
```

### 3. ML 모델 학습 (최초 1회)

```bash
cd backend
python ml/train_models.py
```

### 4. 프로덕션 배포

```bash
# 프론트엔드 빌드 (Vercel)
cd nextjs
npm run build
vercel --prod

# 백엔드 Docker 빌드 (Railway)
cd backend
docker build -t aoddudwns17821/fc-dashboard-backend:latest .
docker push aoddudwns17821/fc-dashboard-backend:latest
```

---

## ⚙️ 환경변수

### 백엔드 (`backend/.env`)

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | — |
| `BACKEND_INTERNAL_URL` | 프론트→백엔드 내부 URL | `http://127.0.0.1:8001` |

> `openai_api_key.txt` 파일로도 설정 가능 (`.env` 우선)

### 프론트엔드

프론트엔드는 별도 환경변수 없음. `next.config.js`의 rewrites가 `/api/*` 요청을 백엔드로 자동 프록시합니다.

> **보안 주의**: `.env`, `*_api_key.txt`, `*.pkl`, `*.csv`, `mlruns/` 등은 `.gitignore`로 추적 제외 (화이트리스트 방식).

---

## 🖥️ 주요 화면

### 공정 모니터링 대시보드
> OEE, 생산량, 설비 상태 KPI를 한눈에 확인

![Dashboard](docs/screenshots/dashboard.png)
<!-- TODO: 스크린샷 추가 -->

### FMCS 스탠드 제어
> 9개 압연 스탠드 실시간 제어 및 AI 자동제어 현황

![StandControl](docs/screenshots/stand_control.png)
<!-- TODO: 스크린샷 추가 -->

### 품질/SPC 분석
> SPC 관리도, 수율 예측, SHAP 기반 AI 근거 제공

![Analysis](docs/screenshots/analysis.png)
<!-- TODO: 스크린샷 추가 -->

### AI 모델/MLOps
> 7종 ML 모델 성능 지표 및 버전 관리 (Production 배포 선택)

![Models](docs/screenshots/models.png)
<!-- TODO: 스크린샷 추가 -->

---

## 🔬 기술 상세

### Canvas 실시간 차트
`RealtimeLineCanvas` / `RealtimeMultiLineCanvas` 컴포넌트는 HTML5 Canvas 2D API로 구현된 고성능 실시간 차트입니다.
- Recharts(SVG)보다 빠른 렌더링으로 **60fps** 업데이트 지원
- **RAF 통합 루프**: 9개 캔버스를 단일 requestAnimationFrame 루프로 배치 처리
- **Binary search viewport culling**: 화면 밖 데이터 포인트 렌더링 제거
- **Catmull-Rom spline 보간**: 부드러운 곡선 연결
- Load, Speed 등 다중 지표 동시 표시
- 스탠드 제어 패널에서 9개 스탠드 병렬 시각화에 활용

### ML 모델 7종

| # | 모델명 | 알고리즘 | 용도 |
|---|--------|---------|------|
| 1 | 설비 고장 예측 | RandomForest + SHAP | 고장 확률 분류 |
| 2 | 불량 감지 | Isolation Forest | 이상 센서 탐지 |
| 3 | 고장 유형 분류 | TF-IDF + RandomForest | 고장 보고 텍스트 분류 |
| 4 | 설비 군집화 | K-Means | 유사 설비 그룹핑 |
| 5 | 수율 예측 | LightGBM / GradientBoosting | 공정 수율 회귀 |
| 6 | 정비 품질 평가 | RandomForest Classifier | 정비 작업 품질 분류 |
| 7 | 설비 RUL | GradientBoosting Regressor | 잔여 수명 회귀 |

모든 모델은 MLflow로 버전 관리되며, `model_*.pkl` 형태로 저장됩니다. 하이퍼파라미터 튜닝은 Optuna 기반 자동 탐색(파라미터 체크박스 선택)을 지원하며, AutoGluon 선택 시 앙상블 가중치 관리가 비활성화됩니다.

### 스탠드 시뮬레이터 (StandSimulator)
- 9개 압연 스탠드의 실시간 물리 시뮬레이션
- sin 룩업 테이블(1024포인트) 기반 고속 근사 연산
- 시간 기반 연속 시뮬레이션 — 호출마다 독립적 난수가 아닌 연속적 상태 유지
- 전류, 속도, 하중, 온도 4개 물리량 동시 시뮬레이션

**3개 생산라인 독립 시뮬레이터 (라인별 차별화)**

| 라인 ID | 라인명 | 생산 제품 | current_factor | speed_factor | temp_offset | AI 자동제어 초기값 |
|---------|--------|----------|---------------|-------------|------------|----------------|
| FM-LINE1 | 사상압연 1라인 | H300x300 | 1.00 | 1.00 | 0 | 35본 |
| FM-LINE2 | 사상압연 2라인 | H400x400 | 1.05 | 0.97 | 0 | 28본 |
| FM-LINE3 | 사상압연 3라인 | H250x250 | 0.97 | 1.00 | +10℃ | 42본 |

각 라인은 독립적인 난수 시드(`seed_offset`)와 물리 파라미터로 서로 다른 공정 특성을 재현합니다. FM-LINE2는 대형 H형강(400mm) 생산으로 전류가 5% 높고 속도가 느리며, FM-LINE3는 소형 제품(250mm) 생산으로 온도가 10℃ 높게 설정됩니다.

### 자동화 엔진 파이프라인
각 엔진은 `action_logger.py`를 통해 파이프라인 실행 이력을 기록합니다.

```
요청 수신
    ↓
후보 설비 선정 (규칙 기반)
    ↓
최적화 점수 계산 (0~100)
    ↓
액션 추천 (파라미터조정 / 설비업그레이드 / 공정변경 / 정비스케줄)
    ↓
실행 및 이력 저장
```

### UI 스타일 시스템
- **Tailwind CSS** + `sf-*` 커스텀 팔레트 (스마트팩토리 브랜드 접두사)
- **폰트**: Pretendard (한국어 최적화)
- **애니메이션**: framer-motion (`slide-up`, `scale-in`, `fade-in`, `shimmer` 등)
- **아이콘**: lucide-react
- **다이어그램**: @xyflow/react (React Flow)
- **마크다운**: react-markdown + remark-gfm
- **수식**: KaTeX

**sf-* 컬러 팔레트**

| 토큰 | 색상값 | 용도 |
|------|--------|------|
| `sf-blue` | #2563EB | 주 브랜드 색 |
| `sf-dark` | #0F172A | 텍스트 |
| `sf-light` | #F8FAFC | 밝은 배경 |
| `sf-accent` | #10B981 | 성공/초록 |
| `sf-warn` | #F59E0B | 경고 |
| `sf-danger` | #EF4444 | 위험 |
| `sf-orange` | #FF8C42 | 사이드바 강조 |

커스텀 그림자: `shadow-sf`, `shadow-sf-lg`, `shadow-soft`, `shadow-lift`, `shadow-glow`

### SSE 이벤트 프로토콜
백엔드 → 프론트 7종 이벤트:

| 이벤트 | 설명 |
|--------|------|
| `delta` | AI 응답 스트리밍 토큰 |
| `tool_start` | 도구 호출 시작 |
| `tool_end` | 도구 호출 완료 + 결과 |
| `done` | 응답 완료 |
| `error` | 오류 발생 |
| `agent_start` | 에이전트 시작 |
| `agent_end` | 에이전트 종료 |

### 실시간 폴링 훅
`usePolling(fn, intervalMs)` — 탭 가시성 기반 스마트 폴링:
- `usePageVisibility()`: `document.hidden` 기반, 탭 비활성 시 interval 자동 해제
- 에러 발생 시 exponential backoff (최대 30초)
- 탭 전환 시 이전 in-flight 요청 AbortController로 취소

### 시뮬레이션 환경
별도 외부 데이터 없이 **즉시 체험 가능**합니다.
- StandSimulator 내장으로 압연 공정 물리 시뮬레이션 실시간 제공
- `train_models.py` 실행 시 제조 도메인 가상 데이터 자동 생성 후 모델 학습
- `/login` 페이지에서 체험용 계정(admin / operator / analyst / user) 빠른 로그인 지원

---

## 📄 라이선스

내부 프로젝트 — 무단 배포 금지
