"""Administration endpoints: users, members, organization, audit log."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import CurrentPrincipal, DbSession, PaginationParams, require_permission
from app.core.rate_limit import Policies, rate_limit
from app.models.enums import Role, UserStatus
from app.schemas.admin import (
    AdminUserRow,
    AuditLogRow,
    MemberInviteRequest,
    OrganizationOut,
    OrganizationUpdate,
    RoleChangeRequest,
    SystemStats,
    UserStatusRequest,
)
from app.schemas.common import Message, Page, Success, build_page
from app.security.rbac import Permission
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get(
    "/users",
    response_model=Page[AdminUserRow],
    dependencies=[
        Depends(require_permission(Permission.USER_MANAGE_ANY)),
        Depends(rate_limit(Policies.API_USER)),
    ],
    summary="List organization members",
)
async def list_users(
    principal: CurrentPrincipal,
    db: DbSession,
    pagination: PaginationParams,
    search: Annotated[str | None, Query(max_length=80)] = None,
    role: Annotated[Role | None, Query()] = None,
    status_filter: Annotated[UserStatus | None, Query(alias="status")] = None,
) -> Page[AdminUserRow]:
    users, total = await user_service.list_users(
        db, principal, pagination, search=search, role=role, status=status_filter
    )
    return build_page(users, total, pagination)


@router.post(
    "/users/{user_id}/role",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Change a member's role",
)
async def change_role(
    user_id: uuid.UUID,
    payload: RoleChangeRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Message:
    await user_service.change_role(db, user_id, payload.role, principal, request)
    await db.commit()
    return Message(message=f"Role updated to {payload.role.value}")


@router.post(
    "/users/{user_id}/status",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Suspend or reactivate a member",
)
async def change_status(
    user_id: uuid.UUID,
    payload: UserStatusRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Message:
    await user_service.set_status(
        db, user_id, payload.status, principal, request, reason=payload.reason
    )
    await db.commit()
    return Message(message=f"Account status set to {payload.status.value.lower()}")


@router.post(
    "/members",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission(Permission.ORG_MEMBER_MANAGE)),
        Depends(rate_limit(Policies.WRITE_USER)),
    ],
    summary="Add an existing account to this organization",
)
async def add_member(
    payload: MemberInviteRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Message:
    await user_service.add_member(db, payload.email, payload.role, principal, request)
    await db.commit()
    return Message(message="Member added")


@router.delete(
    "/members/{user_id}",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.WRITE_USER))],
    summary="Remove a member from this organization",
)
async def remove_member(
    user_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Message:
    await user_service.remove_member(db, user_id, principal, request)
    await db.commit()
    return Message(message="Member removed")


@router.get(
    "/organization",
    response_model=Success[OrganizationOut],
    summary="Get the current organization",
)
async def get_organization(
    principal: CurrentPrincipal, db: DbSession
) -> Success[OrganizationOut]:
    return Success(data=await user_service.get_organization(db, principal))


@router.patch(
    "/organization",
    response_model=Success[OrganizationOut],
    dependencies=[
        Depends(require_permission(Permission.ORG_SETTINGS_UPDATE)),
        Depends(rate_limit(Policies.WRITE_USER)),
    ],
    summary="Update organization settings",
)
async def update_organization(
    payload: OrganizationUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[OrganizationOut]:
    await user_service.update_organization(db, payload, principal, request)
    await db.commit()
    return Success(data=await user_service.get_organization(db, principal))


@router.get(
    "/audit-logs",
    response_model=Page[AuditLogRow],
    dependencies=[
        Depends(require_permission(Permission.AUDIT_READ)),
        Depends(rate_limit(Policies.API_USER)),
    ],
    summary="Read the audit log",
)
async def list_audit_logs(
    principal: CurrentPrincipal,
    db: DbSession,
    pagination: PaginationParams,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[AuditLogRow]:
    entries, total = await user_service.list_audit_logs(
        db, principal, pagination, action=action, actor_id=actor_id
    )
    return build_page(
        [AuditLogRow.model_validate(entry) for entry in entries], total, pagination
    )


@router.get(
    "/system",
    response_model=Success[SystemStats],
    dependencies=[Depends(require_permission(Permission.SYSTEM_ADMIN))],
    summary="Platform-wide statistics (super administrators only)",
)
async def system_stats(principal: CurrentPrincipal, db: DbSession) -> Success[SystemStats]:
    return Success(data=await user_service.system_stats(db, principal))
