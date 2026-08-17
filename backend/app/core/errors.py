"""Centralised error taxonomy and exception handlers.

Every error leaves the API in one shape:

    {"success": false, "error": {"code": "...", "message": "...", "details": ...}}

Internal details (stack traces, SQL, filesystem paths) never cross the boundary
in production.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import app_logger, request_id_ctx


class AppError(Exception):
    """Base class for every error the application raises deliberately."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    message: str = "Request could not be processed"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        self.headers = headers or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        if request_id := request_id_ctx.get():
            error["request_id"] = request_id
        return {"success": False, "error": error}


class ValidationError(AppError):
    status_code = 422  # literal: the Starlette constant name changed across versions
    code = "VALIDATION_ERROR"
    message = "The submitted data is invalid"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "NOT_AUTHENTICATED"
    message = "Authentication required"


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"


class TokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_TOKEN"
    message = "Token is invalid or has expired"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action"


class CSRFError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "CSRF_FAILED"
    message = "CSRF verification failed"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "RESOURCE_NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "RESOURCE_CONFLICT"
    message = "Resource already exists"


class PayloadTooLargeError(AppError):
    status_code = 413  # literal: the Starlette constant name changed across versions
    code = "PAYLOAD_TOO_LARGE"
    message = "Uploaded file is too large"


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "UNSUPPORTED_MEDIA_TYPE"
    message = "Unsupported file type"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please slow down and try again shortly."


class AccountLockedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "ACCOUNT_TEMPORARILY_LOCKED"
    message = "Too many failed attempts. Please try again later."


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"
    message = "Service temporarily unavailable"


_HTTP_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "RESOURCE_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "RESOURCE_CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    if request_id := request_id_ctx.get():
        error["request_id"] = request_id
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": error},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            app_logger.error("app_error", extra={"code": exc.code}, exc_info=exc)
        return _error_response(
            exc.status_code,
            exc.code,
            exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or "body",
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        return _error_response(
            422,
            "VALIDATION_ERROR",
            "The submitted data is invalid",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
        message = (
            exc.detail if isinstance(exc.detail, str) else "Request could not be processed"
        )
        return _error_response(
            exc.status_code, code, message, headers=dict(exc.headers or {})
        )

    @app.exception_handler(SQLAlchemyError)
    async def _database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        # The driver message can contain schema and connection details — log it,
        # never return it.
        app_logger.error("database_error", exc_info=exc)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred",
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        app_logger.error("unhandled_exception", exc_info=exc)
        message = "An unexpected error occurred"
        details = None
        if not settings.is_production and settings.DEBUG:
            details = {"exception": type(exc).__name__, "detail": str(exc)}
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            message,
            details=details,
        )
