"""Media uploads.

The upload path is: stream with a hard byte ceiling → validate by content →
sanitise/re-encode → store under a server-generated key → record a row. The
original filename is kept only as a display label.
"""

from __future__ import annotations

import uuid

from fastapi import Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, PayloadTooLargeError, PermissionDeniedError
from app.core.logging import security_logger
from app.models.enums import AuditAction, MediaKind, ResourceType
from app.models.media import Media
from app.security.image_validation import build_storage_key, validate_image
from app.security.rbac import Permission, Principal
from app.security.sanitize import clean_text
from app.services import audit_service
from app.storage import get_storage

# Per-organization ceiling; keeps a compromised account from filling the disk.
MAX_MEDIA_PER_ORGANIZATION = 500

_CHUNK_SIZE = 64 * 1024


async def read_upload(file: UploadFile, *, max_bytes: int | None = None) -> bytes:
    """Read an upload with a hard ceiling.

    Content-Length is checked by the body-size middleware, but a client can lie
    about it, so the stream itself is capped too.
    """
    limit = max_bytes or settings.MAX_UPLOAD_BYTES
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            security_logger.warning(
                "upload_exceeded_limit", extra={"limit_bytes": limit}
            )
            raise PayloadTooLargeError(
                f"File must be smaller than {limit // 1024} KB",
                details={"max_bytes": limit},
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def upload_media(
    db: AsyncSession,
    file: UploadFile,
    kind: MediaKind,
    principal: Principal,
    request: Request,
    *,
    allow_svg: bool = True,
) -> Media:
    principal.require(Permission.MEDIA_UPLOAD)
    if principal.organization_id is None:
        raise PermissionDeniedError("You are not a member of any organization")

    used = await db.scalar(
        select(func.count(Media.id)).where(
            Media.organization_id == principal.organization_id
        )
    ) or 0
    if used >= MAX_MEDIA_PER_ORGANIZATION:
        raise PermissionDeniedError(
            "This organization has reached its media storage limit",
            code="QUOTA_EXCEEDED",
        )

    raw = await read_upload(file)
    validated = validate_image(
        raw,
        declared_content_type=file.content_type,
        filename=file.filename,
        allow_svg=allow_svg,
    )

    # Key components come from internal ids and a random name — never from the
    # uploaded filename.
    storage_key = build_storage_key(
        f"{principal.organization_id}/{kind.value.lower()}", validated.extension
    )
    public_url = await get_storage().save(
        storage_key, validated.content, content_type=validated.content_type
    )

    media = Media(
        organization_id=principal.organization_id,
        uploaded_by_id=principal.user_id,
        kind=kind,
        storage_key=storage_key,
        public_url=public_url,
        original_filename=clean_text(file.filename, max_length=255),
        content_type=validated.content_type,
        size_bytes=validated.size_bytes,
        width=validated.width or None,
        height=validated.height or None,
        checksum_sha256=validated.checksum_sha256,
    )
    db.add(media)
    await db.flush()

    await audit_service.record(
        db,
        action=AuditAction.MEDIA_UPLOADED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=principal.organization_id,
        resource_type=ResourceType.MEDIA,
        resource_id=media.id,
        metadata={
            "kind": kind.value,
            "content_type": validated.content_type,
            "size_bytes": validated.size_bytes,
        },
        request=request,
    )
    return media


async def get_media_or_404(
    db: AsyncSession, media_id: uuid.UUID, principal: Principal
) -> Media:
    media = await db.get(Media, media_id)
    if media is None or not principal.in_organization(media.organization_id):
        raise NotFoundError("File not found")
    return media


async def load_bytes(media: Media) -> bytes | None:
    return await get_storage().load(media.storage_key)


async def delete_media(
    db: AsyncSession, media: Media, principal: Principal, request: Request
) -> None:
    is_owner = media.uploaded_by_id == principal.user_id
    if not (is_owner or principal.has(Permission.MEDIA_DELETE_ANY)):
        raise PermissionDeniedError("You cannot delete this file")

    await audit_service.record(
        db,
        action=AuditAction.MEDIA_DELETED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=media.organization_id,
        resource_type=ResourceType.MEDIA,
        resource_id=media.id,
        metadata={"kind": media.kind.value},
        request=request,
    )
    await db.delete(media)
    # Storage deletion is best-effort and happens after the row is gone, so a
    # storage outage can never leave a dangling reference in the database.
    await get_storage().delete(media.storage_key)


async def list_media(
    db: AsyncSession, principal: Principal, kind: MediaKind | None = None, limit: int = 50
) -> list[Media]:
    query = select(Media).order_by(Media.created_at.desc()).limit(min(limit, 100))
    if not principal.is_super_admin:
        query = query.where(Media.organization_id == principal.organization_id)
    if kind is not None:
        query = query.where(Media.kind == kind)
    return list((await db.execute(query)).scalars())
