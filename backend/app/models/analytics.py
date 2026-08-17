from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import AnalyticsEventType, DeviceType

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.link import Link


class AnalyticsEvent(UUIDPrimaryKeyMixin, Base):
    """One privacy-conscious interaction record.

    Deliberately *not* stored: raw IP addresses, full user-agent strings, cookies
    or any cross-site identifier. `visitor_hash` is a rotating salted digest used
    only for same-day de-duplication and unique-visitor counts.
    """

    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_group_type_time", "group_id", "event_type", "occurred_at"),
        Index("ix_analytics_link_time", "link_id", "occurred_at"),
        Index("ix_analytics_org_time", "organization_id", "occurred_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("links.id", ondelete="CASCADE"), index=True
    )

    event_type: Mapped[AnalyticsEventType] = mapped_column(
        pg_enum(AnalyticsEventType, "analytics_event_type"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    device_type: Mapped[DeviceType] = mapped_column(
        pg_enum(DeviceType, "device_type"), default=DeviceType.UNKNOWN, nullable=False
    )
    browser: Mapped[str | None] = mapped_column(String(40))
    os: Mapped[str | None] = mapped_column(String(40))
    # Registrable domain of the referrer only — never the full URL (it can carry
    # query parameters and personal data).
    referrer_domain: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2))

    visitor_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    group: Mapped["Group"] = relationship()
    link: Mapped["Link | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AnalyticsEvent {self.event_type} group={self.group_id}>"
