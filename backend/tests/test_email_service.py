"""Тесты email-сервиса с мокнутым SMTP (реальная сеть не дёргается)."""

from app.schemas.contact import AIAnalysis, ContactRequestIn
from app.services import email_service as email_mod
from app.services.email_service import EmailService
from tests.conftest import valid_payload


def _contact(**overrides) -> ContactRequestIn:
    return ContactRequestIn(**valid_payload(**overrides))


def _analysis() -> AIAnalysis:
    return AIAnalysis(
        sentiment="positive", category="order", priority="high",
        summary="Резюме обращения", reply="Черновик ответа", provider="claude",
    )


async def test_both_emails_sent_when_smtp_configured(monkeypatch):
    monkeypatch.setattr(email_mod.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_mod.settings, "smtp_user", "user")

    sent = []

    async def fake_send(message, **kwargs):
        sent.append((message["To"], message["Subject"]))

    monkeypatch.setattr(email_mod.aiosmtplib, "send", fake_send)

    result = await EmailService().send_contact_notifications(
        _contact(email="client@example.com"), _analysis(), "rid-1"
    )

    assert result == {"owner": True, "user": True}
    recipients = [to for to, _ in sent]
    assert email_mod.settings.owner_email in recipients   # письмо владельцу
    assert "client@example.com" in recipients             # копия пользователю


async def test_dry_run_when_smtp_not_configured(monkeypatch):
    monkeypatch.setattr(email_mod.settings, "smtp_host", "")
    monkeypatch.setattr(email_mod.settings, "smtp_user", "")

    result = await EmailService().send_contact_notifications(_contact(), _analysis(), "rid-2")
    # Без SMTP письма не отправляются (пишутся в лог), сервис не падает.
    assert result == {"owner": False, "user": False}


async def test_best_effort_on_smtp_error(monkeypatch):
    monkeypatch.setattr(email_mod.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_mod.settings, "smtp_user", "user")

    async def boom(message, **kwargs):
        raise RuntimeError("SMTP недоступен")

    monkeypatch.setattr(email_mod.aiosmtplib, "send", boom)

    # Ошибка отправки не должна пробрасываться наружу (best-effort).
    result = await EmailService().send_contact_notifications(_contact(), _analysis(), "rid-3")
    assert result == {"owner": False, "user": False}


def test_owner_html_escapes_user_data():
    # XSS-инъекция в имени/сообщении должна быть экранирована в HTML письма.
    html = EmailService._owner_html(
        _contact(name="Иван", message="<script>alert(1)</script>"),
        _analysis(),
        "rid-4",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
