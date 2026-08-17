"""Redis-backed rate limiting.

A sliding-window log implemented as a single Lua script, so the check and the
increment are atomic across every worker process — an in-memory limiter would
reset on redeploy and be trivially bypassed by hitting a different worker.

Policies compose: an endpoint can enforce a per-IP *and* a per-user limit at the
same time, which is what stops an attacker from bypassing a per-account limit by
cycling through usernames.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitError
from app.core.logging import security_logger
from app.core.redis import RedisKeys, get_redis

# KEYS[1] = bucket key
# ARGV = now_ms, window_ms, limit, member
_SLIDING_WINDOW_LUA = """
local key    = KEYS[1]
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local used = redis.call('ZCARD', key)

if used < limit then
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, window)
  return {1, limit - used - 1, 0}
end

local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry_after = window
if oldest[2] then
  retry_after = window - (now - tonumber(oldest[2]))
end
if retry_after < 1 then retry_after = 1 end
return {0, 0, retry_after}
"""

_script_sha: str | None = None
# Set when the Redis implementation has no scripting support (some managed
# proxies and the in-memory test double); the pipeline fallback is used instead.
_scripting_unavailable = False


class KeyBy(str, Enum):
    IP = "ip"
    USER = "user"
    USER_OR_IP = "user_or_ip"
    IDENTITY = "identity"  # caller-supplied value, e.g. the submitted email


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: int
    key_by: KeyBy = KeyBy.IP
    # Authentication endpoints fail *closed* if Redis is unreachable: losing the
    # limiter there would open the door to unbounded credential stuffing.
    fail_open: bool = True

    @property
    def description(self) -> str:
        return f"{self.limit} requests per {self.window_seconds}s"


# ---------------------------------------------------------------------------
# Endpoint policies
# ---------------------------------------------------------------------------
class Policies:
    LOGIN_IP = RateLimitPolicy("login:ip", 5, 60, KeyBy.IP, fail_open=False)
    LOGIN_ACCOUNT = RateLimitPolicy("login:account", 10, 900, KeyBy.IDENTITY, fail_open=False)
    REGISTER = RateLimitPolicy("register:ip", 5, 3600, KeyBy.IP, fail_open=False)
    FORGOT_PASSWORD_IP = RateLimitPolicy("forgot:ip", 3, 900, KeyBy.IP, fail_open=False)
    FORGOT_PASSWORD_ACCOUNT = RateLimitPolicy(
        "forgot:account", 3, 3600, KeyBy.IDENTITY, fail_open=False
    )
    RESET_PASSWORD = RateLimitPolicy("reset:ip", 5, 900, KeyBy.IP, fail_open=False)
    REFRESH = RateLimitPolicy("refresh:ip", 60, 300, KeyBy.IP)
    CHANGE_PASSWORD = RateLimitPolicy("password:user", 5, 900, KeyBy.USER, fail_open=False)

    API_USER = RateLimitPolicy("api:user", 100, 60, KeyBy.USER_OR_IP)
    WRITE_USER = RateLimitPolicy("write:user", 60, 60, KeyBy.USER_OR_IP)
    QR_RENDER = RateLimitPolicy("qr:user", 30, 60, KeyBy.USER_OR_IP)
    MEDIA_UPLOAD = RateLimitPolicy("upload:user", 20, 300, KeyBy.USER_OR_IP)

    PUBLIC_PAGE = RateLimitPolicy("public:ip", 120, 60, KeyBy.IP)
    PUBLIC_QR = RateLimitPolicy("public-qr:ip", 30, 60, KeyBy.IP)
    ANALYTICS_INGEST = RateLimitPolicy("analytics:ip", 60, 60, KeyBy.IP)
    ANALYTICS_READ = RateLimitPolicy("analytics-read:user", 60, 60, KeyBy.USER_OR_IP)


def client_ip(request: Request) -> str:
    """Resolve the caller's IP.

    `X-Forwarded-For` is only honoured because the deployment terminates TLS at a
    reverse proxy that overwrites the header (see `nginx.conf`). The *left-most*
    entry is taken but the value is length-capped so a spoofed header cannot be
    used to explode the Redis keyspace.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:45]
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()[:45]
    return request.client.host if request.client else "unknown"


def _current_user_id(request: Request) -> str | None:
    """Best-effort user id for keying, without a database round-trip."""
    if (principal := getattr(request.state, "principal", None)) is not None:
        return str(principal.user_id)
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    from app.core.errors import TokenError
    from app.security.tokens import decode_access_token

    try:
        return str(decode_access_token(header[7:].strip()).user_id)
    except TokenError:
        return None


def _resolve_identity(policy: RateLimitPolicy, request: Request,
                      identity: str | None) -> str:
    if policy.key_by is KeyBy.IP:
        return f"ip:{client_ip(request)}"
    if policy.key_by is KeyBy.IDENTITY:
        return f"id:{(identity or 'anonymous')[:128]}"
    user_id = _current_user_id(request)
    if policy.key_by is KeyBy.USER:
        return f"user:{user_id or 'anonymous'}"
    return f"user:{user_id}" if user_id else f"ip:{client_ip(request)}"


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


async def _check_with_pipeline(
    redis, key: str, now_ms: int, window_ms: int, limit: int
) -> list[int]:
    """Scripting-free fallback.

    A MULTI/EXEC pipeline is still atomic, so the window cannot be corrupted by
    concurrent requests. The difference from the Lua version is that a rejected
    attempt also lands in the window — deliberately stricter, since an abusive
    client should not get a fresh allowance by hammering.
    """
    async with redis.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, now_ms - window_ms)
        pipe.zadd(key, {uuid.uuid4().hex: now_ms})
        pipe.zcard(key)
        pipe.pexpire(key, window_ms)
        pipe.zrange(key, 0, 0, withscores=True)
        results = await pipe.execute()

    used = int(results[2])
    if used <= limit:
        return [1, limit - used, 0]

    oldest = results[4]
    retry_after_ms = window_ms
    if oldest:
        retry_after_ms = max(1, window_ms - (now_ms - int(oldest[0][1])))
    return [0, 0, retry_after_ms]


async def check_rate_limit(
    policy: RateLimitPolicy,
    request: Request,
    *,
    identity: str | None = None,
) -> RateLimitResult:
    """Consume one token from the policy's bucket."""
    if not settings.RATE_LIMIT_ENABLED:
        return RateLimitResult(True, policy.limit, policy.limit, 0)

    global _script_sha, _scripting_unavailable
    key = RedisKeys.rate_limit(
        policy.name, _resolve_identity(policy, request, identity), policy.window_seconds
    )
    now_ms = int(time.time() * 1000)
    window_ms = policy.window_seconds * 1000

    try:
        redis = get_redis()
        if _scripting_unavailable:
            raw = await _check_with_pipeline(redis, key, now_ms, window_ms, policy.limit)
        else:
            try:
                if _script_sha is None:
                    _script_sha = await redis.script_load(_SLIDING_WINDOW_LUA)
                raw = await redis.evalsha(
                    _script_sha, 1, key, now_ms, window_ms, policy.limit, uuid.uuid4().hex
                )
            except (ConnectionError, TimeoutError, OSError):
                raise
            except Exception as exc:  # noqa: BLE001
                message = str(exc).upper()
                if "NOSCRIPT" in message:
                    # Redis restarted and dropped its script cache.
                    _script_sha = await redis.script_load(_SLIDING_WINDOW_LUA)
                    raw = await redis.evalsha(
                        _script_sha, 1, key, now_ms, window_ms, policy.limit,
                        uuid.uuid4().hex,
                    )
                else:
                    security_logger.warning(
                        "rate_limit_scripting_unavailable", extra={"error": str(exc)}
                    )
                    _scripting_unavailable = True
                    raw = await _check_with_pipeline(
                        redis, key, now_ms, window_ms, policy.limit
                    )
    except RateLimitError:
        raise
    except Exception as exc:  # noqa: BLE001 - Redis outage
        security_logger.error(
            "rate_limit_backend_unavailable",
            extra={"policy": policy.name, "fail_open": policy.fail_open, "error": str(exc)},
        )
        if policy.fail_open:
            return RateLimitResult(True, policy.limit, policy.limit, 0)
        raise RateLimitError(
            "Service is temporarily unable to verify request limits. Please retry shortly.",
            headers={"Retry-After": "30"},
        ) from exc

    allowed, remaining, retry_after_ms = (int(raw[0]), int(raw[1]), int(raw[2]))
    return RateLimitResult(
        allowed=bool(allowed),
        limit=policy.limit,
        remaining=remaining,
        retry_after_seconds=max(1, -(-retry_after_ms // 1000)) if not allowed else 0,
    )


def _apply_headers(request: Request, policy: RateLimitPolicy,
                   result: RateLimitResult) -> None:
    """Stash headers for `RateLimitHeaderMiddleware` to attach to the response.

    The most constrained policy wins when several apply to one endpoint.
    """
    existing = getattr(request.state, "rate_limit_headers", None)
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(max(0, result.remaining)),
        "X-RateLimit-Policy": f"{policy.limit};w={policy.window_seconds}",
    }
    if existing is None or int(existing.get("X-RateLimit-Remaining", "0")) > result.remaining:
        request.state.rate_limit_headers = headers


async def enforce(
    policies: Sequence[RateLimitPolicy],
    request: Request,
    *,
    identity: str | None = None,
) -> None:
    for policy in policies:
        result = await check_rate_limit(policy, request, identity=identity)
        _apply_headers(request, policy, result)
        if not result.allowed:
            security_logger.warning(
                "rate_limit_exceeded",
                extra={
                    "policy": policy.name,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            raise RateLimitError(
                "Too many requests. Please wait a moment and try again.",
                details={"retry_after_seconds": result.retry_after_seconds},
                headers={
                    "Retry-After": str(result.retry_after_seconds),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )


def rate_limit(*policies: RateLimitPolicy) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency factory.

    Usage:
        @router.post("/groups", dependencies=[Depends(rate_limit(Policies.WRITE_USER))])
    """

    async def dependency(request: Request) -> None:
        await enforce(policies, request)

    return dependency
