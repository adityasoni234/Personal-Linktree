"""QR matrix generation and shape layout.

Both renderers (SVG and PNG) consume the same geometry, so a design looks
identical in a vector download and in a raster export. Coordinates are in
pixels of the QR square, with the origin at its top-left corner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import qrcode
from qrcode.constants import (
    ERROR_CORRECT_H,
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
)

from app.models.enums import DotStyle, ErrorCorrection, EyeBallStyle, EyeFrameStyle
from app.qr.spec import QRSpec

_ERROR_CORRECTION_MAP = {
    ErrorCorrection.L: ERROR_CORRECT_L,
    ErrorCorrection.M: ERROR_CORRECT_M,
    ErrorCorrection.Q: ERROR_CORRECT_Q,
    ErrorCorrection.H: ERROR_CORRECT_H,
}

FINDER_SIZE = 7
EYE_BALL_SIZE = 3


# ---------------------------------------------------------------------------
# Shape vocabulary
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RoundedRect:
    x: float
    y: float
    width: float
    height: float
    # clockwise from top-left
    radii: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class Circle:
    cx: float
    cy: float
    r: float


@dataclass(frozen=True, slots=True)
class Polygon:
    points: tuple[tuple[float, float], ...]


Shape = RoundedRect | Circle | Polygon


@dataclass(frozen=True, slots=True)
class Ring:
    """An outline: `outer` filled, `hole` punched out of it."""

    outer: Shape
    hole: Shape


@dataclass(slots=True)
class QRGeometry:
    size: float
    module_count: int
    module_px: float
    offset: float
    data_shapes: list[Shape] = field(default_factory=list)
    eye_rings: list[Ring] = field(default_factory=list)
    eye_balls: list[Shape] = field(default_factory=list)
    logo_reserve: RoundedRect | None = None


def build_matrix(data: str, error_correction: ErrorCorrection) -> list[list[bool]]:
    code = qrcode.QRCode(
        version=None,
        error_correction=_ERROR_CORRECTION_MAP[error_correction],
        box_size=1,
        border=0,
    )
    code.add_data(data)
    code.make(fit=True)
    return [[bool(cell) for cell in row] for row in code.get_matrix()]


def _finder_origins(module_count: int) -> tuple[tuple[int, int], ...]:
    last = module_count - FINDER_SIZE
    return ((0, 0), (0, last), (last, 0))


def _in_finder(row: int, col: int, module_count: int) -> bool:
    return any(
        origin_row <= row < origin_row + FINDER_SIZE
        and origin_col <= col < origin_col + FINDER_SIZE
        for origin_row, origin_col in _finder_origins(module_count)
    )


def _neighbours(matrix: list[list[bool]], row: int, col: int) -> tuple[bool, bool, bool, bool]:
    """(up, right, down, left) presence flags."""
    count = len(matrix)

    def filled(r: int, c: int) -> bool:
        return 0 <= r < count and 0 <= c < count and matrix[r][c]

    return filled(row - 1, col), filled(row, col + 1), filled(row + 1, col), filled(row, col - 1)


def _module_shape(
    style: DotStyle,
    x: float,
    y: float,
    m: float,
    neighbours: tuple[bool, bool, bool, bool],
) -> Shape:
    up, right, down, left = neighbours
    full = m / 2

    if style is DotStyle.SQUARE:
        return RoundedRect(x, y, m, m)

    if style is DotStyle.DOT:
        return Circle(x + full, y + full, full * 0.86)

    if style is DotStyle.DIAMOND:
        return Polygon(
            ((x + full, y), (x + m, y + full), (x + full, y + m), (x, y + full))
        )

    if style is DotStyle.ROUNDED:
        # Round only the corners that are not shared with a neighbour, so runs
        # of modules stay visually connected and remain easy to decode.
        return RoundedRect(
            x,
            y,
            m,
            m,
            (
                0.0 if (up or left) else full,
                0.0 if (up or right) else full,
                0.0 if (down or right) else full,
                0.0 if (down or left) else full,
            ),
        )

    if style is DotStyle.CLASSY:
        # Asymmetric: only the top-left and bottom-right corners are cut.
        return RoundedRect(
            x,
            y,
            m,
            m,
            (
                0.0 if (up or left) else full,
                0.0,
                0.0 if (down or right) else full,
                0.0,
            ),
        )

    return RoundedRect(x, y, m, m)


def _run_shapes(
    matrix: list[list[bool]],
    skip: set[tuple[int, int]],
    module_px: float,
    offset: float,
    *,
    vertical: bool,
) -> list[Shape]:
    """Merge consecutive modules into rounded bars (vertical/horizontal styles)."""
    count = len(matrix)
    thickness = module_px * 0.86
    inset = (module_px - thickness) / 2
    shapes: list[Shape] = []

    outer = range(count)
    for primary in outer:
        run_start: int | None = None
        for secondary in range(count + 1):
            if secondary < count:
                row, col = (secondary, primary) if vertical else (primary, secondary)
                filled = matrix[row][col] and (row, col) not in skip
            else:
                filled = False

            if filled and run_start is None:
                run_start = secondary
            elif not filled and run_start is not None:
                length = (secondary - run_start) * module_px
                if vertical:
                    x = offset + primary * module_px + inset
                    y = offset + run_start * module_px
                    shapes.append(
                        RoundedRect(x, y, thickness, length, (thickness / 2,) * 4)
                    )
                else:
                    x = offset + run_start * module_px
                    y = offset + primary * module_px + inset
                    shapes.append(
                        RoundedRect(x, y, length, thickness, (thickness / 2,) * 4)
                    )
                run_start = None
    return shapes


def _eye_ring(style: EyeFrameStyle, x: float, y: float, side: float, m: float) -> Ring:
    hole_side = side - 2 * m
    hole_x, hole_y = x + m, y + m

    if style is EyeFrameStyle.CIRCLE:
        return Ring(
            Circle(x + side / 2, y + side / 2, side / 2),
            Circle(x + side / 2, y + side / 2, hole_side / 2),
        )

    if style is EyeFrameStyle.ROUNDED:
        radius = side * 0.28
        return Ring(
            RoundedRect(x, y, side, side, (radius,) * 4),
            RoundedRect(hole_x, hole_y, hole_side, hole_side, (max(radius - m, 0.0),) * 4),
        )

    if style is EyeFrameStyle.LEAF:
        radius = side * 0.5
        inner = max(radius - m, 0.0)
        return Ring(
            RoundedRect(x, y, side, side, (radius, 0.0, radius, 0.0)),
            RoundedRect(hole_x, hole_y, hole_side, hole_side, (inner, 0.0, inner, 0.0)),
        )

    if style is EyeFrameStyle.SHIELD:
        top, bottom = side * 0.45, side * 0.12
        return Ring(
            RoundedRect(x, y, side, side, (top, top, bottom, bottom)),
            RoundedRect(
                hole_x,
                hole_y,
                hole_side,
                hole_side,
                (max(top - m, 0.0), max(top - m, 0.0), max(bottom - m, 0.0), max(bottom - m, 0.0)),
            ),
        )

    return Ring(
        RoundedRect(x, y, side, side),
        RoundedRect(hole_x, hole_y, hole_side, hole_side),
    )


def _eye_ball(style: EyeBallStyle, x: float, y: float, side: float) -> Shape:
    if style is EyeBallStyle.CIRCLE:
        return Circle(x + side / 2, y + side / 2, side / 2)
    if style is EyeBallStyle.ROUNDED:
        return RoundedRect(x, y, side, side, (side * 0.3,) * 4)
    if style is EyeBallStyle.DIAMOND:
        half = side / 2
        return Polygon(
            ((x + half, y), (x + side, y + half), (x + half, y + side), (x, y + half))
        )
    return RoundedRect(x, y, side, side)


def build_geometry(spec: QRSpec, matrix: list[list[bool]] | None = None) -> QRGeometry:
    matrix = matrix or build_matrix(spec.data, spec.effective_error_correction)
    module_count = len(matrix)

    total_modules = module_count + 2 * spec.margin
    module_px = spec.size / total_modules
    offset = spec.margin * module_px
    content_px = module_count * module_px

    geometry = QRGeometry(
        size=spec.size,
        module_count=module_count,
        module_px=module_px,
        offset=offset,
    )

    # ---- Logo reserve ----------------------------------------------------
    skip: set[tuple[int, int]] = set()
    if spec.has_logo and spec.reserve_ratio > 0:
        reserve_px = content_px * spec.reserve_ratio
        reserve_x = offset + (content_px - reserve_px) / 2
        reserve_y = offset + (content_px - reserve_px) / 2
        radius = {
            "square": 0.0,
            "rounded": reserve_px * 0.18,
            "circle": reserve_px / 2,
        }[spec.logo_shape.value]
        geometry.logo_reserve = RoundedRect(
            reserve_x, reserve_y, reserve_px, reserve_px, (radius,) * 4
        )
        for row in range(module_count):
            for col in range(module_count):
                cx = offset + (col + 0.5) * module_px
                cy = offset + (row + 0.5) * module_px
                if (
                    reserve_x <= cx <= reserve_x + reserve_px
                    and reserve_y <= cy <= reserve_y + reserve_px
                ):
                    skip.add((row, col))

    # ---- Data modules ----------------------------------------------------
    for row in range(module_count):
        for col in range(module_count):
            if _in_finder(row, col, module_count):
                skip.add((row, col))

    if spec.dot_style in (DotStyle.VERTICAL, DotStyle.HORIZONTAL):
        geometry.data_shapes = _run_shapes(
            matrix,
            skip,
            module_px,
            offset,
            vertical=spec.dot_style is DotStyle.VERTICAL,
        )
    else:
        for row in range(module_count):
            for col in range(module_count):
                if not matrix[row][col] or (row, col) in skip:
                    continue
                geometry.data_shapes.append(
                    _module_shape(
                        spec.dot_style,
                        offset + col * module_px,
                        offset + row * module_px,
                        module_px,
                        _neighbours(matrix, row, col),
                    )
                )

    # ---- Finder patterns -------------------------------------------------
    finder_px = FINDER_SIZE * module_px
    ball_px = EYE_BALL_SIZE * module_px
    for origin_row, origin_col in _finder_origins(module_count):
        x = offset + origin_col * module_px
        y = offset + origin_row * module_px
        geometry.eye_rings.append(
            _eye_ring(spec.eye_frame_style, x, y, finder_px, module_px)
        )
        geometry.eye_balls.append(
            _eye_ball(
                spec.eye_ball_style,
                x + 2 * module_px,
                y + 2 * module_px,
                ball_px,
            )
        )

    return geometry
