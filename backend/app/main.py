"""Точка сборки приложения.

Здесь всё соединяется: настройки, логи, БД, middleware, CORS, обработчики
ошибок, роутеры и (опционально) отдача статического лендинга.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import contact, health, metrics
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger, setup_logging
from app.db.database import init_db
from app.middleware.request_context import RequestContextMiddleware

settings = get_settings()
setup_logging(settings)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Старт %s v%s (env=%s)", settings.app_name, settings.app_version, settings.app_env)
    await init_db()

    # Явно предупреждаем, в каком режиме поднялись — чтобы не гадать по логам.
    if not settings.ai_enabled:
        logger.warning("ANTHROPIC_API_KEY не задан → AI в режиме fallback (эвристика)")
    if not settings.smtp_configured:
        logger.warning("SMTP не настроен → письма пишутся в лог (dry-run)")

    yield
    logger.info("Остановка приложения")


TAGS_METADATA = [
    {"name": "Contact", "description": "Форма обратной связи с AI-анализом обращений."},
    {"name": "System", "description": "Служебные эндпоинты: health-check и метрики."},
]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Бэкенд лендинга-презентации разработчика.\n\n"
        "Полный цикл обработки обращения: **валидация → AI-анализ "
        "(Claude) → сохранение → email-уведомления → ответ**. "
        "При недоступности AI включается эвристический fallback."
    ),
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

# --- CORS (внешний слой) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# --- Контекст запроса: request-id + логирование (внутренний слой) ---
app.add_middleware(RequestContextMiddleware)

# --- Глобальные обработчики ошибок ---
register_exception_handlers(app)

# --- Роутеры ---
app.include_router(contact.router)
app.include_router(health.router)
app.include_router(metrics.router)


def _resolve_frontend_dir() -> Path | None:
    if not settings.serve_frontend:
        return None
    candidate = (
        Path(settings.frontend_dir)
        if settings.frontend_dir
        else Path(__file__).resolve().parents[2] / "frontend"
    )
    return candidate if candidate.is_dir() else None


_frontend_dir = _resolve_frontend_dir()
if _frontend_dir:
    # Монтируем последним: конкретные роуты (/api/*, /docs) имеют приоритет,
    # а корень отдаёт лендинг. html=True → "/" вернёт index.html.
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info("Лендинг отдаётся из %s", _frontend_dir)
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")
