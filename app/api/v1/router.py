from fastapi import APIRouter
from app.modules.health.routes import router as health_router
from app.modules.spreads.routes import router as spreads_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(spreads_router, prefix="/spreads", tags=["spreads"])
