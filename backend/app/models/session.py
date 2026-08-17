from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A refresh-token family (one browser/device).

    The raw refresh token is never stored — only a SHA-256 digest of it. Each
    refresh rotates the digest; presenting a *previous* digest is treated as
    theft and revokes the whole family.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_revoked", "user_id", "revoked_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(64))

    # Coarse device label for the "active sessions" screen. No raw IP is kept.
    user_agent_label: Mapped[str | None] = mapped_column(String(120))
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    user: Mapped["User"] = relationship(back_populates="sessions")

    @property
    def is_active(self) -> bool:
        from app.db.base import as_utc, utcnow

        expires_at = as_utc(self.expires_at)
        return self.revoked_at is None and expires_at is not None and expires_at > utcnow()


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single-use password reset grant. Only the token digest is persisted."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="reset_tokens")
