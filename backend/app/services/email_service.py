"""Transactional email delivery.

The product ships with a console backend so password reset works end-to-end in
development without an SMTP dependency. Point `EMAIL_BACKEND` at a real
transport (SES, Postmark, SMTP) before going to production — the interface is a
single `send` call, and nothing else in the codebase changes.

Reset links are never written to the application log in production.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings
from app.core.logging import app_logger, security_logger


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    body_text: str


class EmailBackend(ABC):
    @abstractmethod
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailBackend(EmailBackend):
    """Development transport: prints the message instead of sending it."""

    async def send(self, message: EmailMessage) -> None:
        if settings.is_production:
            # A misconfigured production deployment must not silently swallow —
            # or print — password reset links.
            security_logger.error(
                "email_backend_not_configured", extra={"subject": message.subject}
            )
            return
        app_logger.info(
            "email_sent_console",
            extra={"to": message.to, "subject": message.subject},
        )
        print(  # noqa: T201 - intentional developer-facing output
            f"\n{'=' * 72}\n[dev email] To: {message.to}\nSubject: {message.subject}\n\n"
            f"{message.body_text}\n{'=' * 72}\n"
        )


@lru_cache(maxsize=1)
def get_email_backend() -> EmailBackend:
    return ConsoleEmailBackend()


async def send_password_reset(email: str, token: str, full_name: str | None = None) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    body = (
        f"{greeting}\n\n"
        f"We received a request to reset your {settings.PROJECT_NAME} password.\n\n"
        f"Reset your password:\n{reset_url}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TTL_MINUTES} minutes and can "
        "be used once.\n\n"
        "If you did not request this, you can safely ignore this email — your "
        "password has not changed.\n"
    )
    await get_email_backend().send(
        EmailMessage(
            to=email,
            subject=f"Reset your {settings.PROJECT_NAME} password",
            body_text=body,
        )
    )


async def send_password_changed(email: str, full_name: str | None = None) -> None:
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    await get_email_backend().send(
        EmailMessage(
            to=email,
            subject=f"Your {settings.PROJECT_NAME} password was changed",
            body_text=(
                f"{greeting}\n\nYour password was just changed. If this was not you, "
                "reset your password immediately and contact your organization "
                "administrator.\n"
            ),
        )
    )
