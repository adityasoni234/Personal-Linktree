"""Structured logging with request correlation and secret redaction.

Log channels are separated by logger name so they can be routed independently
by the log shipper:

    app.*         general application logs (INFO / WARNING / ERROR)
    app.security  authentication and abuse-prevention events
    app.audit     durable record of security-sensitive operations
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

# Keys whose values must never reach a log sink, at any nesting depth.
REDACTED_KEYS = frozenset(
    {
        "password",
        "new_password",
        "current_password",
        "confirm_password",
        "token",
        "access_token",
        "refresh_token",
        "reset_token",
        "csrf_token",
        "authorization",
        "cookie",
        "set-cookie",
        "secret",
        "api_key",
        "apikey",
        "session_secret",
        "jwt_secret",
        "private_key",
    }
)

_REDACTED = "[REDACTED]"

_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime", "taskName"}


def redact(value: Any, _depth: int = 0) -> Any:
    """Recursively strip sensitive values out of a structure before logging."""
    if _depth > 6:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {
            key: (
                _REDACTED
                if str(key).lower() in REDACTED_KEYS
                else redact(val, _depth + 1)
            )
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth + 1) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id := request_id_ctx.get():
            payload["request_id"] = request_id
        if user_id := user_id_ctx.get():
            payload["user_id"] = user_id
        extras = {
            key: val for key, val in record.__dict__.items() if key not in _RESERVED
        }
        if extras:
            payload.update(redact(extras))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-readable development output."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{self.formatTime(record, '%H:%M:%S')} "
            f"{record.levelname:<8} {record.name:<24} {record.getMessage()}"
        )
        if request_id := request_id_ctx.get():
            base += f"  [req={request_id[:8]}]"
        extras = {
            key: val for key, val in record.__dict__.items() if key not in _RESERVED
        }
        if extras:
            base += "  " + json.dumps(redact(extras), default=str)
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.LOG_JSON else ConsoleFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # Uvicorn duplicates the root handler otherwise.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


app_logger = get_logger("app")
security_logger = get_logger("app.security")
audit_logger = get_logger("app.audit")
