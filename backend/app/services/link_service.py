"""Link management within a group."""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.models.analytics import AnalyticsEvent
from app.models.enums import AnalyticsEventType, AuditAction, ResourceType
from app.models.group import Group
from app.models.link import Link
from app.schemas.link import LinkCreate, LinkOut, LinkUpdate
from app.security.rbac import Principal, can_edit_group
from app.security.url_validation import validate_link_url
from app.services import audit_service

MAX_LINKS_PER_GROUP = 60


def _assert_can_manage(principal: Principal, group: Group) -> None:
    if not can_edit_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot modify links in this group")


def to_out(link: Link, click_count: int = 0) -> LinkOut:
    return LinkOut(
        id=link.id,
        group_id=link.group_id,
        title=link.title,
        url=link.url,
        description=link.description,
        icon=link.icon,
        style=link.style or {},
        position=link.position,
        is_active=link.is_active,
        created_at=link.created_at,
        updated_at=link.updated_at,
        click_count=click_count,
    )


async def list_links(
    db: AsyncSession, group: Group, *, include_counts: bool = True
) -> list[LinkOut]:
    result = await db.execute(
        select(Link).where(Link.group_id == group.id).order_by(Link.position, Link.created_at)
    )
    links = list(result.scalars())

    counts: dict[uuid.UUID, int] = {}
    if include_counts and links:
        rows = await db.execute(
            select(AnalyticsEvent.link_id, func.count(AnalyticsEvent.id))
            .where(
                AnalyticsEvent.group_id == group.id,
                AnalyticsEvent.event_type == AnalyticsEventType.LINK_CLICK,
                AnalyticsEvent.link_id.is_not(None),
            )
            .group_by(AnalyticsEvent.link_id)
        )
        counts = {link_id: count for link_id, count in rows}

    return [to_out(link, counts.get(link.id, 0)) for link in links]


async def get_link_or_404(db: AsyncSession, link_id: uuid.UUID, principal: Principal) -> tuple[Link, Group]:
    result = await db.execute(select(Link).where(Link.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundError("Link not found")

    group = await db.get(Group, link.group_id)
    if group is None:
        raise NotFoundError("Link not found")

    from app.security.rbac import can_read_group

    if not can_read_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise NotFoundError("Link not found")
    return link, group


async def create_link(
    db: AsyncSession, group: Group, payload: LinkCreate, principal: Principal, request: Request
) -> Link:
    _assert_can_manage(principal, group)

    existing = await db.scalar(
        select(func.count(Link.id)).where(Link.group_id == group.id)
    ) or 0
    if existing >= MAX_LINKS_PER_GROUP:
        raise ValidationError(
            f"A group can hold at most {MAX_LINKS_PER_GROUP} links",
            code="QUOTA_EXCEEDED",
        )

    position = payload.position
    if position is None:
        position = (
            await db.scalar(
                select(func.coalesce(func.max(Link.position), -1)).where(
                    Link.group_id == group.id
                )
            )
        ) + 1

    link = Link(
        group_id=group.id,
        title=payload.title,
        # Re-validated here even though the schema already did: the service
        # layer is the enforcement point, and it is also reachable from tests,
        # imports and background jobs that bypass the schema.
        url=validate_link_url(payload.url),
        description=payload.description,
        icon=payload.icon,
        style=payload.style.model_dump(mode="json"),
        position=position,
        is_active=payload.is_active,
    )
    db.add(link)
    await db.flush()

    await audit_service.record(
        db,
        action=AuditAction.LINK_CREATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.LINK,
        resource_id=link.id,
        metadata={"title": link.title, "group_id": str(group.id)},
        request=request,
    )
    return link


async def update_link(
    db: AsyncSession,
    link: Link,
    group: Group,
    payload: LinkUpdate,
    principal: Principal,
    request: Request,
) -> Link:
    _assert_can_manage(principal, group)

    if payload.title is not None:
        link.title = payload.title
    if payload.url is not None:
        link.url = validate_link_url(payload.url)
    if payload.description is not None:
        link.description = payload.description
    if payload.icon is not None:
        link.icon = payload.icon or None
    if payload.style is not None:
        link.style = payload.style.model_dump(mode="json")
    if payload.is_active is not None:
        link.is_active = payload.is_active
    if payload.position is not None:
        link.position = payload.position

    await audit_service.record(
        db,
        action=AuditAction.LINK_UPDATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.LINK,
        resource_id=link.id,
        metadata={"title": link.title},
        request=request,
    )
    return link


async def delete_link(
    db: AsyncSession, link: Link, group: Group, principal: Principal, request: Request
) -> None:
    _assert_can_manage(principal, group)
    await audit_service.record(
        db,
        action=AuditAction.LINK_DELETED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.LINK,
        resource_id=link.id,
        metadata={"title": link.title, "group_id": str(group.id)},
        request=request,
    )
    await db.delete(link)


async def duplicate_link(
    db: AsyncSession, link: Link, group: Group, principal: Principal, request: Request
) -> Link:
    _assert_can_manage(principal, group)
    copy = Link(
        group_id=group.id,
        title=f"{link.title} (copy)"[:120],
        url=link.url,
        description=link.description,
        icon=link.icon,
        style=dict(link.style or {}),
        position=link.position + 1,
        is_active=False,
    )
    db.add(copy)
    await db.flush()

    await audit_service.record(
        db,
        action=AuditAction.LINK_CREATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.LINK,
        resource_id=copy.id,
        metadata={"title": copy.title, "duplicated_from": str(link.id)},
        request=request,
    )
    return copy


async def reorder_links(
    db: AsyncSession,
    group: Group,
    ordering: dict[uuid.UUID, int],
    principal: Principal,
    request: Request,
) -> None:
    _assert_can_manage(principal, group)
    if not ordering:
        return

    result = await db.execute(
        select(Link).where(Link.group_id == group.id, Link.id.in_(list(ordering)))
    )
    links = list(result.scalars())
    if len(links) != len(ordering):
        raise NotFoundError("One or more links could not be found")

    for link in links:
        link.position = ordering[link.id]

    await audit_service.record(
        db,
        action=AuditAction.LINK_REORDERED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.GROUP,
        resource_id=group.id,
        metadata={"count": len(links)},
        request=request,
    )


async def public_links(db: AsyncSession, group_id: uuid.UUID) -> list[Link]:
    result = await db.execute(
        select(Link)
        .where(Link.group_id == group_id, Link.is_active.is_(True))
        .order_by(Link.position, Link.created_at)
        .limit(MAX_LINKS_PER_GROUP)
    )
    return list(result.scalars())
