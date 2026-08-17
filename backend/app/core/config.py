"""Application configuration.

All secrets and deployment-specific values come from the environment. Nothing
sensitive is ever hardcoded here, and production refuses to boot with insecure
defaults (see `_validate_production_hardening`).
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Runtime ---------------------------------------------------------
    ENVIRONMENT: Environment = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "IEEE SOU Link Hub"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # ---- Database --------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://linkhub:linkhub@localhost:5432/linkhub"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO: bool = False

    # ---- Redis -----------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- JWT -------------------------------------------------------------
    JWT_SECRET: str = ""
    JWT_REFRESH_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 14
    PASSWORD_RESET_TTL_MINUTES: int = 30

    # ---- Cookies ---------------------------------------------------------
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    REFRESH_COOKIE_NAME: str = "lh_refresh"
    CSRF_COOKIE_NAME: str = "lh_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # ---- CORS / URLs -----------------------------------------------------
    # Comma-separated in the environment; read through `cors_origins`.
    CORS_ORIGINS: str = "http://localhost:5173"
    FRONTEND_URL: str = "http://localhost:5173"
    PUBLIC_BASE_URL: str = "http://localhost:5173"

    # ---- Analytics -------------------------------------------------------
    ANALYTICS_IP_PEPPER: str = ""
    ANALYTICS_DEDUPE_WINDOW_SECONDS: int = 1800

    # ---- Storage ---------------------------------------------------------
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_DIR: str = "/var/lib/linkhub/media"
    STORAGE_PUBLIC_BASE_URL: str = "http://localhost:8000/media"
    STORAGE_BUCKET: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    STORAGE_REGION: str = "auto"
    STORAGE_ENDPOINT_URL: str | None = None

    # ---- Uploads ---------------------------------------------------------
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024
    MAX_IMAGE_DIMENSION: int = 4096
    MAX_IMAGE_PIXELS: int = 25_000_000

    # ---- Pagination ------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ---- Rate limiting ---------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True

    # ---- Bootstrap -------------------------------------------------------
    BOOTSTRAP_ORG_NAME: str = "IEEE SOU"
    BOOTSTRAP_ORG_SLUG: str = "ieee-sou"
    BOOTSTRAP_SUPERADMIN_EMAIL: str = ""
    BOOTSTRAP_SUPERADMIN_PASSWORD: str = ""

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _join_origins(cls, value: object) -> object:
        """Accept a list as well as the comma-separated string form."""
        if isinstance(value, (list, tuple)):
            return ",".join(str(origin).strip() for origin in value)
        return value

    @field_validator("COOKIE_DOMAIN", "STORAGE_ENDPOINT_URL", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("FRONTEND_URL", "PUBLIC_BASE_URL", "STORAGE_PUBLIC_BASE_URL")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _fill_dev_secrets(self) -> "Settings":
        """Development gets ephemeral random secrets so `docker compose up` just
        works; production must supply real ones (enforced below)."""
        if self.ENVIRONMENT != "production":
            if not self.JWT_SECRET:
                self.JWT_SECRET = secrets.token_urlsafe(64)
            if not self.JWT_REFRESH_SECRET:
                self.JWT_REFRESH_SECRET = secrets.token_urlsafe(64)
            if not self.ANALYTICS_IP_PEPPER:
                self.ANALYTICS_IP_PEPPER = secrets.token_urlsafe(32)
        return self

    @model_validator(mode="after")
    def _validate_production_hardening(self) -> "Settings":
        if self.ENVIRONMENT != "production":
            return self

        problems: list[str] = []
        if len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be set and at least 32 characters")
        if len(self.JWT_REFRESH_SECRET) < 32:
            problems.append("JWT_REFRESH_SECRET must be set and at least 32 characters")
        if self.JWT_SECRET == self.JWT_REFRESH_SECRET:
            problems.append("JWT_SECRET and JWT_REFRESH_SECRET must differ")
        if len(self.ANALYTICS_IP_PEPPER) < 16:
            problems.append("ANALYTICS_IP_PEPPER must be set and at least 16 characters")
        if not self.COOKIE_SECURE:
            problems.append("COOKIE_SECURE must be true in production")
        if self.DEBUG:
            problems.append("DEBUG must be false in production")
        origins = self.cors_origins
        if not origins or any(origin == "*" for origin in origins):
            problems.append("CORS_ORIGINS must be an explicit non-wildcard allowlist")
        if any(origin.startswith("http://") for origin in origins):
            problems.append("CORS_ORIGINS must use https:// in production")
        if self.STORAGE_BACKEND == "s3" and not self.STORAGE_BUCKET:
            problems.append("STORAGE_BUCKET is required when STORAGE_BACKEND=s3")

        if problems:
            raise ValueError(
                "Insecure production configuration:\n  - " + "\n  - ".join(problems)
            )
        return self

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------
    @property
    def cors_origins(self) -> list[str]:
        """Explicit allowlist of browser origins permitted to call the API."""
        return [
            origin.strip().rstrip("/")
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def access_token_ttl_seconds(self) -> int:
        return self.ACCESS_TOKEN_TTL_MINUTES * 60

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return self.REFRESH_TOKEN_TTL_DAYS * 24 * 3600

    def public_group_url(self, slug: str) -> str:
        return f"{self.PUBLIC_BASE_URL}/g/{slug}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
