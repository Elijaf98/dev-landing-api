"""Общие схемы: health, метрики, формат ошибки (для документации)."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str  # ok | degraded
    version: str
    uptime_seconds: float
    checks: dict[str, str]  # db / ai / email -> up|down|disabled


class MetricsResponse(BaseModel):
    total_requests: int
    last_24h: int
    by_sentiment: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    last_request_at: datetime | None


class ErrorResponse(BaseModel):
    """Единый формат ошибки. Объявлен ради корректной схемы в Swagger."""

    success: bool = False
    error: str
    message: str
    request_id: str | None = None
    details: dict | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "error": "validation_error",
                "message": "Проверьте корректность переданных данных",
                "request_id": "1f3c9a7e-2b6d-4e1a-9f0c-8d2b1a4c5e6f",
                "details": {"email": "value is not a valid email address"},
            }
        }
    }
