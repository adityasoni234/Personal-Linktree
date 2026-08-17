"""Authentication endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.api.deps import CurrentAuth, DbSession, require_csrf_token
from app.core.config import settings
from app.core.errors import NotFoundError, TokenError
from app.core.rate_limit import Policies, enforce, rate_limit
from app.db.base import utcnow
from app.models.enums import AuditAction, ResourceType
from app.schemas.admin import ProfileUpdate
from app.schemas.auth import (
    AuthSession,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionInfo,
    UserProfile,
)
from app.schemas.common import Message, Success
from app.security.tokens import decode_refresh_token
from app.services import audit_service, auth_service, user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _session_payload(issued: auth_service.IssuedSession, membership) -> AuthSession:
    return AuthSession(
        access_token=issued.access_token,
        expires_in=settings.access_token_ttl_seconds,
        expires_at=issued.access_expires_at,
        csrf_token=issued.csrf_token,
        user=auth_service.build_profile(issued.user, membership),
    )


def _attach_session(response: Response, issued: auth_service.IssuedSession) -> None:
    set_auth_cookies(
        response,
        refresh_token=issued.refresh_token,
        csrf_token=issued.csrf_token,
    )


@router.post(
    "/register",
    response_model=Success[AuthSession],
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> Success[AuthSession]:
    await enforce([Policies.REGISTER], request)

    issued = await auth_service.register(db, payload, request)
    await db.commit()

    membership = await auth_service.primary_membership(db, issued.user.id)
    _attach_session(response, issued)
    return Success(data=_session_payload(issued, membership))


@router.post("/login", response_model=Success[AuthSession], summary="Sign in")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> Success[AuthSession]:
    # Two limits on purpose: per IP (stops one host hammering many accounts) and
    # per submitted email (stops a botnet hammering one account).
    await enforce(
        [Policies.LOGIN_IP, Policies.LOGIN_ACCOUNT], request, identity=payload.email
    )

    issued = await auth_service.login(db, payload, request)
    await db.commit()

    membership = await auth_service.primary_membership(db, issued.user.id)
    _attach_session(response, issued)
    return Success(data=_session_payload(issued, membership))


@router.post(
    "/refresh",
    response_model=Success[AuthSession],
    dependencies=[Depends(rate_limit(Policies.REFRESH)), Depends(require_csrf_token)],
    summary="Exchange the refresh cookie for a new access token",
)
async def refresh(
    request: Request, response: Response, db: DbSession
) -> Success[AuthSession]:
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token:
        raise TokenError("No active session", code="NO_SESSION")

    try:
        issued = await auth_service.refresh(db, raw_token, request)
    except TokenError:
        # A dead session should not leave a stale cookie behind to retry with.
        clear_auth_cookies(response)
        raise

    await db.commit()
    membership = await auth_service.primary_membership(db, issued.user.id)
    _attach_session(response, issued)
    return Success(data=_session_payload(issued, membership))


@router.post(
    "/logout",
    response_model=Message,
    dependencies=[Depends(require_csrf_token)],
    summary="Sign out of this device",
)
async def logout(request: Request, response: Response, db: DbSession) -> Message:
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw_token:
        try:
            claims = decode_refresh_token(raw_token)
            await auth_service.revoke_session(db, claims.session_id, reason="logout")
            await audit_service.record(
                db,
                action=AuditAction.LOGOUT,
                actor_id=claims.user_id,
                resource_type=ResourceType.SESSION,
                resource_id=claims.session_id,
                request=request,
            )
            await db.commit()
        except TokenError:
            # Already expired or tampered with: clearing the cookie is enough.
            pass

    clear_auth_cookies(response)
    return Message(message="Signed out")


@router.post("/logout-all", response_model=Message, summary="Sign out everywhere")
async def logout_all(
    auth: CurrentAuth, request: Request, response: Response, db: DbSession
) -> Message:
    revoked = await auth_service.revoke_all_sessions(
        db, auth.user.id, reason="logout_all"
    )
    auth.user.tokens_valid_after = utcnow()
    await audit_service.record(
        db,
        action=AuditAction.LOGOUT,
        actor_id=auth.user.id,
        actor_email=auth.user.email,
        resource_type=ResourceType.SESSION,
        metadata={"revoked_sessions": revoked},
        request=request,
    )
    await db.commit()

    clear_auth_cookies(response)
    return Message(message=f"Signed out of {revoked} device(s)")


@router.get("/me", response_model=Success[UserProfile], summary="Current user")
async def me(auth: CurrentAuth) -> Success[UserProfile]:
    return Success(data=auth_service.build_profile(auth.user, auth.membership))


@router.patch("/me", response_model=Success[UserProfile], summary="Update your profile")
async def update_me(
    payload: ProfileUpdate, auth: CurrentAuth, request: Request, db: DbSession
) -> Success[UserProfile]:
    await user_service.update_profile(db, auth.user, payload, request)
    await db.commit()
    return Success(data=auth_service.build_profile(auth.user, auth.membership))


@router.post(
    "/forgot-password",
    response_model=Message,
    summary="Request a password reset link",
)
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: DbSession
) -> Message:
    await enforce(
        [Policies.FORGOT_PASSWORD_IP, Policies.FORGOT_PASSWORD_ACCOUNT],
        request,
        identity=payload.email,
    )

    await auth_service.request_password_reset(db, payload.email, request)
    await db.commit()

    # Always the same response: revealing whether an address is registered would
    # turn this endpoint into an account-enumeration oracle.
    return Message(
        message="If an account exists for that address, we have sent reset instructions."
    )


@router.post("/reset-password", response_model=Message, summary="Set a new password")
async def reset_password(
    payload: ResetPasswordRequest, request: Request, response: Response, db: DbSession
) -> Message:
    await enforce([Policies.RESET_PASSWORD], request)

    await auth_service.reset_password(db, payload.token, payload.new_password, request)
    await db.commit()

    clear_auth_cookies(response)
    return Message(message="Your password has been reset. Please sign in.")


@router.post(
    "/change-password",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.CHANGE_PASSWORD))],
    summary="Change your password",
)
async def change_password(
    payload: ChangePasswordRequest, auth: CurrentAuth, request: Request, db: DbSession
) -> Message:
    await auth_service.change_password(
        db, auth.user, payload, auth.principal.session_id, request
    )
    await db.commit()
    return Message(message="Your password has been changed")


@router.get(
    "/sessions",
    response_model=Success[list[SessionInfo]],
    summary="List your active sessions",
)
async def list_sessions(auth: CurrentAuth, db: DbSession) -> Success[list[SessionInfo]]:
    sessions = await auth_service.list_sessions(db, auth.user.id)
    return Success(
        data=[
            SessionInfo(
                id=session.id,
                created_at=session.created_at,
                last_used_at=session.last_used_at,
                expires_at=session.expires_at,
                user_agent_label=session.user_agent_label,
                is_current=session.id == auth.principal.session_id,
            )
            for session in sessions
        ]
    )


@router.delete(
    "/sessions/{session_id}", response_model=Message, summary="Revoke a session"
)
async def revoke_session(
    session_id: uuid.UUID, auth: CurrentAuth, request: Request, db: DbSession
) -> Message:
    sessions = await auth_service.list_sessions(db, auth.user.id)
    # Only your own sessions are revocable, and the id must be one you own.
    if not any(session.id == session_id for session in sessions):
        raise NotFoundError("Session not found")

    await auth_service.revoke_session(db, session_id, reason="revoked_by_user")
    await audit_service.record(
        db,
        action=AuditAction.SESSION_REVOKED,
        actor_id=auth.user.id,
        actor_email=auth.user.email,
        resource_type=ResourceType.SESSION,
        resource_id=session_id,
        request=request,
    )
    await db.commit()
    return Message(message="Session revoked")
