from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import Role

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's role inside one organization. A user may belong to several."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_memberships_user_org"),
        Index("ix_memberships_org_role", "organization_id", "role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[Role] = mapped_column(
        pg_enum(Role, "role"), default=Role.USER, nullable=False
    )
    is_default: Mapped[bool] = mapped_column(default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship(back_populates="memberships")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Membership user={self.user_id} org={self.organization_id} role={self.role}>"
