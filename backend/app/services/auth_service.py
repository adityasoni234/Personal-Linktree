"""Authentication and session lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.privacy import hash_ip
from app.core.config import settings
from app.core.errors import (
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    PermissionDeniedError,
    TokenError,
    ValidationError,
)
from app.core.logging import security_logger
from app.core.rate_limit import client_ip
from app.core.redis import RedisKeys, get_redis
from app.db.base import as_utc, utcnow
from app.models.enums import AuditAction, ResourceType, Role, UserStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.session import PasswordResetToken, UserSession
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserProfile,
)
from app.security import bruteforce
from app.security.csrf import generate_csrf_token
from app.security.passwords import (
    generate_token,
    hash_password,
    hash_token,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.security.rbac import ROLE_PERMISSIONS, Principal
from app.security.sanitize import user_agent_label
from app.security.tokens import create_access_token, create_refresh_token, decode_refresh_token
from app.services import audit_service, email_service


# A refresh token that was rotated away this recently is still accepted once,
# so a benign race (two tabs, a retried request) does not look like theft.
REFRESH_ROTATION_GRACE_SECONDS = 20


@dataclass(frozen=True, slots=True)
class IssuedSession:
    user: User
    session: UserSession
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    csrf_token: str


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def primary_membership(db: AsyncSession, user_id: uuid.UUID) -> Membership | None:
    result = await db.execute(
        select(Membership)
        .where(Membership.user_id == user_id)
        .options(selectinload(Membership.organization))
        .order_by(Membership.is_default.desc(), Membership.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def default_organization(db: AsyncSession, slug: str | None = None) -> Organization:
    """Resolve the organization a new account joins."""
    target_slug = (slug or settings.BOOTSTRAP_ORG_SLUG).strip().lower()
    result = await db.execute(select(Organization).where(Organization.slug == target_slug))
    organization = result.scalar_one_or_none()
    if organization is None:
        raise NotFoundError("Organization not found", details={"field": "organization_slug"})
    if not organization.is_active:
        raise PermissionDeniedError("This organization is not accepting new members")
    return organization


# ---------------------------------------------------------------------------
# Profile projection
# ---------------------------------------------------------------------------
def build_profile(user: User, membership: Membership | None) -> UserProfile:
    organization_role = membership.role if membership else None
    effective = (
        Role.SUPER_ADMIN if user.is_super_admin else (organization_role or Role.USER)
    )
    return UserProfile(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        system_role=user.system_role,
        status=user.status,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        organization_id=membership.organization_id if membership else None,
        organization_name=(
            membership.organization.name if membership and membership.organization else None
        ),
        organization_role=organization_role,
        effective_role=effective,
        permissions=sorted(permission.value for permission in ROLE_PERMISSIONS[effective]),
    )


def principal_from(user: User, membership: Membership | None,
                   session_id: uuid.UUID) -> Principal:
    return Principal(
        user_id=user.id,
        email=user.email,
        session_id=session_id,
        system_role=user.system_role,
        organization_id=membership.organization_id if membership else None,
        organization_role=membership.role if membership else None,
    )


# ---------------------------------------------------------------------------
# Session issuing
# ---------------------------------------------------------------------------
async def issue_session(
    db: AsyncSession,
    user: User,
    request: Request,
    *,
    membership: Membership | None = None,
) -> IssuedSession:
    membership = membership or await primary_membership(db, user.id)
    session_id = uuid.uuid4()

    refresh_token, refresh_expires_at = create_refresh_token(
        user_id=user.id, session_id=session_id
    )
    access_token, access_expires_at = create_access_token(
        user_id=user.id,
        session_id=session_id,
        system_role=user.system_role.value,
        organization_id=membership.organization_id if membership else None,
        organization_role=membership.role.value if membership else None,
    )

    session = UserSession(
        id=session_id,
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=refresh_expires_at,
        last_used_at=utcnow(),
        user_agent_label=user_agent_label(request.headers.get("user-agent")),
        ip_hash=hash_ip(client_ip(request)),
    )
    db.add(session)

    return IssuedSession(
        user=user,
        session=session,
        access_token=access_token,
        access_expires_at=access_expires_at,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
        csrf_token=generate_csrf_token(),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
async def register(
    db: AsyncSession, payload: RegisterRequest, request: Request
) -> IssuedSession:
    organization = await default_organization(db, payload.organization_slug)

    settings_blob = organization.settings or {}
    if not settings_blob.get("allow_public_registration", True):
        raise PermissionDeniedError("This organization is invitation-only")

    validate_password_strength(
        payload.password, email=payload.email, full_name=payload.full_name
    )

    existing = await get_user_by_email(db, payload.email)
    if existing is not None:
        # Registration cannot be silent (the user needs to know why it failed),
        # but the rate limiter caps how fast this can be used to probe.
        raise ConflictError(
            "An account with this email already exists",
            code="EMAIL_ALREADY_REGISTERED",
            details={"field": "email"},
        )

    # The very first account in an organization becomes its administrator.
    member_count = await db.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == organization.id
        )
    )
    default_role = Role(settings_blob.get("default_member_role", Role.USER.value))
    role = Role.ADMIN if not member_count else default_role

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        system_role=Role.USER,
        status=UserStatus.ACTIVE,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role=role,
        is_default=True,
    )
    db.add(membership)
    await db.flush()
    membership.organization = organization

    issued = await issue_session(db, user, request, membership=membership)
    user.last_login_at = utcnow()

    await audit_service.record(
        db,
        action=AuditAction.USER_REGISTERED,
        actor_id=user.id,
        actor_email=user.email,
        organization_id=organization.id,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        metadata={"role": role.value},
        request=request,
    )
    security_logger.info("user_registered", extra={"user_id": str(user.id)})
    return issued


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
async def login(db: AsyncSession, payload: LoginRequest, request: Request) -> IssuedSession:
    ip = client_ip(request)
    await bruteforce.assert_not_locked(payload.email, f"ip:{ip}")
    await bruteforce.apply_progressive_delay(payload.email)

    user = await get_user_by_email(db, payload.email)
    password_ok = verify_password(payload.password, user.password_hash if user else None)

    if not user or not password_ok:
        await bruteforce.register_failure(payload.email, f"ip:{ip}")
        security_logger.warning(
            "login_failed",
            extra={"reason": "invalid_credentials", "user_exists": bool(user)},
        )
        if user is not None:
            await audit_service.record(
                db,
                action=AuditAction.LOGIN_FAILED,
                actor_id=user.id,
                actor_email=user.email,
                resource_type=ResourceType.USER,
                resource_id=user.id,
                metadata={"reason": "invalid_password"},
                request=request,
            )
            await db.commit()
        # Identical response whether or not the account exists.
        raise InvalidCredentialsError()

    if user.status is UserStatus.SUSPENDED:
        security_logger.warning("login_blocked_suspended", extra={"user_id": str(user.id)})
        raise PermissionDeniedError(
            "This account has been suspended. Contact your organization administrator.",
            code="ACCOUNT_SUSPENDED",
        )
    if user.status is UserStatus.DELETED:
        raise InvalidCredentialsError()

    # Transparently upgrade hashes when the Argon2 parameters are raised.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    await bruteforce.clear_failures(payload.email, f"ip:{ip}")

    membership = await primary_membership(db, user.id)
    issued = await issue_session(db, user, request, membership=membership)
    user.last_login_at = utcnow()

    await audit_service.record(
        db,
        action=AuditAction.LOGIN_SUCCEEDED,
        actor_id=user.id,
        actor_email=user.email,
        organization_id=membership.organization_id if membership else None,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        request=request,
    )
    security_logger.info("login_succeeded", extra={"user_id": str(user.id)})
    return issued


# ---------------------------------------------------------------------------
# Refresh with rotation + reuse detection
# ---------------------------------------------------------------------------
async def refresh(db: AsyncSession, raw_token: str, request: Request) -> IssuedSession:
    claims = decode_refresh_token(raw_token)
    presented = hash_token(raw_token)

    session = await db.get(UserSession, claims.session_id)
    if session is None or session.user_id != claims.user_id:
        security_logger.warning("refresh_unknown_session")
        raise TokenError("Session is no longer valid")

    if session.revoked_at is not None:
        security_logger.warning(
            "refresh_revoked_session", extra={"session_id": str(session.id)}
        )
        raise TokenError("Session is no longer valid")

    if (as_utc(session.expires_at) or utcnow()) <= utcnow():
        raise TokenError("Session has expired", code="TOKEN_EXPIRED")

    if presented != session.token_hash:
        rotated_at = as_utc(session.last_used_at)
        within_grace = (
            rotated_at is not None
            and (utcnow() - rotated_at).total_seconds() <= REFRESH_ROTATION_GRACE_SECONDS
        )

        if (
            session.previous_token_hash
            and presented == session.previous_token_hash
            and within_grace
        ):
            # Two requests raced with the same cookie — a second tab opening, or
            # a retry after a dropped response. Inside the grace window this is
            # benign, so rotate normally instead of destroying the session.
            security_logger.info(
                "refresh_token_grace_retry", extra={"session_id": str(session.id)}
            )
        elif session.previous_token_hash and presented == session.previous_token_hash:
            # The same token came back long after it was rotated away: assume
            # theft and kill the whole family, not just this request.
            await revoke_all_sessions(db, session.user_id, reason="token_reuse")
            security_logger.error(
                "refresh_token_reuse_detected",
                extra={"user_id": str(session.user_id), "session_id": str(session.id)},
            )
            await audit_service.record(
                db,
                action=AuditAction.TOKEN_REUSE_DETECTED,
                actor_id=session.user_id,
                resource_type=ResourceType.SESSION,
                resource_id=session.id,
                request=request,
            )
            await db.commit()
            raise TokenError(
                "Your session was ended for security reasons. Please sign in again.",
                code="SESSION_REVOKED",
            )
        else:
            security_logger.warning("refresh_token_mismatch")
            raise TokenError("Session is no longer valid")

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise TokenError("Session is no longer valid")

    # A password change or forced sign-out invalidates tokens issued earlier.
    valid_after = as_utc(user.tokens_valid_after)
    if valid_after and claims.issued_at < valid_after:
        raise TokenError("Session is no longer valid", code="SESSION_REVOKED")

    membership = await primary_membership(db, user.id)

    new_refresh, refresh_expires_at = create_refresh_token(
        user_id=user.id, session_id=session.id
    )
    access_token, access_expires_at = create_access_token(
        user_id=user.id,
        session_id=session.id,
        system_role=user.system_role.value,
        organization_id=membership.organization_id if membership else None,
        organization_role=membership.role.value if membership else None,
    )

    session.previous_token_hash = session.token_hash
    session.token_hash = hash_token(new_refresh)
    session.last_used_at = utcnow()
    # Sliding expiry, capped at the configured maximum lifetime.
    absolute_deadline = (as_utc(session.created_at) or utcnow()) + timedelta(
        days=settings.REFRESH_TOKEN_TTL_DAYS * 2
    )
    session.expires_at = min(refresh_expires_at, absolute_deadline)

    return IssuedSession(
        user=user,
        session=session,
        access_token=access_token,
        access_expires_at=access_expires_at,
        refresh_token=new_refresh,
        refresh_expires_at=session.expires_at,
        csrf_token=generate_csrf_token(),
    )


# ---------------------------------------------------------------------------
# Logout / session management
# ---------------------------------------------------------------------------
async def _mark_revoked_in_cache(session_id: uuid.UUID) -> None:
    """Mirror the revocation into Redis.

    Access tokens are stateless, so without this an already-issued token would
    keep working until it expired. The TTL only needs to outlive the longest
    possible access token.
    """
    try:
        await get_redis().set(
            RedisKeys.revoked_session(str(session_id)),
            "1",
            ex=settings.access_token_ttl_seconds + 60,
        )
    except Exception as exc:  # noqa: BLE001 - the DB row is still authoritative
        security_logger.error("session_revocation_cache_failed", extra={"error": str(exc)})


async def revoke_session(
    db: AsyncSession, session_id: uuid.UUID, *, reason: str = "logout"
) -> None:
    session = await db.get(UserSession, session_id)
    if session and session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoked_reason = reason
    await _mark_revoked_in_cache(session_id)


async def revoke_all_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    reason: str = "logout_all",
    keep_session_id: uuid.UUID | None = None,
) -> int:
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
    )
    revoked = 0
    for session in result.scalars():
        if keep_session_id and session.id == keep_session_id:
            continue
        session.revoked_at = utcnow()
        session.revoked_reason = reason
        await _mark_revoked_in_cache(session.id)
        revoked += 1
    return revoked


async def list_sessions(db: AsyncSession, user_id: uuid.UUID) -> list[UserSession]:
    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utcnow(),
        )
        .order_by(UserSession.last_used_at.desc().nullslast())
        .limit(50)
    )
    return list(result.scalars())


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
async def request_password_reset(db: AsyncSession, email: str, request: Request) -> None:
    """Always completes successfully — the response must not reveal whether the
    address is registered."""
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        security_logger.info("password_reset_requested_unknown_account")
        return

    # Any outstanding token is invalidated so only the newest link works.
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.invalidated.is_(False),
        )
    )
    for token in result.scalars():
        token.invalidated = True

    raw_token = generate_token(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        )
    )

    await audit_service.record(
        db,
        action=AuditAction.PASSWORD_RESET_REQUESTED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        request=request,
    )
    await email_service.send_password_reset(user.email, raw_token, user.full_name)
    security_logger.info("password_reset_requested", extra={"user_id": str(user.id)})


async def reset_password(
    db: AsyncSession, raw_token: str, new_password: str, request: Request
) -> None:
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(raw_token)
        )
    )
    token = result.scalar_one_or_none()

    if (
        token is None
        or token.invalidated
        or token.used_at is not None
        or (as_utc(token.expires_at) or utcnow()) <= utcnow()
    ):
        security_logger.warning("password_reset_invalid_token")
        raise ValidationError(
            "This reset link is invalid or has expired. Request a new one.",
            code="INVALID_RESET_TOKEN",
        )

    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise ValidationError(
            "This reset link is invalid or has expired. Request a new one.",
            code="INVALID_RESET_TOKEN",
        )

    validate_password_strength(new_password, email=user.email, full_name=user.full_name)

    user.password_hash = hash_password(new_password)
    # Everything issued before now stops working — including any session the
    # attacker may already hold.
    user.tokens_valid_after = utcnow()
    token.used_at = utcnow()
    await revoke_all_sessions(db, user.id, reason="password_reset")

    await audit_service.record(
        db,
        action=AuditAction.PASSWORD_RESET_COMPLETED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        request=request,
    )
    await email_service.send_password_changed(user.email, user.full_name)
    security_logger.info("password_reset_completed", extra={"user_id": str(user.id)})


async def change_password(
    db: AsyncSession,
    user: User,
    payload: ChangePasswordRequest,
    current_session_id: uuid.UUID,
    request: Request,
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        security_logger.warning(
            "password_change_wrong_current", extra={"user_id": str(user.id)}
        )
        raise ValidationError(
            "Your current password is incorrect",
            code="INVALID_CREDENTIALS",
            details={"field": "current_password"},
        )
    if payload.current_password == payload.new_password:
        raise ValidationError(
            "Choose a password different from your current one",
            details={"field": "new_password"},
        )

    validate_password_strength(
        payload.new_password, email=user.email, full_name=user.full_name
    )
    user.password_hash = hash_password(payload.new_password)

    if payload.revoke_other_sessions:
        await revoke_all_sessions(
            db, user.id, reason="password_change", keep_session_id=current_session_id
        )

    await audit_service.record(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        metadata={"revoked_other_sessions": payload.revoke_other_sessions},
        request=request,
    )
    await email_service.send_password_changed(user.email, user.full_name)


async def purge_expired_tokens(db: AsyncSession) -> int:
    """Housekeeping for expired sessions and reset tokens."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
    sessions = await db.execute(
        select(UserSession).where(UserSession.expires_at < cutoff).limit(1000)
    )
    removed = 0
    for session in sessions.scalars():
        await db.delete(session)
        removed += 1

    tokens = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.expires_at < cutoff).limit(1000)
    )
    for token in tokens.scalars():
        await db.delete(token)
        removed += 1
    return removed
