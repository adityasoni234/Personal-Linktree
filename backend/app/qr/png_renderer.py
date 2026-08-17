"""Raster (PNG) QR renderer.

Shapes are rasterised into single-channel masks at a supersampled resolution and
composited with a solid colour or a gradient, then downscaled — which gives
clean antialiased edges without pulling in a vector rasteriser for the common
case. The working resolution is capped so a large `size` request cannot be used
to exhaust server memory.
"""

from __future__ import annotations

import io
import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFont

from app.core.logging import app_logger
from app.models.enums import FrameStyle, GradientType, LogoShape
from app.qr.geometry import Circle, Polygon, RoundedRect, Shape, build_geometry
from app.qr.layout import compute_layout
from app.qr.spec import QRSpec
from app.security.colors import to_rgba

# Upper bound on the intermediate canvas; keeps peak memory bounded regardless
# of the requested output size.
MAX_WORK_PIXELS = 2560
GRADIENT_SOURCE_SIZE = 256

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)


# ---------------------------------------------------------------------------
# Shape rasterisation
# ---------------------------------------------------------------------------
def _draw_shape(draw: ImageDraw.ImageDraw, shape: Shape, scale: float,
                dx: float = 0.0, dy: float = 0.0) -> None:
    """Draw `shape` with value 255 onto a single-channel mask."""
    if isinstance(shape, Circle):
        cx, cy, r = (shape.cx + dx) * scale, (shape.cy + dy) * scale, shape.r * scale
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        return

    if isinstance(shape, Polygon):
        draw.polygon(
            [((x + dx) * scale, (y + dy) * scale) for x, y in shape.points], fill=255
        )
        return

    x0 = (shape.x + dx) * scale
    y0 = (shape.y + dy) * scale
    x1 = x0 + shape.width * scale
    y1 = y0 + shape.height * scale
    limit = min(shape.width, shape.height) * scale / 2
    tl, tr, br, bl = (min(radius * scale, limit) for radius in shape.radii)

    draw.rectangle([x0, y0, x1, y1], fill=255)
    if not any((tl, tr, br, bl)):
        return

    # Cut each rounded corner out of the rectangle, then paint the quarter disc
    # back in. Corner squares lie strictly inside this shape's own box, so this
    # never damages an adjacent module.
    corners = (
        (tl, (x0, y0, x0 + tl, y0 + tl), (x0, y0, x0 + 2 * tl, y0 + 2 * tl), 180, 270),
        (tr, (x1 - tr, y0, x1, y0 + tr), (x1 - 2 * tr, y0, x1, y0 + 2 * tr), 270, 360),
        (br, (x1 - br, y1 - br, x1, y1), (x1 - 2 * br, y1 - 2 * br, x1, y1), 0, 90),
        (bl, (x0, y1 - bl, x0 + bl, y1), (x0, y1 - 2 * bl, x0 + 2 * bl, y1), 90, 180),
    )
    for radius, square, pie_box, start, end in corners:
        if radius <= 0:
            continue
        draw.rectangle(square, fill=0)
        draw.pieslice(pie_box, start, end, fill=255)


def _shape_mask(size: tuple[int, int], shapes: list[Shape], scale: float) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for shape in shapes:
        _draw_shape(draw, shape, scale)
    return mask


# ---------------------------------------------------------------------------
# Paint
# ---------------------------------------------------------------------------
def _gradient_image(spec: QRSpec, size: int) -> Image.Image:
    """Build the gradient at low resolution and upscale — visually identical to
    computing it per pixel, and far cheaper."""
    start = to_rgba(spec.gradient_start or spec.foreground)[:3]
    end = to_rgba(spec.gradient_end or spec.foreground)[:3]
    source = Image.new("RGB", (GRADIENT_SOURCE_SIZE, GRADIENT_SOURCE_SIZE))
    pixels: list[tuple[int, int, int]] = []

    n = GRADIENT_SOURCE_SIZE
    if spec.gradient_type is GradientType.RADIAL:
        centre = (n - 1) / 2
        max_distance = math.hypot(centre, centre)
        for y in range(n):
            for x in range(n):
                t = min(1.0, math.hypot(x - centre, y - centre) / max_distance)
                pixels.append(
                    tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3))  # type: ignore[misc]
                )
    else:
        angle = math.radians(spec.gradient_angle)
        dx, dy = math.cos(angle), math.sin(angle)
        centre = (n - 1) / 2
        # Half-extent of the projection so t spans exactly [0, 1] across the box.
        half = (abs(dx) + abs(dy)) * centre or 1.0
        for y in range(n):
            for x in range(n):
                projection = (x - centre) * dx + (y - centre) * dy
                t = min(1.0, max(0.0, projection / (2 * half) + 0.5))
                pixels.append(
                    tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3))  # type: ignore[misc]
                )

    source.putdata(pixels)
    return source.resize((size, size), Image.BICUBIC)


def _paint(canvas: Image.Image, mask: Image.Image, colour: str | None,
           gradient: Image.Image | None, origin: tuple[int, int]) -> None:
    if gradient is not None and colour is None:
        layer = gradient.convert("RGBA")
        canvas.paste(layer, origin, mask)
    else:
        canvas.paste(to_rgba(colour or "#000000"), origin, mask)


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------
def _rasterise_svg(data: bytes, size: int) -> Image.Image | None:
    """Rasterise an already-sanitised SVG, if a rasteriser is installed."""
    try:
        import cairosvg  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001 - optional dependency / missing system libs
        app_logger.warning("svg_rasteriser_unavailable")
        return None
    try:
        png_bytes = cairosvg.svg2png(
            bytestring=data, output_width=size, output_height=size
        )
    except Exception as exc:  # noqa: BLE001 - a bad logo must not break the QR
        app_logger.warning("svg_rasterise_failed", extra={"error": str(exc)})
        return None
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def _load_logo(spec: QRSpec, size: int) -> Image.Image | None:
    if not spec.logo_bytes:
        return None
    if spec.logo_is_svg:
        return _rasterise_svg(spec.logo_bytes, size)
    try:
        with Image.open(io.BytesIO(spec.logo_bytes)) as image:
            logo = image.convert("RGBA")
            logo.thumbnail((size, size), Image.LANCZOS)
            return logo.copy()
    except Exception as exc:  # noqa: BLE001
        app_logger.warning("logo_load_failed", extra={"error": str(exc)})
        return None


def _shape_clip(image: Image.Image, shape: LogoShape) -> Image.Image:
    if shape is LogoShape.SQUARE:
        return image
    width, height = image.size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    if shape is LogoShape.CIRCLE:
        draw.ellipse([0, 0, width - 1, height - 1], fill=255)
    else:
        draw.rounded_rectangle(
            [0, 0, width - 1, height - 1], radius=int(min(width, height) * 0.18), fill=255
        )
    clipped = image.copy()
    clipped.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return clipped


# ---------------------------------------------------------------------------
# Caption
# ---------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _draw_caption(canvas: Image.Image, layout, spec: QRSpec, scale: float) -> None:  # noqa: ANN001
    if not (layout.caption_box and layout.caption_text):
        return
    box_x, box_y, box_w, box_h = (value * scale for value in layout.caption_box)
    draw = ImageDraw.Draw(canvas)
    font = _font(max(8, int(layout.caption_font_size * scale)))

    text = layout.caption_text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = box_x + (box_w - text_w) / 2 - bbox[0]
    y = box_y + (box_h - text_h) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=to_rgba(spec.frame_text_color))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render_png(spec: QRSpec, matrix: list[list[bool]] | None = None) -> bytes:
    geometry = build_geometry(spec, matrix)
    layout = compute_layout(spec)

    supersample = 3 if spec.size <= 720 else 2
    work_width = min(int(layout.canvas_width * supersample), MAX_WORK_PIXELS)
    scale = work_width / layout.canvas_width
    work_height = max(1, int(round(layout.canvas_height * scale)))
    work_size = (work_width, work_height)

    canvas = Image.new("RGBA", work_size, (0, 0, 0, 0))

    # ---- Frame -----------------------------------------------------------
    if layout.has_frame:
        frame_mask = _shape_mask(
            work_size,
            [
                RoundedRect(
                    0,
                    0,
                    layout.canvas_width,
                    layout.canvas_height,
                    (layout.frame_radius,) * 4,
                )
            ],
            scale,
        )
        canvas.paste(to_rgba(spec.frame_color), (0, 0), frame_mask)

        if spec.frame_style is FrameStyle.TICKET and layout.notch_radius:
            notch_y = layout.qr_y + layout.qr_size + layout.frame_thickness * 0.5
            notch_mask = _shape_mask(
                work_size,
                [
                    Circle(0.0, notch_y, layout.notch_radius),
                    Circle(layout.canvas_width, notch_y, layout.notch_radius),
                ],
                scale,
            )
            canvas.paste((0, 0, 0, 0), (0, 0), notch_mask)

    # ---- QR square -------------------------------------------------------
    qr_pixels = max(1, int(round(layout.qr_size * scale)))
    qr_canvas = Image.new(
        "RGBA",
        (qr_pixels, qr_pixels),
        (0, 0, 0, 0) if spec.transparent_background else to_rgba(spec.background),
    )

    use_gradient = (
        spec.gradient_type is not GradientType.NONE
        and spec.gradient_start
        and spec.gradient_end
    )
    gradient = _gradient_image(spec, qr_pixels) if use_gradient else None

    data_mask = _shape_mask((qr_pixels, qr_pixels), geometry.data_shapes, scale)
    _paint(qr_canvas, data_mask, None if use_gradient else spec.foreground, gradient, (0, 0))

    # Finder rings: draw the outline, subtract the hole, so the centre stays
    # transparent instead of being over-painted with the background colour.
    ring_mask = Image.new("L", (qr_pixels, qr_pixels), 0)
    ring_draw = ImageDraw.Draw(ring_mask)
    hole_mask = Image.new("L", (qr_pixels, qr_pixels), 0)
    hole_draw = ImageDraw.Draw(hole_mask)
    for ring in geometry.eye_rings:
        _draw_shape(ring_draw, ring.outer, scale)
        _draw_shape(hole_draw, ring.hole, scale)
    ring_mask = ImageChops.subtract(ring_mask, hole_mask)

    eye_colour = spec.eye_color
    _paint(
        qr_canvas,
        ring_mask,
        eye_colour if eye_colour else (None if use_gradient else spec.foreground),
        gradient,
        (0, 0),
    )

    ball_mask = _shape_mask((qr_pixels, qr_pixels), geometry.eye_balls, scale)
    ball_colour = spec.eye_ball_color or spec.eye_color
    _paint(
        qr_canvas,
        ball_mask,
        ball_colour if ball_colour else (None if use_gradient else spec.foreground),
        gradient,
        (0, 0),
    )

    # ---- Logo ------------------------------------------------------------
    if geometry.logo_reserve and spec.has_logo:
        reserve = geometry.logo_reserve
        reserve_px = max(1, int(round(reserve.width * scale)))
        reserve_x = int(round(reserve.x * scale))
        reserve_y = int(round(reserve.y * scale))

        if spec.logo_background:
            backdrop_mask = _shape_mask((qr_pixels, qr_pixels), [reserve], scale)
            backdrop = "#FFFFFF" if spec.transparent_background else spec.background
            qr_canvas.paste(to_rgba(backdrop), (0, 0), backdrop_mask)

        padding_px = int(reserve_px * 0.12)
        inner_px = max(8, reserve_px - 2 * padding_px)
        logo = _load_logo(spec, inner_px)
        if logo is not None:
            logo = _shape_clip(logo, spec.logo_shape)
            paste_x = reserve_x + (reserve_px - logo.width) // 2
            paste_y = reserve_y + (reserve_px - logo.height) // 2
            qr_canvas.alpha_composite(logo, (paste_x, paste_y))

    canvas.alpha_composite(
        qr_canvas, (int(round(layout.qr_x * scale)), int(round(layout.qr_y * scale)))
    )

    _draw_caption(canvas, layout, spec, scale)

    # ---- Downscale and encode -------------------------------------------
    final_width = int(round(layout.canvas_width))
    final_height = int(round(layout.canvas_height))
    output = canvas.resize((final_width, final_height), Image.LANCZOS)
    if not spec.transparent_background and not layout.has_frame:
        flattened = Image.new("RGB", output.size, to_rgba(spec.background)[:3])
        flattened.paste(output, mask=output.getchannel("A"))
        output = flattened

    buffer = io.BytesIO()
    output.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
