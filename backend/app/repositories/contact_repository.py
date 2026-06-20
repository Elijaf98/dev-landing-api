"""Репозиторий обращений — единственное место, где трогаем таблицу contact_requests.

Сервисы работают с данными только через этот класс, не зная про SQL.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContactRequest
from app.schemas.contact import AIAnalysis, ContactRequestIn


class ContactRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        data: ContactRequestIn,
        analysis: AIAnalysis,
        ip_address: str | None,
    ) -> ContactRequest:
        obj = ContactRequest(
            name=data.name,
            phone=data.phone,
            email=str(data.email),
            message=data.message,
            ip_address=ip_address,
            ai_sentiment=analysis.sentiment,
            ai_category=analysis.category,
            ai_priority=analysis.priority,
            ai_summary=analysis.summary,
            ai_reply=analysis.reply,
            ai_provider=analysis.provider,
        )
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    # --- агрегаты для /api/metrics ---

    async def total(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(ContactRequest)) or 0

    async def count_since(self, moment: datetime) -> int:
        stmt = select(func.count()).select_from(ContactRequest).where(
            ContactRequest.created_at >= moment
        )
        return await self.session.scalar(stmt) or 0

    async def group_count(self, column) -> dict[str, int]:
        """Считает количество записей в разрезе указанной колонки (sentiment/category/...)."""
        stmt = select(column, func.count()).group_by(column)
        rows = await self.session.execute(stmt)
        return {(key or "unknown"): count for key, count in rows.all()}

    async def last_created_at(self) -> datetime | None:
        return await self.session.scalar(select(func.max(ContactRequest.created_at)))
