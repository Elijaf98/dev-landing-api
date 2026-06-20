"""Контроллер метрик: агрегированная статистика обращений."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.schemas.common import MetricsResponse
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/api", tags=["System"])


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Статистика обращений",
    description="Всего обращений, за последние 24 часа и разбивки по тональности, категории и приоритету.",
)
async def metrics(session: AsyncSession = Depends(get_session)) -> MetricsResponse:
    return await MetricsService(session).collect()
