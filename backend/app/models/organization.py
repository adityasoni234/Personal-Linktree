from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit import AuditLog
    from app.models.group import Group
    from app.models.membership import Membership


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(512))
    website_url: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Org-level defaults (theme palette, feature flags, group quota).
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )
    groups: Mapped[list["Group"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="organization", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Organization {self.slug}>"
