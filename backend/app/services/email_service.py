"""Отправка email-уведомлений (async SMTP).

По одному обращению уходит два письма:
  1. Владельцу сайта — данные клиента + результат AI-анализа + черновик ответа.
  2. Пользователю — подтверждение, что обращение принято.

Отправка best-effort: если SMTP не настроен или письмо не ушло, мы пишем это
в лог, но обращение всё равно считается принятым (оно уже в БД). Так форма
не «падает» из-за проблем с почтой.
"""

import asyncio
from email.message import EmailMessage
from html import escape

import aiosmtplib

from app.config import get_settings
from app.core.logger import get_logger
from app.schemas.contact import AIAnalysis, ContactRequestIn

logger = get_logger("app.email")
settings = get_settings()

# Человекочитаемые подписи для технических кодов — пригодятся в письме владельцу.
_SENTIMENT_RU = {"positive": "позитивная 🙂", "neutral": "нейтральная 😐", "negative": "негативная 😠"}
_CATEGORY_RU = {
    "order": "Заказ / проект",
    "question": "Вопрос",
    "cooperation": "Сотрудничество",
    "complaint": "Жалоба",
    "spam": "Спам / реклама",
    "other": "Прочее",
}
_PRIORITY_RU = {"high": "🔴 высокий", "medium": "🟡 средний", "low": "🟢 низкий"}


class EmailService:
    async def send_contact_notifications(
        self,
        contact: ContactRequestIn,
        analysis: AIAnalysis,
        request_id: str,
    ) -> dict[str, bool]:
        """Шлёт оба письма. Возвращает {'owner': bool, 'user': bool}."""
        owner_ok = await self._safe_send(
            to=settings.owner_email,
            subject=f"📬 Новое обращение ({_CATEGORY_RU.get(analysis.category, analysis.category)})",
            html=self._owner_html(contact, analysis, request_id),
        )

        # Пауза перед вторым письмом — обходим лимит «писем в секунду» у бесплатных SMTP.
        if settings.email_send_delay_seconds > 0:
            await asyncio.sleep(settings.email_send_delay_seconds)

        user_ok = await self._safe_send(
            to=str(contact.email),
            subject="Мы получили ваше обращение",
            html=self._user_html(contact, analysis),
        )
        return {"owner": owner_ok, "user": user_ok}

    async def _safe_send(self, to: str, subject: str, html: str) -> bool:
        # Нет реального SMTP — не падаем, а логируем (удобно в dev и для ревьюера).
        if not settings.smtp_configured:
            logger.info("[EMAIL:dry-run] -> %s | %s", to, subject)
            return False

        message = EmailMessage()
        message["From"] = settings.mail_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(
            "Письмо в формате HTML. Откройте его в почтовом клиенте с поддержкой HTML."
        )
        message.add_alternative(html, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=settings.smtp_use_tls,
            )
            logger.info("Письмо отправлено -> %s | %s", to, subject)
            return True
        except Exception as exc:  # noqa: BLE001 — почта не критична для приёма обращения
            logger.error("Не удалось отправить письмо на %s: %s", to, exc)
            return False

    # ----------------------------- шаблоны ----------------------------- #
    # Стили инлайновые: почтовые клиенты вырезают внешний и <style> CSS.

    @staticmethod
    def _owner_html(contact: ContactRequestIn, analysis: AIAnalysis, request_id: str) -> str:
        return f"""\
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
  <h2 style="color:#4f46e5;margin-bottom:4px">Новое обращение с сайта</h2>
  <p style="color:#666;margin-top:0;font-size:13px">request_id: {escape(request_id)}</p>

  <table style="width:100%;border-collapse:collapse;margin:16px 0">
    <tr><td style="padding:6px 0;width:120px;color:#888">Имя</td><td><b>{escape(contact.name)}</b></td></tr>
    <tr><td style="padding:6px 0;color:#888">Телефон</td><td>{escape(contact.phone)}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Email</td><td>{escape(str(contact.email))}</td></tr>
  </table>

  <div style="background:#f5f5f7;border-radius:8px;padding:12px 16px;margin:12px 0">
    <div style="color:#888;font-size:13px;margin-bottom:4px">Сообщение</div>
    <div style="white-space:pre-wrap">{escape(contact.message)}</div>
  </div>

  <div style="border-left:3px solid #4f46e5;padding:8px 16px;margin:16px 0;background:#fafaff">
    <div style="font-weight:bold;margin-bottom:8px">🤖 AI-анализ ({escape(analysis.provider)})</div>
    <div>Тональность: <b>{_SENTIMENT_RU.get(analysis.sentiment, analysis.sentiment)}</b></div>
    <div>Категория: <b>{_CATEGORY_RU.get(analysis.category, analysis.category)}</b></div>
    <div>Приоритет: <b>{_PRIORITY_RU.get(analysis.priority, analysis.priority)}</b></div>
    <div style="margin-top:8px;color:#444">{escape(analysis.summary)}</div>
  </div>

  <div style="margin:16px 0">
    <div style="color:#888;font-size:13px;margin-bottom:4px">✍️ Черновик ответа клиенту</div>
    <div style="background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;white-space:pre-wrap">{escape(analysis.reply)}</div>
  </div>
</div>"""

    @staticmethod
    def _user_html(contact: ContactRequestIn, analysis: AIAnalysis) -> str:
        first_name = escape(contact.name.split()[0])
        return f"""\
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
  <h2 style="color:#4f46e5">Спасибо за обращение, {first_name}!</h2>
  <p>Мы получили ваше сообщение и свяжемся с вами в ближайшее время.</p>

  <div style="background:#f5f5f7;border-radius:8px;padding:12px 16px;margin:16px 0">
    <div style="color:#888;font-size:13px;margin-bottom:4px">Ваше сообщение</div>
    <div style="white-space:pre-wrap">{escape(contact.message)}</div>
  </div>

  <p style="color:#666;font-size:14px">
    Это автоматическое подтверждение — отвечать на него не нужно.
  </p>
</div>"""


_email_service = EmailService()


def get_email_service() -> EmailService:
    return _email_service
