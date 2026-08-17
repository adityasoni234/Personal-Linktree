"""Media upload endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status

from app.api.deps import CurrentPrincipal, DbSession
from app.core.rate_limit import Policies, rate_limit
from app.models.enums import MediaKind
from app.schemas.common import Message, Success
from app.schemas.media import MediaOut
from app.services import media_service

router = APIRouter(prefix="/media", tags=["Media"])


@router.post(
    "",
    response_model=Success[MediaOut],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(Policies.MEDIA_UPLOAD))],
    summary="Upload an image",
)
async def upload(
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
    file: Annotated[UploadFile, File(description="PNG, JPG, WEBP or SVG")],
    kind: Annotated[MediaKind, Query(description="What the image will be used for")],
) -> Success[MediaOut]:
    """Validate, sanitise and store an uploaded image.

    The file is identified by its bytes, re-encoded (rasters) or sanitised
    (SVG), and stored under a server-generated key.
    """
    media = await media_service.upload_media(db, file, kind, principal, request)
    await db.commit()
    await db.refresh(media)
    return Success(data=MediaOut.model_validate(media))


@router.get(
    "",
    response_model=Success[list[MediaOut]],
    summary="List uploaded images",
)
async def list_media(
    principal: CurrentPrincipal,
    db: DbSession,
    kind: Annotated[MediaKind | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Success[list[MediaOut]]:
    items = await media_service.list_media(db, principal, kind, limit)
    return Success(data=[MediaOut.model_validate(item) for item in items])


@router.delete("/{media_id}", response_model=Message, summary="Delete an image")
async def delete_media(
    media_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, request: Request
) -> Message:
    media = await media_service.get_media_or_404(db, media_id, principal)
    await media_service.delete_media(db, media, principal, request)
    await db.commit()
    return Message(message="File deleted")
