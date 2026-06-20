"""Юнит-тесты эвристического fallback AI-сервиса.

Ключ в тестах не задан, поэтому AIService уходит в локальную эвристику —
проверяем, что она вменяемо определяет тональность, категорию и приоритет
и всегда формирует summary + reply.
"""

from app.schemas.contact import ContactRequestIn
from app.services.ai_service import AIService
from tests.conftest import valid_payload


def _contact(**overrides) -> ContactRequestIn:
    return ContactRequestIn(**valid_payload(**overrides))


async def test_fallback_positive_sentiment():
    result = AIService()._fallback(
        _contact(message="Спасибо большое, всё супер, очень понравилась работа!")
    )
    assert result.sentiment == "positive"
    assert result.provider == "fallback"


async def test_fallback_negative_goes_high_priority():
    result = AIService()._fallback(
        _contact(message="Это просто ужас, всё плохо, я крайне недоволен и разочарован")
    )
    assert result.sentiment == "negative"
    assert result.priority == "high"


async def test_fallback_category_order():
    result = AIService()._fallback(
        _contact(message="Хочу заказать сайт под ключ, какая стоимость и бюджет?")
    )
    assert result.category == "order"


async def test_fallback_category_spam_low_priority():
    result = AIService()._fallback(
        _contact(message="Закажите наше seo продвижение и крипту тут https://spam.example")
    )
    assert result.category == "spam"
    assert result.priority == "low"


async def test_fallback_always_fills_reply_and_summary():
    result = AIService()._fallback(
        _contact(message="Нейтральное сообщение без особых ключевых слов внутри")
    )
    assert result.reply.strip()
    assert result.summary.strip()
    # Имя клиента должно попасть в черновик ответа.
    assert "Илья" in result.reply
