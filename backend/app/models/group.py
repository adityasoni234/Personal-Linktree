from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.link import Link
    from app.models.organization import Organization
    from app.models.qr import QRConfiguration
    from app.models.user import User


class Group(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A public link page (e.g. "Computer Society") owned by an organization."""

    __tablename__ = "groups"
    __table_args__ = (
        Index("ix_groups_org_position", "organization_id", "position"),
        # Drives the public page lookup: /g/{slug} for live groups only.
        Index("ix_groups_public_lookup", "slug", "is_published", "is_archived"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Globally unique: it is the public URL path segment (/g/{slug}).
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(512))

    # Serialised Theme schema — validated by Pydantic before it is written.
    theme: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )
    # SEO / OpenGraph overrides for the public page.
    seo: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped["Organization"] = relationship(back_populates="groups")
    owner: Mapped["User | None"] = relationship(
        back_populates="owned_groups", foreign_keys=[owner_id]
    )
    links: Mapped[list["Link"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Link.position",
    )
    qr_configuration: Mapped["QRConfiguration | None"] = relationship(
        back_populates="group", cascade="all, delete-orphan", uselist=False,
        passive_deletes=True,
    )

    @property
    def is_public(self) -> bool:
        return self.is_published and not self.is_archived

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Group {self.slug}>"
