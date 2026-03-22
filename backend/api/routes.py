"""
api/routes.py - 라우터 통합 모듈
=================================
각 도메인별 라우터를 하나의 APIRouter로 통합합니다.
main.py에서는 이 router 하나만 include하면 됩니다.

도메인 분리:
  - routes_admin.py        : 인증, 사용자, 설정, 내보내기, 헬스체크
  - routes_equipment.py    : 설비, 설비유형, 대시보드, 분석, 통계
  - routes_production.py   : 생산라인 검색/분석/세그먼트/성과
  - routes_maintenance.py  : 정비 자동배정, 파이프라인, n8n 콜백
  - routes_ml.py           : MLflow, 공정 파라미터 최적화
  - routes_automation.py   : 자동화 엔진 (고장예방정비/트러블슈팅/생산리포트)
"""
from fastapi import APIRouter

from api.routes_admin import router as admin_router
from api.routes_equipment import router as equipment_router
from api.routes_production import router as production_router
from api.routes_maintenance import router as maintenance_router
from api.routes_ml import router as ml_router
from api.routes_automation import router as automation_router
from api.routes_stands import router as stands_router

router = APIRouter()

router.include_router(admin_router)
router.include_router(equipment_router)
router.include_router(production_router)
router.include_router(maintenance_router)
router.include_router(ml_router)
router.include_router(automation_router)
router.include_router(stands_router)
