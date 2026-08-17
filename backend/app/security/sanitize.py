"""Normalisation of user-supplied text.

Every free-text field is stored as plain text — no HTML is accepted anywhere in
the product, so the safest treatment is to strip markup rather than try to allow
a subset of it. The React frontend renders these values as text nodes (never
`dangerouslySetInnerHTML`), giving defence in depth.
"""

from __future__ import annotations

import re
import unicodedata

# C0/C1 controls, except tab/newline/carriage return which are handled per field.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
# Zero-width and bidirectional-override characters: invisible, and used for
# homograph and "Trojan Source" style spoofing in display names.
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿⁦-⁩]")
_HTML_TAG = re.compile(r"<[^>]*>")
_WHITESPACE_RUN = re.compile(r"[ \t]{2,}")
_NEWLINE_RUN = re.compile(r"\n{3,}")


def clean_text(
    value: str | None,
    *,
    max_length: int | None = None,
    allow_newlines: bool = False,
) -> str | None:
    """Return a normalised, markup-free version of `value`.

    Returns `None` for input that is empty once cleaned, so optional fields end
    up as SQL NULL rather than an empty string.
    """
    if value is None:
        return None

    text = unicodedata.normalize("NFC", value)
    text = _INVISIBLE.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _CONTROL_CHARS.sub("", text)

    if allow_newlines:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _NEWLINE_RUN.sub("\n\n", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
    else:
        text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")

    text = _WHITESPACE_RUN.sub(" ", text).strip()

    if max_length is not None and len(text) > max_length:
        text = text[:max_length].rstrip()

    return text or None


def clean_required_text(value: str, *, max_length: int, field: str,
                        allow_newlines: bool = False) -> str:
    from app.core.errors import ValidationError

    cleaned = clean_text(value, max_length=max_length, allow_newlines=allow_newlines)
    if not cleaned:
        raise ValidationError("This field is required", details={"field": field})
    return cleaned


def normalize_email(value: str) -> str:
    """Lowercase and trim. Stored normalised so uniqueness is case-insensitive."""
    return (value or "").strip().lower()


def user_agent_label(user_agent: str | None) -> str | None:
    """Short, human-readable device label.

    The full user-agent string is a fingerprinting vector, so only a truncated,
    sanitised label is retained for the "active sessions" screen.
    """
    if not user_agent:
        return None
    cleaned = _CONTROL_CHARS.sub("", user_agent).strip()
    return cleaned[:120] or None
