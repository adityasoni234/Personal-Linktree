"""Administration schemas: users, memberships, audit log, organization settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import AuditAction, ResourceType, Role, UserStatus
from app.schemas.common import ORMModel
from app.security.sanitize import clean_text, normalize_email


class AdminUserRow(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    avatar_url: str | None
    system_role: Role
    status: UserStatus
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None
    organization_role: Role | None = None
    organization_name: str | None = None
    group_count: int = 0


class RoleChangeRequest(BaseModel):
    role: Role


class UserStatusRequest(BaseModel):
    status: UserStatus
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("reason")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=200)


class MemberInviteRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    role: Role = Role.USER

    @field_validator("email")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalize_email(value)


class AuditLogRow(ORMModel):
    id: uuid.UUID
    action: AuditAction
    actor_id: uuid.UUID | None
    actor_email: str | None
    resource_type: ResourceType | None
    resource_id: str | None
    event_metadata: dict[str, Any]
    created_at: datetime


class OrganizationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_public_registration: bool = True
    default_member_role: Role = Role.USER
    max_groups_per_user: int = Field(default=25, ge=1, le=500)
    require_group_approval: bool = False


class OrganizationOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    website_url: str | None
    is_active: bool
    settings: OrganizationSettings
    created_at: datetime
    member_count: int = 0
    group_count: int = 0


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=512)
    website_url: str | None = Field(default=None, max_length=512)
    settings: OrganizationSettings | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=120)

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=500, allow_newlines=True)

    @field_validator("website_url")
    @classmethod
    def _validate_website(cls, value: str | None) -> str | None:
        if not value:
            return None
        from app.security.url_validation import validate_link_url

        return validate_link_url(value, allow_contact_schemes=False)


class SystemStats(BaseModel):
    users: int
    organizations: int
    groups: int
    links: int
    events_last_30d: int
    published_groups: int


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=512)

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_text(value, max_length=120)
        if not cleaned or len(cleaned) < 2:
            raise ValueError("Enter your full name")
        return cleaned
