"""Group lifecycle: create, edit, publish, archive, duplicate, reorder."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import Request
from sqlalchemy import Select, func, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.db.base import utcnow
from app.models.analytics import AnalyticsEvent
from app.models.enums import AnalyticsEventType, AuditAction, ResourceType
from app.models.group import Group
from app.models.link import Link
from app.models.qr import QRConfiguration
from app.schemas.common import Pagination
from app.schemas.group import GroupCreate, GroupDetail, GroupStats, GroupSummary, GroupUpdate
from app.security.rbac import (
    Permission,
    Principal,
    can_delete_group,
    can_edit_group,
    can_publish_group,
    can_read_group,
)
from app.security.slug import MAX_SLUG_LENGTH, slugify, suffixed_slug, validate_slug
from app.services import audit_service

GroupFilter = Literal["all", "published", "draft", "archived", "mine"]
GroupSort = Literal["position", "name", "created_at", "updated_at"]

MAX_SLUG_ATTEMPTS = 12


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------
async def slug_exists(db: AsyncSession, slug: str, *, exclude_id: uuid.UUID | None = None) -> bool:
    query = select(func.count(Group.id)).where(Group.slug == slug)
    if exclude_id:
        query = query.where(Group.id != exclude_id)
    return bool(await db.scalar(query))


async def ensure_unique_slug(
    db: AsyncSession,
    desired: str,
    *,
    exclude_id: uuid.UUID | None = None,
    auto_suffix: bool = True,
) -> str:
    candidate = validate_slug(desired)
    if not await slug_exists(db, candidate, exclude_id=exclude_id):
        return candidate
    if not auto_suffix:
        raise ConflictError(
            "That address is already taken. Try another.",
            code="SLUG_TAKEN",
            details={"field": "slug", "slug": candidate},
        )
    base = candidate[:MAX_SLUG_LENGTH]
    for attempt in range(MAX_SLUG_ATTEMPTS):
        alternative = validate_slug(suffixed_slug(base, attempt))
        if not await slug_exists(db, alternative, exclude_id=exclude_id):
            return alternative
    raise ConflictError("Could not generate a unique address", code="SLUG_TAKEN")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _visible_groups_query(principal: Principal) -> Select:
    """Base query scoped to what the principal may see.

    A SUPER_ADMIN sees everything; everyone else is confined to their
    organization, and a plain USER additionally only sees groups they own.
    """
    query = select(Group)
    if not principal.is_super_admin:
        query = query.where(Group.organization_id == principal.organization_id)
        if not principal.has(Permission.GROUP_READ_ANY):
            query = query.where(Group.owner_id == principal.user_id)
    return query


async def stats_for(db: AsyncSession, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, GroupStats]:
    """One aggregate query per metric family instead of per-group lookups."""
    stats: dict[uuid.UUID, GroupStats] = {gid: GroupStats() for gid in group_ids}
    if not group_ids:
        return stats

    link_counts = await db.execute(
        select(Link.group_id, func.count(Link.id))
        .where(Link.group_id.in_(group_ids))
        .group_by(Link.group_id)
    )
    for group_id, count in link_counts:
        stats[group_id].link_count = count

    event_counts = await db.execute(
        select(AnalyticsEvent.group_id, AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .where(AnalyticsEvent.group_id.in_(group_ids))
        .group_by(AnalyticsEvent.group_id, AnalyticsEvent.event_type)
    )
    for group_id, event_type, count in event_counts:
        entry = stats[group_id]
        if event_type is AnalyticsEventType.PAGE_VIEW:
            entry.page_views = count
        elif event_type is AnalyticsEventType.QR_SCAN:
            entry.qr_scans = count
        elif event_type is AnalyticsEventType.LINK_CLICK:
            entry.link_clicks = count
    return stats


def to_summary(group: Group, stats: GroupStats | None = None) -> GroupSummary:
    return GroupSummary(
        id=group.id,
        organization_id=group.organization_id,
        owner_id=group.owner_id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        logo_url=group.logo_url,
        is_published=group.is_published,
        is_archived=group.is_archived,
        position=group.position,
        created_at=group.created_at,
        updated_at=group.updated_at,
        public_url=settings.public_group_url(group.slug),
        stats=stats or GroupStats(),
    )


def to_detail(group: Group, stats: GroupStats | None = None) -> GroupDetail:
    # `group.owner` is only read when the relationship was eager-loaded.
    # Touching an unloaded relationship here would emit lazy IO inside an async
    # request, which SQLAlchemy cannot do and which would surface as a 500.
    owner_name: str | None = None
    if "owner" not in sa_inspect(group).unloaded and group.owner is not None:
        owner_name = group.owner.full_name

    summary = to_summary(group, stats)
    return GroupDetail(
        **summary.model_dump(),
        theme=group.theme or {},
        seo=group.seo or {},
        published_at=group.published_at,
        owner_name=owner_name,
    )


async def list_groups(
    db: AsyncSession,
    principal: Principal,
    pagination: Pagination,
    *,
    search: str | None = None,
    status_filter: GroupFilter = "all",
    sort: GroupSort = "position",
) -> tuple[list[GroupSummary], int]:
    query = _visible_groups_query(principal)

    if status_filter == "published":
        query = query.where(Group.is_published.is_(True), Group.is_archived.is_(False))
    elif status_filter == "draft":
        query = query.where(Group.is_published.is_(False), Group.is_archived.is_(False))
    elif status_filter == "archived":
        query = query.where(Group.is_archived.is_(True))
    elif status_filter == "mine":
        query = query.where(Group.owner_id == principal.user_id, Group.is_archived.is_(False))
    else:
        query = query.where(Group.is_archived.is_(False))

    if search:
        # Parameterised LIKE — the term is bound, never concatenated into SQL.
        term = f"%{search.strip()[:80].lower()}%"
        query = query.where(
            or_(func.lower(Group.name).like(term), func.lower(Group.slug).like(term))
        )

    total = await db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    ) or 0

    order = {
        "position": (Group.position.asc(), Group.created_at.asc()),
        "name": (func.lower(Group.name).asc(),),
        "created_at": (Group.created_at.desc(),),
        "updated_at": (Group.updated_at.desc(),),
    }[sort]

    result = await db.execute(
        query.order_by(*order).offset(pagination.offset).limit(pagination.limit)
    )
    groups = list(result.scalars().unique())
    stats = await stats_for(db, [group.id for group in groups])
    return [to_summary(group, stats.get(group.id)) for group in groups], total


async def get_group_or_404(
    db: AsyncSession, group_id: uuid.UUID, principal: Principal, *, with_owner: bool = False
) -> Group:
    query = select(Group).where(Group.id == group_id)
    if with_owner:
        query = query.options(selectinload(Group.owner))
    group = (await db.execute(query)).scalar_one_or_none()

    # Not-found and not-permitted return the same response, so the endpoint
    # cannot be used to probe which group ids exist.
    if group is None or not can_read_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise NotFoundError("Group not found")
    return group


async def get_public_group(db: AsyncSession, slug: str) -> Group:
    """Public page lookup: published and non-archived only."""
    result = await db.execute(
        select(Group)
        .where(
            Group.slug == slug.strip().lower(),
            Group.is_published.is_(True),
            Group.is_archived.is_(False),
        )
        .options(selectinload(Group.organization))
    )
    group = result.scalar_one_or_none()
    if group is None:
        # Identical for "never existed", "draft" and "archived": an unpublished
        # group must not be discoverable.
        raise NotFoundError("This page is not available")
    return group


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
async def _assert_quota(db: AsyncSession, principal: Principal) -> None:
    if principal.has(Permission.GROUP_UPDATE_ANY):
        return
    owned = await db.scalar(
        select(func.count(Group.id)).where(
            Group.owner_id == principal.user_id, Group.is_archived.is_(False)
        )
    ) or 0
    if owned >= 25:
        raise ValidationError(
            "You have reached the maximum number of groups. Archive one to create another.",
            code="QUOTA_EXCEEDED",
        )


async def create_group(
    db: AsyncSession, payload: GroupCreate, principal: Principal, request: Request
) -> Group:
    principal.require(Permission.GROUP_CREATE)
    if principal.organization_id is None:
        raise PermissionDeniedError("You are not a member of any organization")
    await _assert_quota(db, principal)

    slug = await ensure_unique_slug(
        db, payload.slug or slugify(payload.name), auto_suffix=payload.slug is None
    )

    next_position = (
        await db.scalar(
            select(func.coalesce(func.max(Group.position), -1)).where(
                Group.organization_id == principal.organization_id
            )
        )
    ) + 1

    can_publish = can_publish_group(
        principal, organization_id=principal.organization_id, owner_id=principal.user_id
    )
    publish = payload.is_published and can_publish

    group = Group(
        organization_id=principal.organization_id,
        owner_id=principal.user_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        logo_url=payload.logo_url,
        theme=payload.theme.model_dump(mode="json"),
        seo=payload.seo.model_dump(mode="json"),
        is_published=publish,
        published_at=utcnow() if publish else None,
        position=next_position,
    )
    db.add(group)
    await db.flush()

    # Every group gets a QR design immediately, so its code exists from creation.
    db.add(QRConfiguration(group_id=group.id, preset="ieee-classic"))

    await audit_service.record(
        db,
        action=AuditAction.GROUP_CREATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=group.id,
        metadata={"name": group.name, "slug": group.slug},
        request=request,
    )
    return group


async def update_group(
    db: AsyncSession,
    group: Group,
    payload: GroupUpdate,
    principal: Principal,
    request: Request,
) -> Group:
    if not can_edit_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot edit this group")

    changes: dict[str, object] = {}

    if payload.name is not None and payload.name != group.name:
        group.name = payload.name
        changes["name"] = payload.name
    if payload.description is not None:
        group.description = payload.description
        changes["description"] = True
    if payload.logo_url is not None:
        group.logo_url = payload.logo_url or None
        changes["logo_url"] = True
    if payload.theme is not None:
        group.theme = payload.theme.model_dump(mode="json")
        changes["theme"] = True
    if payload.seo is not None:
        group.seo = payload.seo.model_dump(mode="json")
        changes["seo"] = True

    slug_changed = False
    if payload.slug is not None and payload.slug != group.slug:
        old_slug = group.slug
        group.slug = await ensure_unique_slug(
            db, payload.slug, exclude_id=group.id, auto_suffix=False
        )
        changes["slug"] = {"from": old_slug, "to": group.slug}
        slug_changed = True

    await audit_service.record(
        db,
        action=AuditAction.GROUP_SLUG_CHANGED if slug_changed else AuditAction.GROUP_UPDATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=group.id,
        metadata={"name": group.name, "changes": sorted(changes)},
        request=request,
    )
    return group


async def set_published(
    db: AsyncSession, group: Group, published: bool, principal: Principal, request: Request
) -> Group:
    if not can_publish_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot publish or unpublish this group")
    if published and group.is_archived:
        raise ValidationError("Restore this group before publishing it")

    group.is_published = published
    if published and group.published_at is None:
        group.published_at = utcnow()

    await audit_service.record(
        db,
        action=AuditAction.GROUP_PUBLISHED if published else AuditAction.GROUP_UNPUBLISHED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=group.id,
        metadata={"name": group.name, "slug": group.slug},
        request=request,
    )
    return group


async def set_archived(
    db: AsyncSession, group: Group, archived: bool, principal: Principal, request: Request
) -> Group:
    if not can_edit_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot archive this group")

    group.is_archived = archived
    if archived:
        # Archiving must also take the page offline.
        group.is_published = False

    await audit_service.record(
        db,
        action=AuditAction.GROUP_ARCHIVED if archived else AuditAction.GROUP_RESTORED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=group.id,
        metadata={"name": group.name},
        request=request,
    )
    return group


async def delete_group(
    db: AsyncSession, group: Group, principal: Principal, request: Request
) -> None:
    if not can_delete_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot delete this group")

    await audit_service.record(
        db,
        action=AuditAction.GROUP_DELETED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=group.id,
        metadata={"name": group.name, "slug": group.slug},
        request=request,
    )
    # Links, QR configuration and analytics cascade at the database level.
    await db.delete(group)


async def duplicate_group(
    db: AsyncSession,
    group: Group,
    principal: Principal,
    request: Request,
    *,
    name: str | None = None,
    include_links: bool = True,
    include_qr_design: bool = True,
) -> Group:
    principal.require(Permission.GROUP_CREATE)
    await _assert_quota(db, principal)

    new_name = (name or f"{group.name} (copy)")[:120]
    copy = Group(
        organization_id=group.organization_id,
        owner_id=principal.user_id,
        name=new_name,
        slug=await ensure_unique_slug(db, slugify(new_name)),
        description=group.description,
        logo_url=group.logo_url,
        theme=dict(group.theme or {}),
        seo=dict(group.seo or {}),
        # A duplicate always starts as a draft — never silently live.
        is_published=False,
        position=group.position + 1,
    )
    db.add(copy)
    await db.flush()

    if include_links:
        links = await db.execute(
            select(Link).where(Link.group_id == group.id).order_by(Link.position)
        )
        for link in links.scalars():
            db.add(
                Link(
                    group_id=copy.id,
                    title=link.title,
                    url=link.url,
                    description=link.description,
                    icon=link.icon,
                    style=dict(link.style or {}),
                    position=link.position,
                    is_active=link.is_active,
                )
            )

    source_qr = (
        await db.execute(select(QRConfiguration).where(QRConfiguration.group_id == group.id))
    ).scalar_one_or_none()

    if include_qr_design and source_qr is not None:
        columns = {
            column.name: getattr(source_qr, column.name)
            for column in QRConfiguration.__table__.columns
            if column.name not in {"id", "group_id", "created_at", "updated_at"}
        }
        db.add(QRConfiguration(group_id=copy.id, **columns))
    else:
        db.add(QRConfiguration(group_id=copy.id, preset="ieee-classic"))

    await audit_service.record(
        db,
        action=AuditAction.GROUP_DUPLICATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=copy.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=copy.id,
        metadata={"name": copy.name, "source_group_id": str(group.id)},
        request=request,
    )
    return copy


async def reorder_groups(
    db: AsyncSession,
    ordering: dict[uuid.UUID, int],
    principal: Principal,
    request: Request,
) -> None:
    if not ordering:
        return
    result = await db.execute(
        _visible_groups_query(principal).where(Group.id.in_(list(ordering)))
    )
    groups = list(result.scalars())
    if len(groups) != len(ordering):
        # Silently ignoring unknown ids would let a caller probe for them.
        raise NotFoundError("One or more groups could not be found")

    for group in groups:
        if not can_edit_group(
            principal, organization_id=group.organization_id, owner_id=group.owner_id
        ):
            raise PermissionDeniedError("You cannot reorder these groups")
        group.position = ordering[group.id]

    await audit_service.record(
        db,
        action=AuditAction.GROUP_REORDERED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=principal.organization_id,
        resource_type=ResourceType.GROUP,
        metadata={"count": len(groups)},
        request=request,
    )
