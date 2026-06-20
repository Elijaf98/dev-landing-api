"""Middleware контекста запроса.

Делает три вещи на каждый HTTP-запрос:
  - выдаёт request_id и кладёт его в request.state (его подхватывают логи и
    обработчики ошибок) + возвращает в заголовке X-Request-ID;
  - вычисляет реальный IP клиента (с учётом X-Forwarded-For за nginx);
  - логирует строку доступа: метод, путь, статус, время ответа, IP.

Это и есть «логирование всех запросов в файл» из ТЗ (хендлер файла настроен
в core/logger.py).
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logger import get_logger

logger = get_logger("app.access")


def get_client_ip(request: Request) -> str:
    # За обратным прокси реальный адрес — в X-Forwarded-For (берём первый).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.client_ip = get_client_ip(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s -> %s | %.1f ms | ip=%s | rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request.state.client_ip,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response
