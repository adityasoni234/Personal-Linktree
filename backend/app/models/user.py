from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import Role, UserStatus

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.membership import Membership
    from app.models.session import PasswordResetToken, UserSession


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_status_created_at", "status", "created_at"),)

    # Stored lowercased; uniqueness is enforced on the normalised value.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    # Platform-wide role. Organization-scoped roles live on Membership.
    system_role: Mapped[Role] = mapped_column(
        pg_enum(Role, "role"), default=Role.USER, nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status"), default=UserStatus.ACTIVE, nullable=False
    )

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Any refresh token issued before this instant is rejected. Bumped on
    # password change, forced logout and role changes.
    tokens_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    owned_groups: Mapped[list["Group"]] = relationship(
        back_populates="owner", foreign_keys="Group.owner_id"
    )

    @property
    def is_super_admin(self) -> bool:
        return self.system_role is Role.SUPER_ADMIN

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id}>"
