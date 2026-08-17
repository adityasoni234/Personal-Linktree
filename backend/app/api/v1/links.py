"""Link management endpoints.

Links are nested under a group for creation and listing, and addressed directly
by id for updates — matching the documented API surface.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import CurrentPrincipal, DbSession
from app.core.errors import ValidationError
from app.core.rate_limit import Policies, rate_limit
from app.schemas.common import Message, ReorderRequest, Success
from app.schemas.link import LinkCreate, LinkOut, LinkUpdate
from app.services import group_service, link_service

router = APIRouter(tags=["Links"])


def _parse_ordering(payload: ReorderRequest) -> dict[uuid.UUID, int]:
    ordering: dict[uuid.UUID, int] = {}
    for item in payload.items:
        try:
            ordering[uuid.UUID(item.id)] = item.position
        except ValueError as exc:
            raise ValidationError("Invalid resource id", details={"id": item.id}) from exc
    return ordering


@router.get(
    "/groups/{group_id}/links",
    response_model=Success[list[LinkOut]],
    dependencies=[Depends(rate_limit(Policies.API_USER))],
    summary="List the links in a group",
)
async def list_links(
    group_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> Success[list[LinkOut]]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    return Success(data=await link_service.list_links(db, group))


@router.post(
    "/groups/{group_id}/links",
    response_model=Success[LinkOut],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Add a link to a group",
)
async def create_link(
    group_id: uuid.UUID,
    payload: LinkCreate,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[LinkOut]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    link = await link_service.create_link(db, group, payload, principal, request)
    await db.commit()
    await db.refresh(link)
    return Success(data=link_service.to_out(link))


@router.patch(
    "/links/{link_id}",
    response_model=Success[LinkOut],
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Update a link",
)
async def update_link(
    link_id: uuid.UUID,
    payload: LinkUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[LinkOut]:
    link, group = await link_service.get_link_or_404(db, link_id, principal)
    await link_service.update_link(db, link, group, payload, principal, request)
    await db.commit()
    await db.refresh(link)
    return Success(data=link_service.to_out(link))


@router.delete(
    "/links/{link_id}",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Delete a link",
)
async def delete_link(
    link_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Message:
    link, group = await link_service.get_link_or_404(db, link_id, principal)
    await link_service.delete_link(db, link, group, principal, request)
    await db.commit()
    return Message(message="Link deleted")


@router.post(
    "/links/{link_id}/duplicate",
    response_model=Success[LinkOut],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Duplicate a link",
)
async def duplicate_link(
    link_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Success[LinkOut]:
    link, group = await link_service.get_link_or_404(db, link_id, principal)
    copy = await link_service.duplicate_link(db, link, group, principal, request)
    await db.commit()
    await db.refresh(copy)
    return Success(data=link_service.to_out(copy))


@router.post(
    "/groups/{group_id}/links/reorder",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Reorder the links in a group",
)
async def reorder_links(
    group_id: uuid.UUID,
    payload: ReorderRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Message:
    group = await group_service.get_group_or_404(db, group_id, principal)
    await link_service.reorder_links(
        db, group, _parse_ordering(payload), principal, request
    )
    await db.commit()
    return Message(message="Order updated")
