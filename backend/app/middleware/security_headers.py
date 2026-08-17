"""Security response headers.

The API serves JSON, redirects and images — never HTML that a browser should
execute — so the policy is deliberately close to "deny everything". The two
exceptions are the interactive API docs (development only) and the media route.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# Locked-down default for API responses.
API_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "img-src 'self' data: blob:; "
    "sandbox"
)

# Swagger UI / ReDoc need their bundles and inline bootstrap script.
DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)

MEDIA_CSP = (
    "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; "
    "frame-ancestors 'none'; base-uri 'none'; sandbox"
)

PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), usb=(), "
    "interest-cohort=(), browsing-topics=()"
)

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        path = request.url.path

        if path.startswith(_DOCS_PATHS):
            csp = DOCS_CSP
        elif path.startswith("/media"):
            csp = MEDIA_CSP
        else:
            csp = API_CSP

        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        # Never let a proxy or browser cache an authenticated API response.
        if path.startswith(settings.API_V1_PREFIX) and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"

        # HSTS is only meaningful over TLS and would be ignored (or harmful in
        # development) otherwise.
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )

        # Reduce server fingerprinting.
        if "server" in response.headers:
            del response.headers["server"]
        return response
