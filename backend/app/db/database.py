"""Подключение к БД (async SQLAlchemy 2.0).

Один движок на приложение. URL берётся из настроек: PostgreSQL в проде/Docker,
SQLite — как fallback для локального запуска без внешней БД.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("app.db")
settings = get_settings()


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = settings.effective_database_url
    # SQLite не умеет пул соединений как Postgres — лишние опции ему ни к чему.
    if url.startswith("sqlite"):
        return create_async_engine(url, echo=False)
    return create_async_engine(url, echo=False, pool_pre_ping=True, pool_size=10, max_overflow=5)


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    """FastAPI-зависимость: отдаёт сессию, откатывает при ошибке и закрывает."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Создаёт таблицы при старте.

    Для пет-проекта/теста этого достаточно. На бою с эволюцией схемы
    подключился бы Alembic (см. README, раздел про миграции).
    """
    # Для SQLite заранее создаём каталог под файл БД.
    if settings.effective_database_url.startswith("sqlite"):
        Path("data").mkdir(exist_ok=True)

    # Импорт моделей обязателен здесь, иначе Base.metadata о них не знает.
    from app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("БД инициализирована (%s)", "postgres" if settings.is_postgres else "sqlite")


async def check_db() -> bool:
    """Пинг БД для /api/health."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — для health нам важен только факт доступности
        logger.warning("БД недоступна: %s", exc)
        return False
