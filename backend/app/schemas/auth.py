"""Authentication request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Role, UserStatus
from app.schemas.common import ORMModel
from app.security.sanitize import clean_text, normalize_email


class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    full_name: str = Field(min_length=2, max_length=120)
    # Strength is enforced by `validate_password_strength`; the bounds here only
    # stop absurd payloads from reaching the hasher.
    password: str = Field(min_length=10, max_length=128)
    organization_slug: str | None = Field(default=None, max_length=64)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = clean_text(value, max_length=120)
        if not cleaned or len(cleaned) < 2:
            raise ValueError("Enter your full name")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return normalize_email(value)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=320)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return normalize_email(value)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
    # When true every other device is signed out.
    revoke_other_sessions: bool = True


class MembershipSummary(ORMModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: Role


class UserProfile(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    system_role: Role
    status: UserStatus
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None

    organization_id: uuid.UUID | None = None
    organization_name: str | None = None
    organization_role: Role | None = None
    effective_role: Role
    permissions: list[str] = []


class AuthSession(BaseModel):
    """Payload returned by register / login / refresh.

    The refresh token is *not* in this body — it is set as an HttpOnly cookie.
    The access token is short-lived and is meant to be held in memory only.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: datetime
    csrf_token: str
    user: UserProfile


class SessionInfo(ORMModel):
    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    user_agent_label: str | None
    is_current: bool = False
