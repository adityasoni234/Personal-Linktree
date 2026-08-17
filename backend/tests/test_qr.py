"""QR generation: rendering, styling, scannability guards and the target-URL invariant."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.models.enums import (
    DotStyle,
    ErrorCorrection,
    EyeBallStyle,
    EyeFrameStyle,
    FrameStyle,
    GradientType,
)
from app.qr.engine import render_sync
from app.qr.geometry import build_matrix
from app.qr.presets import PRESETS, get_preset, preset_catalogue
from app.qr.spec import QRSpec, clamp_size, scannability_report, validate_spec
from app.security.colors import contrast_ratio

TARGET = "https://linkhub.ieeesou.org/g/computer-society?src=qr"


def spec(**overrides) -> QRSpec:
    overrides.setdefault("size", 256)
    return QRSpec(data=TARGET, **overrides)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def test_png_render_produces_a_png():
    payload = render_sync(spec(), "png")
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(payload) > 500


def test_svg_render_produces_an_svg():
    payload = render_sync(spec(), "svg")
    assert payload.startswith(b'<?xml version="1.0"')
    assert b"<svg" in payload
    # Self-contained: nothing is fetched from another host at view time.
    assert b"http://" not in payload.replace(b"http://www.w3.org/2000/svg", b"")


@pytest.mark.parametrize("dot_style", list(DotStyle))
def test_every_module_style_renders(dot_style):
    assert render_sync(spec(dot_style=dot_style), "png")[:8] == b"\x89PNG\r\n\x1a\n"
    assert b"<svg" in render_sync(spec(dot_style=dot_style), "svg")


@pytest.mark.parametrize("eye_frame", list(EyeFrameStyle))
@pytest.mark.parametrize("eye_ball", list(EyeBallStyle))
def test_every_finder_combination_renders(eye_frame, eye_ball):
    payload = render_sync(spec(eye_frame_style=eye_frame, eye_ball_style=eye_ball), "svg")
    assert b"<svg" in payload


@pytest.mark.parametrize("frame_style", list(FrameStyle))
def test_every_frame_style_renders(frame_style):
    payload = render_sync(spec(frame_style=frame_style, caption="SCAN ME"), "png")
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("gradient", [GradientType.LINEAR, GradientType.RADIAL])
def test_gradients_render(gradient):
    rendered = spec(
        gradient_type=gradient, gradient_start="#0B2545", gradient_end="#00A3E0"
    )
    assert render_sync(rendered, "png")[:8] == b"\x89PNG\r\n\x1a\n"
    assert b"Gradient" in render_sync(rendered, "svg")


def test_transparent_background_produces_an_alpha_channel():
    from PIL import Image
    import io

    payload = render_sync(spec(transparent_background=True), "png")
    with Image.open(io.BytesIO(payload)) as image:
        assert image.mode == "RGBA"
        assert image.getextrema()[3][0] == 0  # at least one fully transparent pixel


# ---------------------------------------------------------------------------
# Scannability
# ---------------------------------------------------------------------------
def test_low_contrast_is_reported_as_unscannable():
    report = scannability_report(
        validate_spec(spec(foreground="#EEEEEE", background="#FFFFFF"))
    )
    assert report["is_scannable"] is False
    assert any(item["severity"] == "error" for item in report["warnings"])


def test_high_contrast_is_reported_as_scannable():
    report = scannability_report(validate_spec(spec()))
    assert report["is_scannable"] is True
    assert report["contrast_ratio"] >= 3.0


def test_a_logo_forces_maximum_error_correction():
    with_logo = spec(logo_bytes=b"\x89PNG\r\n\x1a\n", error_correction=ErrorCorrection.L)
    assert with_logo.effective_error_correction is ErrorCorrection.H


def test_an_oversized_logo_warns():
    report = scannability_report(
        validate_spec(spec(logo_bytes=b"\x89PNG\r\n\x1a\n", logo_size=0.29))
    )
    assert any(item["field"] == "logo_size" for item in report["warnings"])


def test_a_tiny_quiet_zone_warns():
    report = scannability_report(validate_spec(spec(margin=1)))
    assert any(item["field"] == "margin" for item in report["warnings"])


def test_logo_size_is_range_checked():
    with pytest.raises(ValidationError):
        validate_spec(spec(logo_bytes=b"x", logo_size=0.6))


def test_margin_is_range_checked():
    with pytest.raises(ValidationError):
        validate_spec(spec(margin=99))


def test_a_gradient_needs_both_stops():
    with pytest.raises(ValidationError):
        validate_spec(spec(gradient_type=GradientType.LINEAR, gradient_start="#000000"))


def test_invalid_colour_is_rejected():
    with pytest.raises(ValidationError):
        validate_spec(spec(foreground="not-a-colour"))


# ---------------------------------------------------------------------------
# Abuse prevention
# ---------------------------------------------------------------------------
def test_output_size_is_bounded():
    with pytest.raises(ValidationError):
        clamp_size(100_000)
    with pytest.raises(ValidationError):
        clamp_size(1)
    assert clamp_size(1024) == 1024


def test_cache_key_changes_with_every_visual_parameter():
    base = validate_spec(spec())
    variants = [
        spec(foreground="#111111"),
        spec(background="#EEEEEE"),
        spec(dot_style=DotStyle.DOT),
        spec(eye_frame_style=EyeFrameStyle.CIRCLE),
        spec(margin=6),
        spec(caption="SCAN"),
        spec(size=512),
    ]
    keys = {validate_spec(variant).cache_key() for variant in variants}
    assert base.cache_key() not in keys
    assert len(keys) == len(variants)


def test_cache_key_is_stable_for_identical_input():
    assert validate_spec(spec()).cache_key() == validate_spec(spec()).cache_key()


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------
def test_all_documented_presets_exist():
    assert set(PRESETS) == {
        "ieee-classic",
        "minimal",
        "professional",
        "event",
        "modern",
        "dark",
    }


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_preset_is_scannable_and_renders(name):
    values = get_preset(name)
    assert values is not None

    rendered = QRSpec(
        data=TARGET,
        size=256,
        foreground=values["foreground_color"],
        background=values["background_color"],
        gradient_type=values["gradient_type"],
        gradient_start=values.get("gradient_start_color"),
        gradient_end=values.get("gradient_end_color"),
        dot_style=values["dot_style"],
        eye_frame_style=values["eye_frame_style"],
        eye_ball_style=values["eye_ball_style"],
        margin=values["margin"],
        error_correction=values["error_correction"],
        frame_style=values["frame_style"],
        caption=values.get("caption"),
    )
    assert scannability_report(validate_spec(rendered))["is_scannable"] is True
    assert render_sync(rendered, "png")[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_preset_meets_the_contrast_floor(name):
    values = get_preset(name)
    assert values is not None
    foreground = values.get("gradient_start_color") or values["foreground_color"]
    assert contrast_ratio(foreground, values["background_color"]) >= 3.0


def test_preset_catalogue_is_json_serialisable():
    import json

    assert json.dumps(preset_catalogue())


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------
def test_higher_error_correction_produces_a_denser_matrix():
    low = len(build_matrix(TARGET, ErrorCorrection.L))
    high = len(build_matrix(TARGET, ErrorCorrection.H))
    assert high >= low


def test_matrix_is_square_and_has_finder_patterns():
    matrix = build_matrix(TARGET, ErrorCorrection.Q)
    assert all(len(row) == len(matrix) for row in matrix)
    # Top-left finder: a filled 7x7 ring.
    assert all(matrix[0][column] for column in range(7))
    assert all(matrix[row][0] for row in range(7))


# ---------------------------------------------------------------------------
# The invariant that matters most
# ---------------------------------------------------------------------------
@pytest.mark.security
@pytest.mark.asyncio
async def test_qr_always_encodes_the_group_page_never_a_client_supplied_url(member_client):
    group = (
        await member_client.post("/api/v1/groups", json={"name": "QR Target Test"})
    ).json()["data"]

    # Try to smuggle a different destination through the preview payload.
    response = await member_client.post(
        f"/api/v1/groups/{group['id']}/qr/preview",
        json={
            "foreground_color": "#00629B",
            "background_color": "#FFFFFF",
            "data": "https://evil.example/phish",
            "target_url": "https://evil.example/phish",
            "size": 256,
        },
    )
    # Unknown fields are refused outright by the schema.
    assert response.status_code == 422

    saved = await member_client.get(f"/api/v1/groups/{group['id']}/qr")
    assert saved.status_code == 200
    target = saved.json()["data"]["render"]["target_url"]
    assert target.endswith("/g/qr-target-test?src=qr")
    assert "evil.example" not in target


@pytest.mark.asyncio
async def test_qr_download_returns_the_right_content_types(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Download Me"})).json()[
        "data"
    ]

    png = await member_client.get(f"/api/v1/groups/{group['id']}/qr.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert 'filename="download-me-qr.png"' in png.headers["content-disposition"]

    svg = await member_client.get(f"/api/v1/groups/{group['id']}/qr.svg")
    assert svg.status_code == 200
    assert svg.headers["content-type"] == "image/svg+xml"


@pytest.mark.asyncio
async def test_saving_an_unscannable_design_is_refused(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Bad Design"})).json()[
        "data"
    ]

    response = await member_client.post(
        f"/api/v1/groups/{group['id']}/qr",
        json={"foreground_color": "#F5F5F5", "background_color": "#FFFFFF"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QR_NOT_SCANNABLE"


@pytest.mark.asyncio
async def test_applying_a_preset_updates_the_stored_design(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Preset Group"})).json()[
        "data"
    ]

    response = await member_client.post(f"/api/v1/groups/{group['id']}/qr/preset/modern")
    assert response.status_code == 200
    config = response.json()["data"]["config"]
    assert config["preset"] == "modern"
    assert config["dot_style"] == "dot"


@pytest.mark.asyncio
async def test_unknown_preset_is_rejected(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "No Preset"})).json()[
        "data"
    ]
    response = await member_client.post(f"/api/v1/groups/{group['id']}/qr/preset/does-not-exist")
    assert response.status_code == 404


def test_low_contrast_finder_pattern_is_reported():
    """A scanner locates a code by its corner markers before reading any data."""
    report = scannability_report(
        validate_spec(spec(eye_color="#EFEFEF", background="#FFFFFF"))
    )
    assert report["is_scannable"] is False
    assert any(item["field"] == "eye_color" for item in report["warnings"])
