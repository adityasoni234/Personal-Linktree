"""QR configuration and rendering.

The single most important invariant in this module: **the encoded payload is
always the group's public page URL, derived server-side from the slug.** A
client never supplies the QR target, so a printed code can never be repointed at
an attacker-chosen destination, and the links behind it stay editable forever.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.core.logging import app_logger
from app.models.enums import AuditAction, MediaKind, ResourceType
from app.models.group import Group
from app.models.media import Media
from app.models.qr import QRConfiguration
from app.qr import engine
from app.qr.presets import get_preset
from app.qr.spec import QRSpec, scannability_report
from app.schemas.qr import QRConfigOut, QRConfigUpdate, QRRenderInfo, QRWarning
from app.security.colors import MIN_QR_CONTRAST_RATIO, contrast_ratio
from app.security.rbac import Principal, can_edit_group
from app.services import audit_service

_LOGO_CACHE_FIELDS = ("logo_media_id",)


QR_SOURCE_PARAM = "src=qr"


def target_url(group: Group) -> str:
    """The one and only thing a group QR code ever encodes.

    The `src=qr` marker is what lets a scan be counted separately from a direct
    visit. It is appended server-side and is the only query parameter the code
    ever carries — the destination itself is always this group's public page.
    """
    return f"{settings.public_group_url(group.slug)}?{QR_SOURCE_PARAM}"


async def get_or_create_config(db: AsyncSession, group: Group) -> QRConfiguration:
    result = await db.execute(
        select(QRConfiguration).where(QRConfiguration.group_id == group.id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = QRConfiguration(group_id=group.id, preset="ieee-classic")
        db.add(config)
        await db.flush()
    return config


async def _logo_for(db: AsyncSession, config: QRConfiguration,
                    principal: Principal | None) -> tuple[bytes | None, str | None, str | None]:
    """Load the logo bytes for rendering, enforcing organization ownership."""
    if not config.logo_media_id:
        return None, None, None

    media = await db.get(Media, config.logo_media_id)
    if media is None:
        return None, None, None

    # A logo can only ever be an asset belonging to the group's organization —
    # checked against the stored row, not against anything the caller sent.
    group = await db.get(Group, config.group_id)
    if group is not None and media.organization_id != group.organization_id:
        app_logger.warning(
            "qr_logo_cross_organization_blocked",
            extra={"media_id": str(media.id), "group_id": str(config.group_id)},
        )
        return None, None, None

    from app.services.media_service import load_bytes

    data = await load_bytes(media)
    return data, media.content_type, media.public_url


async def build_spec(
    db: AsyncSession,
    group: Group,
    config: QRConfiguration,
    *,
    size: int = 1024,
    principal: Principal | None = None,
    overrides: QRConfigUpdate | None = None,
) -> tuple[QRSpec, str | None]:
    """Assemble a render specification. `overrides` powers live preview."""
    source = overrides or config
    logo_bytes, logo_type, logo_url = (None, None, None)

    logo_media_id = getattr(source, "logo_media_id", None) or config.logo_media_id
    if logo_media_id:
        probe = QRConfiguration(group_id=group.id, logo_media_id=logo_media_id)
        logo_bytes, logo_type, logo_url = await _logo_for(db, probe, principal)

    spec = QRSpec(
        data=target_url(group),
        foreground=source.foreground_color,
        background=source.background_color,
        transparent_background=source.transparent_background,
        gradient_type=source.gradient_type,
        gradient_start=source.gradient_start_color,
        gradient_end=source.gradient_end_color,
        gradient_angle=source.gradient_angle,
        dot_style=source.dot_style,
        eye_frame_style=source.eye_frame_style,
        eye_ball_style=source.eye_ball_style,
        eye_color=source.eye_color,
        eye_ball_color=source.eye_ball_color,
        margin=source.margin,
        error_correction=source.error_correction,
        logo_bytes=logo_bytes,
        logo_content_type=logo_type,
        logo_size=source.logo_size,
        logo_padding=source.logo_padding,
        logo_shape=source.logo_shape,
        logo_background=source.logo_background,
        frame_style=source.frame_style,
        frame_color=source.frame_color,
        frame_text_color=source.frame_text_color,
        caption=source.caption,
        size=size,
    )
    return spec, logo_url


def _assert_scannable(spec: QRSpec) -> None:
    """Reject a design that provably cannot be scanned.

    Advisory issues are returned as warnings; only a code that is certain to
    fail is blocked, because a printed unscannable QR is a real-world failure,
    not a cosmetic one.
    """
    background = spec.background if not spec.transparent_background else "#FFFFFF"
    foreground = (
        spec.gradient_start if spec.gradient_type.value != "none" else spec.foreground
    ) or spec.foreground

    ratio = contrast_ratio(foreground, background)
    if ratio < MIN_QR_CONTRAST_RATIO:
        raise ValidationError(
            f"Contrast between the code and its background is only {ratio}:1. "
            f"At least {MIN_QR_CONTRAST_RATIO}:1 is required for a scannable code.",
            code="QR_NOT_SCANNABLE",
            details={"field": "foreground_color", "contrast_ratio": ratio},
        )
    if spec.gradient_end:
        end_ratio = contrast_ratio(spec.gradient_end, background)
        if end_ratio < MIN_QR_CONTRAST_RATIO:
            raise ValidationError(
                f"The gradient fades to {end_ratio}:1 contrast, which will not scan.",
                code="QR_NOT_SCANNABLE",
                details={"field": "gradient_end_color", "contrast_ratio": end_ratio},
            )


async def update_config(
    db: AsyncSession,
    group: Group,
    payload: QRConfigUpdate,
    principal: Principal,
    request: Request,
) -> QRConfiguration:
    if not can_edit_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot change the QR design for this group")

    config = await get_or_create_config(db, group)

    if payload.logo_media_id is not None:
        media = await db.get(Media, payload.logo_media_id)
        if media is None or media.organization_id != group.organization_id:
            raise NotFoundError("Logo image not found")
        if media.kind not in (MediaKind.QR_LOGO, MediaKind.GROUP_LOGO, MediaKind.ORG_LOGO):
            raise ValidationError("That file cannot be used as a QR logo")

    data = payload.model_dump()
    for field, value in data.items():
        setattr(config, field, value)

    spec, _ = await build_spec(db, group, config, principal=principal)
    _assert_scannable(spec)

    await audit_service.record(
        db,
        action=AuditAction.QR_CONFIG_UPDATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.QR_CONFIGURATION,
        resource_id=config.id,
        metadata={
            "name": group.name,
            "preset": config.preset,
            "dot_style": config.dot_style.value,
            "has_logo": bool(config.logo_media_id),
        },
        request=request,
    )
    return config


async def apply_preset(
    db: AsyncSession, group: Group, preset_name: str, principal: Principal, request: Request
) -> QRConfiguration:
    values = get_preset(preset_name)
    if values is None:
        raise NotFoundError("Unknown preset", details={"field": "preset"})

    if not can_edit_group(
        principal, organization_id=group.organization_id, owner_id=group.owner_id
    ):
        raise PermissionDeniedError("You cannot change the QR design for this group")

    config = await get_or_create_config(db, group)
    for field, value in values.items():
        setattr(config, field, value)
    # A preset never carries a gradient when the field is absent.
    config.preset = preset_name.strip().lower()
    if "gradient_start_color" not in values:
        config.gradient_start_color = None
        config.gradient_end_color = None

    await audit_service.record(
        db,
        action=AuditAction.QR_CONFIG_UPDATED,
        actor_id=principal.user_id,
        actor_email=principal.email,
        organization_id=group.organization_id,
        resource_type=ResourceType.QR_CONFIGURATION,
        resource_id=config.id,
        metadata={"name": group.name, "preset": config.preset},
        request=request,
    )
    return config


def to_out(config: QRConfiguration, logo_url: str | None = None) -> QRConfigOut:
    return QRConfigOut.model_validate(
        {
            **{
                column.name: getattr(config, column.name)
                for column in QRConfiguration.__table__.columns
            },
            "logo_url": logo_url,
        }
    )


async def render_info(
    spec: QRSpec, group: Group, *, include_preview: bool = True
) -> QRRenderInfo:
    report = scannability_report(spec)
    preview = None
    if include_preview:
        preview = await engine.render_data_uri(spec.with_size(420), "png")

    base = f"{settings.API_V1_PREFIX}/groups/{group.id}/qr"
    return QRRenderInfo(
        target_url=spec.data,
        contrast_ratio=report["contrast_ratio"],
        is_scannable=report["is_scannable"],
        warnings=[QRWarning(**warning) for warning in report["warnings"]],
        preview_data_uri=preview,
        png_url=f"{base}.png",
        svg_url=f"{base}.svg",
    )


async def render(
    db: AsyncSession,
    group: Group,
    fmt: engine.RenderFormat,
    *,
    size: int = 1024,
    principal: Principal | None = None,
) -> bytes:
    config = await get_or_create_config(db, group)
    spec, _ = await build_spec(db, group, config, size=size, principal=principal)
    return await engine.render(spec, fmt)


async def invalidate_for_group(db: AsyncSession, group_id: uuid.UUID) -> None:
    """Called when a slug changes — the encoded URL, and so the cache key, moves."""
    group = await db.get(Group, group_id)
    if group is None:
        return
    config = await get_or_create_config(db, group)
    spec, _ = await build_spec(db, group, config)
    await engine.invalidate_cache(spec)
