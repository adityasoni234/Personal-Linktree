"""Auth cookie handling.

Two cookies are used:

    lh_refresh  HttpOnly, Secure, SameSite — the refresh token. JavaScript can
                never read it, which is what makes XSS unable to steal a
                long-lived credential.
    lh_csrf     readable by JavaScript on purpose: the frontend echoes it in the
                X-CSRF-Token header, completing the double-submit check.

The access token is deliberately *not* a cookie: it travels in the Authorization
header and lives only in the frontend's memory.
"""

from __future__ import annotations

from fastapi import Response

from app.core.config import settings

# The refresh cookie is only ever sent to the auth endpoints that need it.
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"


def set_auth_cookies(response: Response, *, refresh_token: str, csrf_token: str,
                     max_age: int | None = None) -> None:
    max_age = max_age or settings.refresh_token_ttl_seconds

    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        # Intentionally readable: the frontend must copy it into a header.
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
    )
