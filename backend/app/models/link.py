from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.group import Group


class Link(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "links"
    __table_args__ = (
        Index("ix_links_group_position", "group_id", "position"),
        Index("ix_links_group_active", "group_id", "is_active"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # Always re-validated server-side against the scheme allowlist before write.
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(64))

    # Per-link presentation overrides (background, text colour, radius, style).
    style: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="links")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Link {self.id} {self.title!r}>"
