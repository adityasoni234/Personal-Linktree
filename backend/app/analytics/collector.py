"""Analytics ingestion.

Trust model: the client can tell us *that* an interaction happened; everything
recorded about it is derived on the server.

  * group and link are resolved from the URL path, not from the request body;
  * the timestamp is the server clock;
  * device, browser and OS come from the User-Agent we received;
  * the referrer is reduced to a bare domain;
  * the visitor is identified by a rotating salted hash that is never reversible.

Bot traffic is classified and dropped, and repeat events from the same visitor
inside a short window are de-duplicated in Redis so counts cannot be inflated by
reloading a page.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.privacy import (
    classify_browser,
    classify_device,
    classify_os,
    country_from_headers,
    hash_ip,
    visitor_fingerprint,
)
from app.core.config import settings
from app.core.logging import app_logger
from app.core.rate_limit import client_ip
from app.core.redis import RedisKeys, get_redis
from app.db.session import session_scope
from app.models.analytics import AnalyticsEvent
from app.models.enums import AnalyticsEventType, DeviceType
from app.security.url_validation import referrer_domain

# Repeat page views from the same visitor inside this window are ignored.
DEDUPE_WINDOWS: dict[AnalyticsEventType, int] = {
    AnalyticsEventType.PAGE_VIEW: 1800,
    AnalyticsEventType.QR_SCAN: 1800,
    AnalyticsEventType.LINK_CLICK: 5,
    AnalyticsEventType.SHARE: 300,
}


async def _is_duplicate(
    event_type: AnalyticsEventType, target: str, fingerprint: str
) -> bool:
    window = DEDUPE_WINDOWS.get(event_type, settings.ANALYTICS_DEDUPE_WINDOW_SECONDS)
    key = RedisKeys.analytics_dedupe(event_type.value, target, fingerprint)
    try:
        # SET NX is atomic: the first request in the window wins, everyone else
        # is a duplicate — no read-then-write race.
        stored = await get_redis().set(key, "1", ex=window, nx=True)
        return not stored
    except Exception as exc:  # noqa: BLE001 - never lose an event to a cache fault
        app_logger.warning("analytics_dedupe_unavailable", extra={"error": str(exc)})
        return False


def _extract_context(request: Request) -> dict:
    user_agent = request.headers.get("user-agent")
    return {
        "user_agent": user_agent,
        "device_type": classify_device(user_agent),
        "browser": classify_browser(user_agent),
        "os": classify_os(user_agent),
        "referrer_domain": referrer_domain(request.headers.get("referer")),
        "country": country_from_headers(request.headers),
        "ip": client_ip(request),
    }


async def record_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    group_id: uuid.UUID,
    event_type: AnalyticsEventType,
    request: Request,
    link_id: uuid.UUID | None = None,
) -> AnalyticsEvent | None:
    """Persist one event, or return None when it is filtered out."""
    context = _extract_context(request)

    if context["device_type"] is DeviceType.BOT:
        # Crawlers and link-preview fetchers would otherwise dominate the counts.
        return None

    target = f"{group_id}:{link_id or ''}"
    fingerprint = visitor_fingerprint(context["ip"], context["user_agent"], scope=target)
    if await _is_duplicate(event_type, target, fingerprint):
        return None

    event = AnalyticsEvent(
        organization_id=organization_id,
        group_id=group_id,
        link_id=link_id,
        event_type=event_type,
        device_type=context["device_type"],
        browser=context["browser"],
        os=context["os"],
        referrer_domain=context["referrer_domain"],
        country=context["country"],
        # Day-scoped and salted: useful for unique counts, useless for tracking.
        visitor_hash=hash_ip(context["ip"]),
    )
    db.add(event)
    return event


async def record_event_background(
    *,
    organization_id: uuid.UUID,
    group_id: uuid.UUID,
    event_type: AnalyticsEventType,
    device_type: DeviceType,
    browser: str | None,
    os_name: str | None,
    referrer: str | None,
    country: str | None,
    visitor_hash: str | None,
    dedupe_target: str,
    fingerprint: str,
    link_id: uuid.UUID | None = None,
) -> None:
    """Write an event outside the request/response cycle.

    Used by the public page and the click redirect so the visitor never waits on
    an analytics INSERT. The request-derived context is captured *before* the
    task is scheduled, because the `Request` object does not outlive the response.
    """
    if device_type is DeviceType.BOT:
        return
    if await _is_duplicate(event_type, dedupe_target, fingerprint):
        return

    try:
        async with session_scope() as db:
            db.add(
                AnalyticsEvent(
                    organization_id=organization_id,
                    group_id=group_id,
                    link_id=link_id,
                    event_type=event_type,
                    device_type=device_type,
                    browser=browser,
                    os=os_name,
                    referrer_domain=referrer,
                    country=country,
                    visitor_hash=visitor_hash,
                )
            )
    except Exception as exc:  # noqa: BLE001 - analytics must never break a page view
        app_logger.error("analytics_write_failed", extra={"error": str(exc)})


def capture_context(request: Request, *, group_id: uuid.UUID,
                    link_id: uuid.UUID | None = None) -> dict:
    """Snapshot everything a background task needs from the live request."""
    context = _extract_context(request)
    target = f"{group_id}:{link_id or ''}"
    return {
        "device_type": context["device_type"],
        "browser": context["browser"],
        "os_name": context["os"],
        "referrer": context["referrer_domain"],
        "country": context["country"],
        "visitor_hash": hash_ip(context["ip"]),
        "dedupe_target": target,
        "fingerprint": visitor_fingerprint(
            context["ip"], context["user_agent"], scope=target
        ),
    }
