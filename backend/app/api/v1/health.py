"""Liveness and readiness probes.

`/health` answers "is the process up?" and is safe to expose. `/ready` answers
"can it serve traffic?" and checks its dependencies — but reports only booleans,
never hostnames, versions, connection strings or error text.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.redis import redis_healthy
from app.db.session import database_healthy

router = APIRouter(tags=["Health"])

_STARTED_AT = time.monotonic()


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
    }


@router.get("/ready", summary="Readiness probe")
async def ready(response: Response) -> dict:
    database_ok = await database_healthy()
    redis_ok = await redis_healthy()
    ready_now = database_ok and redis_ok

    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if ready_now else "degraded",
        "checks": {"database": database_ok, "redis": redis_ok},
    }
