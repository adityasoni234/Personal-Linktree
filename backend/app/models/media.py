from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import MediaKind

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Media(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An uploaded asset.

    `storage_key` is always server-generated. The user-supplied filename is kept
    only as a display label and is never used to build a filesystem path.
    """

    __tablename__ = "media"
    __table_args__ = (Index("ix_media_org_kind", "organization_id", "kind"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    kind: Mapped[MediaKind] = mapped_column(pg_enum(MediaKind, "media_kind"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    public_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    organization: Mapped["Organization"] = relationship()
    uploaded_by: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Media {self.id} {self.kind}>"
