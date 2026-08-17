"""Test fixtures.

The suite runs against SQLite (via aiosqlite) and an in-memory Redis double, so
it needs no external services. Every model uses portable column types precisely
so this is possible.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

# Environment must be configured before anything under `app` is imported, since
# `Settings` is instantiated at module import time.
os.environ.update(
    {
        "ENVIRONMENT": "development",
        "DEBUG": "false",
        "LOG_LEVEL": "WARNING",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_SECRET": "test-jwt-secret-value-that-is-long-enough-1234567890",
        "JWT_REFRESH_SECRET": "test-refresh-secret-value-that-is-long-enough-0987654321",
        "ANALYTICS_IP_PEPPER": "test-analytics-pepper-value-1234567890",
        "COOKIE_SECURE": "false",
        "CORS_ORIGINS": "http://localhost:5173",
        "FRONTEND_URL": "http://localhost:5173",
        "PUBLIC_BASE_URL": "http://localhost:5173",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_DIR": "/tmp/linkhub-test-media",
        "STORAGE_PUBLIC_BASE_URL": "http://testserver/media",
        "RATE_LIMIT_ENABLED": "true",
        "BOOTSTRAP_ORG_SLUG": "ieee-sou",
        "BOOTSTRAP_ORG_NAME": "IEEE SOU",
        "BOOTSTRAP_SUPERADMIN_EMAIL": "",
        "BOOTSTRAP_SUPERADMIN_PASSWORD": "",
    }
)

import fakeredis.aioredis  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import redis as redis_module  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Membership, Organization, Role, User, UserStatus  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402

TEST_PASSWORD = "Str0ng-Test-Pass!42"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def engine():
    # A single shared in-memory connection: StaticPool keeps every session
    # pointed at the same database for the duration of the test.
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def db(session_factory) -> AsyncGenerator:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_module.set_redis(client)
    yield client
    await client.flushall()
    await client.aclose()
    redis_module.set_redis(None)


@pytest_asyncio.fixture
async def organization(session_factory) -> Organization:
    async with session_factory() as session:
        org = Organization(
            name="IEEE SOU",
            slug="ieee-sou",
            settings={
                "allow_public_registration": True,
                "default_member_role": "USER",
                "max_groups_per_user": 25,
                "require_group_approval": False,
            },
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)
        return org


@pytest_asyncio.fixture
async def app(session_factory, redis_client, organization):
    application = create_app()

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_db] = override_get_db
    # `session_scope` is used by background analytics writes; point it at the
    # test database too.
    import app.db.session as session_module

    original_factory = session_module.SessionLocal
    session_module.SessionLocal = session_factory
    yield application
    session_module.SessionLocal = original_factory
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"user-agent": "pytest/1.0 Mozilla/5.0 (Macintosh) Chrome/120"},
    ) as async_client:
        yield async_client


# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------
async def _make_user(
    session_factory,
    organization: Organization,
    *,
    email: str,
    role: Role,
    system_role: Role = Role.USER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    async with session_factory() as session:
        user = User(
            email=email,
            full_name="Test Person",
            password_hash=hash_password(TEST_PASSWORD),
            system_role=system_role,
            status=status,
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            Membership(
                user_id=user.id,
                organization_id=organization.id,
                role=role,
                is_default=True,
            )
        )
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def make_user(session_factory, organization):
    async def factory(
        role: Role = Role.USER,
        *,
        email: str | None = None,
        system_role: Role = Role.USER,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        return await _make_user(
            session_factory,
            organization,
            email=email or f"user-{uuid.uuid4().hex[:10]}@ieee.example",
            role=role,
            system_role=system_role,
            status=status,
        )

    return factory


class AuthedClient:
    """Thin wrapper that carries the access token and CSRF header."""

    def __init__(self, client: AsyncClient, access_token: str, csrf_token: str, user: User):
        self._client = client
        self.access_token = access_token
        self.csrf_token = csrf_token
        self.user = user

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-CSRF-Token": self.csrf_token,
        }

    async def request(self, method: str, url: str, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        return await self._client.request(method, url, headers=headers, **kwargs)

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs):
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs):
        return await self.request("DELETE", url, **kwargs)


@pytest_asyncio.fixture
async def sign_in(client: AsyncClient):
    async def _sign_in(user: User) -> AuthedClient:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": TEST_PASSWORD},
        )
        assert response.status_code == 200, response.text
        payload = response.json()["data"]
        return AuthedClient(client, payload["access_token"], payload["csrf_token"], user)

    return _sign_in


@pytest_asyncio.fixture
async def editor_client(make_user, sign_in) -> AuthedClient:
    return await sign_in(await make_user(Role.EDITOR))


@pytest_asyncio.fixture
async def admin_client(make_user, sign_in) -> AuthedClient:
    return await sign_in(await make_user(Role.ADMIN))


@pytest_asyncio.fixture
async def member_client(make_user, sign_in) -> AuthedClient:
    return await sign_in(await make_user(Role.USER))
