"""QR configuration, preview and download endpoints.

Rendering is authenticated and rate limited because it is CPU-bound; the public
download route for a *published* group is separate and more tightly capped.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import CurrentPrincipal, DbSession
from app.core.rate_limit import Policies, rate_limit
from app.qr import engine
from app.qr.presets import preset_catalogue
from app.qr.spec import DEFAULT_OUTPUT_SIZE, MAX_OUTPUT_SIZE, MIN_OUTPUT_SIZE
from app.schemas.common import Success
from app.schemas.qr import (
    QRConfigResponse,
    QRConfigUpdate,
    QRPresetOut,
    QRPreviewRequest,
    QRRenderInfo,
)
from app.services import group_service, qr_service

router = APIRouter(tags=["QR Codes"])

SizeQuery = Annotated[
    int, Query(ge=MIN_OUTPUT_SIZE, le=MAX_OUTPUT_SIZE, description="Output size in pixels")
]


@router.get(
    "/qr/presets",
    response_model=Success[list[QRPresetOut]],
    summary="List QR design presets",
)
async def list_presets(_: CurrentPrincipal) -> Success[list[QRPresetOut]]:
    return Success(data=[QRPresetOut(**preset) for preset in preset_catalogue()])


@router.get(
    "/groups/{group_id}/qr",
    response_model=Success[QRConfigResponse],
    dependencies=[Depends(rate_limit(Policies.QR_RENDER))],
    summary="Get the QR design for a group",
)
async def get_qr(
    group_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> Success[QRConfigResponse]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    config = await qr_service.get_or_create_config(db, group)
    await db.commit()

    spec, logo_url = await qr_service.build_spec(db, group, config, principal=principal)
    return Success(
        data=QRConfigResponse(
            config=qr_service.to_out(config, logo_url),
            render=await qr_service.render_info(spec, group),
        )
    )


@router.post(
    "/groups/{group_id}/qr",
    response_model=Success[QRConfigResponse],
    dependencies=[Depends(rate_limit(Policies.QR_RENDER))],
    summary="Save the QR design for a group",
)
async def update_qr(
    group_id: uuid.UUID,
    payload: QRConfigUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[QRConfigResponse]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    config = await qr_service.update_config(db, group, payload, principal, request)
    await db.commit()
    await db.refresh(config)

    spec, logo_url = await qr_service.build_spec(db, group, config, principal=principal)
    return Success(
        data=QRConfigResponse(
            config=qr_service.to_out(config, logo_url),
            render=await qr_service.render_info(spec, group),
        )
    )


@router.post(
    "/groups/{group_id}/qr/preset/{preset_name}",
    response_model=Success[QRConfigResponse],
    dependencies=[Depends(rate_limit(Policies.QR_RENDER))],
    summary="Apply a preset to a group's QR design",
)
async def apply_preset(
    group_id: uuid.UUID,
    preset_name: str,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
) -> Success[QRConfigResponse]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    config = await qr_service.apply_preset(db, group, preset_name, principal, request)
    await db.commit()
    await db.refresh(config)

    spec, logo_url = await qr_service.build_spec(db, group, config, principal=principal)
    return Success(
        data=QRConfigResponse(
            config=qr_service.to_out(config, logo_url),
            render=await qr_service.render_info(spec, group),
        )
    )


@router.post(
    "/groups/{group_id}/qr/preview",
    response_model=Success[QRRenderInfo],
    dependencies=[Depends(rate_limit(Policies.QR_RENDER))],
    summary="Render an unsaved QR design",
)
async def preview_qr(
    group_id: uuid.UUID,
    payload: QRPreviewRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> Success[QRRenderInfo]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    config = await qr_service.get_or_create_config(db, group)
    await db.commit()

    # The encoded URL still comes from the group, never from the payload.
    spec, _ = await qr_service.build_spec(
        db,
        group,
        config,
        size=payload.size,
        principal=principal,
        overrides=payload,
    )
    return Success(data=await qr_service.render_info(spec, group))


@router.get(
    "/groups/{group_id}/qr.{fmt}",
    dependencies=[Depends(rate_limit(Policies.QR_RENDER))],
    response_class=Response,
    summary="Download a group's QR code",
    responses={
        200: {
            "content": {"image/png": {}, "image/svg+xml": {}},
            "description": "Rendered QR code",
        }
    },
)
async def download_qr(
    group_id: uuid.UUID,
    fmt: Literal["png", "svg"],
    principal: CurrentPrincipal,
    db: DbSession,
    size: SizeQuery = DEFAULT_OUTPUT_SIZE,
    download: Annotated[bool, Query()] = True,
) -> Response:
    group = await group_service.get_group_or_404(db, group_id, principal)
    payload = await qr_service.render(db, group, fmt, size=size, principal=principal)
    await db.commit()

    disposition = "attachment" if download else "inline"
    return Response(
        content=payload,
        media_type=engine.CONTENT_TYPES[fmt],
        headers={
            # Filename is built from the validated slug, so it cannot contain
            # path separators or header-injection characters.
            "Content-Disposition": f'{disposition}; filename="{group.slug}-qr.{fmt}"',
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
