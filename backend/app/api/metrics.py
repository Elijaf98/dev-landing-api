"""Контроллер метрик: агрегированная статистика обращений."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_metrics_auth
from app.db.database import get_session
from app.schemas.common import ErrorResponse, MetricsResponse
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/api", tags=["System"])


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    dependencies=[Depends(require_metrics_auth)],
    summary="Статистика обращений",
    description=(
        "Всего обращений, за последние 24 часа и разбивки по тональности, категории "
        "и приоритету. Если задан METRICS_API_KEY — нужен заголовок X-API-Key."
    ),
    responses={401: {"model": ErrorResponse, "description": "Нужен API-ключ"}},
)
async def metrics(session: AsyncSession = Depends(get_session)) -> MetricsResponse:
    return await MetricsService(session).collect()
