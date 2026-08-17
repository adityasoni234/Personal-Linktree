"""QR configuration schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    DotStyle,
    ErrorCorrection,
    EyeBallStyle,
    EyeFrameStyle,
    FrameStyle,
    GradientType,
    LogoShape,
)
from app.qr.spec import (
    MAX_LOGO_RATIO,
    MAX_OUTPUT_SIZE,
    MIN_LOGO_RATIO,
    MIN_OUTPUT_SIZE,
)
from app.schemas.common import ORMModel
from app.security.colors import normalize_hex
from app.security.sanitize import clean_text


class QRConfigBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: str | None = Field(default=None, max_length=32)

    foreground_color: str = "#00629B"
    background_color: str = "#FFFFFF"
    transparent_background: bool = False

    gradient_type: GradientType = GradientType.NONE
    gradient_start_color: str | None = None
    gradient_end_color: str | None = None
    gradient_angle: int = Field(default=45, ge=0, le=360)

    dot_style: DotStyle = DotStyle.SQUARE
    eye_frame_style: EyeFrameStyle = EyeFrameStyle.SQUARE
    eye_ball_style: EyeBallStyle = EyeBallStyle.SQUARE
    eye_color: str | None = None
    eye_ball_color: str | None = None

    margin: int = Field(default=4, ge=0, le=12)
    error_correction: ErrorCorrection = ErrorCorrection.Q

    logo_media_id: uuid.UUID | None = None
    logo_size: float = Field(default=0.20, ge=MIN_LOGO_RATIO, le=MAX_LOGO_RATIO)
    logo_padding: float = Field(default=0.04, ge=0.0, le=0.10)
    logo_shape: LogoShape = LogoShape.ROUNDED
    logo_background: bool = True

    frame_style: FrameStyle = FrameStyle.NONE
    frame_color: str = "#00629B"
    frame_text_color: str = "#FFFFFF"
    caption: str | None = Field(default=None, max_length=48)

    @field_validator(
        "foreground_color", "background_color", "gradient_start_color",
        "gradient_end_color", "eye_color", "eye_ball_color", "frame_color",
        "frame_text_color",
    )
    @classmethod
    def _hex(cls, value: str | None) -> str | None:
        return normalize_hex(value) if value else None

    @field_validator("caption")
    @classmethod
    def _clean_caption(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=48)

    @field_validator("preset")
    @classmethod
    def _validate_preset(cls, value: str | None) -> str | None:
        if not value:
            return None
        from app.qr.presets import PRESETS

        candidate = value.strip().lower()
        if candidate not in PRESETS:
            raise ValueError("Unknown preset")
        return candidate


class QRConfigUpdate(QRConfigBase):
    """Full replacement of the design. Every field has a safe default."""


class QRConfigOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    preset: str | None

    foreground_color: str
    background_color: str
    transparent_background: bool

    gradient_type: GradientType
    gradient_start_color: str | None
    gradient_end_color: str | None
    gradient_angle: int

    dot_style: DotStyle
    eye_frame_style: EyeFrameStyle
    eye_ball_style: EyeBallStyle
    eye_color: str | None
    eye_ball_color: str | None

    margin: int
    error_correction: ErrorCorrection

    logo_media_id: uuid.UUID | None
    logo_url: str | None = None
    logo_size: float
    logo_padding: float
    logo_shape: LogoShape
    logo_background: bool

    frame_style: FrameStyle
    frame_color: str
    frame_text_color: str
    caption: str | None

    updated_at: datetime


class QRWarning(BaseModel):
    field: str
    severity: Literal["info", "warning", "error"]
    message: str


class QRRenderInfo(BaseModel):
    """Everything the designer needs after a save or a preview."""

    target_url: str
    contrast_ratio: float
    is_scannable: bool
    warnings: list[QRWarning] = []
    preview_data_uri: str | None = None
    png_url: str
    svg_url: str


class QRConfigResponse(BaseModel):
    config: QRConfigOut
    render: QRRenderInfo


class QRPreviewRequest(QRConfigBase):
    """Render an unsaved design. The target URL is always derived server-side
    from the group — a client can never make a QR point somewhere else."""

    size: int = Field(default=512, ge=MIN_OUTPUT_SIZE, le=MAX_OUTPUT_SIZE)


class QRPresetOut(BaseModel):
    id: str
    label: str
    description: str
    config: dict[str, Any]
