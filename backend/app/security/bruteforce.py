"""Brute-force and credential-stuffing protection for the login endpoint.

Layered with (not instead of) rate limiting:

    rate limiting   caps request volume per IP and per account
    this module     tracks *failed* attempts, adds a progressive delay, and
                    temporarily locks the account after repeated failures

Counters are kept per account identifier and per IP, so neither rotating the
email nor rotating the source address defeats the control on its own. Responses
never differ between "no such account" and "wrong password".
"""

from __future__ import annotations

import asyncio
import hashlib

from app.core.config import settings
from app.core.errors import AccountLockedError
from app.core.logging import security_logger
from app.core.redis import RedisKeys, get_redis

# failures -> lockout duration in seconds
LOCKOUT_LADDER: tuple[tuple[int, int], ...] = (
    (5, 60),
    (8, 300),
    (12, 1800),
    (20, 7200),
)
FAILURE_WINDOW_SECONDS = 3600
# Delay starts after this many failures, doubling up to DELAY_CAP.
DELAY_AFTER_FAILURES = 3
DELAY_CAP_SECONDS = 4.0


def _identity_key(value: str) -> str:
    """Hash the identifier so raw emails never sit in Redis."""
    digest = hashlib.sha256(
        f"{settings.ANALYTICS_IP_PEPPER}:{value.strip().lower()}".encode()
    ).hexdigest()
    return digest[:32]


def _lockout_seconds(failures: int) -> int:
    duration = 0
    for threshold, seconds in LOCKOUT_LADDER:
        if failures >= threshold:
            duration = seconds
    return duration


async def assert_not_locked(*identifiers: str) -> None:
    """Raise `AccountLockedError` if any identifier is currently locked out."""
    redis = get_redis()
    for identifier in identifiers:
        if not identifier:
            continue
        key = RedisKeys.login_lockout(_identity_key(identifier))
        try:
            ttl = await redis.ttl(key)
        except Exception as exc:  # noqa: BLE001 - Redis outage
            security_logger.error("bruteforce_backend_unavailable", extra={"error": str(exc)})
            return
        if ttl and ttl > 0:
            security_logger.warning("login_blocked_locked_out", extra={"ttl": ttl})
            raise AccountLockedError(
                "Too many failed sign-in attempts. Please try again later.",
                details={"retry_after_seconds": ttl},
                headers={"Retry-After": str(ttl)},
            )


async def register_failure(*identifiers: str) -> None:
    """Record a failed attempt and lock out once the ladder threshold is hit."""
    redis = get_redis()
    for identifier in identifiers:
        if not identifier:
            continue
        hashed = _identity_key(identifier)
        failure_key = RedisKeys.login_failures(hashed)
        try:
            failures = await redis.incr(failure_key)
            if failures == 1:
                await redis.expire(failure_key, FAILURE_WINDOW_SECONDS)

            lockout = _lockout_seconds(int(failures))
            if lockout:
                await redis.set(RedisKeys.login_lockout(hashed), "1", ex=lockout)
                security_logger.warning(
                    "login_lockout_applied",
                    extra={"failures": int(failures), "lockout_seconds": lockout},
                )
        except Exception as exc:  # noqa: BLE001 - never break login on Redis errors
            security_logger.error("bruteforce_record_failed", extra={"error": str(exc)})


async def clear_failures(*identifiers: str) -> None:
    """Reset counters after a successful sign-in."""
    redis = get_redis()
    for identifier in identifiers:
        if not identifier:
            continue
        hashed = _identity_key(identifier)
        try:
            await redis.delete(
                RedisKeys.login_failures(hashed), RedisKeys.login_lockout(hashed)
            )
        except Exception as exc:  # noqa: BLE001
            security_logger.error("bruteforce_clear_failed", extra={"error": str(exc)})


async def failure_count(identifier: str) -> int:
    try:
        value = await get_redis().get(RedisKeys.login_failures(_identity_key(identifier)))
    except Exception:  # noqa: BLE001
        return 0
    return int(value) if value else 0


async def apply_progressive_delay(identifier: str) -> None:
    """Slow down repeated guessing without blocking a legitimate typo."""
    failures = await failure_count(identifier)
    if failures < DELAY_AFTER_FAILURES:
        return
    delay = min(DELAY_CAP_SECONDS, 0.25 * (2 ** (failures - DELAY_AFTER_FAILURES)))
    await asyncio.sleep(delay)
