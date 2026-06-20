"""Rate limiting — защита формы от спама.

Алгоритм: sliding window по IP. На каждый IP держим очередь временных меток
последних запросов; перед новым запросом выкидываем устаревшие и сравниваем
остаток с лимитом.

Хранилище — in-memory. Для одного инстанса (наш случай) этого достаточно и
не тянет лишних зависимостей. Для горизонтального масштабирования заменяется
на Redis с TTL — об этом отдельно сказано в README.
"""

import time
from collections import defaultdict, deque
from functools import lru_cache

from fastapi import Request

from app.config import get_settings
from app.core.exceptions import RateLimitError

settings = get_settings()


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        """Возвращает (разрешено?, через_сколько_секунд_можно_повторить)."""
        now = time.monotonic()
        hits = self._hits[key]

        # Чистим всё, что вышло за окно.
        threshold = now - self.window
        while hits and hits[0] <= threshold:
            hits.popleft()

        if len(hits) >= self.max_requests:
            retry_after = int(self.window - (now - hits[0])) + 1
            return False, retry_after

        hits.append(now)
        return True, 0


@lru_cache
def get_rate_limiter() -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )


async def rate_limit_guard(request: Request) -> None:
    """FastAPI-зависимость: вешается на защищаемые эндпоинты (форма обратной связи)."""
    limiter = get_rate_limiter()
    client_ip = getattr(request.state, "client_ip", None) or "unknown"

    allowed, retry_after = limiter.check(client_ip)
    if not allowed:
        raise RateLimitError(
            f"Превышен лимит запросов. Повторите через {retry_after} с.",
            retry_after=retry_after,
        )
