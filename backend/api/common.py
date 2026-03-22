"""
api/common.py - 라우트 공통 모듈
Pydantic 모델, 인증, 유틸 등 모든 라우트 파일에서 공유하는 요소
"""
import json
from datetime import datetime
from typing import Optional, List

import pandas as pd
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from core.constants import DEFAULT_SYSTEM_PROMPT
from core.utils import json_sanitize
import state as st

# ============================================================
# 인증
# ============================================================
security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    if username not in st.USERS or st.USERS[username]["password"] != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 실패",
            headers={"WWW-Authenticate": "Basic"},
        )
    return {"username": username, "role": st.USERS[username]["role"], "name": st.USERS[username]["name"]}


# ============================================================
# SSE 유틸
# ============================================================
def sse_pack(event: str, data: dict) -> str:
    """SSE 이벤트 포맷으로 직렬화 (비표준 객체도 안전하게 처리)"""
    safe_data = json_sanitize(data)
    return f"event: {event}\ndata: {json.dumps(safe_data, ensure_ascii=False)}\n\n"


# ============================================================
# 시간 포맷 유틸
# ============================================================
def time_ago(dt_value, now: datetime = None) -> str:
    """datetime → '방금 전', 'N분 전', 'N시간 전', 'N일 전' 형태 문자열"""
    if dt_value is None or (isinstance(dt_value, float) and pd.isna(dt_value)) or pd.isna(dt_value):
        return "방금 전"
    if now is None:
        now = datetime.now()
    diff = now - dt_value
    if diff.days > 0:
        return f"{diff.days}일 전"
    if diff.seconds >= 3600:
        return f"{diff.seconds // 3600}시간 전"
    if diff.seconds >= 60:
        return f"{max(1, diff.seconds // 60)}분 전"
    return "방금 전"


# ============================================================
# 에러 응답 통일
# ============================================================
def error_response(message: str, **kwargs) -> dict:
    """표준 에러 응답 형식"""
    return {"status": "error", "message": message, **kwargs}


# ============================================================
# Pydantic 모델
# ============================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class EquipmentRequest(BaseModel):
    equipment_id: str


class CategoryRequest(BaseModel):
    category_id: str


class UserRequest(BaseModel):
    user_id: str


class MaintenanceReplyRequest(BaseModel):
    text: str
    ticket_category: str = Field("일반", description="정비 요청 카테고리")
    grade: str = Field("Standard", description="설비 등급")


class MaintenanceQualityRequest(BaseModel):
    ticket_category: str = Field("일반", description="정비 요청 카테고리")
    grade: str = Field("Standard", description="설비 등급")
    priority_score: float = Field(0.0, description="우선순위 점수 (-1.0 ~ 1.0)")
    cost_estimate: float = Field(50000, description="예상 정비 비용")
    is_repeat_issue: bool = Field(False, description="반복 고장 여부")
    text_length: int = Field(100, description="정비 요청 텍스트 길이")


class MaintenancePipelineRequest(BaseModel):
    """정비 자동화 파이프라인 요청"""
    inquiry_text: str = Field(..., description="정비 요청 텍스트")
    grade: str = Field("Standard", description="설비 등급")
    work_order_id: Optional[str] = Field(None, description="작업지시 ID")
    cost_estimate: float = Field(50000, description="예상 정비 비용")
    is_repeat_issue: bool = Field(False, description="반복 고장 여부")
    confidence_threshold: float = Field(0.75, description="자동 처리 신뢰도 임계값 (0.0~1.0)")


class MaintenancePipelineAnswerRequest(BaseModel):
    """정비 파이프라인 답변 생성 요청"""
    inquiry_text: str = Field(..., description="정비 요청 텍스트")
    inquiry_category: str = Field("기타", description="정비 요청 카테고리")
    grade: str = Field("Standard", description="설비 등급")
    work_order_id: Optional[str] = Field(None, description="작업지시 ID")
    api_key: str = Field("", alias="apiKey")
    class Config:
        populate_by_name = True
        allow_population_by_field_name = True
        allow_population_by_alias = True


class TextClassifyRequest(BaseModel):
    text: str


class AgentRequest(BaseModel):
    user_input: str = Field(..., alias="user_input")
    api_key: str = Field("", alias="apiKey")
    model: str = Field("gpt-4o-mini", alias="model")
    max_tokens: int = Field(8000, alias="maxTokens")
    system_prompt: str = Field(DEFAULT_SYSTEM_PROMPT, alias="systemPrompt")
    temperature: Optional[float] = Field(None, alias="temperature")
    top_p: Optional[float] = Field(None, alias="topP")
    presence_penalty: Optional[float] = Field(None, alias="presencePenalty")
    frequency_penalty: Optional[float] = Field(None, alias="frequencyPenalty")
    seed: Optional[int] = Field(None, alias="seed")
    timeout_ms: Optional[int] = Field(None, alias="timeoutMs")
    retries: Optional[int] = Field(None, alias="retries")
    stream: Optional[bool] = Field(None, alias="stream")
    debug: bool = Field(True, alias="debug")
    class Config:
        populate_by_name = True
        allow_population_by_field_name = True
        allow_population_by_alias = True


class UserCreateRequest(BaseModel):
    user_id: str
    name: str
    password: str
    role: str


class DeleteFileRequest(BaseModel):
    filename: str
    api_key: str = Field("", alias="apiKey")
    skip_reindex: bool = Field(False, alias="skipReindex")
    class Config:
        populate_by_name = True
        allow_population_by_field_name = True
        allow_population_by_alias = True


class ProcessOptimizeRequest(BaseModel):
    """공정 파라미터 최적화 요청 모델"""
    line_id: Optional[str] = Field(None, description="생산라인 ID")
    top_n: int = Field(10, description="상위 N개 결과")
    target_equipment: Optional[List[str]] = Field(None, alias="targetEquipment", description="대상 설비 ID 리스트")
    budget_constraints: Optional[dict] = Field(None, alias="budgetConstraints", description="예산 제약 (예: {'total': 1000000})")
    max_iterations: int = Field(10, alias="maxIterations", description="PSO 최대 반복 횟수")
    class Config:
        populate_by_name = True
        allow_population_by_field_name = True
        allow_population_by_alias = True


class ModelSelectRequest(BaseModel):
    model_name: str
    version: str


class SystemPromptRequest(BaseModel):
    system_prompt: str = Field(..., alias="systemPrompt")
    class Config:
        populate_by_name = True


class LLMSettingsRequest(BaseModel):
    """LLM 설정 요청 모델"""
    selected_model: str = Field("gpt-4o-mini", alias="selectedModel")
    custom_model: str = Field("", alias="customModel")
    temperature: float = Field(0.7, alias="temperature")
    top_p: float = Field(1.0, alias="topP")
    presence_penalty: float = Field(0.0, alias="presencePenalty")
    frequency_penalty: float = Field(0.0, alias="frequencyPenalty")
    max_tokens: int = Field(8000, alias="maxTokens")
    seed: Optional[int] = Field(None, alias="seed")
    timeout_ms: int = Field(30000, alias="timeoutMs")
    retries: int = Field(2, alias="retries")
    stream: bool = Field(True, alias="stream")
    class Config:
        populate_by_name = True
