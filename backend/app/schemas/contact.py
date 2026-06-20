"""Схемы формы обратной связи: вход, результат AI, ответ API."""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Телефон принимаем в свободном формате (+7, 8, скобки, дефисы, пробелы),
# но цифр должно быть от 7 до 15 — как в рекомендации E.164.
_PHONE_DIGITS = re.compile(r"\d")


class ContactRequestIn(BaseModel):
    # str_strip_whitespace убирает крайние пробелы у всех строк — меньше ручной возни.
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "Илья Фарафонов",
                "phone": "+7 (999) 123-45-67",
                "email": "ilya@example.com",
                "message": "Здравствуйте! Хочу заказать лендинг под ключ, бюджет обсудим.",
            }
        },
    )

    name: str = Field(min_length=2, max_length=120, description="Имя отправителя")
    phone: str = Field(min_length=5, max_length=32, description="Телефон в любом формате")
    email: EmailStr = Field(max_length=255, description="Email для обратной связи")
    message: str = Field(min_length=10, max_length=4000, description="Текст обращения")

    @field_validator("name")
    @classmethod
    def name_has_letters(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value):
            raise ValueError("Имя должно содержать буквы")
        return value

    @field_validator("phone")
    @classmethod
    def phone_has_enough_digits(cls, value: str) -> str:
        digits = _PHONE_DIGITS.findall(value)
        if not 7 <= len(digits) <= 15:
            raise ValueError("Телефон должен содержать от 7 до 15 цифр")
        return value


class AIAnalysis(BaseModel):
    """Полный результат AI-анализа (используется внутри сервисов и для писем)."""

    sentiment: str  # positive | neutral | negative
    category: str   # order | question | cooperation | complaint | spam | other
    priority: str   # low | medium | high
    summary: str    # короткое резюме обращения для владельца
    reply: str      # черновик вежливого ответа клиенту
    provider: str   # claude | fallback


class AIAnalysisPublic(BaseModel):
    """Подмножество анализа, которое отдаём наружу (без черновика ответа)."""

    sentiment: str
    category: str
    priority: str
    provider: str


class ContactResponse(BaseModel):
    success: bool = True
    request_id: str
    message: str
    analysis: AIAnalysisPublic

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "request_id": "1f3c9a7e-2b6d-4e1a-9f0c-8d2b1a4c5e6f",
                "message": "Спасибо! Мы получили ваше обращение и скоро свяжемся с вами.",
                "analysis": {
                    "sentiment": "positive",
                    "category": "order",
                    "priority": "high",
                    "provider": "claude",
                },
            }
        }
    )
