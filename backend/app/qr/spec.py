"""Normalised, validated QR render specification.

`QRSpec` is the single input to both renderers. It is built from the stored
`QRConfiguration` (or from a preview payload) and is fully validated — the
renderers assume every value is already safe and in range.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256

from app.core.errors import ValidationError
from app.models.enums import (
    DotStyle,
    ErrorCorrection,
    EyeBallStyle,
    EyeFrameStyle,
    FrameStyle,
    GradientType,
    LogoShape,
)
from app.security.colors import contrast_ratio, normalize_hex

MIN_OUTPUT_SIZE = 128
MAX_OUTPUT_SIZE = 2048
DEFAULT_OUTPUT_SIZE = 1024

MIN_LOGO_RATIO = 0.08
MAX_LOGO_RATIO = 0.30
# Above this the damaged-module area starts to exceed what even level-H error
# correction can recover.
SAFE_LOGO_RATIO = 0.22

MAX_MARGIN = 12
MAX_CAPTION_LENGTH = 48


@dataclass(frozen=True, slots=True)
class QRSpec:
    data: str

    foreground: str = "#00629B"
    background: str = "#FFFFFF"
    transparent_background: bool = False

    gradient_type: GradientType = GradientType.NONE
    gradient_start: str | None = None
    gradient_end: str | None = None
    gradient_angle: int = 45

    dot_style: DotStyle = DotStyle.SQUARE
    eye_frame_style: EyeFrameStyle = EyeFrameStyle.SQUARE
    eye_ball_style: EyeBallStyle = EyeBallStyle.SQUARE
    eye_color: str | None = None
    eye_ball_color: str | None = None

    margin: int = 4
    error_correction: ErrorCorrection = ErrorCorrection.Q

    logo_bytes: bytes | None = field(default=None, repr=False)
    logo_content_type: str | None = None
    logo_size: float = 0.20
    logo_padding: float = 0.04
    logo_shape: LogoShape = LogoShape.ROUNDED
    logo_background: bool = True

    frame_style: FrameStyle = FrameStyle.NONE
    frame_color: str = "#00629B"
    frame_text_color: str = "#FFFFFF"
    caption: str | None = None

    size: int = DEFAULT_OUTPUT_SIZE

    # ---- Derived ---------------------------------------------------------
    @property
    def has_logo(self) -> bool:
        return bool(self.logo_bytes)

    @property
    def logo_is_svg(self) -> bool:
        return self.logo_content_type == "image/svg+xml"

    @property
    def effective_error_correction(self) -> ErrorCorrection:
        """A logo always forces level H — it destroys modules by design."""
        if self.has_logo:
            return ErrorCorrection.H
        return self.error_correction

    @property
    def reserve_ratio(self) -> float:
        """Fraction of the QR width the logo plus its padding occupies."""
        if not self.has_logo:
            return 0.0
        return min(MAX_LOGO_RATIO + 0.08, self.logo_size + 2 * self.logo_padding)

    def cache_key(self) -> str:
        """Stable digest of everything that affects the rendered output."""
        parts = [
            self.data,
            self.foreground,
            self.background,
            str(self.transparent_background),
            self.gradient_type.value,
            self.gradient_start or "",
            self.gradient_end or "",
            str(self.gradient_angle),
            self.dot_style.value,
            self.eye_frame_style.value,
            self.eye_ball_style.value,
            self.eye_color or "",
            self.eye_ball_color or "",
            str(self.margin),
            self.effective_error_correction.value,
            f"{self.logo_size:.3f}",
            f"{self.logo_padding:.3f}",
            self.logo_shape.value,
            str(self.logo_background),
            self.frame_style.value,
            self.frame_color,
            self.frame_text_color,
            self.caption or "",
            str(self.size),
            sha256(self.logo_bytes).hexdigest() if self.logo_bytes else "",
        ]
        return sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]

    def with_size(self, size: int) -> "QRSpec":
        return replace(self, size=clamp_size(size))


def clamp_size(size: int | None) -> int:
    if size is None:
        return DEFAULT_OUTPUT_SIZE
    if size < MIN_OUTPUT_SIZE or size > MAX_OUTPUT_SIZE:
        raise ValidationError(
            f"Size must be between {MIN_OUTPUT_SIZE} and {MAX_OUTPUT_SIZE} pixels",
            details={"field": "size", "min": MIN_OUTPUT_SIZE, "max": MAX_OUTPUT_SIZE},
        )
    return int(size)


def validate_spec(spec: QRSpec) -> QRSpec:
    """Normalise colours and range-check every numeric field."""
    foreground = normalize_hex(spec.foreground, field="foreground_color")
    background = normalize_hex(spec.background, field="background_color")

    gradient_start = (
        normalize_hex(spec.gradient_start, field="gradient_start_color")
        if spec.gradient_start
        else None
    )
    gradient_end = (
        normalize_hex(spec.gradient_end, field="gradient_end_color")
        if spec.gradient_end
        else None
    )
    if spec.gradient_type is not GradientType.NONE and not (gradient_start and gradient_end):
        raise ValidationError(
            "A gradient needs both a start and an end colour",
            details={"field": "gradient_start_color"},
        )

    if not 0 <= spec.gradient_angle <= 360:
        raise ValidationError(
            "Gradient angle must be between 0 and 360", details={"field": "gradient_angle"}
        )
    if not 0 <= spec.margin <= MAX_MARGIN:
        raise ValidationError(
            f"Margin must be between 0 and {MAX_MARGIN} modules", details={"field": "margin"}
        )
    if spec.has_logo and not MIN_LOGO_RATIO <= spec.logo_size <= MAX_LOGO_RATIO:
        raise ValidationError(
            f"Logo size must be between {int(MIN_LOGO_RATIO * 100)}% and "
            f"{int(MAX_LOGO_RATIO * 100)}% of the code",
            details={"field": "logo_size"},
        )
    if not 0 <= spec.logo_padding <= 0.10:
        raise ValidationError(
            "Logo padding must be between 0% and 10%", details={"field": "logo_padding"}
        )

    caption = (spec.caption or "").strip() or None
    if caption and len(caption) > MAX_CAPTION_LENGTH:
        raise ValidationError(
            f"Caption must be at most {MAX_CAPTION_LENGTH} characters",
            details={"field": "caption"},
        )
    if spec.frame_style is not FrameStyle.NONE and not caption:
        caption = None  # frame without text is fine; just do not render an empty bar

    return replace(
        spec,
        foreground=foreground,
        background=background,
        gradient_start=gradient_start,
        gradient_end=gradient_end,
        eye_color=normalize_hex(spec.eye_color, field="eye_color") if spec.eye_color else None,
        eye_ball_color=(
            normalize_hex(spec.eye_ball_color, field="eye_ball_color")
            if spec.eye_ball_color
            else None
        ),
        frame_color=normalize_hex(spec.frame_color, field="frame_color"),
        frame_text_color=normalize_hex(spec.frame_text_color, field="frame_text_color"),
        caption=caption,
        size=clamp_size(spec.size),
    )


def scannability_report(spec: QRSpec) -> dict:
    """Non-blocking guidance surfaced in the designer UI.

    Hard failures (contrast far too low) are raised as validation errors by the
    service; everything here is advisory.
    """
    warnings: list[dict[str, str]] = []
    effective_fg = spec.gradient_start if spec.gradient_type is not GradientType.NONE else spec.foreground
    background = spec.background if not spec.transparent_background else "#FFFFFF"

    ratio = contrast_ratio(effective_fg or spec.foreground, background)
    if ratio < 3.0:
        warnings.append(
            {
                "field": "foreground_color",
                "severity": "error",
                "message": (
                    f"Contrast is only {ratio}:1. Most scanners need at least 3:1 — "
                    "darken the foreground or lighten the background."
                ),
            }
        )
    elif ratio < 5.0:
        warnings.append(
            {
                "field": "foreground_color",
                "severity": "warning",
                "message": f"Contrast is {ratio}:1. Aim for 5:1 or higher for reliable scanning in poor light.",
            }
        )

    if spec.gradient_type is not GradientType.NONE and spec.gradient_end:
        end_ratio = contrast_ratio(spec.gradient_end, background)
        if end_ratio < 3.0:
            warnings.append(
                {
                    "field": "gradient_end_color",
                    "severity": "error",
                    "message": f"The gradient fades to {end_ratio}:1 contrast, which will not scan.",
                }
            )

    # The finder patterns are what a scanner locks onto first, so a
    # low-contrast eye breaks decoding even when the data modules are fine.
    for field, colour in (
        ("eye_color", spec.eye_color),
        ("eye_ball_color", spec.eye_ball_color),
    ):
        if not colour:
            continue
        eye_ratio = contrast_ratio(colour, background)
        if eye_ratio < 3.0:
            warnings.append(
                {
                    "field": field,
                    "severity": "error",
                    "message": (
                        f"The finder pattern is only {eye_ratio}:1 against the background. "
                        "Scanners locate a code by its three corner markers, so this will not scan."
                    ),
                }
            )

    if spec.has_logo:
        if spec.logo_size > SAFE_LOGO_RATIO:
            warnings.append(
                {
                    "field": "logo_size",
                    "severity": "warning",
                    "message": (
                        f"A logo covering {int(spec.logo_size * 100)}% of the code may exceed "
                        "what error correction can recover. Keep it at or below "
                        f"{int(SAFE_LOGO_RATIO * 100)}% and always test-scan before printing."
                    ),
                }
            )
        if spec.error_correction is not ErrorCorrection.H:
            warnings.append(
                {
                    "field": "error_correction",
                    "severity": "info",
                    "message": "Error correction was raised to level H automatically because a logo is used.",
                }
            )

    if spec.margin < 2:
        warnings.append(
            {
                "field": "margin",
                "severity": "warning",
                "message": "A quiet zone below 2 modules stops many scanners from locking on.",
            }
        )

    if spec.transparent_background:
        warnings.append(
            {
                "field": "transparent_background",
                "severity": "info",
                "message": "Transparent codes take the colour of whatever they are placed on — test on the final background.",
            }
        )

    return {
        "contrast_ratio": ratio,
        "warnings": warnings,
        "is_scannable": not any(item["severity"] == "error" for item in warnings),
    }
