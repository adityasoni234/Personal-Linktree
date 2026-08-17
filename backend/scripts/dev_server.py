"""Zero-dependency development server.

Runs the API against SQLite and an in-memory Redis, so no Postgres or Redis is
needed to work on the app:

    python scripts/dev_server.py

Port 8010 by default (8000 is a common collision). Override with PORT.
Use docker compose for anything resembling production.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./linkhub-dev.db")
os.environ.setdefault("JWT_SECRET", "dev-only-jwt-secret-value-not-for-production-1234")
os.environ.setdefault("JWT_REFRESH_SECRET", "dev-only-refresh-secret-not-for-production-5678")
os.environ.setdefault("ANALYTICS_IP_PEPPER", "dev-only-analytics-pepper-0000")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:5173")
os.environ.setdefault("STORAGE_LOCAL_DIR", "./media")
os.environ.setdefault("STORAGE_PUBLIC_BASE_URL", "http://localhost:5173/media")

PORT = int(os.environ.get("PORT", "8010"))

import fakeredis.aioredis  # noqa: E402

from app.core import redis as redis_module  # noqa: E402

# Swap Redis for an in-memory double and neutralise the lifespan hooks.
redis_module.set_redis(fakeredis.aioredis.FakeRedis(decode_responses=True))
redis_module.init_redis = lambda: asyncio.sleep(0, result=redis_module.get_redis())  # type: ignore[assignment]
redis_module.close_redis = lambda: asyncio.sleep(0)  # type: ignore[assignment]

import app.models  # noqa: E402,F401  (registers every mapper on Base.metadata)
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(create_schema())

import uvicorn  # noqa: E402

if __name__ == "__main__":
    print(f"\n  IEEE SOU Link Hub API  →  http://127.0.0.1:{PORT}")
    print(f"  Docs                   →  http://127.0.0.1:{PORT}/docs\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="info")
