# 🏭 FMCS 사상압연 제어 시스템 — 프론트엔드

> **SmartFactory AI Platform** — Next.js 14 기반 제조 공정 실시간 모니터링 · 제어 · 분석 웹 앱

![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38BDF8?logo=tailwindcss)
![Recharts](https://img.shields.io/badge/Recharts-3.7-22C55E)
![framer-motion](https://img.shields.io/badge/framer--motion-11-EF3675?logo=framer)
![React Flow](https://img.shields.io/badge/@xyflow/react-12-FF0072)
![lucide-react](https://img.shields.io/badge/lucide--react-0.452-F97316)
![KaTeX](https://img.shields.io/badge/KaTeX-0.16-1D8348)

---

## 📁 디렉토리 구조

```
nextjs/
├── pages/
│   ├── _app.js               # 전역 앱 — NProgress 라우트 연동, ToastProvider 마운트
│   ├── _document.js          # HTML 문서 — lang="ko", Pretendard CDN preconnect
│   ├── index.js              # 진입점 — 세션 확인 후 /app 또는 /login 리다이렉트
│   ├── login.js              # 로그인 페이지 (Basic Auth, 체험용 계정 빠른 로그인)
│   └── app.js                # 메인 SPA — 탭 기반 패널 라우터
│
├── components/
│   ├── Layout.js             # 전체 레이아웃 (Topbar + Sidebar + main)
│   ├── Topbar.js             # 상단 헤더 바
│   ├── Sidebar.js            # 좌측 사이드바 (웰컴 팝업 포함)
│   ├── Tabs.js               # 탭 네비게이션 컴포넌트
│   ├── KpiCard.js            # KPI 지표 카드
│   ├── RealtimeLineCanvas.js # Canvas 2D 실시간 차트 (RAF 통합 루프)
│   ├── SectionHeader.js      # 섹션 제목 컴포넌트
│   ├── Skeleton.js           # 로딩 스켈레톤
│   ├── EmptyState.js         # 빈 상태 표시
│   ├── ToastProvider.js      # react-hot-toast 프로바이더
│   ├── panels/
│   │   ├── DashboardPanel.js       # 공정 모니터링 대시보드
│   │   ├── StandControlPanel.js    # 스탠드 제어 패널 (관리자 전용)
│   │   ├── AnalysisPanel.js        # re-export → analysis/AnalysisPanel
│   │   ├── ModelsPanel.js          # AI 모델 / MLOps 패널 (관리자 전용)
│   │   ├── UsersPanel.js           # 사용자 관리 (관리자 전용)
│   │   ├── LogsPanel.js            # 활동 로그 (관리자 전용)
│   │   ├── analysis/
│   │   │   ├── AnalysisPanel.js    # 품질/SPC 메인 (5개 서브탭)
│   │   │   ├── AnomalyTab.js       # 이상탐지 탭
│   │   │   ├── PredictionTab.js    # 공정능력/예측 탭
│   │   │   ├── LifecycleTab.js     # 롤 수명 관리 탭
│   │   │   ├── TrendTab.js         # 생산 트렌드 탭
│   │   │   ├── MaintenanceTab.js   # 정비 분석 탭
│   │   │   └── common/             # 분석 패널 공유 상수/컴포넌트
│   │   └── hooks/
│   │       └── usePageVisibility.js  # usePageVisibility + usePolling 훅
│   └── common/
│       ├── buttonStyles.js   # sf-* 버튼 스타일 유틸
│       ├── CustomTooltip.js  # Recharts 커스텀 툴팁
│       ├── StatCard.js       # 통계 카드
│       └── constants.js      # 공유 상수
│
├── lib/
│   ├── api.js                # fetch 클라이언트 (캐시, in-flight 중복 방지)
│   ├── storage.js            # localStorage / sessionStorage 헬퍼
│   ├── cn.js                 # Tailwind 클래스 병합 유틸
│   └── progress.js           # nprogress 연동
│
├── styles/
│   ├── globals.css           # 전역 CSS (Pretendard 폰트, 디자인 토큰)
│   └── nprogress.css         # 페이지 로딩 프로그레스 바
│
├── next.config.js            # Next.js 설정 (API 프록시 rewrites)
├── tailwind.config.js        # Tailwind 설정 (sf-* 팔레트, 커스텀 애니메이션)
├── jsconfig.json             # 경로 별칭 (@/ → 프로젝트 루트)
└── package.json
```

---

## 📄 페이지 구성

### `pages/_app.js` — 전역 앱 설정

모든 페이지에 공통으로 적용되는 전역 설정입니다.

- **NProgress**: `Router.events`의 `routeChangeStart/Complete/Error`에 `progressStart/progressDone` 연결하여 페이지 전환 시 상단 프로그레스 바 표시
- **ToastProvider**: `react-hot-toast` 토스트 알림을 전역으로 마운트
- **전역 CSS**: `globals.css`, `nprogress.css` 임포트

### `pages/_document.js` — HTML 문서 커스터마이징

- `lang="ko"` 설정으로 스크린 리더 및 검색엔진 언어 선언
- `cdn.jsdelivr.net`에 `preconnect` + `dns-prefetch`로 Pretendard 폰트 로딩 가속
- Pretendard v1.3.9 정적 CSS CDN 로드

### `pages/index.js` — 진입점 리다이렉트

세션 스토리지(`sf_auth`)에 인증 정보가 있으면 `/app`으로, 없으면 `/login`으로 즉시 리다이렉트합니다. 스피너만 렌더링되며 실제 콘텐츠는 없습니다.

### `pages/login.js` — 로그인 페이지

| 기능 | 설명 |
|------|------|
| **Basic Auth** | `username:password`를 `btoa()`로 인코딩해 `sessionStorage`에 저장 |
| **체험용 계정** | 관리자 / 운영자 / 분석가 / 사용자 4개 계정을 클릭 한 번으로 즉시 로그인 |
| **플로팅 아이콘** | framer-motion 없이 CSS `sf-float` 애니메이션으로 배경 제조 아이콘 연출. 내부 페이지와 통일된 sf-orange/sf-brown/sf-beige 톤 적용 |
| **서버 운영 안내** | AM 9:00 ~ PM 6:00 KST 운영 시간 표시 |

로그인 성공 시 `{ username, password_b64, user_name, user_role }` 객체를 `sessionStorage`에 저장하고 `/app`으로 이동합니다.

### `pages/app.js` — 메인 SPA

탭 기반 Single Page Application입니다. 모든 패널 컴포넌트는 `next/dynamic`으로 **지연 로딩**되어 초기 번들 크기를 최소화합니다.

#### 탭 목록 (역할별 분기)

| 탭 키 | 레이블 | 접근 권한 |
|--------|--------|-----------|
| `dashboard` | 📊 공정 모니터링 | 전체 |
| `control` | 🎛️ 스탠드 제어 | **관리자 전용** |
| `analysis` | 📈 품질/SPC | 전체 |
| `models` | 🧠 AI 모델/MLOps | **관리자 전용** |
| `users` | 👥 사용자 관리 | **관리자 전용** |
| `logs` | 📋 로그 | **관리자 전용** |

#### 주요 상태 관리

- **인증**: `sessionStorage`에서 복원, 없으면 `/login` 리다이렉트
- **설정/로그**: `localStorage`에 300ms debounce로 자동 저장
- **반응형 zoom**: 화면 너비 < 1280px → `0.85`, 그 외 → `0.9`
- **설비/카테고리**: `/api/equipment`, `/api/equipment-types` API 자동 로드

---

## 🧩 패널 컴포넌트 상세

### 📊 DashboardPanel — 공정 모니터링

실시간 설비 KPI를 한눈에 확인하는 메인 대시보드입니다.

- **KPI 카드**: 전류·속도·온도 등 핵심 지표, `AnimatedValue`로 숫자 부드럽게 보간
- **LIVE 인디케이터**: 1초 단위 실시간 시계, 탭 비활성 시 업데이트 중지
- **미니 스파크라인**: Recharts `LineChart`로 스탠드별 추이 시각화
- **Recharts 차트**: `ComposedChart`, `LineChart`로 복합 공정 데이터 표시
- **폴링**: `usePolling` 훅으로 데이터 자동 갱신, 탭 숨김 시 중지
- **framer-motion**: `FadeInSection`으로 스크롤 진입 시 섹션 fade-in

### 🎛️ StandControlPanel — 스탠드 제어 (관리자 전용)

9개 압연 스탠드(S1~S9)의 실시간 제어 현황을 시각화합니다.

- **StepIndicator**: 빌렛이 S1→S9를 통과하는 단계를 원형 인디케이터 + 연결선으로 표시, 현재 스탠드 위치에 애니메이션 흐름 효과
- **SVG Arc Gauge**: AI 자동제어 적용률을 원호(arc) 게이지로 시각화
- **빌렛 이동 애니메이션**: framer-motion으로 압연 공정 흐름 시각화
- **AnimatedNumber**: RAF 기반 카운팅 애니메이션 (600ms easing)
- **ProgressBar**: framer-motion `animate`로 부드러운 프로그레스 바
- **RealtimeLineCanvas**: 각 스탠드의 전류/속도/Setpoint Canvas 실시간 차트

### 📈 AnalysisPanel — 품질/SPC (5개 서브탭)

압연 공정의 품질 분석을 5개 탭으로 제공합니다. Recharts 사용 탭은 `dynamic import`로 코드 스플리팅됩니다.

| 탭 | 기능 |
|----|------|
| **이상탐지** | SPC 관리도, 이상 감지 알림, 생산라인/본 2단계 선택 |
| **공정능력/예측** | Cp/Cpk 공정능력 지표, ML 예측값 시각화 (7종 모델) |
| **롤 수명 관리** | 압연 롤 수명 예측, 교체 주기 관리 |
| **생산 트렌드** | 기간별(7일/30일/90일) 생산량·불량률 추이 |
| **정비 분석** | 정비 이력, CS 데이터 분석 |

### 🧠 ModelsPanel — AI 모델/MLOps (관리자 전용)

MLflow 연동 모델 성능 대시보드입니다.

- 모델별 상태 배지 (정상 / 주의 / 위험 / OK / WARNING / CRITICAL)
- PSI(Population Stability Index) 바 차트로 모델 드리프트 모니터링
- Recharts `LineChart`, `BarChart`로 성능 지표 추이 시각화
- framer-motion `staggerChildren`으로 카드 순차 등장 애니메이션
- **하이퍼파라미터 튜닝**: Optuna 기반 자동 탐색. 10개 파라미터 중 체크박스로 대상을 선택하면 자동으로 최적 조합을 탐색
- **앙상블 가중치 관리**: AutoGluon(WeightedEnsemble) 선택 시 비활성화 (내부 자동 결정)
- **모델별 버전 관리 UI**: 모델별 그룹 카드 형태로 버전 목록 표시, Production 배포 버전 선택 지원
- **실험 기록 섹션**: 제거됨 (버전 관리 UI로 통합)

### 👥 UsersPanel — 사용자 관리 (관리자 전용)

사용자 조회 및 신규 등록 기능을 제공합니다.

- `/api/users` GET으로 사용자 목록 조회
- `/api/users` POST로 신규 사용자 등록 (아이디, 이름, 비밀번호, 역할)
- 역할: 관리자 / 운영자 / 분석가 / 사용자

### 📋 LogsPanel — 활동 로그 (관리자 전용)

클라이언트 측 활동 이력을 표로 표시합니다.

- `app.js`의 `activityLog` 상태를 받아 최신순으로 렌더링 (`useMemo` 캐싱)
- 표시 컬럼: 시간, 사용자, 작업, 상세
- 로그는 `localStorage`에 300ms debounce로 자동 저장

---

## ⚡ 핵심 컴포넌트

### `RealtimeLineCanvas` — Canvas 2D 실시간 스파크라인

`components/RealtimeLineCanvas.js`에 `RealtimeLineCanvas`(단일 라인)와 `RealtimeMultiLineCanvas`(다중 라인) 두 컴포넌트가 함께 정의되어 있습니다.

#### 성능 최적화 기법

| 기법 | 설명 |
|------|------|
| **통합 RAF 루프** | 모듈 스코프 `rafCallbacks` Set으로 9개 캔버스를 단일 `requestAnimationFrame` 루프에서 처리. 캔버스 수가 증가해도 RAF는 1개 |
| **Binary Search Viewport Culling** | `lowerBound()` 함수로 O(log n) 탐색. 뷰포트(현재 시각 기준 windowMs) 밖의 포인트는 렌더링 건너뜀 |
| **포인트 버퍼 재사용** | `pointBuf.current` 배열을 매 프레임 재사용하여 GC pressure 최소화 |
| **Gradient 캐싱** | `gradientCache` Map에 색상+높이 키로 `LinearGradient` 1회 생성 후 재사용 |
| **가상 포인트 연장** | 마지막 데이터 포인트를 현재 시각까지 수평 연장하여 끊김 없는 흐름 표현 |
| **DPR 대응** | `devicePixelRatio`로 레티나 디스플레이 선명도 보장, 마운트 시 1회만 설정 |
| **Catmull-Rom Spline** | `drawSpline()`으로 포인트 사이를 부드러운 베지어 곡선으로 연결 |

#### `RealtimeMultiLineCanvas` 추가 기능

- 다중 라인: `lines` prop으로 `{ dataKey, color, strokeWidth, dashed, yAxisSide }` 배열 전달
- 라인별 Y축 레이블 (좌/우 독립 스케일)
- 그리드 라인 (4분할), X축 시간 레이블 (분:초 형식)
- 라인별 독립 포인트 버퍼 (`lineBufs.current[dataKey]`)

---

## 🪝 커스텀 Hooks

`components/panels/hooks/usePageVisibility.js`에 정의됩니다.

### `usePageVisibility()`

```js
const isVisible = usePageVisibility();
```

`document.visibilitychange` 이벤트를 구독해 현재 탭 활성 여부를 boolean으로 반환합니다. 탭이 숨겨지면 `false`를 반환하여 불필요한 업데이트를 차단합니다.

### `usePolling(fn, intervalMs, options)`

```js
usePolling(async (signal) => {
  const data = await apiCall({ endpoint: '/api/production', auth });
  setData(data);
}, 5000, { immediate: true });
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `enabled` | `true` | 폴링 활성화 여부 |
| `immediate` | `false` | 마운트/탭 복귀 시 즉시 1회 실행 |
| `maxBackoff` | `30000` | 최대 백오프 간격 (ms) |

**핵심 동작:**
- 탭 비활성(`isVisible = false`) 시 interval 완전 해제, 활성 복귀 시 재시작
- 탭 전환 시 이전 요청 `AbortController`로 즉시 취소
- 에러 발생 시 exponential backoff: `interval × 2^failures` (최대 `maxBackoff`)
- 내부적으로 `usePageVisibility()`를 사용

---

## 🎨 스타일 시스템

### sf-* 커스텀 팔레트

`tailwind.config.js`에 정의된 SmartFactory 브랜드 컬러입니다.

| 토큰 | 값 | 용도 |
|------|----|------|
| `sf-blue` | `#2563EB` | 주요 액션, 포인트 컬러 |
| `sf-dark` | `#0F172A` | 본문 텍스트, 어두운 배경 |
| `sf-light` | `#F8FAFC` | 밝은 배경 |
| `sf-accent` | `#10B981` | 성공, 정상 상태 |
| `sf-warn` | `#F59E0B` | 경고 상태 |
| `sf-danger` | `#EF4444` | 위험, 에러 상태 |
| `sf-cream` | `#F1F5F9` | 페이지 배경 |
| `sf-beige` | `#E2E8F0` | 카드 배경, 구분선 |
| `sf-pink` | `#F472B6` | 강조 포인트 |
| `sf-brown` | `#5C4A3D` | 따뜻한 텍스트 톤 |
| `sf-yellow` | `#FFD93D` | 하이라이트 |
| `sf-orange` | `#FF8C42` | 레이아웃 배경 그라데이션 |

### 폰트

```css
font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif;
```

`tailwind.config.js`의 `fontFamily.sans`를 오버라이드하여 Pretendard를 기본 폰트로 사용합니다.

### 박스 섀도우

| 클래스 | 설명 |
|--------|------|
| `shadow-sf` | 기본 SF 블루 그림자 |
| `shadow-sf-lg` | 큰 SF 블루 그림자 |
| `shadow-sf-sm` | 작은 SF 블루 그림자 |
| `shadow-soft` | 부드러운 다크 그림자 |
| `shadow-soft-lg` | 큰 부드러운 그림자 |
| `shadow-lift` | 카드 부상 효과 |
| `shadow-lift-lg` | 강한 카드 부상 효과 |
| `shadow-glow` | SF 블루 글로우 |
| `shadow-inner-glow` | 내부 하이라이트 |

### 커스텀 애니메이션 (Tailwind keyframes)

| 클래스 | 동작 | Easing |
|--------|------|--------|
| `animate-slide-up` | 아래→위 0.35s | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-slide-down` | 위→아래 0.35s | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-scale-in` | 0.95→1 scale 0.25s | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-fade-in` | opacity 0→1 0.3s | `ease-out` |
| `animate-shimmer` | 스켈레톤 shimmer 2s loop | `linear` |

---

## 🔌 API 프록시 구조

`next.config.js`의 `rewrites()`로 브라우저가 항상 동일 오리진에 요청하도록 합니다.

```
브라우저 (localhost:3000)
    │
    │  GET/POST /api/*
    ▼
Next.js Dev Server (rewrites)
    │
    │  → http://127.0.0.1:8001/api/*
    ▼
FastAPI 백엔드
```

```js
// next.config.js
async rewrites() {
  const backend = process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:8001';
  return [
    { source: '/api/:path*', destination: `${backend}/api/:path*` },
  ];
}
```

CORS 설정 없이 프론트엔드 개발이 가능하며, 프로덕션에서도 동일한 오리진으로 배포할 수 있습니다.

### `lib/api.js` — fetch 클라이언트

```js
import { apiCall, makeBasicAuthHeader } from '@/lib/api';

const res = await apiCall({
  endpoint: '/api/production',
  method: 'GET',
  auth: { username, password_b64 },
  timeoutMs: 30000,
});
```

| 기능 | 설명 |
|------|------|
| **Basic Auth** | `makeBasicAuthHeader()`로 `Authorization: Basic <base64>` 헤더 자동 첨부 |
| **TTL 캐시** | `/api/equipment`, `/api/equipment-types` 엔드포인트에 60초 in-memory 캐시 (최대 50개) |
| **In-flight 공유** | 동일 GET 요청이 진행 중이면 새 fetch 없이 기존 Promise 반환 |
| **AbortController** | `timeoutMs` 초과 시 요청 자동 취소 |
| **환경변수** | `NEXT_PUBLIC_API_BASE`로 백엔드 URL 오버라이드 가능 (기본: 동일 오리진) |

---

## 🛠️ 개발 환경

### 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 시작 (http://localhost:3000)
npm run dev

# 프로덕션 빌드
npm run build

# 프로덕션 서버 시작
npm start

# ESLint 검사
npm run lint
```

### 환경변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `BACKEND_INTERNAL_URL` | `http://127.0.0.1:8001` | Next.js → FastAPI 프록시 대상 URL |
| `NEXT_PUBLIC_API_BASE` | `''` (동일 오리진) | 브라우저에서 API 호출 시 베이스 URL |

`.env.local` 파일 예시:

```env
BACKEND_INTERNAL_URL=http://127.0.0.1:8001
NEXT_PUBLIC_API_BASE=
```

### 주요 의존성 버전

| 패키지 | 버전 |
|--------|------|
| `next` | ^14.2.0 |
| `react` / `react-dom` | ^18.2.0 |
| `tailwindcss` | ^3.4.1 |
| `recharts` | ^3.7.0 |
| `framer-motion` | ^11.0.0 |
| `@xyflow/react` | ^12.10.0 |
| `lucide-react` | ^0.452.0 |
| `katex` | ^0.16.28 |
| `react-markdown` | ^9.0.1 |
| `react-hot-toast` | ^2.4.1 |
| `nprogress` | ^0.2.0 |

---

## 🔑 인증 흐름

```
1. /login 에서 username + password 입력
        │
        ▼
2. POST /api/login (Basic Auth 헤더)
        │
        ├── 성공 → { username, password_b64, user_name, user_role }
        │          sessionStorage 저장 후 /app 이동
        └── 실패 → 에러 메시지 표시
                │
3. /app 진입 시 sessionStorage 복원
        │
        ├── user_role === '관리자' → 6개 탭 전체
        └── 그 외 → dashboard + analysis 2개 탭
```

인증 정보는 **sessionStorage**에 저장되므로 브라우저 탭을 닫으면 자동 로그아웃됩니다. 설정 및 활동 로그는 **localStorage**에 저장되어 세션 간 유지됩니다.

---

*© 2026 SmartFactory AI Platform*
