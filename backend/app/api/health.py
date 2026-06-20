"""Контроллер служебных эндпоинтов: health."""

import time

from fastapi import APIRouter

from app.config import get_settings
from app.db.database import check_db
from app.schemas.common import HealthResponse
from app.services.ai_service import get_ai_service

router = APIRouter(prefix="/api", tags=["System"])
settings = get_settings()

# Момент старта процесса — для расчёта uptime.
_STARTED_AT = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Статус сервиса",
    description="Проверка живости: версия, uptime и доступность БД / AI / почты.",
)
async def health() -> HealthResponse:
    db_ok = await check_db()

    checks = {
        "db": "up" if db_ok else "down",
        "ai": "up" if get_ai_service().available else "disabled",
        "email": "up" if settings.smtp_configured else "disabled",
    }

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.app_version,
        uptime_seconds=round(time.time() - _STARTED_AT, 1),
        checks=checks,
    )
