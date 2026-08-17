"""Vector (SVG) QR renderer.

Produces a self-contained SVG: gradients are `<defs>`, raster logos are inlined
as data URIs and vector logos are embedded as a nested `<svg>`. Nothing external
is referenced, so the download works offline and in a print workflow.
"""

from __future__ import annotations

import base64
import math
from xml.sax.saxutils import escape

from defusedxml.ElementTree import fromstring as safe_fromstring

from app.models.enums import FrameStyle, GradientType
from app.qr.geometry import Circle, Polygon, Ring, RoundedRect, Shape, build_geometry
from app.qr.layout import compute_layout
from app.qr.spec import QRSpec

_DATA_GRADIENT_ID = "lh-qr-gradient"
_LOGO_CLIP_ID = "lh-logo-clip"


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _rounded_rect_path(rect: RoundedRect) -> str:
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    max_radius = min(w, h) / 2
    tl, tr, br, bl = (min(radius, max_radius) for radius in rect.radii)
    return (
        f"M{_fmt(x + tl)},{_fmt(y)}"
        f"H{_fmt(x + w - tr)}"
        f"A{_fmt(tr)},{_fmt(tr)} 0 0 1 {_fmt(x + w)},{_fmt(y + tr)}"
        f"V{_fmt(y + h - br)}"
        f"A{_fmt(br)},{_fmt(br)} 0 0 1 {_fmt(x + w - br)},{_fmt(y + h)}"
        f"H{_fmt(x + bl)}"
        f"A{_fmt(bl)},{_fmt(bl)} 0 0 1 {_fmt(x)},{_fmt(y + h - bl)}"
        f"V{_fmt(y + tl)}"
        f"A{_fmt(tl)},{_fmt(tl)} 0 0 1 {_fmt(x + tl)},{_fmt(y)}Z"
    )


def _circle_path(circle: Circle) -> str:
    cx, cy, r = circle.cx, circle.cy, circle.r
    return (
        f"M{_fmt(cx - r)},{_fmt(cy)}"
        f"A{_fmt(r)},{_fmt(r)} 0 1 0 {_fmt(cx + r)},{_fmt(cy)}"
        f"A{_fmt(r)},{_fmt(r)} 0 1 0 {_fmt(cx - r)},{_fmt(cy)}Z"
    )


def _polygon_path(polygon: Polygon) -> str:
    head, *tail = polygon.points
    body = "".join(f"L{_fmt(x)},{_fmt(y)}" for x, y in tail)
    return f"M{_fmt(head[0])},{_fmt(head[1])}{body}Z"


def shape_to_path(shape: Shape) -> str:
    if isinstance(shape, RoundedRect):
        return _rounded_rect_path(shape)
    if isinstance(shape, Circle):
        return _circle_path(shape)
    return _polygon_path(shape)


def _gradient_defs(spec: QRSpec, x: float, y: float, size: float) -> str:
    if spec.gradient_type is GradientType.NONE or not (spec.gradient_start and spec.gradient_end):
        return ""

    stops = (
        f'<stop offset="0%" stop-color="{spec.gradient_start}"/>'
        f'<stop offset="100%" stop-color="{spec.gradient_end}"/>'
    )

    if spec.gradient_type is GradientType.RADIAL:
        return (
            f'<radialGradient id="{_DATA_GRADIENT_ID}" gradientUnits="userSpaceOnUse" '
            f'cx="{_fmt(x + size / 2)}" cy="{_fmt(y + size / 2)}" r="{_fmt(size * 0.72)}">'
            f"{stops}</radialGradient>"
        )

    angle = math.radians(spec.gradient_angle)
    dx, dy = math.cos(angle), math.sin(angle)
    cx, cy = x + size / 2, y + size / 2
    half = size / 2
    return (
        f'<linearGradient id="{_DATA_GRADIENT_ID}" gradientUnits="userSpaceOnUse" '
        f'x1="{_fmt(cx - dx * half)}" y1="{_fmt(cy - dy * half)}" '
        f'x2="{_fmt(cx + dx * half)}" y2="{_fmt(cy + dy * half)}">'
        f"{stops}</linearGradient>"
    )


def _module_fill(spec: QRSpec) -> str:
    if spec.gradient_type is not GradientType.NONE and spec.gradient_start and spec.gradient_end:
        return f"url(#{_DATA_GRADIENT_ID})"
    return spec.foreground


def _embed_logo(spec: QRSpec, reserve: RoundedRect) -> str:
    """Place the logo inside the reserved area, clipped to its shape."""
    if not spec.logo_bytes:
        return ""

    padding = reserve.width * (spec.logo_padding / max(spec.reserve_ratio, 1e-6)) * 0.5
    inner = max(reserve.width - 2 * padding, reserve.width * 0.6)
    inner_x = reserve.x + (reserve.width - inner) / 2
    inner_y = reserve.y + (reserve.height - inner) / 2

    parts: list[str] = []
    if spec.logo_background:
        # An opaque backdrop keeps the logo legible over dark modules; on a
        # transparent code it also guarantees the logo is not lost on a dark
        # surface.
        backdrop = "#FFFFFF" if spec.transparent_background else spec.background
        parts.append(f'<path d="{_rounded_rect_path(reserve)}" fill="{backdrop}"/>')

    clip_rect = RoundedRect(
        inner_x,
        inner_y,
        inner,
        inner,
        tuple(min(radius, inner / 2) for radius in reserve.radii),  # type: ignore[arg-type]
    )
    parts.append(
        f'<clipPath id="{_LOGO_CLIP_ID}"><path d="{_rounded_rect_path(clip_rect)}"/></clipPath>'
    )

    if spec.logo_is_svg:
        parts.append(
            f'<g clip-path="url(#{_LOGO_CLIP_ID})">'
            + _nested_svg(spec.logo_bytes, inner_x, inner_y, inner)
            + "</g>"
        )
    else:
        encoded = base64.b64encode(spec.logo_bytes).decode("ascii")
        mime = spec.logo_content_type or "image/png"
        parts.append(
            f'<image x="{_fmt(inner_x)}" y="{_fmt(inner_y)}" width="{_fmt(inner)}" '
            f'height="{_fmt(inner)}" preserveAspectRatio="xMidYMid meet" '
            f'clip-path="url(#{_LOGO_CLIP_ID})" '
            f'href="data:{mime};base64,{encoded}"/>'
        )
    return "".join(parts)


def _nested_svg(logo: bytes, x: float, y: float, size: float) -> str:
    """Re-frame an already-sanitised SVG so it fits the reserved square."""
    from xml.etree import ElementTree as ET

    try:
        root = safe_fromstring(logo.decode("utf-8"), forbid_dtd=True)
    except Exception:  # noqa: BLE001 - a broken logo must not break the QR code
        return ""

    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    root.set("x", _fmt(x))
    root.set("y", _fmt(y))
    root.set("width", _fmt(size))
    root.set("height", _fmt(size))
    root.set("preserveAspectRatio", "xMidYMid meet")

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="unicode")


def _frame_elements(spec: QRSpec, layout) -> str:  # noqa: ANN001 - Layout, avoids cycle
    if not layout.has_frame:
        return ""

    frame = RoundedRect(
        0,
        0,
        layout.canvas_width,
        layout.canvas_height,
        (layout.frame_radius,) * 4,
    )
    parts = [f'<path d="{_rounded_rect_path(frame)}" fill="{spec.frame_color}"/>']

    if spec.frame_style is FrameStyle.TICKET and layout.notch_radius:
        notch_y = layout.qr_y + layout.qr_size + layout.frame_thickness * 0.5
        for cx in (0.0, layout.canvas_width):
            parts.append(
                f'<circle cx="{_fmt(cx)}" cy="{_fmt(notch_y)}" '
                f'r="{_fmt(layout.notch_radius)}" fill="#FFFFFF"/>'
            )

    if layout.caption_box and layout.caption_text:
        box_x, box_y, box_w, box_h = layout.caption_box
        font_size = layout.caption_font_size
        parts.append(
            f'<text x="{_fmt(box_x + box_w / 2)}" y="{_fmt(box_y + box_h / 2)}" '
            f'fill="{spec.frame_text_color}" font-size="{_fmt(font_size)}" '
            'font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-weight="700" letter-spacing="{_fmt(font_size * 0.06)}" '
            'text-anchor="middle" dominant-baseline="central">'
            f"{escape(layout.caption_text)}</text>"
        )
    return "".join(parts)


def render_svg(spec: QRSpec, matrix: list[list[bool]] | None = None) -> bytes:
    """Render `spec` to a standalone SVG document."""
    geometry = build_geometry(spec, matrix)
    layout = compute_layout(spec)

    # Geometry coordinates are local to the QR square; the whole group is
    # translated into position so the frame can surround it.
    qr_parts: list[str] = []
    if not spec.transparent_background:
        qr_parts.append(
            f'<rect x="0" y="0" width="{_fmt(layout.qr_size)}" '
            f'height="{_fmt(layout.qr_size)}" fill="{spec.background}"/>'
        )

    module_fill = _module_fill(spec)
    eye_fill = spec.eye_color or module_fill
    ball_fill = spec.eye_ball_color or eye_fill

    data_path = "".join(shape_to_path(shape) for shape in geometry.data_shapes)
    if data_path:
        qr_parts.append(f'<path d="{data_path}" fill="{module_fill}" fill-rule="evenodd"/>')

    # Outer outline and punched hole share one path with evenodd fill, which
    # keeps the finder ring hollow without painting the background colour over it.
    ring_path = "".join(
        shape_to_path(ring.outer) + shape_to_path(ring.hole) for ring in geometry.eye_rings
    )
    if ring_path:
        qr_parts.append(f'<path d="{ring_path}" fill="{eye_fill}" fill-rule="evenodd"/>')

    ball_path = "".join(shape_to_path(shape) for shape in geometry.eye_balls)
    if ball_path:
        qr_parts.append(f'<path d="{ball_path}" fill="{ball_fill}"/>')

    if geometry.logo_reserve and spec.has_logo:
        qr_parts.append(_embed_logo(spec, geometry.logo_reserve))

    defs = _gradient_defs(spec, 0.0, 0.0, layout.qr_size)
    defs_block = f"<defs>{defs}</defs>" if defs else ""

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_fmt(layout.canvas_width)}" height="{_fmt(layout.canvas_height)}" '
        f'viewBox="0 0 {_fmt(layout.canvas_width)} {_fmt(layout.canvas_height)}" '
        'shape-rendering="geometricPrecision" role="img" '
        'aria-label="QR code linking to this group page">'
        f"{defs_block}"
        f"{_frame_elements(spec, layout)}"
        f'<g transform="translate({_fmt(layout.qr_x)},{_fmt(layout.qr_y)})">'
        f"{''.join(qr_parts)}"
        "</g>"
        "</svg>"
    )
    return svg.encode("utf-8")
