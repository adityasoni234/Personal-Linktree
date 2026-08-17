"""Group, theme and SEO schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.security.colors import contrast_ratio, normalize_hex, readable_text_color
from app.security.sanitize import clean_text
from app.security.slug import validate_slug

ThemePreset = Literal["ieee-classic", "minimal-white", "dark", "corporate", "gradient", "event"]
ButtonStyle = Literal["solid", "outline", "soft", "glass"]
ButtonRadius = Literal["none", "sm", "md", "lg", "full"]
FontFamily = Literal["inter", "dm-sans", "space-grotesk", "source-serif", "system"]
BackgroundStyle = Literal["solid", "gradient", "pattern"]


class Theme(BaseModel):
    """Public page appearance.

    Colours are normalised and contrast-checked: the text colour is recomputed
    automatically whenever the author's choice would be unreadable, so a group
    can never be published in a state that fails WCAG on its own background.
    """

    model_config = ConfigDict(extra="forbid")

    preset: ThemePreset = "ieee-classic"
    primary_color: str = "#00629B"
    secondary_color: str = "#0B2545"
    background_color: str = "#F5F7FA"
    background_end_color: str | None = None
    background_style: BackgroundStyle = "solid"
    text_color: str | None = None
    button_style: ButtonStyle = "solid"
    button_radius: ButtonRadius = "lg"
    font: FontFamily = "inter"

    @field_validator(
        "primary_color", "secondary_color", "background_color", "background_end_color",
        "text_color",
    )
    @classmethod
    def _hex(cls, value: str | None) -> str | None:
        return normalize_hex(value) if value else None

    @model_validator(mode="after")
    def _ensure_readable(self) -> "Theme":
        if self.background_style == "gradient" and not self.background_end_color:
            self.background_end_color = self.primary_color
        chosen = self.text_color
        if not chosen or contrast_ratio(chosen, self.background_color) < 4.5:
            # Silently correcting beats publishing an unreadable page; the UI
            # surfaces the computed value so the author can see what happened.
            self.text_color = readable_text_color(self.background_color)
        return self


class SEO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=70)
    description: str | None = Field(default=None, max_length=200)
    og_image_url: str | None = Field(default=None, max_length=512)

    @field_validator("title", "description")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=200)


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=512)
    theme: Theme = Field(default_factory=Theme)
    seo: SEO = Field(default_factory=SEO)
    is_published: bool = False

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = clean_text(value, max_length=120)
        if not cleaned or len(cleaned) < 2:
            raise ValueError("Group name is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=500, allow_newlines=True)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str | None) -> str | None:
        return validate_slug(value) if value else None


class GroupUpdate(BaseModel):
    """Partial update — only the supplied fields are written."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=512)
    theme: Theme | None = None
    seo: SEO | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_text(value, max_length=120)
        if not cleaned or len(cleaned) < 2:
            raise ValueError("Group name is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return clean_text(value, max_length=500, allow_newlines=True)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str | None) -> str | None:
        return validate_slug(value) if value else None


class GroupStats(BaseModel):
    link_count: int = 0
    page_views: int = 0
    qr_scans: int = 0
    link_clicks: int = 0


class GroupSummary(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    owner_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    is_published: bool
    is_archived: bool
    position: int
    created_at: datetime
    updated_at: datetime
    public_url: str
    stats: GroupStats = Field(default_factory=GroupStats)


class GroupDetail(GroupSummary):
    theme: Theme
    seo: SEO
    published_at: datetime | None = None
    owner_name: str | None = None


class GroupDuplicateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    include_links: bool = True
    include_qr_design: bool = True


class GroupPublishRequest(BaseModel):
    is_published: bool
