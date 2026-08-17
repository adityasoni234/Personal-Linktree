"""User, membership and organization administration."""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.db.base import utcnow
from app.models.analytics import AnalyticsEvent
from app.models.audit import AuditLog
from app.models.enums import AuditAction, ResourceType, Role, UserStatus
from app.models.group import Group
from app.models.link import Link
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.admin import (
    AdminUserRow,
    OrganizationOut,
    OrganizationUpdate,
    ProfileUpdate,
    SystemStats,
)
from app.schemas.common import Pagination
from app.security.rbac import Permission, Principal, assert_can_assign_role
from app.services import audit_service


# ---------------------------------------------------------------------------
# Profile (self-service)
# ---------------------------------------------------------------------------
async def update_profile(
    db: AsyncSession, user: User, payload: ProfileUpdate, request: Request
) -> User:
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url or None
    return user


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------
async def list_users(
    db: AsyncSession,
    principal: Principal,
    pagination: Pagination,
    *,
    search: str | None = None,
    role: Role | None = None,
    status: UserStatus | None = None,
) -> tuple[list[AdminUserRow], int]:
    principal.require(Permission.USER_MANAGE_ANY)

    query = (
        select(User, Membership, Organization)
        .join(Membership, Membership.user_id == User.id)
        .join(Organization, Organization.id == Membership.organization_id)
    )
    if not principal.is_super_admin:
        query = query.where(Membership.organization_id == principal.organization_id)
    if role is not None:
        query = query.where(
            or_(Membership.role == role, User.system_role == role)
        )
    if status is not None:
        query = query.where(User.status == status)
    else:
        query = query.where(User.status != UserStatus.DELETED)
    if search:
        term = f"%{search.strip()[:80].lower()}%"
        query = query.where(
            or_(func.lower(User.full_name).like(term), func.lower(User.email).like(term))
        )

    total = await db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    ) or 0

    rows = (
        await db.execute(
            query.order_by(User.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).all()

    user_ids = [user.id for user, _, _ in rows]
    group_counts: dict[uuid.UUID, int] = {}
    if user_ids:
        counts = await db.execute(
            select(Group.owner_id, func.count(Group.id))
            .where(Group.owner_id.in_(user_ids))
            .group_by(Group.owner_id)
        )
        group_counts = dict(counts.all())

    return (
        [
            AdminUserRow(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                system_role=user.system_role,
                status=user.status,
                email_verified=user.email_verified,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
                organization_role=membership.role,
                organization_name=organization.name,
                group_count=group_counts.get(user.id, 0),
            )
            for user, membership, organization in rows
        ],
        total,
    )


async def get_managed_user(
    db: AsyncSession, user_id: uuid.UUID, principal: Principal
) -> tuple[User, Membership]:
    """Fetch a user the principal is allowed to administer."""
    principal.require(Permission.USER_MANAGE_ANY)

    result = await db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(User.id == user_id)
        .options(selectinload(Membership.organization))
    )
    row = result.first()
    if row is None:
        raise NotFoundError("User not found")

    user, membership = row
    if not principal.in_organization(membership.organization_id):
        raise NotFoundError("User not found")
    return user, membership


# ---------------------------------------------------------------------------
# Role and status changes
# ---------------------------------------------------------------------------
async def change_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    new_role: Role,
    principal: Principal,
    request: Request,
) -> Membership:
    user, membership = await get_managed_user(db, user_id, principal)

    current = Role.SUPER_ADMIN if user.is_super_admin else membership.role
    assert_can_assign_role(
        principal, target_user_id=user.id, new_role=new_role, current_role=current
    )

    previous = current
    if new_role is Role.SUPER_ADMIN:
        user.system_role = Role.SUPER_ADMIN
        membership.role = Role.ADMIN
    else:
        user.system_role = Role.USER
        membership.role = new_role

    # A role change must not be usable until the next token is issued, so every
    # existing access token for that user is invalidated immediately.
    user.tokens_valid_after = utcnow()

    await audit_service.record(
        db,
        action=AuditAction.ROLE_CHANGED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=membership.organization_id,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        metadata={
            "target_email": user.email,
            "previous_role": previous.value,
            "new_role": new_role.value,
        },
        request=request,
    )
    return membership


async def set_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: UserStatus,
    principal: Principal,
    request: Request,
    *,
    reason: str | None = None,
) -> User:
    user, membership = await get_managed_user(db, user_id, principal)

    if user.id == principal.user_id:
        raise PermissionDeniedError("You cannot change your own account status")

    target_role = Role.SUPER_ADMIN if user.is_super_admin else membership.role
    if target_role.rank >= principal.effective_role.rank and not principal.is_super_admin:
        raise PermissionDeniedError("You cannot modify a user at or above your own role")

    user.status = status
    if status in (UserStatus.SUSPENDED, UserStatus.DELETED):
        from app.services.auth_service import revoke_all_sessions

        user.tokens_valid_after = utcnow()
        await revoke_all_sessions(db, user.id, reason=f"status_{status.value.lower()}")

    action = {
        UserStatus.SUSPENDED: AuditAction.USER_SUSPENDED,
        UserStatus.ACTIVE: AuditAction.USER_REACTIVATED,
        UserStatus.DELETED: AuditAction.USER_DELETED,
    }.get(status, AuditAction.USER_SUSPENDED)

    await audit_service.record(
        db,
        action=action,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=membership.organization_id,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        metadata={"target_email": user.email, "status": status.value, "reason": reason},
        request=request,
    )
    return user


async def add_member(
    db: AsyncSession,
    email: str,
    role: Role,
    principal: Principal,
    request: Request,
) -> Membership:
    """Add an existing account to the principal's organization."""
    principal.require(Permission.ORG_MEMBER_MANAGE)
    if principal.organization_id is None:
        raise PermissionDeniedError("You are not a member of any organization")
    if role.rank > principal.effective_role.rank:
        raise PermissionDeniedError("You cannot grant a role higher than your own")

    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(
            "No account exists with that email. Ask them to register first.",
            details={"field": "email"},
        )

    existing = await db.scalar(
        select(func.count(Membership.id)).where(
            Membership.user_id == user.id,
            Membership.organization_id == principal.organization_id,
        )
    )
    if existing:
        raise ConflictError("That person is already a member of this organization")

    membership = Membership(
        user_id=user.id,
        organization_id=principal.organization_id,
        role=role,
        is_default=False,
    )
    db.add(membership)

    await audit_service.record(
        db,
        action=AuditAction.MEMBER_ADDED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=principal.organization_id,
        resource_type=ResourceType.MEMBERSHIP,
        resource_id=user.id,
        metadata={"target_email": user.email, "role": role.value},
        request=request,
    )
    return membership


async def remove_member(
    db: AsyncSession, user_id: uuid.UUID, principal: Principal, request: Request
) -> None:
    user, membership = await get_managed_user(db, user_id, principal)
    if user.id == principal.user_id:
        raise PermissionDeniedError("You cannot remove yourself from the organization")

    target_role = Role.SUPER_ADMIN if user.is_super_admin else membership.role
    if target_role.rank >= principal.effective_role.rank and not principal.is_super_admin:
        raise PermissionDeniedError("You cannot remove a user at or above your own role")

    remaining_admins = await db.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == membership.organization_id,
            Membership.role == Role.ADMIN,
            Membership.user_id != user.id,
        )
    ) or 0
    if membership.role is Role.ADMIN and remaining_admins == 0:
        raise ValidationError("An organization must keep at least one administrator")

    await audit_service.record(
        db,
        action=AuditAction.MEMBER_REMOVED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=membership.organization_id,
        resource_type=ResourceType.MEMBERSHIP,
        resource_id=user.id,
        metadata={"target_email": user.email},
        request=request,
    )
    await db.delete(membership)


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------
async def get_organization(
    db: AsyncSession, principal: Principal, organization_id: uuid.UUID | None = None
) -> OrganizationOut:
    target_id = organization_id or principal.organization_id
    if target_id is None:
        raise NotFoundError("Organization not found")
    if not principal.in_organization(target_id):
        raise NotFoundError("Organization not found")

    organization = await db.get(Organization, target_id)
    if organization is None:
        raise NotFoundError("Organization not found")

    member_count = await db.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == organization.id
        )
    ) or 0
    group_count = await db.scalar(
        select(func.count(Group.id)).where(Group.organization_id == organization.id)
    ) or 0

    return OrganizationOut.model_validate(
        {
            **{
                column.name: getattr(organization, column.name)
                for column in Organization.__table__.columns
            },
            "settings": organization.settings or {},
            "member_count": member_count,
            "group_count": group_count,
        }
    )


async def update_organization(
    db: AsyncSession, payload: OrganizationUpdate, principal: Principal, request: Request
) -> Organization:
    principal.require(Permission.ORG_SETTINGS_UPDATE)
    if principal.organization_id is None:
        raise NotFoundError("Organization not found")

    organization = await db.get(Organization, principal.organization_id)
    if organization is None:
        raise NotFoundError("Organization not found")

    if payload.name is not None:
        organization.name = payload.name
    if payload.description is not None:
        organization.description = payload.description
    if payload.logo_url is not None:
        organization.logo_url = payload.logo_url or None
    if payload.website_url is not None:
        organization.website_url = payload.website_url or None
    if payload.settings is not None:
        organization.settings = payload.settings.model_dump(mode="json")

    await audit_service.record(
        db,
        action=AuditAction.ORG_SETTINGS_UPDATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=organization.id,
        resource_type=ResourceType.ORGANIZATION,
        resource_id=organization.id,
        request=request,
    )
    return organization


# ---------------------------------------------------------------------------
# Audit log + platform stats
# ---------------------------------------------------------------------------
async def list_audit_logs(
    db: AsyncSession,
    principal: Principal,
    pagination: Pagination,
    *,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[list[AuditLog], int]:
    principal.require(Permission.AUDIT_READ)

    query = select(AuditLog)
    if not principal.is_super_admin:
        query = query.where(AuditLog.organization_id == principal.organization_id)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)

    total = await db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    ) or 0
    rows = await db.execute(
        query.order_by(AuditLog.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    return list(rows.scalars()), total


async def system_stats(db: AsyncSession, principal: Principal) -> SystemStats:
    principal.require(Permission.SYSTEM_ADMIN)
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=30)
    return SystemStats(
        users=await db.scalar(
            select(func.count(User.id)).where(User.status != UserStatus.DELETED)
        ) or 0,
        organizations=await db.scalar(select(func.count(Organization.id))) or 0,
        groups=await db.scalar(select(func.count(Group.id))) or 0,
        links=await db.scalar(select(func.count(Link.id))) or 0,
        events_last_30d=await db.scalar(
            select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.occurred_at >= cutoff)
        ) or 0,
        published_groups=await db.scalar(
            select(func.count(Group.id)).where(
                Group.is_published.is_(True), Group.is_archived.is_(False)
            )
        ) or 0,
    )
