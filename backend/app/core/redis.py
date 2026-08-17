"""Redis client lifecycle.

A single connection pool is shared by rate limiting, session/refresh-token
revocation, analytics de-duplication and QR asset caching.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import app_logger

_client: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
        await _client.ping()
        app_logger.info("redis_connected")
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        app_logger.info("redis_closed")


def get_redis() -> aioredis.Redis:
    if _client is None:  # pragma: no cover - guarded by app lifespan
        raise RuntimeError("Redis is not initialised; call init_redis() first")
    return _client


def set_redis(client: Any) -> None:
    """Test hook — allows injecting a fake Redis implementation."""
    global _client
    _client = client


async def redis_healthy() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:  # noqa: BLE001 - health probe must never raise
        return False


class RedisKeys:
    """Namespaced key builders. Keeping them in one place avoids collisions."""

    @staticmethod
    def rate_limit(scope: str, identity: str, window: int) -> str:
        return f"rl:{scope}:{identity}:{window}"

    @staticmethod
    def login_failures(identity: str) -> str:
        return f"auth:fail:{identity}"

    @staticmethod
    def login_lockout(identity: str) -> str:
        return f"auth:lock:{identity}"

    @staticmethod
    def revoked_session(session_id: str) -> str:
        return f"auth:revoked:{session_id}"

    @staticmethod
    def analytics_dedupe(kind: str, target: str, fingerprint: str) -> str:
        return f"an:dedupe:{kind}:{target}:{fingerprint}"

    @staticmethod
    def qr_asset(config_hash: str, fmt: str) -> str:
        return f"qr:asset:{config_hash}:{fmt}"

    @staticmethod
    def public_group(slug: str) -> str:
        return f"pub:group:{slug}"
