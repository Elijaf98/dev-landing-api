"""Сбор статистики по обращениям для /api/metrics."""

from datetime import datetime, timedelta, timezone

from app.db.models import ContactRequest
from app.repositories.contact_repository import ContactRepository
from app.schemas.common import MetricsResponse


class MetricsService:
    def __init__(self, session):
        self.repo = ContactRepository(session)

    async def collect(self) -> MetricsResponse:
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        return MetricsResponse(
            total_requests=await self.repo.total(),
            last_24h=await self.repo.count_since(day_ago),
            by_sentiment=await self.repo.group_count(ContactRequest.ai_sentiment),
            by_category=await self.repo.group_count(ContactRequest.ai_category),
            by_priority=await self.repo.group_count(ContactRequest.ai_priority),
            last_request_at=await self.repo.last_created_at(),
        )
