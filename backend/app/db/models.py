"""ORM-модели."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ContactRequest(Base):
    """Обращение из формы обратной связи + результат AI-анализа.

    Поля ai_* nullable: при fallback-режиме часть из них может быть пустой,
    а схема не должна от этого ломаться.
    """

    __tablename__ = "contact_requests"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Данные от пользователя
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)

    # Результат AI-анализа
    ai_sentiment: Mapped[str | None] = mapped_column(String(16))
    ai_category: Mapped[str | None] = mapped_column(String(32))
    ai_priority: Mapped[str | None] = mapped_column(String(16))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_reply: Mapped[str | None] = mapped_column(Text)
    ai_provider: Mapped[str | None] = mapped_column(String(32))  # claude | fallback

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<ContactRequest id={self.id} email={self.email!r} category={self.ai_category!r}>"
