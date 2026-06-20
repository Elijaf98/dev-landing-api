"""Тесты ветки Claude в AIService с мокнутым Anthropic-клиентом.

Реальный API не вызывается: подменяем messages.create. Так проверяем разбор
tool_use и то, что любой сбой Claude приводит к fallback, а не к исключению.
"""

from unittest.mock import AsyncMock, MagicMock

from app.schemas.contact import ContactRequestIn
from app.services.ai_service import AIService
from tests.conftest import valid_payload


def _contact(**overrides) -> ContactRequestIn:
    return ContactRequestIn(**valid_payload(**overrides))


def _service_with_client() -> AIService:
    # Обходим __init__, чтобы не тянуть реальный SDK; подменяем _client вручную.
    svc = AIService.__new__(AIService)
    svc._client = MagicMock()
    return svc


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, payload):
        self.input = payload


class _ToolUseResponse:
    def __init__(self, payload):
        self.content = [_ToolUseBlock(payload)]


async def test_claude_parses_tool_use():
    svc = _service_with_client()
    svc._client.messages.create = AsyncMock(return_value=_ToolUseResponse({
        "sentiment": "negative", "category": "complaint", "priority": "high",
        "summary": "Клиент недоволен", "reply": "Приносим извинения",
    }))

    result = await svc.analyze(_contact())

    assert result.provider == "claude"
    assert result.sentiment == "negative"
    assert result.category == "complaint"
    assert result.priority == "high"


async def test_claude_error_falls_back():
    svc = _service_with_client()
    svc._client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))

    result = await svc.analyze(_contact())
    # Любая ошибка Claude → эвристический fallback, без исключения наружу.
    assert result.provider == "fallback"


async def test_claude_without_tool_use_falls_back():
    class _TextBlock:
        type = "text"

    class _TextResponse:
        content = [_TextBlock()]

    svc = _service_with_client()
    svc._client.messages.create = AsyncMock(return_value=_TextResponse())

    result = await svc.analyze(_contact())
    # Модель ответила, но без tool_use — считаем сбоем и уходим в fallback.
    assert result.provider == "fallback"
