"""Public (unauthenticated) page schemas.

Only fields safe for anonymous consumption appear here. Owner ids, internal
counters, draft state and organization settings are all excluded by
construction rather than by filtering.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.group import SEO, Theme
from app.schemas.link import PublicLink


class PublicOrganization(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None


class PublicGroup(BaseModel):
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    theme: Theme
    seo: SEO
    public_url: str
    organization: PublicOrganization
    links: list[PublicLink]
    qr_png_url: str
    qr_svg_url: str


class PublicMeta(BaseModel):
    """Server-rendered metadata for OpenGraph/Twitter cards and SEO."""

    title: str
    description: str
    canonical_url: str
    image_url: str | None = None
    site_name: str
    twitter_card: str = "summary_large_image"
