"""Analytics schemas.

The ingest schema deliberately accepts almost nothing from the client: the
group, the link, the timestamp, the device and the visitor fingerprint are all
derived server-side. A client can say *that* something happened, never *what*.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import AnalyticsEventType, DeviceType

TimeRange = Literal["24h", "7d", "30d", "90d", "12m"]


class TrackEventRequest(BaseModel):
    """Public tracking beacon payload."""

    event_type: Literal[AnalyticsEventType.PAGE_VIEW, AnalyticsEventType.SHARE] = (
        AnalyticsEventType.PAGE_VIEW
    )
    # Only used to distinguish a QR arrival from a direct visit; the value is
    # validated against a fixed set rather than stored verbatim.
    source: Literal["direct", "qr", "share"] = "direct"


class MetricPoint(BaseModel):
    date: date
    page_views: int = 0
    qr_scans: int = 0
    link_clicks: int = 0


class NamedCount(BaseModel):
    id: str | None = None
    label: str
    count: int
    share: float = 0.0


class AnalyticsTotals(BaseModel):
    page_views: int = 0
    qr_scans: int = 0
    link_clicks: int = 0
    unique_visitors: int = 0
    click_through_rate: float = 0.0


class GroupAnalytics(BaseModel):
    group_id: uuid.UUID
    group_name: str
    range: TimeRange
    starts_at: datetime
    ends_at: datetime
    totals: AnalyticsTotals
    timeseries: list[MetricPoint] = []
    top_links: list[NamedCount] = []
    devices: list[NamedCount] = []
    browsers: list[NamedCount] = []
    referrers: list[NamedCount] = []


class OrganizationAnalytics(BaseModel):
    range: TimeRange
    starts_at: datetime
    ends_at: datetime
    totals: AnalyticsTotals
    timeseries: list[MetricPoint] = []
    top_groups: list[NamedCount] = []
    top_links: list[NamedCount] = []
    devices: list[NamedCount] = []


class DashboardActivity(BaseModel):
    id: uuid.UUID
    action: str
    description: str
    actor_name: str | None
    resource_type: str | None
    resource_id: str | None
    created_at: datetime


class DashboardGroupRow(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    links: int
    page_views: int
    qr_scans: int
    status: Literal["published", "draft", "archived"]
    updated_at: datetime


class DashboardOverview(BaseModel):
    total_groups: int
    published_groups: int
    total_links: int
    total_page_views: int
    total_qr_scans: int
    total_link_clicks: int
    totals_range: TimeRange
    timeseries: list[MetricPoint] = []
    recent_activity: list[DashboardActivity] = []
    groups: list[DashboardGroupRow] = []


class EventOut(BaseModel):
    id: uuid.UUID
    event_type: AnalyticsEventType
    occurred_at: datetime
    device_type: DeviceType
    browser: str | None
    referrer_domain: str | None


class AnalyticsQuery(BaseModel):
    range: TimeRange = "30d"
    limit: int = Field(default=10, ge=1, le=50)
