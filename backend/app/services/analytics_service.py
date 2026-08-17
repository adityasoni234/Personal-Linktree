"""Analytics reporting.

Every query is bounded by a time range and an explicit `LIMIT`; nothing here can
scan the whole event table. Aggregation happens in the database, not in Python.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError
from app.models.analytics import AnalyticsEvent
from app.models.audit import AuditLog
from app.models.enums import AnalyticsEventType
from app.models.group import Group
from app.models.link import Link
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsTotals,
    DashboardActivity,
    DashboardGroupRow,
    DashboardOverview,
    GroupAnalytics,
    MetricPoint,
    NamedCount,
    OrganizationAnalytics,
    TimeRange,
)
from app.security.rbac import Permission, Principal, can_read_analytics
from app.services import audit_service

RANGE_DAYS: dict[TimeRange, int] = {
    "24h": 1,
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "12m": 365,
}


def range_bounds(time_range: TimeRange) -> tuple[datetime, datetime]:
    ends_at = datetime.now(tz=timezone.utc)
    return ends_at - timedelta(days=RANGE_DAYS[time_range]), ends_at


def _scoped_events(principal: Principal) -> Select:
    query = select(AnalyticsEvent)
    if not principal.is_super_admin:
        query = query.where(AnalyticsEvent.organization_id == principal.organization_id)
    return query


def _shares(counts: list[tuple[str | None, str, int]]) -> list[NamedCount]:
    total = sum(count for _, _, count in counts) or 1
    return [
        NamedCount(
            id=identifier,
            label=label,
            count=count,
            share=round(count / total * 100, 1),
        )
        for identifier, label, count in counts
    ]


async def _totals(
    db: AsyncSession, base_filters: list, starts_at: datetime, ends_at: datetime
) -> AnalyticsTotals:
    rows = await db.execute(
        select(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .where(
            *base_filters,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
        )
        .group_by(AnalyticsEvent.event_type)
    )
    counts = {event_type: count for event_type, count in rows}

    unique_visitors = await db.scalar(
        select(func.count(func.distinct(AnalyticsEvent.visitor_hash))).where(
            *base_filters,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
            AnalyticsEvent.visitor_hash.is_not(None),
        )
    ) or 0

    page_views = counts.get(AnalyticsEventType.PAGE_VIEW, 0)
    qr_scans = counts.get(AnalyticsEventType.QR_SCAN, 0)
    link_clicks = counts.get(AnalyticsEventType.LINK_CLICK, 0)
    visits = page_views + qr_scans

    return AnalyticsTotals(
        page_views=page_views,
        qr_scans=qr_scans,
        link_clicks=link_clicks,
        unique_visitors=unique_visitors,
        click_through_rate=round(link_clicks / visits * 100, 1) if visits else 0.0,
    )


async def _timeseries(
    db: AsyncSession, base_filters: list, starts_at: datetime, ends_at: datetime
) -> list[MetricPoint]:
    # `func.date` is portable across PostgreSQL and SQLite (used by the tests).
    day = func.date(AnalyticsEvent.occurred_at)
    rows = await db.execute(
        select(day, AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .where(
            *base_filters,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
        )
        .group_by(day, AnalyticsEvent.event_type)
        .order_by(day)
    )

    buckets: dict[str, MetricPoint] = {}
    for bucket_date, event_type, count in rows:
        key = str(bucket_date)[:10]
        point = buckets.setdefault(
            key, MetricPoint(date=datetime.fromisoformat(key).date())
        )
        if event_type is AnalyticsEventType.PAGE_VIEW:
            point.page_views = count
        elif event_type is AnalyticsEventType.QR_SCAN:
            point.qr_scans = count
        elif event_type is AnalyticsEventType.LINK_CLICK:
            point.link_clicks = count

    # Fill the gaps so the chart has one point per day in the range.
    series: list[MetricPoint] = []
    cursor = starts_at.date()
    last = ends_at.date()
    while cursor <= last:
        series.append(buckets.get(cursor.isoformat(), MetricPoint(date=cursor)))
        cursor += timedelta(days=1)
    return series


async def _breakdown(
    db: AsyncSession, column, base_filters: list, starts_at: datetime,
    ends_at: datetime, limit: int = 8
) -> list[NamedCount]:
    rows = await db.execute(
        select(column, func.count(AnalyticsEvent.id))
        .where(
            *base_filters,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
            column.is_not(None),
        )
        .group_by(column)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(limit)
    )
    return _shares(
        [
            (None, str(value.value if hasattr(value, "value") else value).title(), count)
            for value, count in rows
        ]
    )


async def group_analytics(
    db: AsyncSession,
    group: Group,
    principal: Principal,
    *,
    time_range: TimeRange = "30d",
    limit: int = 10,
) -> GroupAnalytics:
    if not can_read_analytics(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot view analytics for this group")

    starts_at, ends_at = range_bounds(time_range)
    filters = [AnalyticsEvent.group_id == group.id]

    top_link_rows = await db.execute(
        select(Link.id, Link.title, func.count(AnalyticsEvent.id))
        .join(AnalyticsEvent, AnalyticsEvent.link_id == Link.id)
        .where(
            AnalyticsEvent.group_id == group.id,
            AnalyticsEvent.event_type == AnalyticsEventType.LINK_CLICK,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
        )
        .group_by(Link.id, Link.title)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(limit)
    )

    return GroupAnalytics(
        group_id=group.id,
        group_name=group.name,
        range=time_range,
        starts_at=starts_at,
        ends_at=ends_at,
        totals=await _totals(db, filters, starts_at, ends_at),
        timeseries=await _timeseries(db, filters, starts_at, ends_at),
        top_links=_shares([(str(lid), title, count) for lid, title, count in top_link_rows]),
        devices=await _breakdown(db, AnalyticsEvent.device_type, filters, starts_at, ends_at),
        browsers=await _breakdown(db, AnalyticsEvent.browser, filters, starts_at, ends_at),
        referrers=await _breakdown(
            db, AnalyticsEvent.referrer_domain, filters, starts_at, ends_at
        ),
    )


def _analytics_scope_filters(principal: Principal) -> list:
    """Restrict aggregates to what the principal is allowed to see."""
    filters: list = []
    if not principal.is_super_admin:
        filters.append(AnalyticsEvent.organization_id == principal.organization_id)
    if not principal.has(Permission.ANALYTICS_READ_ANY):
        # A plain USER only ever sees numbers for groups they own.
        filters.append(
            AnalyticsEvent.group_id.in_(
                select(Group.id).where(Group.owner_id == principal.user_id)
            )
        )
    return filters


async def organization_analytics(
    db: AsyncSession, principal: Principal, *, time_range: TimeRange = "30d", limit: int = 10
) -> OrganizationAnalytics:
    if not principal.has_any(Permission.ANALYTICS_READ_ANY, Permission.ANALYTICS_READ_OWN):
        raise PermissionDeniedError("You cannot view analytics")

    starts_at, ends_at = range_bounds(time_range)
    filters = _analytics_scope_filters(principal)

    top_groups = await db.execute(
        select(Group.id, Group.name, func.count(AnalyticsEvent.id))
        .join(AnalyticsEvent, AnalyticsEvent.group_id == Group.id)
        .where(
            *filters,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
            AnalyticsEvent.event_type.in_(
                [AnalyticsEventType.PAGE_VIEW, AnalyticsEventType.QR_SCAN]
            ),
        )
        .group_by(Group.id, Group.name)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(limit)
    )

    top_links = await db.execute(
        select(Link.id, Link.title, func.count(AnalyticsEvent.id))
        .join(AnalyticsEvent, AnalyticsEvent.link_id == Link.id)
        .where(
            *filters,
            AnalyticsEvent.event_type == AnalyticsEventType.LINK_CLICK,
            AnalyticsEvent.occurred_at >= starts_at,
            AnalyticsEvent.occurred_at <= ends_at,
        )
        .group_by(Link.id, Link.title)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(limit)
    )

    return OrganizationAnalytics(
        range=time_range,
        starts_at=starts_at,
        ends_at=ends_at,
        totals=await _totals(db, filters, starts_at, ends_at),
        timeseries=await _timeseries(db, filters, starts_at, ends_at),
        top_groups=_shares([(str(gid), name, count) for gid, name, count in top_groups]),
        top_links=_shares([(str(lid), title, count) for lid, title, count in top_links]),
        devices=await _breakdown(db, AnalyticsEvent.device_type, filters, starts_at, ends_at),
    )


async def dashboard_overview(
    db: AsyncSession, principal: Principal, *, time_range: TimeRange = "30d"
) -> DashboardOverview:
    starts_at, ends_at = range_bounds(time_range)

    group_query = select(Group)
    if not principal.is_super_admin:
        group_query = group_query.where(Group.organization_id == principal.organization_id)
    if not principal.has(Permission.GROUP_READ_ANY):
        group_query = group_query.where(Group.owner_id == principal.user_id)
    group_query = group_query.where(Group.is_archived.is_(False))

    groups = list((await db.execute(group_query.order_by(Group.position).limit(200))).scalars())
    group_ids = [group.id for group in groups]

    link_counts: dict[uuid.UUID, int] = {}
    if group_ids:
        rows = await db.execute(
            select(Link.group_id, func.count(Link.id))
            .where(Link.group_id.in_(group_ids))
            .group_by(Link.group_id)
        )
        link_counts = dict(rows.all())

    event_counts: dict[tuple[uuid.UUID, AnalyticsEventType], int] = {}
    if group_ids:
        rows = await db.execute(
            select(
                AnalyticsEvent.group_id,
                AnalyticsEvent.event_type,
                func.count(AnalyticsEvent.id),
            )
            .where(AnalyticsEvent.group_id.in_(group_ids))
            .group_by(AnalyticsEvent.group_id, AnalyticsEvent.event_type)
        )
        event_counts = {(gid, etype): count for gid, etype, count in rows}

    filters = _analytics_scope_filters(principal)
    totals = await _totals(db, filters, starts_at, ends_at)

    activity_query = (
        select(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.actor_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(12)
    )
    if not principal.is_super_admin:
        activity_query = activity_query.where(
            AuditLog.organization_id == principal.organization_id
        )
    if not principal.has(Permission.AUDIT_READ):
        activity_query = activity_query.where(AuditLog.actor_id == principal.user_id)

    activity_rows = (await db.execute(activity_query)).all()

    return DashboardOverview(
        total_groups=len(groups),
        published_groups=sum(1 for group in groups if group.is_published),
        total_links=sum(link_counts.values()),
        total_page_views=sum(
            count
            for (_, etype), count in event_counts.items()
            if etype is AnalyticsEventType.PAGE_VIEW
        ),
        total_qr_scans=sum(
            count
            for (_, etype), count in event_counts.items()
            if etype is AnalyticsEventType.QR_SCAN
        ),
        total_link_clicks=sum(
            count
            for (_, etype), count in event_counts.items()
            if etype is AnalyticsEventType.LINK_CLICK
        ),
        totals_range=time_range,
        timeseries=await _timeseries(db, filters, starts_at, ends_at),
        recent_activity=[
            DashboardActivity(
                id=entry.id,
                action=entry.action.value,
                description=audit_service.describe(entry),
                actor_name=actor_name,
                resource_type=entry.resource_type.value if entry.resource_type else None,
                resource_id=entry.resource_id,
                created_at=entry.created_at,
            )
            for entry, actor_name in activity_rows
        ],
        groups=[
            DashboardGroupRow(
                id=group.id,
                name=group.name,
                slug=group.slug,
                links=link_counts.get(group.id, 0),
                page_views=event_counts.get((group.id, AnalyticsEventType.PAGE_VIEW), 0),
                qr_scans=event_counts.get((group.id, AnalyticsEventType.QR_SCAN), 0),
                status=(
                    "archived"
                    if group.is_archived
                    else ("published" if group.is_published else "draft")
                ),
                updated_at=group.updated_at,
            )
            for group in groups[:20]
        ],
    )
