# ── Build Stage ──
FROM python:3.13-slim AS builder

WORKDIR /app

# 빌드용 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사 (캐싱 활용)
COPY requirements.txt .

# 파이썬 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime Stage ──
FROM python:3.13-slim

WORKDIR /app

# 런타임 시스템 의존성 설치 (libgomp1: LightGBM/XGBoost 등 필요)
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 빌드 스테이지에서 설치된 파이썬 패키지 복사
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 소스 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 환경변수
ENV PYTHONUNBUFFERED=1
ENV KMP_DUPLICATE_LIB_OK=TRUE
ENV MALLOC_ARENA_MAX=2
ENV PYTHONMALLOC=malloc

# 실행 (Railway는 PORT 환경변수 자동 주입)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
