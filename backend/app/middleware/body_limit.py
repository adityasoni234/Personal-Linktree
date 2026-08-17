"""Request body size ceiling.

Enforced before routing so an oversized upload is rejected at the edge instead
of being buffered into memory by the multipart parser.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import security_logger

# Multipart framing plus the file itself.
_UPLOAD_OVERHEAD_BYTES = 64 * 1024
# JSON endpoints never legitimately need more than this.
_JSON_BODY_LIMIT = 256 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            is_upload = content_type.startswith("multipart/form-data")
            limit = (
                settings.MAX_UPLOAD_BYTES + _UPLOAD_OVERHEAD_BYTES
                if is_upload
                else _JSON_BODY_LIMIT
            )

            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    declared = int(content_length)
                except ValueError:
                    return _too_large(limit, "Invalid Content-Length header")
                if declared > limit:
                    security_logger.warning(
                        "request_body_too_large",
                        extra={"path": request.url.path, "declared_bytes": declared},
                    )
                    return _too_large(limit)
            elif request.headers.get("transfer-encoding", "").lower() == "chunked":
                # No declared length: the route-level readers cap the stream, but
                # reject obviously unsupported chunked uploads up front.
                if is_upload:
                    return _too_large(limit, "Chunked uploads are not supported")

        return await call_next(request)


def _too_large(limit: int, message: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={
            "success": False,
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": message or f"Request body must be smaller than {limit // 1024} KB",
                "details": {"max_bytes": limit},
            },
        },
    )
