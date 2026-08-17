"""Shared FastAPI dependencies: authentication, authorization and pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, PermissionDeniedError, TokenError
from app.core.logging import security_logger, user_id_ctx
from app.core.redis import RedisKeys, get_redis
from app.db.base import as_utc
from app.db.session import get_db
from app.models.enums import Role, UserStatus
from app.models.membership import Membership
from app.models.session import UserSession
from app.models.user import User
from app.schemas.common import Pagination, pagination_params
from app.security.csrf import verify_csrf
from app.security.rbac import Permission, Principal
from app.security.tokens import decode_access_token
from app.services import auth_service

# `auto_error=False` so a missing header produces our error envelope rather than
# FastAPI's default body.
bearer_scheme = HTTPBearer(auto_error=False, description="Short-lived access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]
PaginationParams = Annotated[Pagination, Depends(pagination_params)]


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    membership: Membership | None
    principal: Principal


async def _session_is_revoked(session_id, db: AsyncSession) -> bool:
    """Check the revocation list.

    Revocations are mirrored into Redis with a TTL matching the access-token
    lifetime, so the common path costs one cache read. If Redis is unavailable
    the check falls back to the database rather than failing open.
    """
    try:
        if await get_redis().exists(RedisKeys.revoked_session(str(session_id))):
            return True
        return False
    except Exception:  # noqa: BLE001 - cache outage
        session = await db.get(UserSession, session_id)
        return session is None or session.revoked_at is not None


async def get_auth_context(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    """Resolve the caller. Raises 401 for anything that is not a live session."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Sign in to continue")

    claims = decode_access_token(credentials.credentials)

    user = await auth_service.get_user_by_id(db, claims.user_id)
    if user is None:
        raise TokenError("Session is no longer valid")

    if user.status is UserStatus.SUSPENDED:
        raise PermissionDeniedError(
            "This account has been suspended", code="ACCOUNT_SUSPENDED"
        )
    if user.status is UserStatus.DELETED or not user.is_active:
        raise TokenError("Session is no longer valid")

    # Password changes, role changes and forced sign-outs move this marker
    # forward, retiring every token issued before it.
    valid_after = as_utc(user.tokens_valid_after)
    if valid_after and claims.issued_at < valid_after:
        security_logger.info("token_rejected_stale", extra={"user_id": str(user.id)})
        raise TokenError("Session is no longer valid", code="SESSION_REVOKED")

    if await _session_is_revoked(claims.session_id, db):
        raise TokenError("Session is no longer valid", code="SESSION_REVOKED")

    membership = await auth_service.primary_membership(db, user.id)

    # The role in the token is advisory; the authoritative value is re-read from
    # the database on every request, so a demotion takes effect immediately.
    principal = Principal(
        user_id=user.id,
        email=user.email,
        session_id=claims.session_id,
        system_role=user.system_role,
        organization_id=membership.organization_id if membership else None,
        organization_role=membership.role if membership else None,
    )

    request.state.principal = principal
    user_id_ctx.set(str(user.id))
    return AuthContext(user=user, membership=membership, principal=principal)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


async def get_principal(auth: CurrentAuth) -> Principal:
    return auth.principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_permission(permission: Permission) -> Callable[[AuthContext], AuthContext]:
    """Route-level permission gate.

    Coarse checks live here; anything that depends on the resource (ownership,
    organization) is decided in the service layer against the stored row.
    """

    def dependency(auth: CurrentAuth) -> AuthContext:
        auth.principal.require(permission)
        return auth

    return dependency


def require_role(minimum: Role) -> Callable[[AuthContext], AuthContext]:
    def dependency(auth: CurrentAuth) -> AuthContext:
        if not auth.principal.effective_role.at_least(minimum):
            raise PermissionDeniedError(
                "You do not have permission to perform this action",
                details={"required_role": minimum.value},
            )
        return auth

    return dependency


async def require_csrf_token(request: Request) -> None:
    """Guard for the two cookie-authenticated endpoints (refresh and logout)."""
    verify_csrf(request)


async def get_optional_principal(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal | None:
    """For endpoints that behave differently when signed in but never require it."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        context = await get_auth_context(request, db, credentials)
    except (AuthenticationError, TokenError, PermissionDeniedError):
        return None
    return context.principal
