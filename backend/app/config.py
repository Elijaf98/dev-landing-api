"""Конфигурация приложения.

Все настройки тянутся из переменных окружения (.env) через pydantic-settings.
Доступ к настройкам — только через get_settings(), результат кешируется,
чтобы не перечитывать .env на каждый запрос.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # лишние переменные в .env не роняют запуск
    )

    # --- Приложение ---
    app_env: str = "development"
    app_name: str = "Dev Landing API"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000

    # --- CORS ---
    # Храним строкой через запятую, а не списком: списки в env требуют JSON,
    # что неудобно править руками. Разбор — в cors_origins_list.
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000"

    # Доверять ли заголовку X-Forwarded-For при определении IP клиента.
    # True — только если перед сервисом стоит доверенный прокси (nginx).
    # При прямом доступе оставляем False, иначе IP легко подделать и обойти rate limit.
    trust_proxy: bool = False

    # --- База данных ---
    database_url: str = ""

    # --- AI (Anthropic) ---
    anthropic_api_key: str = ""
    ai_model: str = "claude-haiku-4-5"
    ai_timeout_seconds: int = 12
    ai_max_tokens: int = 1024

    # --- SMTP ---
    smtp_host: str = "sandbox.smtp.mailtrap.io"
    smtp_port: int = 2525
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    mail_from: str = "Dev Landing <no-reply@devlanding.local>"
    owner_email: str = "owner@example.com"  # реальный адрес задаётся через .env

    # --- Rate limiting ---
    rate_limit_max_requests: int = 5
    rate_limit_window_seconds: int = 3600

    # --- Логи ---
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # --- Фронтенд ---
    # Отдавать ли статический лендинг тем же приложением (удобно для локалки/демо).
    # В проде фронт может отдавать nginx — тогда можно выключить.
    serve_frontend: bool = True
    frontend_dir: str = ""  # пусто — вычислим путь относительно проекта

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_database_url(self) -> str:
        """Если DATABASE_URL не задан — поднимаем локальный SQLite.

        Удобно для разработки и для ревьюера: проект заводится без Postgres,
        просто `uvicorn app.main:app`.
        """
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///./data/app.db"

    @property
    def is_postgres(self) -> bool:
        return self.effective_database_url.startswith("postgresql")

    @property
    def ai_enabled(self) -> bool:
        """AI работает только при наличии ключа. Иначе — эвристический fallback."""
        return bool(self.anthropic_api_key.strip())

    @property
    def smtp_configured(self) -> bool:
        """Есть ли реальный SMTP. Если нет — письма уходят в лог (не падаем)."""
        return bool(self.smtp_host.strip() and self.smtp_user.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
