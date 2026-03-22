"""
api/routes_admin.py - 관리/설정/사용자/헬스체크/내보내기
"""
import os
from datetime import datetime
from io import StringIO, BytesIO

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from core.memory import clear_memory
import state as st
from api.common import (
    verify_credentials, security,
    UserCreateRequest,
)
from fastapi.security import HTTPBasicCredentials

router = APIRouter(prefix="/api", tags=["admin"])


# ============================================================
# 헬스 체크
# ============================================================
@router.get("/health")
def health():
    st.logger.info("HEALTH_CHECK")
    return {
        "status": "success",
        "message": "ok",
        "pid": os.getpid(),
        "platform": "스마트팩토리 AI Platform",
        "models_ready": bool(
            (st.MAINTENANCE_QUALITY_MODEL is not None or "MAINTENANCE_QUALITY_MODEL" not in st._MODEL_LOAD_FAILED) and
            (st.EQUIPMENT_CLUSTER_MODEL is not None or "EQUIPMENT_CLUSTER_MODEL" not in st._MODEL_LOAD_FAILED) and
            (st.DEFECT_DETECTION_MODEL is not None or "DEFECT_DETECTION_MODEL" not in st._MODEL_LOAD_FAILED)
        ),
        "data_ready": {
            "equipment": st.EQUIPMENT_DF is not None and len(st.EQUIPMENT_DF) > 0,
            "categories": st.EQUIPMENT_TYPES_DF is not None and len(st.EQUIPMENT_TYPES_DF) > 0,
            "production_lines": st.PRODUCTION_LINES_DF is not None and len(st.PRODUCTION_LINES_DF) > 0,
            "operation_logs": st.OPERATION_LOGS_DF is not None and len(st.OPERATION_LOGS_DF) > 0,
        },
    }


# ============================================================
# 로그인
# ============================================================
@router.post("/login")
def login(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    if username not in st.USERS or st.USERS[username]["password"] != password:
        raise HTTPException(status_code=401, detail="인증 실패")
    user = st.USERS[username]
    clear_memory(username)
    return {"status": "success", "username": username, "user_name": user["name"], "user_role": user["role"]}


# ============================================================
# 사용자 관리
# ============================================================
@router.get("/users")
def get_users(user: dict = Depends(verify_credentials)):
    if user["role"] != "관리자":
        raise HTTPException(status_code=403, detail="권한 없음")
    return {"status": "success", "data": [{"아이디": k, "이름": v["name"], "권한": v["role"]} for k, v in st.USERS.items()]}


@router.post("/users")
def create_user(req: UserCreateRequest, user: dict = Depends(verify_credentials)):
    if user["role"] != "관리자":
        raise HTTPException(status_code=403, detail="권한 없음")
    if req.user_id in st.USERS:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디")
    st.USERS[req.user_id] = {"password": req.password, "role": req.role, "name": req.name}
    return {"status": "success", "message": f"{req.name} 추가됨"}


# ============================================================
# 설정
# ============================================================
@router.get("/settings/default")
def get_default_settings(user: dict = Depends(verify_credentials)):
    return {
        "status": "success",
        "data": {
            "maxTokens": 8000,
            "temperature": 0.1,
            "topP": 1.0,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": "",
            "timeoutMs": 30000,
            "retries": 2,
            "stream": True,
        },
    }


# ============================================================
# 내보내기
# ============================================================
@router.get("/export/csv")
def export_csv(user: dict = Depends(verify_credentials)):
    output = StringIO()
    export_df = st.OPERATION_LOGS_DF if st.OPERATION_LOGS_DF is not None else pd.DataFrame()
    export_df.to_csv(output, index=False, encoding="utf-8-sig")
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=smartfactory_data_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


@router.get("/export/excel")
def export_excel(user: dict = Depends(verify_credentials)):
    output = BytesIO()
    export_df = st.OPERATION_LOGS_DF if st.OPERATION_LOGS_DF is not None else pd.DataFrame()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="OperationLogs")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=smartfactory_data_{datetime.now().strftime('%Y%m%d')}.xlsx"},
    )
