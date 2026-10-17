"""Explicit SMTP outbox worker; no mail is sent without SMTP configuration."""

import smtplib
import ssl
import time
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Mail, now
from app.db.session import get_engine


def process_one():
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        return False
    with Session(get_engine()) as db:
        row = db.scalar(
            select(Mail).order_by(Mail.created_at).with_for_update(skip_locked=True).limit(1)
        )
        if not row:
            return False
        if row.created_at < now() - 1800 or row.attempts >= 3:
            db.delete(row)
            db.commit()
            return True
        message = EmailMessage()
        message["From"], message["To"] = settings.smtp_from, row.recipient
        message["Subject"] = "Redefinir senha — Arcana"
        message.set_content(row.body)
        row.attempts += 1
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                smtp.send_message(message)
            db.delete(row)
        except (OSError, smtplib.SMTPException):
            pass
        db.commit()
        return True


if __name__ == "__main__":
    while True:
        process_one()
        time.sleep(5)
