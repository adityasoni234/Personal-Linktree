"""Declarative base and shared column mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.types import Uuid

# Deterministic constraint names keep Alembic autogenerate diffs stable and make
# `ALTER TABLE ... DROP CONSTRAINT` migrations possible on Postgres.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime read back from the database to UTC-aware.

    Postgres returns timezone-aware values for `TIMESTAMPTZ`, but SQLite (used
    by the test suite) has no timezone type and hands back naive datetimes.
    Comparing the two raises `TypeError`, so every comparison against `utcnow()`
    goes through here. Naive values are *assumed* to be UTC, which is true
    because every write uses `utcnow()` or `func.now()` on a UTC connection.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def pg_enum(enum_cls: type, name: str) -> SAEnum:
    """Portable enum column.

    `native_enum=False` renders a VARCHAR + CHECK constraint, which behaves the
    same on Postgres and SQLite (used by the test suite) and avoids the painful
    `ALTER TYPE` dance when enum members are added later.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class UUIDPrimaryKeyMixin:
    """Unguessable public identifiers — no sequential integer IDs are exposed."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )


class SlugMixin:
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
