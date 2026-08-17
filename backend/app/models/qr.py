from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import (
    DotStyle,
    ErrorCorrection,
    EyeBallStyle,
    EyeFrameStyle,
    FrameStyle,
    GradientType,
    LogoShape,
)

if TYPE_CHECKING:
    from app.models.group import Group


class QRConfiguration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Design configuration for a group's QR code.

    Only the *configuration* is persisted. Images are rendered on demand and
    cached in Redis, so a design change never orphans a stored asset and the QR
    target URL (the group's public page) stays stable forever.
    """

    __tablename__ = "qr_configurations"

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    preset: Mapped[str | None] = mapped_column(String(32))

    # ---- Colours ---------------------------------------------------------
    foreground_color: Mapped[str] = mapped_column(String(9), default="#00629B", nullable=False)
    background_color: Mapped[str] = mapped_column(String(9), default="#FFFFFF", nullable=False)
    transparent_background: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    gradient_type: Mapped[GradientType] = mapped_column(
        pg_enum(GradientType, "gradient_type"), default=GradientType.NONE, nullable=False
    )
    gradient_start_color: Mapped[str | None] = mapped_column(String(9))
    gradient_end_color: Mapped[str | None] = mapped_column(String(9))
    gradient_angle: Mapped[int] = mapped_column(Integer, default=45, nullable=False)

    # ---- Shapes ----------------------------------------------------------
    dot_style: Mapped[DotStyle] = mapped_column(
        pg_enum(DotStyle, "dot_style"), default=DotStyle.SQUARE, nullable=False
    )
    eye_frame_style: Mapped[EyeFrameStyle] = mapped_column(
        pg_enum(EyeFrameStyle, "eye_frame_style"), default=EyeFrameStyle.SQUARE, nullable=False
    )
    eye_ball_style: Mapped[EyeBallStyle] = mapped_column(
        pg_enum(EyeBallStyle, "eye_ball_style"), default=EyeBallStyle.SQUARE, nullable=False
    )
    eye_color: Mapped[str | None] = mapped_column(String(9))
    eye_ball_color: Mapped[str | None] = mapped_column(String(9))

    # ---- Geometry --------------------------------------------------------
    margin: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    error_correction: Mapped[ErrorCorrection] = mapped_column(
        pg_enum(ErrorCorrection, "error_correction"), default=ErrorCorrection.Q, nullable=False
    )

    # ---- Logo ------------------------------------------------------------
    logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("media.id", ondelete="SET NULL")
    )
    # Fraction of the QR width occupied by the logo (0.10 – 0.30).
    logo_size: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    logo_padding: Mapped[float] = mapped_column(Float, default=0.04, nullable=False)
    logo_shape: Mapped[LogoShape] = mapped_column(
        pg_enum(LogoShape, "logo_shape"), default=LogoShape.ROUNDED, nullable=False
    )
    logo_background: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ---- Frame -----------------------------------------------------------
    frame_style: Mapped[FrameStyle] = mapped_column(
        pg_enum(FrameStyle, "frame_style"), default=FrameStyle.NONE, nullable=False
    )
    frame_color: Mapped[str] = mapped_column(String(9), default="#00629B", nullable=False)
    frame_text_color: Mapped[str] = mapped_column(String(9), default="#FFFFFF", nullable=False)
    caption: Mapped[str | None] = mapped_column(String(48))

    group: Mapped["Group"] = relationship(back_populates="qr_configuration")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<QRConfiguration group={self.group_id}>"
