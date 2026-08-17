"""Async engine, session factory and the FastAPI session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logging import app_logger


def _normalise_db_url(url: str) -> str:
    """Render (and many PaaS providers) supply a plain ``postgres://`` or
    ``postgresql://`` URL.  SQLAlchemy 2 needs the *async* dialect marker so
    it picks asyncpg instead of falling back to the absent psycopg2."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url  # already has a dialect marker (e.g. sqlite, postgresql+asyncpg)


def _create_engine() -> AsyncEngine:
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    db_url = settings.DATABASE_URL if is_sqlite else _normalise_db_url(settings.DATABASE_URL)
    kwargs: dict = {
        "echo": settings.DB_ECHO,
        "pool_pre_ping": True,
        "future": True,
    }
    if is_sqlite:
        # SQLite (test suite) has no meaningful pooling story.
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        )
    return create_async_engine(db_url, **kwargs)


engine: AsyncEngine = _create_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped session.

    The route handler owns the commit; this dependency only guarantees rollback
    and close so a failed request can never leave a half-applied transaction.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Transactional scope for background tasks and CLI utilities."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def database_healthy() -> bool:
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - health probe must never raise
        return False


async def dispose_engine() -> None:
    await engine.dispose()
    app_logger.info("database_engine_disposed")
