from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}


@router.get("/capabilities")
def capabilities():
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "api_version": "0.3.0",
        "tarot": True,
        "natal_astrology": True,
        "unknown_birth_time": True,
        "chart_svg": True,
        "ai_configured": bool(settings.openai_api_key),
        "password_recovery_configured": bool(settings.smtp_host and settings.smtp_from),
        "streaming": "sse",
        "quota_reset_timezone": "UTC",
    }
