"""Input validation: URL schemes, slugs, injection payloads and pagination."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.security.sanitize import clean_text
from app.security.slug import validate_slug
from app.security.url_validation import validate_link_url

pytestmark = pytest.mark.security


# ---------------------------------------------------------------------------
# URL scheme allowlist (unit)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "  javascript:alert(document.cookie)",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "about:blank",
        "blob:https://example.com/uuid",
        "chrome://settings",
        "ftp://files.example.com/x",
        "jar:http://example.com!/",
        "view-source:https://example.com",
    ],
)
def test_dangerous_url_schemes_are_rejected(payload):
    with pytest.raises(ValidationError):
        validate_link_url(payload)


@pytest.mark.parametrize(
    "payload",
    [
        "java\nscript:alert(1)",
        "java\tscript:alert(1)",
        "https://example.com\\@evil.com",
        "https://user:password@evil.com",
    ],
)
def test_obfuscated_and_credential_urls_are_rejected(payload):
    with pytest.raises(ValidationError):
        validate_link_url(payload)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://instagram.com/ieeesou", "https://instagram.com/ieeesou"),
        ("ieeesou.org", "https://ieeesou.org/"),
        ("HTTPS://IEEESOU.ORG/Events", "https://ieeesou.org/Events"),
        ("mailto:Chair@IEEESOU.org", "mailto:Chair@IEEESOU.org"),
        ("tel:+91 90000 00000", "tel:+919000000000"),
    ],
)
def test_safe_urls_are_normalised(raw, expected):
    assert validate_link_url(raw) == expected


def test_url_length_is_capped():
    with pytest.raises(ValidationError):
        validate_link_url("https://example.com/" + "a" * 4000)


def test_host_without_a_dot_is_rejected():
    with pytest.raises(ValidationError):
        validate_link_url("https://localhost")


# ---------------------------------------------------------------------------
# Slugs (unit)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "slug",
    ["admin", "api", "login", "register", "settings", "dashboard", "auth", "qr", "g"],
)
def test_reserved_slugs_are_rejected(slug):
    with pytest.raises(ValidationError):
        validate_slug(slug)


@pytest.mark.parametrize(
    "slug",
    [
        "../../etc/passwd",
        "computer society",
        "Computer-Society!",
        "-leading",
        "trailing-",
        "double--hyphen",
        "ab",
        "a" * 60,
        "12345",
        "<script>",
    ],
)
def test_malformed_slugs_are_rejected(slug):
    with pytest.raises(ValidationError):
        validate_slug(slug)


def test_valid_slug_is_normalised():
    assert validate_slug("  Computer-Society  ") == "computer-society"


# ---------------------------------------------------------------------------
# Text sanitisation (unit)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("<script>alert(1)</script>", "alert(1)"),
        ("<img src=x onerror=alert(1)>", None),
        ("Hello <b>world</b>", "Hello world"),
        ("Zero​width", "Zerowidth"),
        ("Bidi‮override", "Bidioverride"),
        ("  spaced   out  ", "spaced out"),
    ],
)
def test_markup_and_invisible_characters_are_stripped(raw, expected):
    assert clean_text(raw, max_length=200) == expected


def test_control_characters_are_removed():
    assert clean_text("bell\x07null\x00", max_length=50) == "bellnull"


# ---------------------------------------------------------------------------
# API-level validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_api_rejects_a_javascript_link(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Payload Group"})).json()[
        "data"
    ]

    response = await member_client.post(
        f"/api/v1/groups/{group['id']}/links",
        json={"title": "Bad", "url": "javascript:alert(document.cookie)"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_strips_markup_from_a_group_name(member_client):
    response = await member_client.post(
        "/api/v1/groups",
        json={
            "name": "<script>alert('xss')</script>Robotics",
            "description": "<img src=x onerror=alert(1)>Safe description",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "<script>" not in data["name"]
    assert "onerror" not in (data["description"] or "")


@pytest.mark.asyncio
async def test_api_rejects_a_reserved_slug(member_client):
    response = await member_client.post(
        "/api/v1/groups", json={"name": "Admin Panel", "slug": "admin"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_slug_is_rejected_when_explicitly_requested(member_client):
    await member_client.post("/api/v1/groups", json={"name": "First", "slug": "shared-slug"})
    second = await member_client.post(
        "/api/v1/groups", json={"name": "Second", "slug": "shared-slug"}
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SLUG_TAKEN"


@pytest.mark.asyncio
async def test_auto_generated_slugs_do_not_collide(member_client):
    first = await member_client.post("/api/v1/groups", json={"name": "Computer Society"})
    second = await member_client.post("/api/v1/groups", json={"name": "Computer Society"})

    assert first.json()["data"]["slug"] == "computer-society"
    assert second.json()["data"]["slug"] != "computer-society"


@pytest.mark.asyncio
async def test_sql_injection_in_search_is_treated_as_text(member_client):
    await member_client.post("/api/v1/groups", json={"name": "Robotics Club"})

    response = await member_client.get(
        "/api/v1/groups", params={"search": "'; DROP TABLE groups; --"}
    )
    assert response.status_code == 200
    assert response.json()["data"] == []

    # The table is still there.
    assert (await member_client.get("/api/v1/groups")).status_code == 200


@pytest.mark.asyncio
async def test_pagination_limit_is_clamped(member_client):
    response = await member_client.get("/api/v1/groups", params={"limit": 9_999_999})
    # Rejected outright rather than silently honoured.
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pagination_limit_maximum_is_enforced(member_client):
    response = await member_client.get("/api/v1/groups", params={"limit": 100})
    assert response.status_code == 200
    assert response.json()["meta"]["limit"] <= 100


@pytest.mark.asyncio
async def test_unknown_fields_are_rejected_on_update(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Strict"})).json()["data"]

    # `extra="forbid"` stops mass-assignment of columns the client must not set.
    response = await member_client.patch(
        f"/api/v1/groups/{group['id']}",
        json={"name": "Renamed", "owner_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_icon_is_rejected(member_client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Icons"})).json()["data"]

    response = await member_client.post(
        f"/api/v1/groups/{group['id']}/links",
        json={"title": "Bad icon", "url": "https://ieeesou.org", "icon": "../../etc/passwd"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_error_response_never_leaks_internals(client):
    response = await client.get("/api/v1/groups/not-a-uuid")
    assert response.status_code in (401, 422)
    body = response.text.lower()
    for leak in ("traceback", "sqlalchemy", "select ", "/users/", "site-packages"):
        assert leak not in body
