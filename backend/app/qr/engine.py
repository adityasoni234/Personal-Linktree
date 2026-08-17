"""QR rendering entry point with caching.

Rendering is CPU-bound, so it runs in a worker thread (never blocking the event
loop) and every result is cached in Redis keyed by a digest of the full
specification. A repeat download of an unchanged design costs one Redis read.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Literal

from app.core.logging import app_logger
from app.core.redis import RedisKeys, get_redis
from app.qr.png_renderer import render_png
from app.qr.spec import QRSpec, scannability_report, validate_spec
from app.qr.svg_renderer import render_svg

RenderFormat = Literal["png", "svg"]

CONTENT_TYPES: dict[str, str] = {"png": "image/png", "svg": "image/svg+xml"}
CACHE_TTL_SECONDS = 6 * 3600
# Anything larger is cheaper to re-render than to move in and out of Redis.
MAX_CACHEABLE_BYTES = 512 * 1024


def render_sync(spec: QRSpec, fmt: RenderFormat) -> bytes:
    """Synchronous render. Used directly by tests and background jobs."""
    validated = validate_spec(spec)
    if fmt == "svg":
        return render_svg(validated)
    return render_png(validated)


async def render(spec: QRSpec, fmt: RenderFormat, *, use_cache: bool = True) -> bytes:
    validated = validate_spec(spec)
    cache_key = RedisKeys.qr_asset(validated.cache_key(), fmt)

    if use_cache:
        try:
            cached = await get_redis().get(cache_key)
            if cached:
                return base64.b64decode(cached)
        except Exception as exc:  # noqa: BLE001 - cache misses must never fail a render
            app_logger.warning("qr_cache_read_failed", extra={"error": str(exc)})

    renderer = render_svg if fmt == "svg" else render_png
    payload = await asyncio.to_thread(renderer, validated)

    if use_cache and len(payload) <= MAX_CACHEABLE_BYTES:
        try:
            await get_redis().set(
                cache_key,
                base64.b64encode(payload).decode("ascii"),
                ex=CACHE_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            app_logger.warning("qr_cache_write_failed", extra={"error": str(exc)})

    return payload


async def render_data_uri(spec: QRSpec, fmt: RenderFormat = "png") -> str:
    """Inline preview for the designer UI (no file download round-trip)."""
    payload = await render(spec, fmt)
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{CONTENT_TYPES[fmt]};base64,{encoded}"


async def invalidate_cache(spec: QRSpec) -> None:
    try:
        await get_redis().delete(
            RedisKeys.qr_asset(validate_spec(spec).cache_key(), "png"),
            RedisKeys.qr_asset(validate_spec(spec).cache_key(), "svg"),
        )
    except Exception as exc:  # noqa: BLE001
        app_logger.warning("qr_cache_invalidate_failed", extra={"error": str(exc)})


__all__ = [
    "CONTENT_TYPES",
    "QRSpec",
    "RenderFormat",
    "invalidate_cache",
    "render",
    "render_data_uri",
    "render_sync",
    "scannability_report",
    "validate_spec",
]
