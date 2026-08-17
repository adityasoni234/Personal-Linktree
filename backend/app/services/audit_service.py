"""Audit logging.

Every security-sensitive operation writes one row here and one structured line
to the `app.audit` logger, so the trail survives even if the database is later
compromised or truncated. Metadata is scrubbed before it is stored.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.privacy import hash_ip
from app.core.logging import audit_logger, redact
from app.core.rate_limit import client_ip
from app.models.audit import AuditLog
from app.models.enums import AuditAction, ResourceType
from app.security.sanitize import user_agent_label

# Metadata values are truncated so a large payload cannot bloat the audit table.
_MAX_VALUE_LENGTH = 512
_MAX_KEYS = 24


def _scrub(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    cleaned = redact(metadata)
    result: dict[str, Any] = {}
    for index, (key, value) in enumerate(cleaned.items()):
        if index >= _MAX_KEYS:
            break
        if isinstance(value, str) and len(value) > _MAX_VALUE_LENGTH:
            value = value[:_MAX_VALUE_LENGTH] + "…"
        result[str(key)[:64]] = value
    return result


async def record(
    db: AsyncSession,
    *,
    action: AuditAction,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    organization_id: uuid.UUID | None = None,
    resource_type: ResourceType | None = None,
    resource_id: str | uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Append an audit entry. The caller owns the surrounding transaction."""
    entry = AuditLog(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        organization_id=organization_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        event_metadata=_scrub(metadata),
        ip_hash=hash_ip(client_ip(request)) if request else None,
        user_agent_label=(
            user_agent_label(request.headers.get("user-agent")) if request else None
        ),
    )
    db.add(entry)

    audit_logger.info(
        "audit_event",
        extra={
            "action": action.value,
            "actor_id": str(actor_id) if actor_id else None,
            "organization_id": str(organization_id) if organization_id else None,
            "resource_type": resource_type.value if resource_type else None,
            "resource_id": str(resource_id) if resource_id else None,
            "metadata": entry.event_metadata,
        },
    )
    return entry


def describe(entry: AuditLog) -> str:
    """Human-readable summary used by the dashboard activity feed."""
    metadata = entry.event_metadata or {}
    name = metadata.get("name") or metadata.get("title") or metadata.get("slug")
    subject = f" “{name}”" if name else ""

    descriptions: dict[AuditAction, str] = {
        AuditAction.GROUP_CREATED: f"created group{subject}",
        AuditAction.GROUP_UPDATED: f"updated group{subject}",
        AuditAction.GROUP_DELETED: f"deleted group{subject}",
        AuditAction.GROUP_ARCHIVED: f"archived group{subject}",
        AuditAction.GROUP_RESTORED: f"restored group{subject}",
        AuditAction.GROUP_PUBLISHED: f"published group{subject}",
        AuditAction.GROUP_UNPUBLISHED: f"unpublished group{subject}",
        AuditAction.GROUP_DUPLICATED: f"duplicated group{subject}",
        AuditAction.GROUP_SLUG_CHANGED: f"changed the address of group{subject}",
        AuditAction.GROUP_REORDERED: "reordered groups",
        AuditAction.LINK_CREATED: f"added link{subject}",
        AuditAction.LINK_UPDATED: f"updated link{subject}",
        AuditAction.LINK_DELETED: f"removed link{subject}",
        AuditAction.LINK_REORDERED: "reordered links",
        AuditAction.QR_CONFIG_UPDATED: f"updated the QR design for{subject or ' a group'}",
        AuditAction.MEDIA_UPLOADED: "uploaded an image",
        AuditAction.MEDIA_DELETED: "deleted an image",
        AuditAction.USER_REGISTERED: "joined the organization",
        AuditAction.LOGIN_SUCCEEDED: "signed in",
        AuditAction.LOGOUT: "signed out",
        AuditAction.PASSWORD_CHANGED: "changed their password",
        AuditAction.PASSWORD_RESET_COMPLETED: "reset their password",
        AuditAction.ROLE_CHANGED: f"changed a member role to {metadata.get('new_role', '')}".strip(),
        AuditAction.MEMBER_ADDED: "added a member",
        AuditAction.MEMBER_REMOVED: "removed a member",
        AuditAction.USER_SUSPENDED: "suspended a user",
        AuditAction.USER_REACTIVATED: "reactivated a user",
        AuditAction.ORG_SETTINGS_UPDATED: "updated organization settings",
    }
    return descriptions.get(entry.action, entry.action.value.replace("_", " ").lower())
