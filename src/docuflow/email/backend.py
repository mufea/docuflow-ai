from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from docuflow.config import Settings

logger = logging.getLogger("docuflow.email")


class EmailBackend:
    def send(self, *, to: str, subject: str, body: str) -> None:
        raise NotImplementedError


class ConsoleEmailBackend(EmailBackend):
    def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("email_queued to=%s subject=%s", to, subject)
        print(f"[docuflow-email] to={to}\nsubject={subject}\n{body}\n")


class SMTPEmailBackend(EmailBackend):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, *, to: str, subject: str, body: str) -> None:
        if not self.settings.smtp_host:
            raise RuntimeError("SMTP_HOST is not configured.")
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        password = self.settings.reveal_secret(self.settings.smtp_password)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if self.settings.smtp_username and password:
                smtp.login(self.settings.smtp_username, password)
            smtp.send_message(message)


def build_email_backend(settings: Settings) -> EmailBackend:
    if settings.email_backend == "smtp":
        return SMTPEmailBackend(settings)
    return ConsoleEmailBackend()
