"""Request correlation, access logging and response-header plumbing."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import app_logger, request_id_ctx, user_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_INBOUND_REQUEST_ID = 64

# Paths that would otherwise flood the access log.
_QUIET_PATHS = frozenset({"/health", "/ready", "/metrics", "/favicon.ico"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        # An inbound id is echoed for tracing but sanitised — it ends up in logs.
        request_id = (
            inbound[:_MAX_INBOUND_REQUEST_ID]
            if inbound.replace("-", "").isalnum() and inbound
            else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        user_token = user_id_ctx.set(None)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            app_logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)
            user_id_ctx.reset(user_token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        # Rate-limit counters are recorded by the limiter dependency during the
        # request and attached here so they appear on success responses too.
        for header, value in getattr(request.state, "rate_limit_headers", {}).items():
            response.headers.setdefault(header, value)

        if request.url.path not in _QUIET_PATHS:
            level = (
                app_logger.warning if response.status_code >= 400 else app_logger.info
            )
            level(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response
