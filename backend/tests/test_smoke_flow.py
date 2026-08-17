"""End-to-end happy path: register → group → links → publish → public page → QR."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_full_lifecycle(client):
    # ---- Register --------------------------------------------------------
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chair@ieee.example",
            "full_name": "Branch Chair",
            "password": "Str0ng-Test-Pass!42",
        },
    )
    assert register.status_code == 201, register.text
    session = register.json()["data"]
    token = session["access_token"]
    csrf = session["csrf_token"]
    # The first member of an organization becomes its administrator.
    assert session["user"]["organization_role"] == "ADMIN"
    # The refresh token must never appear in the response body.
    assert "refresh_token" not in register.text

    headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

    # ---- Create a group --------------------------------------------------
    created = await client.post(
        "/api/v1/groups",
        headers=headers,
        json={
            "name": "Computer Society",
            "description": "IEEE Computer Society — SOU Student Branch Chapter",
        },
    )
    assert created.status_code == 201, created.text
    group = created.json()["data"]
    assert group["slug"] == "computer-society"
    assert group["public_url"].endswith("/g/computer-society")

    # ---- Add links -------------------------------------------------------
    for title, url, icon in [
        ("Instagram", "https://instagram.com/ieeesou", "instagram"),
        ("LinkedIn", "https://linkedin.com/company/ieeesou", "linkedin"),
        ("Register for Hackathon", "ieeesou.org/hackathon", "ticket"),
    ]:
        response = await client.post(
            f"/api/v1/groups/{group['id']}/links",
            headers=headers,
            json={"title": title, "url": url, "icon": icon},
        )
        assert response.status_code == 201, response.text

    # A bare domain is normalised to https rather than rejected.
    links = (await client.get(f"/api/v1/groups/{group['id']}/links", headers=headers)).json()
    assert links["data"][2]["url"] == "https://ieeesou.org/hackathon"

    # ---- Publish ---------------------------------------------------------
    published = await client.post(
        f"/api/v1/groups/{group['id']}/publish",
        headers=headers,
        json={"is_published": True},
    )
    assert published.status_code == 200, published.text

    # ---- Public page -----------------------------------------------------
    public = await client.get("/api/v1/public/groups/computer-society")
    assert public.status_code == 200, public.text
    body = public.json()["data"]
    assert body["name"] == "Computer Society"
    assert len(body["links"]) == 3
    # No internal fields may leak to anonymous callers.
    assert "owner_id" not in body
    assert "organization_id" not in body
    assert "is_published" not in body

    # ---- QR --------------------------------------------------------------
    qr_config = await client.get(f"/api/v1/groups/{group['id']}/qr", headers=headers)
    assert qr_config.status_code == 200, qr_config.text
    render = qr_config.json()["data"]["render"]
    # The code always encodes the group's own public page.
    assert render["target_url"].startswith("http://localhost:5173/g/computer-society")
    assert render["is_scannable"] is True

    png = await client.get(f"/api/v1/groups/{group['id']}/qr.png", headers=headers)
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    svg = await client.get(f"/api/v1/groups/{group['id']}/qr.svg", headers=headers)
    assert svg.status_code == 200
    assert b"<svg" in svg.content

    # ---- Click redirect --------------------------------------------------
    link_id = body["links"][0]["id"]
    redirect = await client.get(
        f"/api/v1/public/groups/computer-society/links/{link_id}",
        follow_redirects=False,
    )
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://instagram.com/ieeesou"

    # ---- Dashboard -------------------------------------------------------
    overview = await client.get("/api/v1/analytics/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    assert overview.json()["data"]["total_groups"] == 1
    assert overview.json()["data"]["total_links"] == 3
