"""Curated QR design presets.

Every preset is contrast-checked and stays within the logo/error-correction
envelope that keeps a code reliably scannable.
"""

from __future__ import annotations

from typing import Any

from app.models.enums import (
    DotStyle,
    ErrorCorrection,
    EyeBallStyle,
    EyeFrameStyle,
    FrameStyle,
    GradientType,
    LogoShape,
)

IEEE_BLUE = "#00629B"
IEEE_NAVY = "#0B2545"
IEEE_LIGHT = "#00A3E0"
# Mid blue that still clears the 3:1 scan floor on white (4.02:1).
IEEE_MID = "#0F86C4"

PRESETS: dict[str, dict[str, Any]] = {
    "ieee-classic": {
        "label": "IEEE Classic",
        "description": "IEEE blue on white with square modules — maximum scan reliability.",
        "config": {
            "foreground_color": IEEE_BLUE,
            "background_color": "#FFFFFF",
            "transparent_background": False,
            "gradient_type": GradientType.NONE,
            "dot_style": DotStyle.SQUARE,
            "eye_frame_style": EyeFrameStyle.SQUARE,
            "eye_ball_style": EyeBallStyle.SQUARE,
            "eye_color": IEEE_NAVY,
            "eye_ball_color": IEEE_BLUE,
            "margin": 4,
            "error_correction": ErrorCorrection.Q,
            "logo_shape": LogoShape.ROUNDED,
            "logo_size": 0.20,
            "frame_style": FrameStyle.NONE,
            "frame_color": IEEE_BLUE,
            "frame_text_color": "#FFFFFF",
            "caption": None,
        },
    },
    "minimal": {
        "label": "Minimal",
        "description": "Pure black on white, generous quiet zone. Prints anywhere.",
        "config": {
            "foreground_color": "#111827",
            "background_color": "#FFFFFF",
            "transparent_background": False,
            "gradient_type": GradientType.NONE,
            "dot_style": DotStyle.SQUARE,
            "eye_frame_style": EyeFrameStyle.SQUARE,
            "eye_ball_style": EyeBallStyle.SQUARE,
            "eye_color": None,
            "eye_ball_color": None,
            "margin": 5,
            "error_correction": ErrorCorrection.M,
            "logo_shape": LogoShape.SQUARE,
            "logo_size": 0.18,
            "frame_style": FrameStyle.NONE,
            "frame_color": "#111827",
            "frame_text_color": "#FFFFFF",
            "caption": None,
        },
    },
    "professional": {
        "label": "Professional",
        "description": "Softly rounded modules in deep navy — the default for print collateral.",
        "config": {
            "foreground_color": IEEE_NAVY,
            "background_color": "#FFFFFF",
            "transparent_background": False,
            "gradient_type": GradientType.NONE,
            "dot_style": DotStyle.ROUNDED,
            "eye_frame_style": EyeFrameStyle.ROUNDED,
            "eye_ball_style": EyeBallStyle.ROUNDED,
            "eye_color": IEEE_BLUE,
            "eye_ball_color": IEEE_NAVY,
            "margin": 4,
            "error_correction": ErrorCorrection.Q,
            "logo_shape": LogoShape.ROUNDED,
            "logo_size": 0.20,
            "frame_style": FrameStyle.NONE,
            "frame_color": IEEE_NAVY,
            "frame_text_color": "#FFFFFF",
            "caption": None,
        },
    },
    "event": {
        "label": "Event",
        "description": "Framed with a “SCAN ME” banner — designed for posters and standees.",
        "config": {
            "foreground_color": IEEE_NAVY,
            "background_color": "#FFFFFF",
            "transparent_background": False,
            "gradient_type": GradientType.NONE,
            "dot_style": DotStyle.ROUNDED,
            "eye_frame_style": EyeFrameStyle.ROUNDED,
            "eye_ball_style": EyeBallStyle.CIRCLE,
            "eye_color": IEEE_BLUE,
            "eye_ball_color": IEEE_BLUE,
            "margin": 3,
            "error_correction": ErrorCorrection.Q,
            "logo_shape": LogoShape.CIRCLE,
            "logo_size": 0.20,
            "frame_style": FrameStyle.BANNER_BOTTOM,
            "frame_color": IEEE_BLUE,
            "frame_text_color": "#FFFFFF",
            "caption": "SCAN ME",
        },
    },
    "modern": {
        "label": "Modern",
        "description": "Dot modules with an IEEE blue gradient and circular finders.",
        "config": {
            "foreground_color": IEEE_BLUE,
            "background_color": "#FFFFFF",
            "transparent_background": False,
            "gradient_type": GradientType.LINEAR,
            "gradient_start_color": IEEE_NAVY,
            "gradient_end_color": IEEE_MID,
            "gradient_angle": 45,
            "dot_style": DotStyle.DOT,
            "eye_frame_style": EyeFrameStyle.CIRCLE,
            "eye_ball_style": EyeBallStyle.CIRCLE,
            "eye_color": IEEE_NAVY,
            "eye_ball_color": IEEE_MID,
            "margin": 4,
            "error_correction": ErrorCorrection.H,
            "logo_shape": LogoShape.CIRCLE,
            "logo_size": 0.18,
            "frame_style": FrameStyle.NONE,
            "frame_color": IEEE_BLUE,
            "frame_text_color": "#FFFFFF",
            "caption": None,
        },
    },
    "dark": {
        "label": "Dark",
        "description": "Light modules on deep navy for dark backgrounds and slides.",
        "config": {
            "foreground_color": "#FFFFFF",
            "background_color": IEEE_NAVY,
            "transparent_background": False,
            "gradient_type": GradientType.NONE,
            "dot_style": DotStyle.CLASSY,
            "eye_frame_style": EyeFrameStyle.LEAF,
            "eye_ball_style": EyeBallStyle.ROUNDED,
            "eye_color": IEEE_LIGHT,
            "eye_ball_color": "#FFFFFF",
            "margin": 4,
            "error_correction": ErrorCorrection.Q,
            "logo_shape": LogoShape.ROUNDED,
            "logo_size": 0.18,
            "frame_style": FrameStyle.NONE,
            "frame_color": IEEE_NAVY,
            "frame_text_color": "#FFFFFF",
            "caption": None,
        },
    },
}


def preset_names() -> list[str]:
    return list(PRESETS)


def get_preset(name: str) -> dict[str, Any] | None:
    entry = PRESETS.get(name.strip().lower())
    return dict(entry["config"]) if entry else None


def preset_catalogue() -> list[dict[str, Any]]:
    """Serialisable preset list for the designer UI."""
    return [
        {
            "id": key,
            "label": entry["label"],
            "description": entry["description"],
            "config": {
                field: (value.value if hasattr(value, "value") else value)
                for field, value in entry["config"].items()
            },
        }
        for key, entry in PRESETS.items()
    ]
