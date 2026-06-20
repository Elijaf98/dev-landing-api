"""AI-анализ обращений через Claude (Anthropic) с эвристическим fallback.

За один вызов модели получаем сразу пять вещей:
  - тональность (sentiment)
  - категорию запроса (category)
  - приоритет для владельца (priority)
  - краткое резюме обращения (summary)
  - черновик вежливого ответа клиенту (reply)

Главный принцип: метод analyze() НИКОГДА не бросает исключение наружу.
Нет ключа, таймаут, ошибка API — молча уходим в локальную эвристику,
проставляем provider="fallback", и сервис продолжает работать. Это прямое
требование ТЗ (graceful fallback).
"""

import asyncio
from functools import lru_cache

from app.config import get_settings
from app.core.logger import get_logger
from app.schemas.contact import AIAnalysis, ContactRequestIn

logger = get_logger("app.ai")
settings = get_settings()

CATEGORIES = ["order", "question", "cooperation", "complaint", "spam", "other"]

SYSTEM_PROMPT = (
    "Ты — ассистент владельца сайта-портфолио веб-разработчика. "
    "К тебе приходят обращения из формы обратной связи. Твоя задача — "
    "классифицировать обращение и подготовить материалы для владельца. "
    "Отвечай строго через инструмент submit_analysis. Все тексты — на русском языке. "
    "Черновик ответа (reply) пиши вежливо, от первого лица, обращайся к человеку по имени, "
    "без воды и канцелярита, 2–4 предложения."
)

# Инструмент для structured output: модель обязана вернуть валидный JSON по этой схеме.
ANALYSIS_TOOL = {
    "name": "submit_analysis",
    "description": "Сохранить результат анализа обращения с формы обратной связи.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["positive", "neutral", "negative"],
                "description": "Эмоциональная окраска обращения.",
            },
            "category": {
                "type": "string",
                "enum": CATEGORIES,
                "description": (
                    "Тип обращения: order — заказ/проект, question — вопрос, "
                    "cooperation — сотрудничество/вакансия, complaint — жалоба, "
                    "spam — спам/реклама, other — прочее."
                ),
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Насколько срочно владельцу стоит ответить.",
            },
            "summary": {
                "type": "string",
                "description": "Резюме обращения в одну строку для владельца.",
            },
            "reply": {
                "type": "string",
                "description": "Готовый черновик вежливого ответа клиенту.",
            },
        },
        "required": ["sentiment", "category", "priority", "summary", "reply"],
    },
}


class AIService:
    def __init__(self):
        self._client = None
        if settings.ai_enabled:
            # Импортируем здесь, чтобы без ключа не тянуть SDK без надобности.
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=float(settings.ai_timeout_seconds),
                max_retries=1,
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    async def analyze(self, contact: ContactRequestIn) -> AIAnalysis:
        if self._client is None:
            return self._fallback(contact)

        try:
            # Дополнительный «зонтик» поверх таймаута SDK, чтобы запрос пользователя
            # не висел дольше разумного, даже если SDK залип.
            return await asyncio.wait_for(
                self._analyze_with_claude(contact),
                timeout=settings.ai_timeout_seconds + 3,
            )
        except asyncio.TimeoutError:
            logger.warning("Claude не ответил за %s c — fallback", settings.ai_timeout_seconds)
            return self._fallback(contact)
        except Exception as exc:  # noqa: BLE001 — любой сбой AI не должен ронять обращение
            logger.warning("Ошибка обращения к Claude (%s) — fallback", exc)
            return self._fallback(contact)

    async def _analyze_with_claude(self, contact: ContactRequestIn) -> AIAnalysis:
        user_text = (
            f"Имя: {contact.name}\n"
            f"Телефон: {contact.phone}\n"
            f"Email: {contact.email}\n"
            f"Сообщение:\n{contact.message}"
        )

        response = await self._client.messages.create(
            model=settings.ai_model,
            max_tokens=settings.ai_max_tokens,
            system=SYSTEM_PROMPT,
            tools=[ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "submit_analysis"},
            messages=[{"role": "user", "content": user_text}],
        )

        payload = self._extract_tool_input(response)
        if payload is None:
            # Модель ответила, но без tool_use — считаем это сбоем и идём в fallback.
            raise ValueError("Claude не вернул tool_use submit_analysis")

        logger.info("AI-анализ выполнен Claude (%s)", settings.ai_model)
        return AIAnalysis(
            sentiment=payload.get("sentiment", "neutral"),
            category=payload.get("category", "other"),
            priority=payload.get("priority", "medium"),
            summary=payload.get("summary", "").strip() or self._auto_summary(contact),
            reply=payload.get("reply", "").strip() or self._auto_reply(contact),
            provider="claude",
        )

    @staticmethod
    def _extract_tool_input(response) -> dict | None:
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input
        return None

    # ------------------------------------------------------------------ #
    #  Fallback: простая, но честная эвристика без внешних зависимостей.  #
    # ------------------------------------------------------------------ #

    # Маркеры для оценки тональности. Список короткий, но покрывает типовые формы.
    _NEGATIVE = (
        "плохо", "ужас", "отврат", "обман", "развод", "недоволен", "жалоба",
        "верните", "не работает", "кошмар", "хамство", "ужасно", "разочарован",
    )
    _POSITIVE = (
        "спасибо", "отлично", "круто", "супер", "понравил", "класс", "рекоменд",
        "благодар", "хочу заказать", "здорово", "восхищ",
    )

    # Ключевые слова по категориям. Порядок проверки важен: спам и жалоба «сильнее».
    _CATEGORY_MARKERS = {
        "spam": ("http://", "https://", "seo", "продвижение", "крипт", "casino", "ставк", "телеграм-канал"),
        "complaint": ("жалоба", "верните деньги", "не работает", "обман", "недоволен", "ужас"),
        "order": ("заказать", "заказ", "стоимость", "цена", "бюджет", "сколько стоит", "хочу сайт", "разработать", "под ключ"),
        "cooperation": ("сотруднич", "партнёр", "вакансия", "работа", "команд", "оффер", "фриланс"),
        "question": ("?", "как ", "можно ли", "вопрос", "подскажите"),
    }

    def _fallback(self, contact: ContactRequestIn) -> AIAnalysis:
        text = contact.message.lower()

        sentiment = self._guess_sentiment(text)
        category = self._guess_category(text)
        priority = self._guess_priority(category, sentiment)

        return AIAnalysis(
            sentiment=sentiment,
            category=category,
            priority=priority,
            summary=self._auto_summary(contact),
            reply=self._auto_reply(contact),
            provider="fallback",
        )

    def _guess_sentiment(self, text: str) -> str:
        neg = sum(word in text for word in self._NEGATIVE)
        pos = sum(word in text for word in self._POSITIVE)
        if neg > pos:
            return "negative"
        if pos > neg:
            return "positive"
        return "neutral"

    def _guess_category(self, text: str) -> str:
        for category, markers in self._CATEGORY_MARKERS.items():
            if any(marker in text for marker in markers):
                return category
        return "other"

    @staticmethod
    def _guess_priority(category: str, sentiment: str) -> str:
        if category in ("complaint", "order") or sentiment == "negative":
            return "high"
        if category == "spam":
            return "low"
        return "medium"

    @staticmethod
    def _auto_summary(contact: ContactRequestIn) -> str:
        text = " ".join(contact.message.split())
        short = (text[:140] + "…") if len(text) > 140 else text
        return f"Обращение от {contact.name}: {short}"

    @staticmethod
    def _auto_reply(contact: ContactRequestIn) -> str:
        first_name = contact.name.split()[0]
        return (
            f"Здравствуйте, {first_name}! Спасибо за ваше обращение — оно получено, "
            "и я свяжусь с вами в ближайшее время, чтобы обсудить детали. "
            "Хорошего дня!"
        )


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
