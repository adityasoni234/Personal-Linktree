"""Slug generation and validation for public group URLs (`/g/{slug}`)."""

from __future__ import annotations

import re
import secrets
import unicodedata

from app.core.errors import ValidationError

MIN_SLUG_LENGTH = 3
MAX_SLUG_LENGTH = 48

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Paths the frontend and API own. A group slug may never shadow one of these,
# otherwise `/g/...` rewrites or future top-level routes would collide.
RESERVED_SLUGS = frozenset(
    {
        "admin", "administrator", "api", "app", "apps", "assets", "auth", "about",
        "billing", "blog", "config", "console", "contact", "css", "dashboard",
        "docs", "download", "downloads", "edit", "email", "explore", "favicon",
        "feed", "files", "fonts", "forgot-password", "g", "group", "groups",
        "health", "help", "home", "img", "images", "index", "internal", "js",
        "legal", "link", "links", "login", "logout", "media", "metrics", "new",
        "null", "oauth", "org", "organization", "password", "pricing", "privacy",
        "profile", "public", "qr", "ready", "register", "reset-password", "robots",
        "root", "search", "security", "settings", "signin", "signup", "sitemap",
        "static", "status", "support", "system", "terms", "test", "undefined",
        "upload", "uploads", "user", "users", "v1", "verify", "www",
    }
)


def slugify(value: str, *, fallback: str = "group") -> str:
    """Best-effort conversion of a display name into a URL-safe slug."""
    normalised = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)[:MAX_SLUG_LENGTH].strip("-")
    if len(cleaned) < MIN_SLUG_LENGTH:
        cleaned = f"{fallback}-{secrets.token_hex(3)}"
    return cleaned


def validate_slug(slug: str) -> str:
    """Validate a user-chosen slug. Always called server-side before persisting."""
    candidate = (slug or "").strip().lower()

    if not candidate:
        raise ValidationError("A URL slug is required", details={"field": "slug"})
    if len(candidate) < MIN_SLUG_LENGTH:
        raise ValidationError(
            f"Slug must be at least {MIN_SLUG_LENGTH} characters", details={"field": "slug"}
        )
    if len(candidate) > MAX_SLUG_LENGTH:
        raise ValidationError(
            f"Slug must be at most {MAX_SLUG_LENGTH} characters", details={"field": "slug"}
        )
    if not _SLUG_RE.match(candidate):
        raise ValidationError(
            "Slug may only contain lowercase letters, numbers and single hyphens",
            details={"field": "slug"},
        )
    if candidate in RESERVED_SLUGS:
        raise ValidationError(
            f"'{candidate}' is a reserved address and cannot be used",
            details={"field": "slug"},
        )
    # A slug shaped like a UUID or a bare number invites confusion with API ids.
    if re.fullmatch(r"[0-9a-f]{8}-?[0-9a-f]{4}", candidate) or candidate.isdigit():
        raise ValidationError(
            "Slug must contain at least one letter and not look like an identifier",
            details={"field": "slug"},
        )
    return candidate


def suffixed_slug(base: str, attempt: int) -> str:
    """Deterministic-length variant used to resolve collisions."""
    suffix = f"-{secrets.token_hex(2)}" if attempt > 3 else f"-{attempt + 1}"
    trimmed = base[: MAX_SLUG_LENGTH - len(suffix)].rstrip("-")
    return f"{trimmed}{suffix}"
