"""JWT issuing and verification.

Two independently-signed token families:

    access   short lived (minutes), sent in the Authorization header, held only
             in frontend memory — never in localStorage.
    refresh  long lived (days), delivered in an HttpOnly + Secure + SameSite
             cookie, rotated on every use, and bound to a server-side session
             row so it can be revoked.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.core.config import settings
from app.core.errors import TokenError

TokenKind = Literal["access", "refresh"]

_ISSUER = "linkhub"
_AUDIENCE = "linkhub-api"


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    system_role: str
    organization_id: uuid.UUID | None
    organization_role: str | None
    issued_at: datetime
    expires_at: datetime
    jti: str


@dataclass(frozen=True, slots=True)
class RefreshTokenClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    issued_at: datetime
    expires_at: datetime
    jti: str


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _secret(kind: TokenKind) -> str:
    return settings.JWT_SECRET if kind == "access" else settings.JWT_REFRESH_SECRET


def _encode(kind: TokenKind, subject: str, ttl: timedelta, extra: dict[str, Any]) -> tuple[str, datetime]:
    issued_at = _now()
    expires_at = issued_at + ttl
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(issued_at.timestamp()),
        "nbf": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "typ": kind,
        "jti": uuid.uuid4().hex,
        **extra,
    }
    token = jwt.encode(payload, _secret(kind), algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def _decode(kind: TokenKind, token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            _secret(kind),
            # Pinning the algorithm blocks `alg: none` and HS/RS confusion.
            algorithms=[settings.JWT_ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token is invalid") from exc

    if payload.get("typ") != kind:
        # Prevents a refresh token from being replayed as an access token.
        raise TokenError("Token is not valid for this operation")
    return payload


def create_access_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    system_role: str,
    organization_id: uuid.UUID | None,
    organization_role: str | None,
) -> tuple[str, datetime]:
    return _encode(
        "access",
        str(user_id),
        timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
        {
            "sid": str(session_id),
            "role": system_role,
            "org": str(organization_id) if organization_id else None,
            "org_role": organization_role,
        },
    )


def create_refresh_token(*, user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, datetime]:
    return _encode(
        "refresh",
        str(user_id),
        timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        {"sid": str(session_id)},
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    payload = _decode("access", token)
    try:
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            system_role=payload["role"],
            organization_id=uuid.UUID(payload["org"]) if payload.get("org") else None,
            organization_role=payload.get("org_role"),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            jti=payload["jti"],
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise TokenError("Token payload is malformed") from exc


def decode_refresh_token(token: str) -> RefreshTokenClaims:
    payload = _decode("refresh", token)
    try:
        return RefreshTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            jti=payload["jti"],
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise TokenError("Token payload is malformed") from exc
