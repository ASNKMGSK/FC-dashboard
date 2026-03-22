"""
agent/router.py - 스마트팩토리 AI 플랫폼 의도 분류 (키워드 기반)
============================================================
스마트팩토리 AI 플랫폼

질문을 키워드 기반으로 분류한 뒤, 해당 카테고리의 도구만 Executor에 노출합니다.
"""
import re
from typing import Optional
from enum import Enum

from core.utils import safe_str
from agent.intent import (
    ANALYSIS_KEYWORDS, PLATFORM_KEYWORDS, EQUIPMENT_LINE_KEYWORDS,
    EQUIPMENT_KEYWORDS, CS_KEYWORDS, DASHBOARD_KEYWORDS, GENERAL_KEYWORDS,
    MAINTENANCE_KEYWORDS, CONSULTING_KEYWORDS,
)
import state as st

# 설비 ID 패턴 사전 컴파일
_EQUIPMENT_ID_RE = re.compile(r'EQ\d{1,6}', re.IGNORECASE)


# ============================================================
# 카테고리 정의
# ============================================================
class IntentCategory(str, Enum):
    """질문 의도 카테고리"""
    CONSULTING = "consulting"   # 설비 종합진단 (4단계 워크플로우)
    ANALYSIS = "analysis"       # OEE, 생산량, 고장, 가동률, 라이프사이클, 트렌드
    PLATFORM = "platform"       # 플랫폼 정책, 기능, SOP, 매뉴얼
    EQUIPMENT_LINE = "equipment_line"  # 설비 정보, 라인, 성과, 생산량
    EQUIPMENT = "equipment"           # 설비 분석, 클러스터, 불량 탐지
    CS = "cs"                         # 정비 자동배정, 품질 검사, 고장 분류
    MAINTENANCE = "maintenance"       # 고장 예방, 예지보전, 위험 설비 관리
    DASHBOARD = "dashboard"     # 대시보드, 전체 현황
    GENERAL = "general"         # 일반 대화, 인사


# 카테고리별 도구 매핑
CATEGORY_TOOLS = {
    IntentCategory.CONSULTING: [
        "analyze_equipment",
        "predict_equipment_failure",
        "get_equipment_cluster",
        "optimize_process",
        "generate_maintenance_plan",
        "execute_maintenance_action",
    ],
    IntentCategory.ANALYSIS: [
        "get_failure_prediction",
        "get_oee_prediction",
        "get_trend_analysis",
        "get_lifecycle_analysis",
    ],
    IntentCategory.PLATFORM: [
        "get_manufacturing_glossary",
    ],
    IntentCategory.EQUIPMENT_LINE: [
        "get_equipment_info",
        "list_equipment",
        "get_equipment_services",
        "get_equipment_performance",
        "predict_production_yield",
        "optimize_process",
        "get_process_type_info",
        "list_process_types",
        "get_dashboard_summary",
    ],
    IntentCategory.EQUIPMENT: [
        "analyze_equipment",
        "predict_equipment_failure",
        "get_equipment_cluster",
        "detect_defect",
        "get_defect_statistics",
        "get_equipment_cluster_statistics",
        "optimize_process",
        "get_equipment_performance",
        "predict_production_yield",
        "get_equipment_activity_report",
    ],
    IntentCategory.CS: [
        "auto_assign_maintenance",
        "check_maintenance_quality",
        "get_manufacturing_glossary",
        "get_maintenance_statistics",
        "classify_fault",
    ],
    IntentCategory.MAINTENANCE: [
        "get_at_risk_equipment",
        "generate_maintenance_plan",
        "execute_maintenance_action",
        "analyze_equipment",
        "get_maintenance_statistics",
        "get_lifecycle_analysis",
    ],
    IntentCategory.DASHBOARD: [
        "get_dashboard_summary",
        "get_equipment_cluster_statistics",
        "get_maintenance_statistics",
        "get_production_event_statistics",
    ],
    IntentCategory.GENERAL: [],  # 도구 없이 대화만
}


# ============================================================
# 키워드 기반 분류
# ============================================================
def _keyword_classify(text: str) -> Optional[IntentCategory]:
    """
    키워드 기반 빠른 분류

    Returns:
        IntentCategory or None (불확실한 경우)
    """
    t = text.lower()

    # 우선순위: 진단 > 설비ID감지 > 예지보전 > 분석 > 설비 > 라인 > 정비 > 대시보드 > 플랫폼 > 일반

    # 0. 진단 키워드 (최우선 — "EQ0001 진단 해줘")
    if any(kw in t for kw in CONSULTING_KEYWORDS):
        return IntentCategory.CONSULTING

    # 0.5. 설비 ID(EQ0001)가 포함되면 EQUIPMENT 우선 (분석보다 높은 우선순위)
    if _EQUIPMENT_ID_RE.search(text):
        return IntentCategory.EQUIPMENT

    # 0.5. 예지보전 키워드 (ANALYSIS보다 우선 - 고장 예방/위험 설비 관리)
    if any(kw in t for kw in MAINTENANCE_KEYWORDS):
        return IntentCategory.MAINTENANCE

    # 1. 분석 키워드 (설비 ID 없는 일반 분석)
    if any(kw in t for kw in ANALYSIS_KEYWORDS):
        return IntentCategory.ANALYSIS

    # 2. 설비 분석 키워드
    if any(kw in t for kw in EQUIPMENT_KEYWORDS):
        return IntentCategory.EQUIPMENT

    # 3. 설비/라인 정보 관련 (성과, 정보, 공정)
    if any(kw in t for kw in EQUIPMENT_LINE_KEYWORDS):
        return IntentCategory.EQUIPMENT_LINE

    # 4. 정비 관련
    if any(kw in t for kw in CS_KEYWORDS):
        return IntentCategory.CS

    # 5. 대시보드 관련
    if any(kw in t for kw in DASHBOARD_KEYWORDS):
        return IntentCategory.DASHBOARD

    # 6. 플랫폼 관련 (정책, 기능, 용어)
    if any(kw in t for kw in PLATFORM_KEYWORDS):
        return IntentCategory.PLATFORM

    # 7. 일반 대화
    if any(kw in t for kw in GENERAL_KEYWORDS):
        return IntentCategory.GENERAL

    return None


def get_tools_for_category(category: IntentCategory) -> list[str]:
    """카테고리에 해당하는 도구 이름 목록 반환"""
    return CATEGORY_TOOLS.get(category, [])


# ============================================================
# 편의 함수
# ============================================================
def classify_and_get_tools(
    text: str,
    **kwargs,
) -> tuple[IntentCategory, list[str]]:
    """
    질문 분류 및 도구 목록 반환 (키워드 기반)

    Args:
        text: 사용자 질문

    Returns:
        (카테고리, 도구 이름 목록)
    """
    # 키워드 기반 분류
    category = _keyword_classify(text)

    if category is not None:
        st.logger.info(
            "ROUTER_KEYWORD query=%s category=%s",
            text[:40], category.value,
        )
        tools = get_tools_for_category(category)
        return category, tools

    # 기본값: GENERAL
    category = IntentCategory.GENERAL
    st.logger.info(
        "ROUTER_DEFAULT query=%s category=general",
        text[:40],
    )

    tools = get_tools_for_category(category)
    return category, tools
