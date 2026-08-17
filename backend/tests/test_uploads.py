"""Upload validation: SVG sanitisation, type sniffing and size limits."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.errors import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError
from app.security.image_validation import build_storage_key, sniff_content_type, validate_image
from app.security.svg_sanitizer import sanitize_svg

pytestmark = pytest.mark.security


def make_png(size: tuple[int, int] = (256, 256), color=(0, 98, 155, 255)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# SVG sanitisation
# ---------------------------------------------------------------------------
MALICIOUS_SVGS = {
    "script tag": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    "event handler": b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect width="10" height="10"/></svg>',
    "click handler": b'<svg xmlns="http://www.w3.org/2000/svg"><rect onclick="alert(1)" width="10" height="10"/></svg>',
    "foreignObject": b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><body xmlns="http://www.w3.org/1999/xhtml"><script>alert(1)</script></body></foreignObject></svg>',
    "external image": b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.example/track.png"/></svg>',
    "animate": b'<svg xmlns="http://www.w3.org/2000/svg"><animate attributeName="href" values="javascript:alert(1)"/></svg>',
    "css url": b'<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(javascript:alert(1))" width="10" height="10"/></svg>',
    "style import": b'<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(https://evil.example/x.css);</style></svg>',
    "xlink javascript": b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="javascript:alert(1)"><rect width="10" height="10"/></a></svg>',
}


@pytest.mark.parametrize("name,payload", MALICIOUS_SVGS.items(), ids=list(MALICIOUS_SVGS))
def test_malicious_svg_payloads_are_neutralised(name, payload):
    cleaned = sanitize_svg(payload).lower()

    assert b"<script" not in cleaned
    assert b"javascript:" not in cleaned
    assert b"onload" not in cleaned
    assert b"onclick" not in cleaned
    assert b"foreignobject" not in cleaned
    assert b"@import" not in cleaned
    assert b"evil.example" not in cleaned


def test_xxe_entity_declaration_is_rejected():
    payload = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>'
    )
    with pytest.raises(ValidationError):
        sanitize_svg(payload)


def test_billion_laughs_is_rejected():
    payload = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg"><text>&lol2;</text></svg>'
    )
    with pytest.raises(ValidationError):
        sanitize_svg(payload)


def test_oversized_svg_is_rejected():
    payload = b'<svg xmlns="http://www.w3.org/2000/svg">' + b"<rect/>" * 200_000 + b"</svg>"
    with pytest.raises(ValidationError):
        sanitize_svg(payload)


def test_safe_svg_content_is_preserved():
    payload = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        b'<path d="M4 4h16v16H4z" fill="#00629B"/>'
        b"</svg>"
    )
    cleaned = sanitize_svg(payload)
    assert b"M4 4h16v16H4z" in cleaned
    assert b"#00629B" in cleaned
    assert b"viewBox" in cleaned


def test_internal_fragment_references_survive():
    payload = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        b'<defs><linearGradient id="g"><stop offset="0" stop-color="#000"/></linearGradient></defs>'
        b'<rect width="10" height="10" fill="url(#g)"/>'
        b"</svg>"
    )
    cleaned = sanitize_svg(payload)
    assert b"url(#g)" in cleaned


# ---------------------------------------------------------------------------
# Type sniffing
# ---------------------------------------------------------------------------
def test_content_type_is_taken_from_the_bytes():
    assert sniff_content_type(make_png()) == "image/png"
    assert sniff_content_type(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>') == "image/svg+xml"
    assert sniff_content_type(b"not an image at all") is None


def test_executable_disguised_as_png_is_rejected():
    payload = b"MZ\x90\x00" + b"\x00" * 100  # a Windows PE header
    with pytest.raises(UnsupportedMediaTypeError):
        validate_image(payload, filename="logo.png", declared_content_type="image/png")


def test_html_polyglot_is_rejected():
    payload = b"<html><script>alert(1)</script></html>"
    with pytest.raises(UnsupportedMediaTypeError):
        validate_image(payload, filename="logo.png")


def test_declared_type_must_match_the_actual_bytes():
    with pytest.raises(UnsupportedMediaTypeError):
        validate_image(make_png(), filename="logo.png", declared_content_type="image/svg+xml")


def test_extension_must_match_the_actual_bytes():
    with pytest.raises(UnsupportedMediaTypeError):
        validate_image(make_png(), filename="logo.svg")


def test_gif_is_rejected_with_a_clear_message():
    with pytest.raises(UnsupportedMediaTypeError):
        validate_image(b"GIF89a" + b"\x00" * 64, filename="logo.gif")


def test_oversized_upload_is_rejected():
    with pytest.raises(PayloadTooLargeError):
        validate_image(make_png(), max_bytes=64, filename="logo.png")


def test_tiny_image_is_rejected():
    with pytest.raises(ValidationError):
        validate_image(make_png((8, 8)), filename="logo.png")


def test_raster_is_re_encoded_and_metadata_stripped():
    """Re-encoding removes EXIF/GPS and destroys appended payloads."""
    buffer = io.BytesIO()
    image = Image.new("RGB", (128, 128), (255, 0, 0))
    image.save(buffer, format="JPEG", exif=b"Exif\x00\x00sensitive-gps-data")
    payload = buffer.getvalue() + b"<?php system($_GET['c']); ?>"

    result = validate_image(payload, filename="photo.jpg")

    assert result.content_type == "image/png"
    assert b"sensitive-gps-data" not in result.content
    assert b"<?php" not in result.content


def test_large_image_is_downscaled():
    result = validate_image(make_png((2000, 2000)), filename="big.png")
    assert max(result.width, result.height) <= 1024


def test_svg_can_be_refused_where_it_is_not_wanted():
    payload = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    with pytest.raises(UnsupportedMediaTypeError):
        validate_image(payload, filename="logo.svg", allow_svg=False)


# ---------------------------------------------------------------------------
# Storage keys
# ---------------------------------------------------------------------------
def test_storage_keys_are_server_generated():
    first = build_storage_key("org-id/qr_logo", "png")
    second = build_storage_key("org-id/qr_logo", "png")

    assert first != second
    assert first.startswith("org-id/qr_logo/")
    assert first.endswith(".png")
    assert ".." not in first


def test_storage_key_rejects_an_unknown_extension():
    with pytest.raises(UnsupportedMediaTypeError):
        build_storage_key("org-id/qr_logo", "php")


@pytest.mark.asyncio
async def test_local_storage_rejects_path_traversal(tmp_path):
    from app.storage.local import LocalStorage

    storage = LocalStorage(root=str(tmp_path), base_url="http://testserver/media")

    for key in ("../escape.png", "/etc/passwd", "a/../../b.png", "back\\slash.png"):
        with pytest.raises(ValidationError):
            await storage.save(key, b"x", content_type="image/png")


@pytest.mark.asyncio
async def test_upload_endpoint_accepts_a_valid_png(member_client):
    response = await member_client.post(
        "/api/v1/media",
        params={"kind": "GROUP_LOGO"},
        files={"file": ("logo.png", make_png(), "image/png")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_a_malicious_svg(member_client):
    payload = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect width="10" height="10"/></svg>'

    response = await member_client.post(
        "/api/v1/media",
        params={"kind": "QR_LOGO"},
        files={"file": ("logo.svg", payload, "image/svg+xml")},
    )
    # Sanitised rather than refused — but the handler must be gone.
    assert response.status_code == 201, response.text

    from app.storage import get_storage

    stored = await get_storage().load(
        response.json()["data"]["public_url"].split("/media/", 1)[1]
    )
    assert stored is not None
    assert b"onload" not in stored.lower()
