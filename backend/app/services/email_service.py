from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import Settings, get_settings


def email_provider_configured(settings: Settings | None = None) -> bool:
    current = settings or get_settings()
    return bool(current.smtp_host and current.smtp_from_email)


def send_magic_link_email(recipient_email: str, magic_link: str) -> None:
    settings = get_settings()
    if not email_provider_configured(settings):
        raise RuntimeError("email delivery not configured")

    message = EmailMessage()
    message["Subject"] = "Sign in to ThoughtGraph"
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email or ""))
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Use the link below to sign in to ThoughtGraph.",
                "",
                magic_link,
                "",
                "If you did not request this link, you can ignore this email.",
            ]
        )
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
