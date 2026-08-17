"""Colour parsing and WCAG contrast helpers.

Used to validate theme and QR palettes: a QR code with insufficient
foreground/background contrast will not scan, and a theme with unreadable text
fails accessibility.
"""

from __future__ import annotations

import re

from app.core.errors import ValidationError

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# Minimum foreground/background contrast for a reliably scannable QR code.
MIN_QR_CONTRAST_RATIO = 3.0
# WCAG AA for normal-size body text.
MIN_TEXT_CONTRAST_RATIO = 4.5


def normalize_hex(value: str, *, field: str = "color") -> str:
    candidate = (value or "").strip()
    if not HEX_COLOR_RE.match(candidate):
        raise ValidationError(
            "Colour must be a hex value such as #00629B",
            details={"field": field, "value": candidate[:16]},
        )
    candidate = candidate.upper()
    if len(candidate) == 4:  # #ABC -> #AABBCC
        candidate = "#" + "".join(char * 2 for char in candidate[1:])
    return candidate


def to_rgb(value: str) -> tuple[int, int, int]:
    hex_value = normalize_hex(value)[1:]
    return (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
    )


def to_rgba(value: str, *, default_alpha: int = 255) -> tuple[int, int, int, int]:
    hex_value = normalize_hex(value)[1:]
    red, green, blue = (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
    )
    alpha = int(hex_value[6:8], 16) if len(hex_value) == 8 else default_alpha
    return red, green, blue, alpha


def relative_luminance(color: str) -> float:
    """WCAG 2.1 relative luminance."""

    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = to_rgb(color)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    lighter = relative_luminance(foreground)
    darker = relative_luminance(background)
    if lighter < darker:
        lighter, darker = darker, lighter
    return round((lighter + 0.05) / (darker + 0.05), 2)


def readable_text_color(background: str) -> str:
    """Pick black or white text for the given background."""
    return "#0B1F33" if relative_luminance(background) > 0.45 else "#FFFFFF"


def assert_min_contrast(
    foreground: str,
    background: str,
    *,
    minimum: float = MIN_QR_CONTRAST_RATIO,
    field: str = "foreground_color",
) -> float:
    ratio = contrast_ratio(foreground, background)
    if ratio < minimum:
        raise ValidationError(
            f"Contrast ratio {ratio}:1 is too low — needs at least {minimum}:1",
            details={
                "field": field,
                "contrast_ratio": ratio,
                "minimum": minimum,
                "foreground": foreground,
                "background": background,
            },
        )
    return ratio
