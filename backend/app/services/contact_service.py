"""Оркестрация обработки обращения — здесь живёт полный бизнес-цикл:

    AI-анализ -> сохранение в БД -> отправка писем -> результат

Контроллер не знает деталей: он передаёт данные и получает готовый анализ.
"""

from app.core.logger import get_logger
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import AIAnalysis, ContactRequestIn
from app.services.ai_service import get_ai_service
from app.services.email_service import get_email_service

logger = get_logger("app.contact")


class ContactService:
    def __init__(self, session):
        self.repo = ContactRepository(session)
        self.ai = get_ai_service()
        self.email = get_email_service()

    async def process(
        self,
        data: ContactRequestIn,
        ip_address: str | None,
        request_id: str,
    ) -> AIAnalysis:
        # 1. AI-анализ (с гарантированным fallback внутри сервиса).
        analysis = await self.ai.analyze(data)

        # 2. Сохраняем обращение вместе с результатом анализа.
        saved = await self.repo.create(data, analysis, ip_address)

        # 3. Письма — best-effort, ошибки не валят запрос.
        delivery = await self.email.send_contact_notifications(data, analysis, request_id)

        logger.info(
            "Обращение #%s обработано: category=%s priority=%s provider=%s, письма owner=%s/user=%s",
            saved.id,
            analysis.category,
            analysis.priority,
            analysis.provider,
            delivery["owner"],
            delivery["user"],
        )
        return analysis
