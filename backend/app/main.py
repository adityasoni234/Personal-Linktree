"""Application factory and ASGI entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import app_logger, configure_logging
from app.core.redis import close_redis, init_redis
from app.db.session import dispose_engine
from app.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

DESCRIPTION = """
Secure link-hub and dynamic QR platform for IEEE SOU.

**Authentication** — send the short-lived access token as `Authorization: Bearer <token>`.
The refresh token lives in an HttpOnly cookie and is rotated on every use; the
`/auth/refresh` and `/auth/logout` endpoints additionally require the
`X-CSRF-Token` header to match the `lh_csrf` cookie.

**Responses** — successful responses are `{"success": true, "data": ...}`;
errors are `{"success": false, "error": {"code", "message", "details"}}`.

**Rate limits** — responses carry `X-RateLimit-Limit` and `X-RateLimit-Remaining`;
a `429` includes `Retry-After`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app_logger.info(
        "application_starting",
        extra={"environment": settings.ENVIRONMENT, "version": app.version},
    )

    await init_redis()

    from app.db.bootstrap import run_bootstrap

    try:
        await run_bootstrap()
    except Exception as exc:  # noqa: BLE001 - a bootstrap failure must be visible
        app_logger.error("bootstrap_failed", extra={"error": str(exc)})

    app_logger.info("application_ready")
    try:
        yield
    finally:
        await close_redis()
        await dispose_engine()
        app_logger.info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
        # Interactive docs are development-only: they describe the whole attack
        # surface and have no place on a public production host.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True},
        contact={"name": "IEEE SOU Student Branch"},
        license_info={"name": "MIT"},
    )

    register_exception_handlers(app)

    # Starlette runs middleware in reverse registration order, so the last one
    # added is the outermost. Desired order, outside in:
    #   RequestContext → SecurityHeaders → CORS → BodySizeLimit → routes
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # Explicit allowlist. A wildcard is impossible here: credentials are
        # enabled, and the config layer rejects "*" in production outright.
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            settings.CSRF_HEADER_NAME,
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
        ],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Local media is served by the app only in development; production puts the
    # bucket behind a CDN and never routes uploads through this process.
    if settings.STORAGE_BACKEND == "local":
        media_root = Path(settings.STORAGE_LOCAL_DIR)
        try:
            media_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # A missing media directory must not stop the API from booting; the
            # upload endpoints surface a clear error instead.
            app_logger.warning(
                "media_directory_unavailable",
                extra={"path": str(media_root), "error": str(exc)},
            )
        app.mount(
            "/media",
            StaticFiles(directory=str(media_root), check_dir=False),
            name="media",
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.PROJECT_NAME,
            "version": app.version,
            "docs": "/docs" if not settings.is_production else None,
            "api": settings.API_V1_PREFIX,
        }

    return app


app = create_app()
