"""CSRF protection for the cookie-authenticated endpoints.

Most of the API authenticates with a bearer token in the `Authorization`
header, which browsers never attach automatically and is therefore not
CSRF-reachable. The refresh and logout endpoints *do* rely on the refresh
cookie, so they are protected with a signed double-submit token:

    * a random value is stored in a JS-readable cookie (`lh_csrf`);
    * the same value must be echoed in the `X-CSRF-Token` header;
    * the value carries an HMAC so a forged cookie from a sibling subdomain
      cannot be minted.
"""

from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from fastapi import Request

from app.core.config import settings
from app.core.errors import CSRFError
from app.core.logging import security_logger

_SEPARATOR = "."


def _sign(nonce: str) -> str:
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"), nonce.encode("utf-8"), sha256
    ).hexdigest()


def generate_csrf_token() -> str:
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}{_SEPARATOR}{_sign(nonce)}"


def is_valid_csrf_token(token: str | None) -> bool:
    if not token or _SEPARATOR not in token:
        return False
    nonce, _, signature = token.partition(_SEPARATOR)
    if not nonce or not signature:
        return False
    return hmac.compare_digest(signature, _sign(nonce))


def verify_csrf(request: Request) -> None:
    """Raise `CSRFError` unless the cookie and header agree on a signed token."""
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    header_token = request.headers.get(settings.CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        security_logger.warning(
            "csrf_token_missing",
            extra={"path": request.url.path, "has_cookie": bool(cookie_token)},
        )
        raise CSRFError("Missing CSRF token")

    if not hmac.compare_digest(cookie_token, header_token):
        security_logger.warning("csrf_token_mismatch", extra={"path": request.url.path})
        raise CSRFError("CSRF token mismatch")

    if not is_valid_csrf_token(cookie_token):
        security_logger.warning("csrf_token_invalid", extra={"path": request.url.path})
        raise CSRFError("CSRF token is not valid")
