"""Rate limiting — защита формы от спама.

Алгоритм один (sliding window по IP), но две реализации за общим интерфейсом:

  - InMemoryRateLimiter — очереди временных меток в памяти. Хватает для одного
    инстанса, без внешних зависимостей. Используется по умолчанию.
  - RedisRateLimiter — те же окна, но в Redis (sorted set). Нужен, когда инстансов
    несколько и лимит должен быть общим. Включается заданием REDIS_URL.

Выбор реализации — в get_rate_limiter() по наличию settings.redis_url.
"""

import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from functools import lru_cache

from fastapi import Request

from app.config import get_settings
from app.core.exceptions import RateLimitError
from app.core.logger import get_logger

logger = get_logger("app.ratelimit")
settings = get_settings()


class RateLimiter(ABC):
    """Возвращает (разрешено?, через_сколько_секунд_можно_повторить)."""

    @abstractmethod
    async def check(self, key: str) -> tuple[bool, int]: ...


class InMemoryRateLimiter(RateLimiter):
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        hits = self._hits[key]

        threshold = now - self.window
        while hits and hits[0] <= threshold:
            hits.popleft()

        if len(hits) >= self.max_requests:
            retry_after = int(self.window - (now - hits[0])) + 1
            return False, retry_after

        hits.append(now)
        return True, 0


class RedisRateLimiter(RateLimiter):
    """Распределённый sliding window на Redis sorted set.

    На каждый ключ держим ZSET меток времени. Старые метки чистим, считаем
    оставшиеся; если в окне уже максимум — отказываем.
    """

    def __init__(self, redis_url: str, max_requests: int, window_seconds: int):
        import redis.asyncio as redis  # импорт здесь — пакет нужен только в этом режиме

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self.max_requests = max_requests
        self.window = window_seconds

    async def check(self, key: str) -> tuple[bool, int]:
        rkey = f"ratelimit:{key}"
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex}"

        # Чистим устаревшее и считаем текущее окно одной транзакцией.
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(rkey, 0, now - self.window)
            pipe.zcard(rkey)
            results = await pipe.execute()
        count = results[1]

        if count >= self.max_requests:
            oldest = await self._redis.zrange(rkey, 0, 0, withscores=True)
            retry_after = int(self.window - (now - oldest[0][1])) + 1 if oldest else self.window
            return False, retry_after

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zadd(rkey, {member: now})
            pipe.expire(rkey, self.window + 1)
            await pipe.execute()
        return True, 0


@lru_cache
def get_rate_limiter() -> RateLimiter:
    if settings.redis_url:
        logger.info("Rate limiter: Redis (%s)", settings.redis_url)
        return RedisRateLimiter(
            settings.redis_url, settings.rate_limit_max_requests, settings.rate_limit_window_seconds
        )
    logger.info("Rate limiter: in-memory")
    return InMemoryRateLimiter(
        settings.rate_limit_max_requests, settings.rate_limit_window_seconds
    )


async def rate_limit_guard(request: Request) -> None:
    """FastAPI-зависимость: вешается на защищаемые эндпоинты (форма обратной связи)."""
    limiter = get_rate_limiter()
    client_ip = getattr(request.state, "client_ip", None) or "unknown"

    allowed, retry_after = await limiter.check(client_ip)
    if not allowed:
        raise RateLimitError(
            f"Превышен лимит запросов. Повторите через {retry_after} с.",
            retry_after=retry_after,
        )
