"""Server-side URL validation for user-supplied link targets.

The frontend also validates, but this is the enforcement point: anything written
to `links.url` has passed through `validate_link_url`.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from app.core.config import settings
from app.core.errors import ValidationError

MAX_URL_LENGTH = 2048

# Web schemes users may link to.
WEB_SCHEMES = frozenset({"http", "https"})
# Additional schemes explicitly reviewed as safe for contact links.
CONTACT_SCHEMES = frozenset({"mailto", "tel"})
ALLOWED_SCHEMES = WEB_SCHEMES | CONTACT_SCHEMES

# Rejected loudly (rather than silently falling through) so the error message is
# actionable and the attempt is visible in logs.
DANGEROUS_SCHEMES = frozenset(
    {
        "javascript", "data", "vbscript", "file", "about", "blob", "chrome",
        "chrome-extension", "resource", "jar", "view-source", "ws", "wss",
        "ftp", "gopher", "ssh", "telnet", "ldap", "dict", "php", "intent",
    }
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_EMAIL_RE = re.compile(r"^[^@\s]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_TEL_RE = re.compile(r"^\+?[0-9][0-9\s().-]{4,24}$")
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)


def _reject(message: str, value: str | None = None) -> None:
    raise ValidationError(message, details={"field": "url", "value": value})


def _is_private_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def validate_link_url(raw: str, *, allow_contact_schemes: bool = True) -> str:
    """Normalise and validate an outbound link.

    Returns the canonical URL to persist, or raises `ValidationError`.
    """
    if raw is None:
        _reject("A URL is required")

    candidate = raw.strip()
    if not candidate:
        _reject("A URL is required")
    if len(candidate) > MAX_URL_LENGTH:
        _reject(f"URL must be at most {MAX_URL_LENGTH} characters")

    # Strip characters that browsers ignore but that can be used to smuggle a
    # scheme past a naive check (e.g. "java\nscript:alert(1)").
    if _CONTROL_CHARS.search(candidate) or "\\" in candidate:
        _reject("URL contains characters that are not allowed")

    # Bare domains are a common paste; assume https rather than rejecting.
    if "://" not in candidate and not candidate.lower().startswith(("mailto:", "tel:")):
        candidate = f"https://{candidate}"

    parts = urlsplit(candidate)
    scheme = parts.scheme.lower().strip()

    if not scheme:
        _reject("URL must include a scheme (https://)")
    if scheme in DANGEROUS_SCHEMES:
        _reject(f"The '{scheme}:' scheme is not allowed")
    if scheme not in ALLOWED_SCHEMES:
        _reject("Only http:// and https:// links are allowed")
    if scheme in CONTACT_SCHEMES and not allow_contact_schemes:
        _reject("Only http:// and https:// links are allowed")

    if scheme == "mailto":
        address = candidate[len("mailto:"):].split("?", 1)[0].strip()
        if not _EMAIL_RE.match(address):
            _reject("Enter a valid email address")
        return f"mailto:{address}"

    if scheme == "tel":
        number = candidate[len("tel:"):].strip()
        if not _TEL_RE.match(number):
            _reject("Enter a valid phone number")
        return f"tel:{re.sub(r'[\s().-]', '', number)}"

    # ---- http(s) ---------------------------------------------------------
    if "@" in parts.netloc:
        # Credentials in a URL are almost always a phishing/obfuscation signal.
        _reject("URLs must not contain embedded credentials")

    host = (parts.hostname or "").strip()
    if not host:
        _reject("URL must include a host name")

    try:
        # IDNA round-trip rejects homograph payloads that cannot be encoded.
        ascii_host = host.encode("idna").decode("ascii") if not host.replace(".", "").isdigit() else host
    except (UnicodeError, UnicodeDecodeError):
        _reject("URL host name is not valid")
        raise AssertionError  # unreachable, keeps type-checkers happy

    is_ip_literal = False
    try:
        ipaddress.ip_address(ascii_host.strip("[]"))
        is_ip_literal = True
    except ValueError:
        if not _HOSTNAME_RE.match(ascii_host):
            _reject("URL host name is not valid")
        if "." not in ascii_host:
            _reject("URL must use a fully qualified domain name")

    if settings.is_production and (is_ip_literal or _is_private_host(ascii_host)):
        _reject("Links to private or internal addresses are not allowed")

    if parts.port is not None and parts.port not in range(1, 65536):
        _reject("URL port is not valid")

    netloc = ascii_host.lower()
    if parts.port and parts.port not in (80, 443):
        netloc = f"{netloc}:{parts.port}"

    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, parts.fragment))


def referrer_domain(referrer: str | None) -> str | None:
    """Reduce a Referer header to its host.

    Only the domain is retained for analytics — the path and query string can
    contain personal data and are discarded.
    """
    if not referrer:
        return None
    try:
        host = urlsplit(referrer.strip()).hostname
    except ValueError:
        return None
    if not host or len(host) > 255:
        return None
    return host.lower()
