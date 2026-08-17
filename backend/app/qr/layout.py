"""Canvas layout: where the QR square, the frame and the caption bar sit."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import FrameStyle
from app.qr.spec import QRSpec

FRAME_THICKNESS_RATIO = 0.05
CAPTION_BAR_RATIO = 0.16
DEFAULT_BANNER_CAPTION = "SCAN ME"

_BANNER_STYLES = frozenset(
    {FrameStyle.BANNER_BOTTOM, FrameStyle.BANNER_TOP, FrameStyle.TICKET}
)


@dataclass(frozen=True, slots=True)
class Layout:
    canvas_width: float
    canvas_height: float
    qr_x: float
    qr_y: float
    qr_size: float
    frame_thickness: float
    frame_radius: float
    caption_text: str | None
    # (x, y, width, height) of the caption bar, if any
    caption_box: tuple[float, float, float, float] | None
    has_frame: bool
    notch_radius: float = 0.0

    @property
    def caption_font_size(self) -> float:
        if not self.caption_box:
            return 0.0
        return min(self.caption_box[3] * 0.44, self.canvas_width / max(len(self.caption_text or "x"), 6) * 1.4)


def compute_layout(spec: QRSpec) -> Layout:
    size = float(spec.size)
    style = spec.frame_style

    if style is FrameStyle.NONE:
        return Layout(
            canvas_width=size,
            canvas_height=size,
            qr_x=0.0,
            qr_y=0.0,
            qr_size=size,
            frame_thickness=0.0,
            frame_radius=0.0,
            caption_text=None,
            caption_box=None,
            has_frame=False,
        )

    thickness = size * FRAME_THICKNESS_RATIO
    caption = spec.caption or (DEFAULT_BANNER_CAPTION if style in _BANNER_STYLES else None)
    bar_height = size * CAPTION_BAR_RATIO if caption else 0.0

    canvas_width = size + 2 * thickness
    canvas_height = size + 2 * thickness + bar_height

    radius = {
        FrameStyle.SIMPLE: 0.0,
        FrameStyle.ROUNDED: size * 0.08,
        FrameStyle.BANNER_BOTTOM: size * 0.05,
        FrameStyle.BANNER_TOP: size * 0.05,
        FrameStyle.TICKET: size * 0.12,
    }.get(style, 0.0)

    if style is FrameStyle.BANNER_TOP:
        qr_y = thickness + bar_height
        caption_box = (0.0, 0.0, canvas_width, bar_height) if caption else None
    else:
        qr_y = thickness
        caption_box = (
            (0.0, canvas_height - bar_height, canvas_width, bar_height) if caption else None
        )

    return Layout(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        qr_x=thickness,
        qr_y=qr_y,
        qr_size=size,
        frame_thickness=thickness,
        frame_radius=radius,
        caption_text=caption,
        caption_box=caption_box,
        has_frame=True,
        notch_radius=size * 0.045 if style is FrameStyle.TICKET else 0.0,
    )
