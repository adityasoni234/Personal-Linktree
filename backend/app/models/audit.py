from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import AuditAction, ResourceType

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only record of security-sensitive operations.

    `event_metadata` is scrubbed by `app.services.audit_service` before it is
    written — passwords, tokens and secrets never reach this table.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_actor_created", "actor_id", "created_at"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320))

    action: Mapped[AuditAction] = mapped_column(
        pg_enum(AuditAction, "audit_action"), nullable=False, index=True
    )
    resource_type: Mapped[ResourceType | None] = mapped_column(
        pg_enum(ResourceType, "resource_type")
    )
    resource_id: Mapped[str | None] = mapped_column(String(64))

    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_label: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    organization: Mapped["Organization | None"] = relationship(back_populates="audit_logs")
    actor: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuditLog {self.action} actor={self.actor_id}>"
