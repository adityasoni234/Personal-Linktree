"""Public page exposure rules, click redirects and analytics privacy."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import AnalyticsEvent, AnalyticsEventType

pytestmark = pytest.mark.asyncio


async def publish_group(authed, name="Computer Society", links=(("Instagram", "https://instagram.com/ieeesou"),)):
    group = (await authed.post("/api/v1/groups", json={"name": name})).json()["data"]
    for title, url in links:
        await authed.post(f"/api/v1/groups/{group['id']}/links", json={"title": title, "url": url})
    await authed.post(f"/api/v1/groups/{group['id']}/publish", json={"is_published": True})
    return group


# ---------------------------------------------------------------------------
# Exposure rules
# ---------------------------------------------------------------------------
@pytest.mark.security
async def test_draft_group_is_not_publicly_visible(member_client, client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Secret Plans"})).json()[
        "data"
    ]

    response = await client.get(f"/api/v1/public/groups/{group['slug']}")
    assert response.status_code == 404
    # The response must not confirm that the slug exists.
    assert "Secret Plans" not in response.text


@pytest.mark.security
async def test_archived_group_is_not_publicly_visible(member_client, client):
    group = await publish_group(member_client, "Old Event")
    await member_client.post(f"/api/v1/groups/{group['id']}/archive")

    assert (await client.get(f"/api/v1/public/groups/{group['slug']}")).status_code == 404


@pytest.mark.security
async def test_unpublished_group_returns_the_same_error_as_a_missing_one(member_client, client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Draft Group"})).json()[
        "data"
    ]

    draft = await client.get(f"/api/v1/public/groups/{group['slug']}")
    missing = await client.get("/api/v1/public/groups/never-existed-at-all")

    assert draft.status_code == missing.status_code == 404
    assert draft.json()["error"]["message"] == missing.json()["error"]["message"]


@pytest.mark.security
async def test_public_payload_contains_no_internal_fields(member_client, client):
    group = await publish_group(member_client, "Public Group")

    body = (await client.get(f"/api/v1/public/groups/{group['slug']}")).json()["data"]

    for leaked in (
        "owner_id",
        "organization_id",
        "is_published",
        "is_archived",
        "position",
        "stats",
        "created_at",
    ):
        assert leaked not in body


async def test_inactive_links_are_hidden_from_the_public_page(member_client, client):
    group = await publish_group(
        member_client,
        "Mixed Links",
        links=(("Visible", "https://ieeesou.org"), ("Hidden", "https://ieeesou.org/hidden")),
    )

    links = (await member_client.get(f"/api/v1/groups/{group['id']}/links")).json()["data"]
    hidden = next(link for link in links if link["title"] == "Hidden")
    await member_client.patch(f"/api/v1/links/{hidden['id']}", json={"is_active": False})

    public = (await client.get(f"/api/v1/public/groups/{group['slug']}")).json()["data"]
    titles = [link["title"] for link in public["links"]]
    assert titles == ["Visible"]


@pytest.mark.security
@pytest.mark.parametrize(
    "slug", ["../../etc/passwd", "Computer%20Society", "a", "<script>", "a" * 80]
)
async def test_malformed_public_slugs_are_rejected(client, slug):
    response = await client.get(f"/api/v1/public/groups/{slug}")
    assert response.status_code in (404, 422)


# ---------------------------------------------------------------------------
# Redirects
# ---------------------------------------------------------------------------
@pytest.mark.security
async def test_click_redirect_uses_the_stored_url(member_client, client):
    group = await publish_group(member_client, "Redirect Group")
    public = (await client.get(f"/api/v1/public/groups/{group['slug']}")).json()["data"]
    link_id = public["links"][0]["id"]

    response = await client.get(
        f"/api/v1/public/groups/{group['slug']}/links/{link_id}", follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://instagram.com/ieeesou"
    # The destination must not learn where the visitor came from.
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.security
async def test_redirect_rejects_a_link_from_another_group(member_client, client):
    first = await publish_group(member_client, "Group One")
    second = await publish_group(
        member_client, "Group Two", links=(("Other", "https://example.org"),)
    )

    second_links = (await member_client.get(f"/api/v1/groups/{second['id']}/links")).json()["data"]
    foreign_link_id = second_links[0]["id"]

    response = await client.get(
        f"/api/v1/public/groups/{first['slug']}/links/{foreign_link_id}", follow_redirects=False
    )
    assert response.status_code == 404


async def test_redirect_for_an_unknown_link_is_not_found(member_client, client):
    group = await publish_group(member_client, "Missing Link Group")
    response = await client.get(
        f"/api/v1/public/groups/{group['slug']}/links/"
        "00000000-0000-0000-0000-000000000000",
        follow_redirects=False,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
async def test_page_view_is_recorded(member_client, client, session_factory):
    group = await publish_group(member_client, "Tracked Group")

    await client.get(f"/api/v1/public/groups/{group['slug']}")

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.event_type == AnalyticsEventType.PAGE_VIEW
            )
        )
    assert count == 1


async def test_qr_source_is_recorded_as_a_scan(member_client, client, session_factory):
    group = await publish_group(member_client, "Scanned Group")

    await client.get(f"/api/v1/public/groups/{group['slug']}", params={"src": "qr"})

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.event_type == AnalyticsEventType.QR_SCAN
            )
        )
    assert count == 1


@pytest.mark.security
async def test_repeat_views_from_one_visitor_are_de_duplicated(
    member_client, client, session_factory
):
    group = await publish_group(member_client, "Dedupe Group")

    for _ in range(5):
        await client.get(f"/api/v1/public/groups/{group['slug']}")

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.event_type == AnalyticsEventType.PAGE_VIEW
            )
        )
    assert count == 1


@pytest.mark.security
async def test_bot_traffic_is_not_counted(member_client, client, session_factory):
    group = await publish_group(member_client, "Bot Group")

    await client.get(
        f"/api/v1/public/groups/{group['slug']}",
        headers={"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"},
    )

    async with session_factory() as session:
        count = await session.scalar(select(func.count(AnalyticsEvent.id)))
    assert count == 0


@pytest.mark.security
async def test_no_raw_ip_or_user_agent_is_stored(member_client, client, session_factory):
    group = await publish_group(member_client, "Privacy Group")

    await client.get(
        f"/api/v1/public/groups/{group['slug']}",
        headers={
            "x-forwarded-for": "198.51.100.42",
            "user-agent": "Mozilla/5.0 (Macintosh) Chrome/120",
            "referer": "https://instagram.com/ieeesou/p/abc123?utm_source=bio",
        },
    )

    async with session_factory() as session:
        event = (await session.execute(select(AnalyticsEvent))).scalars().first()

    assert event is not None
    assert event.visitor_hash is not None
    # The stored value is a digest, not the address.
    assert "198.51.100.42" not in event.visitor_hash
    assert len(event.visitor_hash) == 64
    # Only the referrer's domain survives — never its path or query string.
    assert event.referrer_domain == "instagram.com"
    assert event.browser == "Chrome"
    assert event.device_type.value == "DESKTOP"


@pytest.mark.security
async def test_client_cannot_choose_which_group_an_event_belongs_to(member_client, client):
    """The tracking beacon carries no ids — the group comes from the URL."""
    group = await publish_group(member_client, "Beacon Group")

    response = await client.post(
        f"/api/v1/public/groups/{group['slug']}/events",
        json={"group_id": "00000000-0000-0000-0000-000000000000", "event_type": "QR_SCAN"},
    )
    assert response.status_code == 200


async def test_public_qr_is_served_for_a_published_group(member_client, client):
    group = await publish_group(member_client, "QR Public")

    response = await client.get(f"/api/v1/public/groups/{group['slug']}/qr.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@pytest.mark.security
async def test_public_qr_is_not_served_for_a_draft(member_client, client):
    group = (await member_client.post("/api/v1/groups", json={"name": "Draft QR"})).json()["data"]

    assert (await client.get(f"/api/v1/public/groups/{group['slug']}/qr.png")).status_code == 404


async def test_public_meta_endpoint_returns_seo_fields(member_client, client):
    group = await publish_group(member_client, "SEO Group")

    body = (await client.get(f"/api/v1/public/groups/{group['slug']}/meta")).json()["data"]
    assert body["title"]
    assert body["canonical_url"].endswith(f"/g/{group['slug']}")
    assert body["twitter_card"] == "summary_large_image"


# ---------------------------------------------------------------------------
# Response headers
# ---------------------------------------------------------------------------
@pytest.mark.security
async def test_security_headers_are_present(client):
    response = await client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in response.headers
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


@pytest.mark.security
async def test_api_responses_are_not_cacheable(member_client):
    response = await member_client.get("/api/v1/groups")
    assert response.headers["cache-control"] == "no-store"


async def test_request_id_is_echoed(client):
    response = await client.get("/health")
    assert response.headers["x-request-id"]
