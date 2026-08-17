"""Link schemas.

URLs are validated twice: a fast structural pass here (so the client gets a
field-level error) and the authoritative pass in `validate_link_url`, which the
service layer always runs before writing to the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel
from app.security.colors import normalize_hex
from app.security.sanitize import clean_text
from app.security.url_validation import validate_link_url

LinkVariant = Literal["default", "solid", "outline", "soft", "minimal", "featured"]

# Icons are chosen from a fixed catalogue rather than free text, so the value
# can be mapped to a component without ever being interpolated into markup.
ICON_CATALOGUE = frozenset(
    {
        "link", "globe", "instagram", "linkedin", "github", "youtube", "facebook",
        "twitter", "x", "whatsapp", "telegram", "discord", "slack", "mail",
        "phone", "calendar", "map-pin", "file-text", "download", "ticket",
        "users", "book-open", "graduation-cap", "presentation", "camera",
        "megaphone", "award", "code", "cpu", "zap", "star", "heart", "external-link",
    }
)


class LinkStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: LinkVariant = "default"
    background_color: str | None = None
    text_color: str | None = None
    border_radius: Literal["none", "sm", "md", "lg", "full"] | None = None

    @field_validator("background_color", "text_color")
    @classmethod
    def _hex(cls, value: str | None) -> str | None:
        return normalize_hex(value) if value else None


class LinkBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=200)
    icon: str | None = Field(default=None, max_length=64)
    style: LinkStyle = Field(default_factory=LinkStyle)
    is_active: bool = True

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str) -> str:
        cleaned = clean_text(value, max_length=120)
        if not cleaned:
            raise ValueError("Link title is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=200)

    @field_validator("icon")
    @classmethod
    def _validate_icon(cls, value: str | None) -> str | None:
        if not value:
            return None
        candidate = value.strip().lower()
        if candidate not in ICON_CATALOGUE:
            raise ValueError("Unknown icon")
        return candidate

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return validate_link_url(value)


class LinkCreate(LinkBase):
    position: int | None = Field(default=None, ge=0, le=10_000)


class LinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=200)
    icon: str | None = Field(default=None, max_length=64)
    style: LinkStyle | None = None
    is_active: bool | None = None
    position: int | None = Field(default=None, ge=0, le=10_000)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_text(value, max_length=120)
        if not cleaned:
            raise ValueError("Link title is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=200)

    @field_validator("icon")
    @classmethod
    def _validate_icon(cls, value: str | None) -> str | None:
        if not value:
            return None
        candidate = value.strip().lower()
        if candidate not in ICON_CATALOGUE:
            raise ValueError("Unknown icon")
        return candidate

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        return validate_link_url(value) if value else None


class LinkOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    title: str
    url: str
    description: str | None
    icon: str | None
    style: LinkStyle
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    click_count: int = 0


class PublicLink(BaseModel):
    """Trimmed projection for the public page — no internal ids or counters."""

    id: uuid.UUID
    title: str
    url: str
    description: str | None
    icon: str | None
    style: LinkStyle
