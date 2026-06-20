"""Доменные исключения и глобальные обработчики ошибок.

Идея простая: бизнес-слой кидает наследников AppError, а единый обработчик
превращает их в аккуратный JSON с нужным HTTP-статусом. Никаких голых
трейсбеков наружу — клиент всегда получает предсказуемый формат:

    { "success": false, "error": "<code>", "message": "...", "request_id": "..." }
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logger import get_logger

logger = get_logger("app.errors")


class AppError(Exception):
    """Базовая ошибка приложения. Несёт HTTP-статус и машинный код."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "Внутренняя ошибка сервиса"

    def __init__(self, message: str | None = None, *, details: dict | None = None):
        if message:
            self.message = message
        self.details = details
        super().__init__(self.message)


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"
    message = "Слишком много запросов. Пожалуйста, попробуйте позже."

    def __init__(self, message: str | None = None, *, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AIServiceError(AppError):
    """Внутренняя проблема AI. Наружу почти никогда не всплывает —
    contact-сервис ловит её и уходит в fallback. Оставлена для явности."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ai_service_error"
    message = "AI-сервис временно недоступен"


class EmailDeliveryError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "email_delivery_error"
    message = "Не удалось отправить письмо"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "service_unavailable"
    message = "Сервис временно недоступен"


def _request_id(request: Request) -> str | None:
    # request_id проставляет RequestContextMiddleware; в редких случаях
    # (ошибка до middleware) его может не быть.
    return getattr(request.state, "request_id", None)


def _error_body(error: str, message: str, request_id: str | None, details=None) -> dict:
    body = {"success": False, "error": error, "message": message, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        # Ошибки уровня 5xx логируем как error, клиентские (4xx) — как warning.
        log = logger.error if exc.status_code >= 500 else logger.warning
        log("AppError [%s] %s", exc.error_code, exc.message)

        headers = {}
        if isinstance(exc, RateLimitError) and exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)

        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, _request_id(request), exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Приводим ошибки Pydantic к компактному виду: поле -> сообщение.
        fields = {}
        for err in exc.errors():
            loc = [str(p) for p in err["loc"] if p not in ("body",)]
            fields[".".join(loc) or "body"] = err["msg"]

        logger.warning("Ошибка валидации: %s", fields)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "validation_error",
                "Проверьте корректность переданных данных",
                _request_id(request),
                fields,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        # Сюда падает всё непредвиденное. Полный трейсбек — только в лог.
        logger.exception("Необработанная ошибка: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "internal_error",
                "Внутренняя ошибка сервиса. Мы уже разбираемся.",
                _request_id(request),
            ),
        )
