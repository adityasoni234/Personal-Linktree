"""Alembic environment.

The database URL always comes from `DATABASE_URL`, and the async driver is
swapped for its sync counterpart because Alembic runs migrations synchronously.
"""

from __future__ import annotations

import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

# Importing the models package registers every table on Base.metadata, which is
# what `--autogenerate` diffs against.
from app.models import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """Convert an async URL into the sync form Alembic needs."""
    url = settings.DATABASE_URL
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", url)
    url = re.sub(r"^sqlite\+aiosqlite://", "sqlite://", url)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=_sync_url().startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_url()

    connectable = engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite stores `now()` verbatim and cannot be compared against
            # `func.now()`, which produces spurious diffs. The real target is
            # PostgreSQL, where the comparison is meaningful.
            compare_server_default=not is_sqlite,
            # SQLite cannot ALTER most things; batch mode rewrites the table.
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
