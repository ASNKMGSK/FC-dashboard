"""
agent/intent.py - 스마트팩토리 AI 플랫폼 인텐트 키워드/유틸리티 (단일 소스)
============================================================
cross-6: 키워드/인텐트 분류에 쓰이는 키워드를 이 파일에서 단일 소스로 정의.
router.py, runner.py 모두 이 파일을 import하여 사용.

M14/M15/M16: 기존 detect_intent/run_deterministic_tools 제거.
L6: want_defect_detection → EQUIPMENT 카테고리로 통합.
L7: LAST_CONTEXT_STORE → 미사용 제거.
"""
from typing import Optional, Dict, List


# ============================================================
# 카테고리별 분류 키워드 (단일 소스 - cross-6)
# ============================================================
# frozenset 사용: O(1) 키워드 검색 (list의 O(n) 대비 성능 향상)
ANALYSIS_KEYWORDS: frozenset = frozenset([
    "생산량", "수율", "yield", "oee", "가동률", "비가동", "성장률",
    "생산실적", "총생산", "생산 금액", "생산액",
    "고장", "failure", "고위험", "중위험", "저위험", "고장률", "고장 요인",
    "라이프사이클", "lifecycle", "잔존수명", "rul", "week1", "week4",
    "트렌드", "trend", "kpi", "mtbf", "mttr", "지표", "변화율",
    "가동 설비", "신규 설비", "도입 추이", "불량률", "변화 분석", "추이 분석",
    "신규 라인", "사이클타임", "택트타임", "생산 분석",
])

PLATFORM_KEYWORDS: frozenset = frozenset([
    "플랫폼", "정책", "기능", "운영", "가이드", "도움말", "사용법",
    "표준작업", "SOP", "안전규정", "정비주기", "보전정책", "교체주기",
    "부품관리", "예비부품", "API", "개발자", "센서설정", "알람설정",
    "설비등록", "라인구성", "공정설계",
    "뜻", "용어", "설명", "정의", "개념", "meaning", "definition",
    "뭐야", "무엇", "어떤", "알려줘", "어떻게 됐", "왜 그런",
    "윤활", "급유", "교정", "캘리브레이션", "점검", "점검주기",
    "ISO", "품질기준", "안전기준", "작업표준",
    "PLC", "SCADA", "MES", "ERP", "IoT",
])

EQUIPMENT_LINE_KEYWORDS: frozenset = frozenset([
    "설비 정보", "설비 서비스", "설비 성과", "설비 생산량",
    "설비 목록", "설비 리스트", "설비 현황", "설비 분포",
    "설비 등급", "설비 타입", "설비 유형",
    "설비 수", "설비 개수", "설비 몇", "설비 통계",
    "전체 설비", "총 설비", "설비 총",
    "라인 정보", "라인 성과", "라인 생산량", "라인 목록", "line",
    "공정별", "라인별", "유형별", "등급별",
    "공정 목록", "공정 전체", "공정 정보", "공정 현황",
    "설비유형 목록", "설비유형 전체", "설비유형 정보", "설비유형 현황",
    "CNC", "프레스", "사출", "용접", "조립", "도장", "열처리",
    "A등급", "B등급", "C등급", "S등급",
    "공정최적화", "공정 최적화", "공정 개선",
])

EQUIPMENT_KEYWORDS: frozenset = frozenset([
    "설비 분석", "설비 정보", "설비 고장", "설비 예측", "생산라인 분석", "설비진단",
    "클러스터", "군집",
    "정상 설비", "주의 설비", "우수 설비", "핵심 설비", "관리 필요 설비",
    "정상", "주의", "관리 필요",
    "이상 설비", "불량", "이상 탐지", "결함", "defect", "비정상", "품질불량", "불량률",
    "defect", "anomaly", "결함 탐지", "불량 탐지", "품질 이상",
])

CS_KEYWORDS: frozenset = frozenset([
    "정비", "정비 요청", "작업지시", "정비 기록", "자동 배정", "자동배정",
    "고장수리", "예방정비", "긴급정비", "정비 문의",
    "정비 품질", "정비 실적", "용어집",
    "고장 분류", "고장유형 분류", "분류해", "작업지시서", "정비계획",
    "센서이상", "진동이상", "온도이상", "압력이상", "정비요청",
])

DASHBOARD_KEYWORDS: frozenset = frozenset([
    "대시보드", "dashboard", "전체 현황", "요약",
    "설비 가동", "가동 현황", "생산 현황", "정비 현황",
    "운영 이벤트", "이벤트 통계", "이벤트 현황", "생산 이벤트", "정비 이벤트",
])

MAINTENANCE_KEYWORDS: frozenset = frozenset([
    # 분석 키워드("잔존수명", "rul")는 ANALYSIS_KEYWORDS와 중복되어 제거
    # → "라이프사이클 분석" 같은 질문이 MAINTENANCE로 잘못 분류되는 문제 방지
    "고장 위험", "고장 분석", "고장 예방", "고장 예측",
    "at-risk", "위험 설비", "정비 전략",
    "예지보전", "예지보전 전략", "정비 스케줄",
    "보전 실행", "정비 실행", "정비계획 실행", "예방정비 실행",
])

CONSULTING_KEYWORDS: frozenset = frozenset([
    "진단", "설비진단", "종합진단", "diagnosis",
    "종합 진단", "설비 종합진단", "설비 진단",
])

GENERAL_KEYWORDS: frozenset = frozenset([
    "안녕", "하이", "헬로", "hi", "hello",
    "고마워", "감사", "thanks",
    "뭐해", "누구", "자기소개",
])


# ============================================================
# 도구 강제 실행용 키워드-도구 매핑 (runner.py에서 사용)
# ============================================================
KEYWORD_TOOL_MAPPING: Dict[str, List[str]] = {
    "detect_defect": ["불량 탐지", "비정상 설비", "결함", "품질이상", "품질불량", "불량률"],
    "get_defect_statistics": ["결함", "불량", "이상 설비", "불량 통계", "불량 현황", "결함 통계", "결함 현황", "defect 통계", "품질 이상", "결함 탐지", "불량 현황"],
    "get_equipment_cluster_statistics": ["클러스터 통계", "설비 클러스터", "설비 분포", "클러스터 분석", "클러스터 현황",
                               "정상 설비", "주의 설비", "우수 설비", "핵심 설비", "관리 필요 설비"],
    "get_production_event_statistics": ["운영 이벤트", "이벤트 통계", "생산 이벤트", "정비 이벤트", "이벤트 현황"],
    "get_maintenance_statistics": ["정비 통계", "정비 현황", "정비 실적", "정비 품질"],
    "classify_fault": ["고장유형 분류", "고장 분류", "분류해줘", "분류해 줘"],
    "get_dashboard_summary": ["대시보드", "전체 현황", "요약 통계", "설비 가동", "가동 현황", "전체 설비", "등급별 분포", "유형별 분포", "전체 라인", "설비 수", "설비 개수", "설비 몇", "총 설비"],
    # 설비 목록/검색 도구
    "list_equipment": ["설비 목록", "설비 리스트", "설비 현황", "등급 설비", "유형 설비"],
    "list_process_types": ["공정 목록", "공정 전체", "공정 정보", "설비유형 목록", "설비유형 전체", "설비유형 정보", "설비유형 현황"],
    # ML 모델 예측 도구
    "predict_equipment_failure": ["고장 예측", "고장 확률", "고장 위험", "고장률", "failure", "설비 고장"],
    "get_equipment_performance": ["성과 분석", "설비 성과", "설비 생산량", "성과 예측", "생산 분석"],
    "optimize_process": ["공정 최적화", "공정 개선", "생산 최적화", "효율 최적화", "라인 최적화", "공정 분석"],
    # 분석 도구
    "get_failure_prediction": ["고장 분석", "고장 현황", "고장 통계", "고위험 설비", "고장 요인"],
    "get_lifecycle_analysis": ["라이프사이클", "수명 분석", "잔존수명 분석", "RUL 분석", "설비수명", "잔존율"],
    "get_trend_analysis": ["트렌드 분석", "KPI 분석", "지표 분석", "MTBF 분석", "상관관계", "가동 설비", "도입 추이", "불량률", "신규 도입", "변화 분석", "추이 분석", "생산량 분석"],
    "get_oee_prediction": ["OEE 예측", "OEE 분석", "가동률 예측", "수율 분석", "생산실적", "생산액"],
    # 설비 활동 리포트
    "get_equipment_activity_report": ["활동 리포트", "활동 보고서", "활동 보여줘", "가동 이력", "활동 내역"],
    # 예지보전(고장 예방) 도구
    "get_at_risk_equipment": ["고장 위험", "위험 설비", "at-risk", "고장 예방"],
    "generate_maintenance_plan": ["정비 계획", "정비 전략", "예지보전 전략"],
    "execute_maintenance_action": ["자동 정비", "보전 실행", "예방정비 실행"],
}


# ============================================================
# 정비 요청 카테고리 추출 (유틸리티)
# ============================================================
def extract_maintenance_category(user_text: str) -> Optional[str]:
    """텍스트에서 정비 요청 카테고리를 추출합니다."""
    if not user_text:
        return None

    category_map = {
        "기계": "mechanical", "mechanical": "mechanical", "기계 관련": "mechanical",
        "전기": "electrical", "electrical": "electrical", "전기 관련": "electrical", "전장": "electrical",
        "유압": "hydraulic", "hydraulic": "hydraulic", "유압 관련": "hydraulic",
        "공압": "pneumatic", "pneumatic": "pneumatic", "공압 관련": "pneumatic",
        "센서": "sensor", "sensor": "sensor", "센서 관련": "sensor", "계측": "sensor",
        "소프트웨어": "software", "software": "software", "PLC": "software", "제어": "software",
    }

    t = user_text.lower()
    for keyword, cat_code in category_map.items():
        if keyword in t:
            return cat_code

    return "general"
