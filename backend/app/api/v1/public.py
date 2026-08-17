"""Public, unauthenticated endpoints for published group pages.

These are the only routes an anonymous visitor can reach. Two rules govern
everything here:

  1. only published, non-archived groups are visible — drafts and archived
     groups are indistinguishable from groups that never existed;
  2. responses are built from `app.schemas.public`, which has no owner ids,
     counters, draft state or organization settings in it at all.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.analytics import collector
from app.api.deps import DbSession
from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.rate_limit import Policies, rate_limit
from app.models.enums import AnalyticsEventType
from app.qr import engine
from app.schemas.common import Message, Success
from app.schemas.group import SEO, Theme
from app.schemas.link import PublicLink
from app.schemas.public import PublicGroup, PublicMeta, PublicOrganization
from app.security.slug import MAX_SLUG_LENGTH
from app.services import group_service, link_service, qr_service

router = APIRouter(prefix="/public", tags=["Public"])

SlugPath = Annotated[
    str,
    Path(
        min_length=3,
        max_length=MAX_SLUG_LENGTH,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Public group address",
    ),
]


def _build_meta(group, description: str | None) -> PublicMeta:
    seo = group.seo or {}
    return PublicMeta(
        title=seo.get("title") or f"{group.name} · {group.organization.name}",
        description=(
            seo.get("description")
            or description
            or f"All the official links for {group.name}."
        ),
        canonical_url=settings.public_group_url(group.slug),
        image_url=seo.get("og_image_url") or group.logo_url,
        site_name=group.organization.name,
    )


@router.get(
    "/groups/{slug}",
    response_model=Success[PublicGroup],
    dependencies=[Depends(rate_limit(Policies.PUBLIC_PAGE))],
    summary="Get a published group page",
)
async def get_public_group(
    slug: SlugPath,
    request: Request,
    db: DbSession,
    background: BackgroundTasks,
    src: Annotated[Literal["direct", "qr", "share"], Query()] = "direct",
) -> Success[PublicGroup]:
    group = await group_service.get_public_group(db, slug)
    links = await link_service.public_links(db, group.id)

    # A scan is a page view that arrived via the QR marker; the distinction is
    # made from the URL the code encodes, not from anything the client asserts.
    event_type = (
        AnalyticsEventType.QR_SCAN if src == "qr" else AnalyticsEventType.PAGE_VIEW
    )
    context = collector.capture_context(request, group_id=group.id)
    background.add_task(
        collector.record_event_background,
        organization_id=group.organization_id,
        group_id=group.id,
        event_type=event_type,
        **context,
    )

    qr_base = f"{settings.API_V1_PREFIX}/public/groups/{group.slug}/qr"
    return Success(
        data=PublicGroup(
            name=group.name,
            slug=group.slug,
            description=group.description,
            logo_url=group.logo_url,
            theme=Theme.model_validate(group.theme or {}),
            seo=SEO.model_validate(group.seo or {}),
            public_url=settings.public_group_url(group.slug),
            organization=PublicOrganization(
                name=group.organization.name,
                slug=group.organization.slug,
                logo_url=group.organization.logo_url,
            ),
            links=[
                PublicLink(
                    id=link.id,
                    title=link.title,
                    url=link.url,
                    description=link.description,
                    icon=link.icon,
                    style=link.style or {},
                )
                for link in links
            ],
            qr_png_url=f"{qr_base}.png",
            qr_svg_url=f"{qr_base}.svg",
        )
    )


@router.get(
    "/groups/{slug}/meta",
    response_model=Success[PublicMeta],
    dependencies=[Depends(rate_limit(Policies.PUBLIC_PAGE))],
    summary="OpenGraph / SEO metadata for a published group",
)
async def get_public_meta(slug: SlugPath, db: DbSession) -> Success[PublicMeta]:
    group = await group_service.get_public_group(db, slug)
    return Success(data=_build_meta(group, group.description))


@router.get(
    "/groups/{slug}/links/{link_id}",
    response_class=RedirectResponse,
    status_code=302,
    dependencies=[Depends(rate_limit(Policies.PUBLIC_PAGE))],
    summary="Follow a link and record the click",
)
async def follow_link(
    slug: SlugPath,
    link_id: uuid.UUID,
    request: Request,
    db: DbSession,
    background: BackgroundTasks,
) -> RedirectResponse:
    group = await group_service.get_public_group(db, slug)

    links = await link_service.public_links(db, group.id)
    link = next((candidate for candidate in links if candidate.id == link_id), None)
    if link is None:
        raise NotFoundError("This link is not available")

    context = collector.capture_context(request, group_id=group.id, link_id=link.id)
    background.add_task(
        collector.record_event_background,
        organization_id=group.organization_id,
        group_id=group.id,
        link_id=link.id,
        event_type=AnalyticsEventType.LINK_CLICK,
        **context,
    )

    # The destination is the stored, already-validated URL — never a value taken
    # from the request, so this cannot be turned into an open redirect.
    return RedirectResponse(
        url=link.url,
        status_code=302,
        headers={
            "Cache-Control": "no-store",
            # Do not leak the referring page to the destination.
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get(
    "/groups/{slug}/qr.{fmt}",
    response_class=Response,
    dependencies=[Depends(rate_limit(Policies.PUBLIC_QR))],
    summary="Download a published group's QR code",
    responses={
        200: {
            "content": {"image/png": {}, "image/svg+xml": {}},
            "description": "Rendered QR code",
        }
    },
)
async def public_qr(
    slug: SlugPath,
    fmt: Literal["png", "svg"],
    db: DbSession,
    size: Annotated[int, Query(ge=128, le=1024)] = 512,
) -> Response:
    group = await group_service.get_public_group(db, slug)
    payload = await qr_service.render(db, group, fmt, size=size)
    await db.commit()

    return Response(
        content=payload,
        media_type=engine.CONTENT_TYPES[fmt],
        headers={
            "Content-Disposition": f'inline; filename="{group.slug}-qr.{fmt}"',
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/groups/{slug}/events",
    response_model=Message,
    dependencies=[Depends(rate_limit(Policies.ANALYTICS_INGEST))],
    summary="Record a share interaction",
)
async def track_event(
    slug: SlugPath, request: Request, db: DbSession, background: BackgroundTasks
) -> Message:
    """The only client-driven event.

    Even here the client cannot choose the group, the link, the timestamp or the
    visitor — those are all resolved from the URL and the connection.
    """
    group = await group_service.get_public_group(db, slug)
    context = collector.capture_context(request, group_id=group.id)
    background.add_task(
        collector.record_event_background,
        organization_id=group.organization_id,
        group_id=group.id,
        event_type=AnalyticsEventType.SHARE,
        **context,
    )
    return Message(message="Recorded")
