"""First-run bootstrap.

Creates the default organization and, when credentials are supplied in the
environment, a super administrator. Both operations are idempotent, so this can
run safely on every boot and on every replica.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import app_logger, security_logger
from app.db.session import engine, session_scope
from app.models import Base
from app.models.enums import Role, UserStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.security.passwords import hash_password, validate_password_strength


async def ensure_database_schema() -> None:
    """Create all ORM tables if they don't already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_default_organization() -> None:
    async with session_scope() as db:
        result = await db.execute(
            select(Organization).where(Organization.slug == settings.BOOTSTRAP_ORG_SLUG)
        )
        if result.scalar_one_or_none() is not None:
            return

        db.add(
            Organization(
                name=settings.BOOTSTRAP_ORG_NAME,
                slug=settings.BOOTSTRAP_ORG_SLUG,
                description=(
                    "Official link hub for IEEE Silver Oak University Student Branch."
                ),
                settings={
                    "allow_public_registration": True,
                    "default_member_role": Role.USER.value,
                    "max_groups_per_user": 25,
                    "require_group_approval": False,
                },
            )
        )
        app_logger.info(
            "bootstrap_organization_created", extra={"slug": settings.BOOTSTRAP_ORG_SLUG}
        )


async def ensure_super_admin() -> None:
    email = settings.BOOTSTRAP_SUPERADMIN_EMAIL.strip().lower()
    password = settings.BOOTSTRAP_SUPERADMIN_PASSWORD

    if not email or not password:
        return

    async with session_scope() as db:
        existing = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            # Never silently reset the password of an existing account.
            if not existing.is_super_admin:
                existing.system_role = Role.SUPER_ADMIN
                security_logger.warning(
                    "bootstrap_promoted_existing_user", extra={"user_id": str(existing.id)}
                )
            return

        try:
            validate_password_strength(password, email=email)
        except Exception:  # noqa: BLE001 - surface as a boot-time warning
            security_logger.error("bootstrap_superadmin_password_too_weak")
            raise

        organization = (
            await db.execute(
                select(Organization).where(Organization.slug == settings.BOOTSTRAP_ORG_SLUG)
            )
        ).scalar_one_or_none()
        if organization is None:
            return

        user = User(
            email=email,
            full_name="Platform Administrator",
            password_hash=hash_password(password),
            system_role=Role.SUPER_ADMIN,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            Membership(
                user_id=user.id,
                organization_id=organization.id,
                role=Role.ADMIN,
                is_default=True,
            )
        )
        security_logger.warning(
            "bootstrap_superadmin_created",
            extra={"user_id": str(user.id), "email": email},
        )


async def run_bootstrap() -> None:
    await ensure_database_schema()
    await ensure_default_organization()
    await ensure_super_admin()
