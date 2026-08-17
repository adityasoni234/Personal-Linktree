"""Privacy-preserving visitor identification and device classification.

Design constraints:
  * raw IP addresses are never written to the database or the logs;
  * the hash is peppered with a server secret *and* a daily salt, so digests
    cannot be correlated across days or rainbow-tabled;
  * user-agent strings are reduced to a coarse family label, not stored whole.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from app.core.config import settings
from app.models.enums import DeviceType

_BOT_PATTERN = re.compile(
    r"bot|crawler|spider|crawling|slurp|facebookexternalhit|preview|monitor|"
    r"curl|wget|python-requests|httpx|headless|lighthouse|pingdom|uptime",
    re.IGNORECASE,
)
_TABLET_PATTERN = re.compile(r"ipad|tablet|playbook|silk|kindle", re.IGNORECASE)
_MOBILE_PATTERN = re.compile(
    r"mobi|android|iphone|ipod|blackberry|iemobile|opera mini", re.IGNORECASE
)

_BROWSERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Edge", re.compile(r"edg[ae]?/", re.IGNORECASE)),
    ("Opera", re.compile(r"opr/|opera", re.IGNORECASE)),
    ("Samsung Internet", re.compile(r"samsungbrowser", re.IGNORECASE)),
    ("Chrome", re.compile(r"chrome/|crios/", re.IGNORECASE)),
    ("Firefox", re.compile(r"firefox/|fxios/", re.IGNORECASE)),
    ("Safari", re.compile(r"safari/", re.IGNORECASE)),
)

_OPERATING_SYSTEMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("iOS", re.compile(r"iphone|ipad|ipod", re.IGNORECASE)),
    ("Android", re.compile(r"android", re.IGNORECASE)),
    ("Windows", re.compile(r"windows nt", re.IGNORECASE)),
    ("macOS", re.compile(r"mac os x|macintosh", re.IGNORECASE)),
    ("Linux", re.compile(r"linux|x11", re.IGNORECASE)),
    ("Chrome OS", re.compile(r"cros", re.IGNORECASE)),
)


def _daily_salt() -> str:
    """Rotates every UTC day so visitor hashes cannot be linked long-term."""
    return date.today().isoformat()


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    payload = f"{settings.ANALYTICS_IP_PEPPER}:{_daily_salt()}:{ip}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def visitor_fingerprint(ip: str | None, user_agent: str | None, scope: str = "") -> str:
    """Short-lived, non-reversible visitor key used for de-duplication only."""
    payload = (
        f"{settings.ANALYTICS_IP_PEPPER}:{_daily_salt()}:{ip or ''}:"
        f"{(user_agent or '')[:180]}:{scope}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_device(user_agent: str | None) -> DeviceType:
    if not user_agent:
        return DeviceType.UNKNOWN
    if _BOT_PATTERN.search(user_agent):
        return DeviceType.BOT
    if _TABLET_PATTERN.search(user_agent):
        return DeviceType.TABLET
    if _MOBILE_PATTERN.search(user_agent):
        return DeviceType.MOBILE
    return DeviceType.DESKTOP


def classify_browser(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    for name, pattern in _BROWSERS:
        if pattern.search(user_agent):
            return name
    return "Other"


def classify_os(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    for name, pattern in _OPERATING_SYSTEMS:
        if pattern.search(user_agent):
            return name
    return "Other"


def country_from_headers(headers) -> str | None:  # noqa: ANN001 - Starlette Headers
    """Read the country from a CDN-provided header, when the edge supplies one.

    No GeoIP database is queried and no lookup service is contacted; if the CDN
    does not tell us, the field stays null.
    """
    for header in ("cf-ipcountry", "x-vercel-ip-country", "x-geo-country", "x-country-code"):
        value = headers.get(header)
        if value and len(value) == 2 and value.isalpha() and value.upper() != "XX":
            return value.upper()
    return None
