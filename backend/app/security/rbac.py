"""Role-based access control.

Every authorization decision in the application funnels through this module and
is evaluated on the server. The frontend hides controls the user cannot use, but
that is presentation only — it is never the enforcement point.

    SUPER_ADMIN  platform operator: everything, across all organizations
    ADMIN        manages their organization: groups, members, roles, audit log
    EDITOR       creates and edits groups and links in their organization
    USER         manages only the resources they own
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from app.core.errors import PermissionDeniedError
from app.models.enums import Role


class Permission(str, Enum):
    # Groups
    GROUP_CREATE = "group:create"
    GROUP_READ_ANY = "group:read:any"
    GROUP_UPDATE_ANY = "group:update:any"
    GROUP_DELETE_ANY = "group:delete:any"
    GROUP_PUBLISH_ANY = "group:publish:any"
    GROUP_MANAGE_OWN = "group:manage:own"

    # Links
    LINK_MANAGE_ANY = "link:manage:any"
    LINK_MANAGE_OWN = "link:manage:own"

    # QR
    QR_MANAGE_ANY = "qr:manage:any"
    QR_MANAGE_OWN = "qr:manage:own"
    QR_RENDER = "qr:render"

    # Analytics
    ANALYTICS_READ_ANY = "analytics:read:any"
    ANALYTICS_READ_OWN = "analytics:read:own"

    # Media
    MEDIA_UPLOAD = "media:upload"
    MEDIA_DELETE_ANY = "media:delete:any"

    # Organization administration
    ORG_SETTINGS_UPDATE = "org:settings:update"
    ORG_MEMBER_MANAGE = "org:member:manage"
    ROLE_ASSIGN = "org:role:assign"
    AUDIT_READ = "audit:read"
    USER_MANAGE_ANY = "user:manage:any"

    # Platform
    SYSTEM_ADMIN = "system:admin"


_USER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.GROUP_CREATE,
        Permission.GROUP_MANAGE_OWN,
        Permission.LINK_MANAGE_OWN,
        Permission.QR_MANAGE_OWN,
        Permission.QR_RENDER,
        Permission.ANALYTICS_READ_OWN,
        Permission.MEDIA_UPLOAD,
    }
)

_EDITOR_PERMISSIONS: frozenset[Permission] = _USER_PERMISSIONS | {
    Permission.GROUP_READ_ANY,
    Permission.GROUP_UPDATE_ANY,
    Permission.LINK_MANAGE_ANY,
    Permission.QR_MANAGE_ANY,
    Permission.ANALYTICS_READ_ANY,
}

_ADMIN_PERMISSIONS: frozenset[Permission] = _EDITOR_PERMISSIONS | {
    Permission.GROUP_DELETE_ANY,
    Permission.GROUP_PUBLISH_ANY,
    Permission.MEDIA_DELETE_ANY,
    Permission.ORG_SETTINGS_UPDATE,
    Permission.ORG_MEMBER_MANAGE,
    Permission.ROLE_ASSIGN,
    Permission.AUDIT_READ,
    Permission.USER_MANAGE_ANY,
}

_SUPER_ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.USER: _USER_PERMISSIONS,
    Role.EDITOR: _EDITOR_PERMISSIONS,
    Role.ADMIN: _ADMIN_PERMISSIONS,
    Role.SUPER_ADMIN: _SUPER_ADMIN_PERMISSIONS,
}


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller, resolved once per request."""

    user_id: uuid.UUID
    email: str
    session_id: uuid.UUID
    system_role: Role
    organization_id: uuid.UUID | None
    organization_role: Role | None

    @property
    def effective_role(self) -> Role:
        """Platform SUPER_ADMIN outranks any organization-scoped role."""
        if self.system_role is Role.SUPER_ADMIN:
            return Role.SUPER_ADMIN
        return self.organization_role or Role.USER

    @property
    def is_super_admin(self) -> bool:
        return self.system_role is Role.SUPER_ADMIN

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS[self.effective_role]

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_any(self, *permissions: Permission) -> bool:
        return any(permission in self.permissions for permission in permissions)

    def require(self, permission: Permission) -> None:
        if not self.has(permission):
            raise PermissionDeniedError(
                "You do not have permission to perform this action",
                details={"required_permission": permission.value},
            )

    def in_organization(self, organization_id: uuid.UUID) -> bool:
        """SUPER_ADMIN crosses org boundaries; everyone else is confined."""
        return self.is_super_admin or self.organization_id == organization_id


# ---------------------------------------------------------------------------
# Resource-scoped helpers
#
# These take the *stored* resource so ownership is checked against the database
# row, never against a client-supplied owner id.
# ---------------------------------------------------------------------------


def _owns(principal: Principal, owner_id: uuid.UUID | None) -> bool:
    return owner_id is not None and owner_id == principal.user_id


def can_read_group(principal: Principal, *, organization_id: uuid.UUID,
                   owner_id: uuid.UUID | None) -> bool:
    if not principal.in_organization(organization_id):
        return False
    return principal.has(Permission.GROUP_READ_ANY) or _owns(principal, owner_id)


def can_edit_group(principal: Principal, *, organization_id: uuid.UUID,
                   owner_id: uuid.UUID | None) -> bool:
    if not principal.in_organization(organization_id):
        return False
    if principal.has(Permission.GROUP_UPDATE_ANY):
        return True
    return principal.has(Permission.GROUP_MANAGE_OWN) and _owns(principal, owner_id)


def can_delete_group(principal: Principal, *, organization_id: uuid.UUID,
                     owner_id: uuid.UUID | None) -> bool:
    if not principal.in_organization(organization_id):
        return False
    if principal.has(Permission.GROUP_DELETE_ANY):
        return True
    return principal.has(Permission.GROUP_MANAGE_OWN) and _owns(principal, owner_id)


def can_publish_group(principal: Principal, *, organization_id: uuid.UUID,
                      owner_id: uuid.UUID | None) -> bool:
    if not principal.in_organization(organization_id):
        return False
    if principal.has(Permission.GROUP_PUBLISH_ANY):
        return True
    return principal.has(Permission.GROUP_MANAGE_OWN) and _owns(principal, owner_id)


def can_read_analytics(principal: Principal, *, organization_id: uuid.UUID,
                       owner_id: uuid.UUID | None) -> bool:
    if not principal.in_organization(organization_id):
        return False
    return principal.has(Permission.ANALYTICS_READ_ANY) or _owns(principal, owner_id)


def assert_can_assign_role(principal: Principal, *, target_user_id: uuid.UUID,
                           new_role: Role, current_role: Role) -> None:
    """Guard against privilege escalation through the role-assignment endpoint.

    Rules:
      * you need ROLE_ASSIGN;
      * you may never change your own role (no self-promotion);
      * you may never grant a role above your own;
      * you may never modify someone who already outranks you;
      * only a SUPER_ADMIN can create another SUPER_ADMIN.
    """
    principal.require(Permission.ROLE_ASSIGN)

    if target_user_id == principal.user_id:
        raise PermissionDeniedError("You cannot change your own role")

    actor_role = principal.effective_role
    if new_role is Role.SUPER_ADMIN and not principal.is_super_admin:
        raise PermissionDeniedError("Only a super administrator can grant that role")
    if new_role.rank > actor_role.rank:
        raise PermissionDeniedError("You cannot grant a role higher than your own")
    if current_role.rank >= actor_role.rank and not principal.is_super_admin:
        raise PermissionDeniedError("You cannot modify a user at or above your own role")
