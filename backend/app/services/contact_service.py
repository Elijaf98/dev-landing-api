"""Оркестрация обработки обращения — здесь живёт полный бизнес-цикл:

    AI-анализ -> сохранение в БД -> отправка писем -> результат

Контроллер не знает деталей: он передаёт данные и получает готовый анализ.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import AIAnalysis, ContactRequestIn
from app.services.ai_service import get_ai_service
from app.services.email_service import get_email_service

logger = get_logger("app.contact")


class ContactService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactRepository(session)
        self.ai = get_ai_service()
        self.email = get_email_service()

    async def process(
        self,
        data: ContactRequestIn,
        ip_address: str | None,
        request_id: str,
    ) -> AIAnalysis:
        """Синхронная часть: AI-анализ + сохранение. Возвращает анализ для ответа.

        Письма отправляются отдельно (send_notifications) в фоне, чтобы не
        задерживать ответ клиенту на время SMTP.
        """
        # 1. AI-анализ (с гарантированным fallback внутри сервиса).
        analysis = await self.ai.analyze(data)

        # 2. Сохраняем обращение и фиксируем транзакцию на уровне сервиса.
        saved = await self.repo.create(data, analysis, ip_address)
        await self.session.commit()

        logger.info(
            "Обращение #%s сохранено: category=%s priority=%s provider=%s",
            saved.id,
            analysis.category,
            analysis.priority,
            analysis.provider,
        )
        return analysis

    async def send_notifications(
        self,
        data: ContactRequestIn,
        analysis: AIAnalysis,
        request_id: str,
    ) -> None:
        """Отправка писем — запускается в фоне (BackgroundTasks).

        Best-effort: ошибки не пробрасываются (обращение уже сохранено), только
        пишутся в лог. Сессия БД здесь не нужна — работаем только с почтой.
        """
        delivery = await self.email.send_contact_notifications(data, analysis, request_id)
        logger.info(
            "Письма по обращению rid=%s: owner=%s / user=%s",
            request_id,
            delivery["owner"],
            delivery["user"],
        )
