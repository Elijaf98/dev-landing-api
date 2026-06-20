"""Общие фикстуры для тестов.

Важно: переменные окружения выставляем ДО импорта приложения, иначе настройки
успеют закешироваться с «боевыми» значениями. os.environ имеет приоритет над
файлом .env, поэтому реальный ключ/SMTP из .env разработчика тесты не зацепят —
AI принудительно работает в режиме fallback, письма уходят в лог.
"""

import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test.db"
os.environ["ANTHROPIC_API_KEY"] = ""   # форсим fallback
os.environ["SMTP_HOST"] = ""           # форсим dry-run почты
os.environ["SMTP_USER"] = ""
os.environ["RATE_LIMIT_MAX_REQUESTS"] = "5"
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "3600"

Path("data").mkdir(exist_ok=True)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def fresh_db():
    """Чистая БД перед каждым тестом — тесты не влияют друг на друга."""
    from app.db import models  # noqa: F401
    from app.db.database import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Сбрасываем счётчики лимитера, чтобы тесты не отъедали лимит друг у друга."""
    from app.middleware.rate_limit import get_rate_limiter

    get_rate_limiter()._hits.clear()
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def valid_payload(**overrides) -> dict:
    """Заготовка корректного обращения; поля можно переопределить под кейс."""
    payload = {
        "name": "Илья Фарафонов",
        "phone": "+7 (999) 123-45-67",
        "email": "ilya@example.com",
        "message": "Здравствуйте! Хочу заказать лендинг под ключ, обсудим бюджет?",
    }
    payload.update(overrides)
    return payload
