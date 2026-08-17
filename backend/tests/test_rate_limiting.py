"""Rate limiting and brute-force protection."""

from __future__ import annotations

import pytest

from app.core.rate_limit import KeyBy, Policies, check_rate_limit
from app.security import bruteforce
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.security

LOGIN_URL = "/api/v1/auth/login"


class _FakeRequest:
    """Minimal stand-in for the parts of `Request` the limiter reads."""

    def __init__(self, ip: str = "203.0.113.7") -> None:
        self.headers = {"x-forwarded-for": ip}
        self.url = type("URL", (), {"path": "/test"})()
        self.method = "POST"
        self.client = type("Client", (), {"host": ip})()
        self.state = type("State", (), {})()


# ---------------------------------------------------------------------------
# Limiter unit behaviour
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_requests_are_allowed_up_to_the_limit(redis_client):
    from app.core.rate_limit import RateLimitPolicy

    policy = RateLimitPolicy("unit:test", limit=3, window_seconds=60, key_by=KeyBy.IP)
    request = _FakeRequest()

    results = [await check_rate_limit(policy, request) for _ in range(4)]

    assert [item.allowed for item in results] == [True, True, True, False]
    assert results[-1].retry_after_seconds >= 1


@pytest.mark.asyncio
async def test_separate_ips_get_separate_budgets(redis_client):
    from app.core.rate_limit import RateLimitPolicy

    policy = RateLimitPolicy("unit:per-ip", limit=1, window_seconds=60, key_by=KeyBy.IP)

    assert (await check_rate_limit(policy, _FakeRequest("198.51.100.1"))).allowed
    assert (await check_rate_limit(policy, _FakeRequest("198.51.100.2"))).allowed
    assert not (await check_rate_limit(policy, _FakeRequest("198.51.100.1"))).allowed


@pytest.mark.asyncio
async def test_identity_keyed_limits_track_the_submitted_value(redis_client):
    from app.core.rate_limit import RateLimitPolicy

    policy = RateLimitPolicy("unit:identity", limit=1, window_seconds=60, key_by=KeyBy.IDENTITY)
    request = _FakeRequest()

    assert (await check_rate_limit(policy, request, identity="a@example.com")).allowed
    assert (await check_rate_limit(policy, request, identity="b@example.com")).allowed
    assert not (await check_rate_limit(policy, request, identity="a@example.com")).allowed


def test_authentication_policies_fail_closed():
    """Losing Redis must not silently disable the login limiter."""
    for policy in (
        Policies.LOGIN_IP,
        Policies.LOGIN_ACCOUNT,
        Policies.REGISTER,
        Policies.FORGOT_PASSWORD_IP,
        Policies.FORGOT_PASSWORD_ACCOUNT,
        Policies.RESET_PASSWORD,
        Policies.CHANGE_PASSWORD,
    ):
        assert policy.fail_open is False


def test_login_is_limited_per_ip_and_per_account():
    """Rotating the email must not reset the per-IP budget, and vice versa."""
    assert Policies.LOGIN_IP.key_by is KeyBy.IP
    assert Policies.LOGIN_ACCOUNT.key_by is KeyBy.IDENTITY


def test_documented_limits_match_the_specification():
    assert (Policies.LOGIN_IP.limit, Policies.LOGIN_IP.window_seconds) == (5, 60)
    assert (Policies.REGISTER.limit, Policies.REGISTER.window_seconds) == (5, 3600)
    assert (
        Policies.FORGOT_PASSWORD_IP.limit,
        Policies.FORGOT_PASSWORD_IP.window_seconds,
    ) == (3, 900)
    assert (Policies.API_USER.limit, Policies.API_USER.window_seconds) == (100, 60)
    assert (Policies.QR_RENDER.limit, Policies.QR_RENDER.window_seconds) == (30, 60)


# ---------------------------------------------------------------------------
# Endpoint behaviour
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_repeated_failed_logins_are_eventually_rejected(client, make_user):
    user = await make_user()
    statuses = []

    for _ in range(8):
        response = await client.post(
            LOGIN_URL, json={"email": user.email, "password": "Wr0ng-Password!1"}
        )
        statuses.append(response.status_code)

    assert 429 in statuses, statuses
    limited = next(
        index for index, status in enumerate(statuses) if status == 429
    )
    # The first few attempts get a normal 401; only then does the limiter bite.
    assert limited >= 3


@pytest.mark.asyncio
async def test_rate_limited_response_carries_retry_after(client, make_user):
    user = await make_user()

    for _ in range(10):
        response = await client.post(
            LOGIN_URL, json={"email": user.email, "password": "Wr0ng-Password!1"}
        )
        if response.status_code == 429:
            assert response.headers.get("retry-after")
            assert response.json()["error"]["code"] in (
                "RATE_LIMIT_EXCEEDED",
                "ACCOUNT_TEMPORARILY_LOCKED",
            )
            return

    pytest.fail("login was never rate limited")


@pytest.mark.asyncio
async def test_successful_requests_expose_rate_limit_headers(member_client):
    response = await member_client.get("/api/v1/groups")
    assert response.status_code == 200
    assert response.headers.get("x-ratelimit-limit")
    assert response.headers.get("x-ratelimit-remaining")


@pytest.mark.asyncio
async def test_registration_is_rate_limited(client):
    statuses = []
    for index in range(8):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"person{index}@ieee.example",
                "full_name": f"Person {index}",
                "password": TEST_PASSWORD,
            },
        )
        statuses.append(response.status_code)

    assert 429 in statuses, statuses


@pytest.mark.asyncio
async def test_forgot_password_is_rate_limited(client, make_user):
    user = await make_user()
    statuses = [
        (
            await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        ).status_code
        for _ in range(6)
    ]
    assert 429 in statuses, statuses


# ---------------------------------------------------------------------------
# Brute-force lockout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lockout_engages_after_repeated_failures(redis_client):
    identity = "lockout@ieee.example"

    for _ in range(5):
        await bruteforce.register_failure(identity)

    with pytest.raises(Exception) as excinfo:
        await bruteforce.assert_not_locked(identity)

    from app.core.errors import AccountLockedError

    assert isinstance(excinfo.value, AccountLockedError)


@pytest.mark.asyncio
async def test_a_successful_sign_in_clears_the_counter(redis_client):
    identity = "recovering@ieee.example"

    for _ in range(5):
        await bruteforce.register_failure(identity)
    await bruteforce.clear_failures(identity)

    # No exception: the ladder was reset.
    await bruteforce.assert_not_locked(identity)
    assert await bruteforce.failure_count(identity) == 0


@pytest.mark.asyncio
async def test_lockout_duration_escalates(redis_client):
    from app.security.bruteforce import _lockout_seconds

    assert _lockout_seconds(4) == 0
    assert _lockout_seconds(5) == 60
    assert _lockout_seconds(8) == 300
    assert _lockout_seconds(12) == 1800
    assert _lockout_seconds(25) == 7200


@pytest.mark.asyncio
async def test_identifiers_are_hashed_before_reaching_redis(redis_client):
    identity = "hashed@ieee.example"
    await bruteforce.register_failure(identity)

    keys = await redis_client.keys("auth:*")
    assert keys
    assert all(identity not in key for key in keys)
