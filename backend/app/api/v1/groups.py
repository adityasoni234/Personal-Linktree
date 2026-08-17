"""Group management endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import CurrentPrincipal, DbSession, PaginationParams
from app.core.errors import ValidationError
from app.core.rate_limit import Policies, rate_limit
from app.schemas.common import Message, Page, ReorderRequest, Success, build_page
from app.schemas.group import (
    GroupCreate,
    GroupDetail,
    GroupDuplicateRequest,
    GroupPublishRequest,
    GroupSummary,
    GroupUpdate,
)
from app.services import group_service, qr_service

router = APIRouter(prefix="/groups", tags=["Groups"])


def _parse_ordering(payload: ReorderRequest) -> dict[uuid.UUID, int]:
    ordering: dict[uuid.UUID, int] = {}
    for item in payload.items:
        try:
            ordering[uuid.UUID(item.id)] = item.position
        except ValueError as exc:
            raise ValidationError("Invalid resource id", details={"id": item.id}) from exc
    return ordering


@router.get(
    "",
    response_model=Page[GroupSummary],
    dependencies=[Depends(rate_limit(Policies.API_USER))],
    summary="List groups",
)
async def list_groups(
    principal: CurrentPrincipal,
    db: DbSession,
    pagination: PaginationParams,
    search: Annotated[str | None, Query(max_length=80)] = None,
    status_filter: Annotated[group_service.GroupFilter, Query(alias="status")] = "all",
    sort: Annotated[group_service.GroupSort, Query()] = "position",
) -> Page[GroupSummary]:
    groups, total = await group_service.list_groups(
        db, principal, pagination, search=search, status_filter=status_filter, sort=sort
    )
    return build_page(groups, total, pagination)


@router.post(
    "",
    response_model=Success[GroupDetail],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Create a group",
)
async def create_group(
    payload: GroupCreate, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Success[GroupDetail]:
    group = await group_service.create_group(db, payload, principal, request)
    await db.commit()
    await db.refresh(group)
    return Success(data=group_service.to_detail(group))


@router.get("/{group_id}", response_model=Success[GroupDetail], summary="Get a group")
async def get_group(
    group_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> Success[GroupDetail]:
    group = await group_service.get_group_or_404(db, group_id, principal, with_owner=True)
    stats = await group_service.stats_for(db, [group.id])
    return Success(data=group_service.to_detail(group, stats.get(group.id)))


@router.patch(
    "/{group_id}",
    response_model=Success[GroupDetail],
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Update a group",
)
async def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[GroupDetail]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    previous_slug = group.slug

    await group_service.update_group(db, group, payload, principal, request)
    await db.commit()
    await db.refresh(group)

    if group.slug != previous_slug:
        # The QR encodes the public URL, so a slug change moves its cache key.
        await qr_service.invalidate_for_group(db, group.id)

    return Success(data=group_service.to_detail(group))


@router.delete(
    "/{group_id}",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Delete a group",
)
async def delete_group(
    group_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Message:
    group = await group_service.get_group_or_404(db, group_id, principal)
    await group_service.delete_group(db, group, principal, request)
    await db.commit()
    return Message(message="Group deleted")


@router.post(
    "/{group_id}/publish",
    response_model=Success[GroupDetail],
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Publish or unpublish a group",
)
async def set_published(
    group_id: uuid.UUID,
    payload: GroupPublishRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[GroupDetail]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    await group_service.set_published(db, group, payload.is_published, principal, request)
    await db.commit()
    await db.refresh(group)
    return Success(data=group_service.to_detail(group))


@router.post(
    "/{group_id}/archive",
    response_model=Success[GroupDetail],
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Archive a group",
)
async def archive_group(
    group_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Success[GroupDetail]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    await group_service.set_archived(db, group, True, principal, request)
    await db.commit()
    await db.refresh(group)
    return Success(data=group_service.to_detail(group))


@router.post(
    "/{group_id}/restore",
    response_model=Success[GroupDetail],
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Restore an archived group",
)
async def restore_group(
    group_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Success[GroupDetail]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    await group_service.set_archived(db, group, False, principal, request)
    await db.commit()
    await db.refresh(group)
    return Success(data=group_service.to_detail(group))


@router.post(
    "/{group_id}/duplicate",
    response_model=Success[GroupDetail],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Duplicate a group",
)
async def duplicate_group(
    group_id: uuid.UUID,
    payload: GroupDuplicateRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[GroupDetail]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    copy = await group_service.duplicate_group(
        db,
        group,
        principal,
        request,
        name=payload.name,
        include_links=payload.include_links,
        include_qr_design=payload.include_qr_design,
    )
    await db.commit()
    await db.refresh(copy)
    return Success(data=group_service.to_detail(copy))


@router.post(
    "/reorder",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Reorder groups",
)
async def reorder_groups(
    payload: ReorderRequest, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Message:
    await group_service.reorder_groups(db, _parse_ordering(payload), principal, request)
    await db.commit()
    return Message(message="Order updated")


@router.get(
    "/slug-available/{slug}",
    response_model=Success[dict],
    dependencies=[Depends(rate_limit(Policies.API_USER))],
    summary="Check whether a public address is available",
)
async def check_slug(
    slug: str, principal: CurrentPrincipal, db: DbSession,
    exclude: Annotated[uuid.UUID | None, Query()] = None,
) -> Success[dict]:
    from app.core.errors import AppError
    from app.security.slug import validate_slug

    try:
        candidate = validate_slug(slug)
    except AppError as exc:
        return Success(data={"available": False, "reason": exc.message, "slug": slug})

    taken = await group_service.slug_exists(db, candidate, exclude_id=exclude)
    return Success(
        data={
            "available": not taken,
            "slug": candidate,
            "reason": "That address is already taken" if taken else None,
        }
    )
