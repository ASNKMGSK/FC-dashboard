"""
main.py - 애플리케이션 진입점
FastAPI 앱 생성, 미들웨어, lifespan, 라우터 등록
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

# .env 파일 로드
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# OpenMP 충돌 방지 (numpy/sklearn 등)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np

# numpy 호환성 패치
if not hasattr(np, "NaN"):
    np.NaN = np.nan  # noqa: N816

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

import state as st
from api.routes import router as api_router
from data.loader import init_data_models


# ============================================================
# Lifespan (startup/shutdown)
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    st.logger.info("APP_STARTUP")
    st.logger.info("BASE_DIR=%s", st.BASE_DIR)
    st.logger.info("LOG_FILE=%s", st.LOG_FILE)
    st.logger.info("PID=%s", os.getpid())

    try:
        init_data_models()
    except Exception as e:
        st.logger.exception("BOOTSTRAP_FAIL: %s", e)
        raise

    yield  # 앱 실행 중

    # ── shutdown ──
    st.logger.info("APP_SHUTDOWN")


# ============================================================
# 앱 생성
# ============================================================
app = FastAPI(title="스마트팩토리 AI 플랫폼", version="2.0.0", lifespan=lifespan)

# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# GZip 압축 (응답 크기 절감, Railway 메모리/대역폭 최적화)
# ============================================================
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ============================================================
# 요청/응답 로깅 미들웨어
# ============================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        st.logger.info("REQ %s %s", request.method, request.url.path)
        resp = await call_next(request)
        st.logger.info("RES %s %s %s", request.method, request.url.path, resp.status_code)
        return resp
    except Exception:
        st.logger.exception("UNHANDLED %s %s", request.method, request.url.path)
        raise

# ============================================================
# 전역 예외 핸들러 (#3: 스택 트레이스 노출 제거)
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    st.logger.exception("EXCEPTION %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "서버 내부 오류가 발생했습니다. 관리자에게 문의하세요.",
        },
    )

# ============================================================
# 라우터 등록
# ============================================================
app.include_router(api_router)

# ============================================================
# 직접 실행
# ============================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_config=None,
        access_log=True,
    )
