"""Простая защита служебных эндпоинтов по API-ключу.

Для демо метрики открыты (METRICS_API_KEY пуст). Если ключ задан — запрос
обязан прислать его в заголовке X-API-Key. Так на проде статистику легко
закрыть, не меняя код.
"""

from fastapi import Request

from app.config import get_settings
from app.core.exceptions import UnauthorizedError

settings = get_settings()


async def require_metrics_auth(request: Request) -> None:
    if not settings.metrics_api_key:
        return  # ключ не задан — эндпоинт открыт
    if request.headers.get("x-api-key") != settings.metrics_api_key:
        raise UnauthorizedError()
