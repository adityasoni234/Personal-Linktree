"""Authentication, session rotation and password lifecycle."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Role, User, UserSession, UserStatus
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.asyncio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"


async def test_register_returns_session_without_refresh_token_in_body(client):
    response = await client.post(
        REGISTER_URL,
        json={
            "email": "New.Person@IEEESOU.org",
            "full_name": "New Person",
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]

    # The refresh token belongs in an HttpOnly cookie and nowhere else.
    assert "refresh_token" not in response.text
    assert response.cookies.get("lh_refresh")
    assert body["access_token"]
    # Email is normalised to lowercase.
    assert body["user"]["email"] == "new.person@ieeesou.org"


async def test_register_rejects_weak_password(client):
    response = await client.post(
        REGISTER_URL,
        json={"email": "weak@ieee.example", "full_name": "Weak Person", "password": "password12"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_register_rejects_password_containing_email(client):
    response = await client.post(
        REGISTER_URL,
        json={
            "email": "aarav@ieee.example",
            "full_name": "Aarav Shah",
            "password": "Aarav-Str0ng!2026",
        },
    )
    assert response.status_code == 422


async def test_register_rejects_duplicate_email(client, make_user):
    user = await make_user(Role.USER)
    response = await client.post(
        REGISTER_URL,
        json={"email": user.email, "full_name": "Impostor", "password": TEST_PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.security
async def test_login_response_does_not_reveal_whether_account_exists(client, make_user):
    user = await make_user(Role.USER)

    wrong_password = await client.post(
        LOGIN_URL, json={"email": user.email, "password": "Wr0ng-Password!99"}
    )
    unknown_account = await client.post(
        LOGIN_URL, json={"email": "nobody@ieee.example", "password": "Wr0ng-Password!99"}
    )

    assert wrong_password.status_code == unknown_account.status_code == 401
    # Identical body and code: this endpoint is not an enumeration oracle.
    assert wrong_password.json()["error"]["code"] == unknown_account.json()["error"]["code"]
    assert wrong_password.json()["error"]["message"] == unknown_account.json()["error"]["message"]


async def test_login_rejects_suspended_account(client, make_user):
    user = await make_user(Role.USER, status=UserStatus.SUSPENDED)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def test_first_member_of_organization_becomes_admin(client):
    response = await client.post(
        REGISTER_URL,
        json={"email": "founder@ieee.example", "full_name": "Founder", "password": TEST_PASSWORD},
    )
    assert response.json()["data"]["user"]["organization_role"] == Role.ADMIN.value


async def test_second_member_joins_with_default_role(client):
    await client.post(
        REGISTER_URL,
        json={"email": "founder@ieee.example", "full_name": "Founder", "password": TEST_PASSWORD},
    )
    second = await client.post(
        REGISTER_URL,
        json={"email": "member@ieee.example", "full_name": "Member", "password": TEST_PASSWORD},
    )
    assert second.json()["data"]["user"]["organization_role"] == Role.USER.value


# ---------------------------------------------------------------------------
# Refresh rotation
# ---------------------------------------------------------------------------
@pytest.mark.security
async def test_refresh_rotates_the_token(client, make_user):
    user = await make_user(Role.USER)
    login = await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    csrf = login.json()["data"]["csrf_token"]
    original_cookie = client.cookies.get("lh_refresh")

    response = await client.post(REFRESH_URL, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    assert client.cookies.get("lh_refresh") != original_cookie


@pytest.mark.security
async def test_refresh_requires_csrf_header(client, make_user):
    user = await make_user(Role.USER)
    await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})

    # Cookie present, header missing: the double-submit check must fail.
    response = await client.post(REFRESH_URL)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.security
async def test_refresh_rejects_mismatched_csrf_header(client, make_user):
    user = await make_user(Role.USER)
    await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})

    response = await client.post(REFRESH_URL, headers={"X-CSRF-Token": "forged.value"})
    assert response.status_code == 403


@pytest.mark.security
async def test_replaying_an_old_refresh_token_destroys_the_session(
    client, make_user, session_factory
):
    """Token reuse outside the grace window is treated as theft."""
    user = await make_user(Role.USER)
    login = await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    assert login.status_code == 200
    stolen_cookie = client.cookies.get("lh_refresh")

    def csrf_header() -> dict[str, str]:
        # Every refresh issues a fresh CSRF token, so read it from the jar.
        return {"X-CSRF-Token": client.cookies.get("lh_csrf", "")}

    assert (await client.post(REFRESH_URL, headers=csrf_header())).status_code == 200

    # Age the rotation past the grace window so the replay is unambiguous.
    from app.db.base import utcnow
    from app.services.auth_service import REFRESH_ROTATION_GRACE_SECONDS
    from datetime import timedelta

    async with session_factory() as session:
        rows = await session.execute(select(UserSession).where(UserSession.user_id == user.id))
        for record in rows.scalars():
            record.last_used_at = utcnow() - timedelta(
                seconds=REFRESH_ROTATION_GRACE_SECONDS + 60
            )
        await session.commit()

    headers = csrf_header()
    client.cookies.set("lh_refresh", stolen_cookie)
    replay = await client.post(REFRESH_URL, headers=headers)

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "SESSION_REVOKED"

    # The whole family is revoked, not just the replayed token.
    async with session_factory() as session:
        rows = await session.execute(select(UserSession).where(UserSession.user_id == user.id))
        assert all(record.revoked_at is not None for record in rows.scalars())


async def test_concurrent_refresh_within_grace_window_is_allowed(client, make_user):
    """Two tabs opening at once must not sign the user out."""
    user = await make_user(Role.USER)
    login = await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    assert login.status_code == 200
    first_cookie = client.cookies.get("lh_refresh")

    assert (
        await client.post(
            REFRESH_URL, headers={"X-CSRF-Token": client.cookies.get("lh_csrf", "")}
        )
    ).status_code == 200

    # Immediately replay the just-rotated token, as a second tab would.
    headers = {"X-CSRF-Token": client.cookies.get("lh_csrf", "")}
    client.cookies.set("lh_refresh", first_cookie)
    retry = await client.post(REFRESH_URL, headers=headers)
    assert retry.status_code == 200


async def test_logout_revokes_the_session(client, make_user, session_factory):
    user = await make_user(Role.USER)
    login = await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    csrf = login.json()["data"]["csrf_token"]

    response = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200

    async with session_factory() as session:
        rows = await session.execute(select(UserSession).where(UserSession.user_id == user.id))
        assert all(record.revoked_at is not None for record in rows.scalars())


async def test_access_token_is_rejected_after_logout(client, make_user):
    user = await make_user(Role.USER)
    login = await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    payload = login.json()["data"]
    headers = {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-CSRF-Token": payload["csrf_token"],
    }

    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
    await client.post("/api/v1/auth/logout", headers=headers)

    # The revocation list makes the still-unexpired access token unusable.
    after = await client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
async def test_change_password_requires_the_current_one(member_client):
    response = await member_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "Not-The-Password!1",
            "new_password": "An0ther-Str0ng!Pass",
            "revoke_other_sessions": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_change_password_succeeds_and_allows_new_login(member_client, client):
    new_password = "Compl3tely-New!Pass"
    response = await member_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": TEST_PASSWORD,
            "new_password": new_password,
            "revoke_other_sessions": True,
        },
    )
    assert response.status_code == 200, response.text

    login = await client.post(
        LOGIN_URL, json={"email": member_client.user.email, "password": new_password}
    )
    assert login.status_code == 200


async def test_forgot_password_always_responds_identically(client, make_user):
    user = await make_user(Role.USER)

    known = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    unknown = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "ghost@ieee.example"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]


async def test_reset_password_rejects_an_unknown_token(client):
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "a" * 43, "new_password": "Brand-New-P4ss!word"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_RESET_TOKEN"


# ---------------------------------------------------------------------------
# Token handling
# ---------------------------------------------------------------------------
@pytest.mark.security
@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbiJ9.",  # alg: none
        "",
    ],
)
async def test_malformed_tokens_are_rejected(client, token):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.security
async def test_refresh_token_cannot_be_used_as_an_access_token(client, make_user):
    """The two token families are separately signed and type-tagged."""
    user = await make_user(Role.USER)
    await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    refresh_cookie = client.cookies.get("lh_refresh")

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_cookie}"}
    )
    assert response.status_code == 401


async def test_unauthenticated_request_is_rejected(client):
    response = await client.get("/api/v1/groups")
    assert response.status_code == 401
    assert response.json()["success"] is False


async def test_password_hash_is_never_returned(client, make_user, session_factory):
    user = await make_user(Role.USER)
    login = await client.post(LOGIN_URL, json={"email": user.email, "password": TEST_PASSWORD})
    assert "password_hash" not in login.text
    assert "$argon2" not in login.text

    async with session_factory() as session:
        stored = await session.get(User, user.id)
        assert stored is not None
        assert stored.password_hash.startswith("$argon2id$")
