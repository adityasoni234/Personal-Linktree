"""Domain enumerations shared by models, schemas and the RBAC layer."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Ordered from most to least privileged.

    `SUPER_ADMIN` is a platform-wide role stored on `User.system_role`;
    the remaining three are organization-scoped and stored on `Membership.role`.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    USER = "USER"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def at_least(self, other: "Role") -> bool:
        return self.rank >= other.rank


_ROLE_RANK: dict[Role, int] = {
    Role.USER: 0,
    Role.EDITOR: 1,
    Role.ADMIN: 2,
    Role.SUPER_ADMIN: 3,
}


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"
    DELETED = "DELETED"


class MediaKind(str, Enum):
    GROUP_LOGO = "GROUP_LOGO"
    QR_LOGO = "QR_LOGO"
    AVATAR = "AVATAR"
    ORG_LOGO = "ORG_LOGO"


class AnalyticsEventType(str, Enum):
    PAGE_VIEW = "PAGE_VIEW"
    QR_SCAN = "QR_SCAN"
    LINK_CLICK = "LINK_CLICK"
    SHARE = "SHARE"


class DeviceType(str, Enum):
    MOBILE = "MOBILE"
    TABLET = "TABLET"
    DESKTOP = "DESKTOP"
    BOT = "BOT"
    UNKNOWN = "UNKNOWN"


class AuditAction(str, Enum):
    # Authentication
    USER_REGISTERED = "USER_REGISTERED"
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    TOKEN_REUSE_DETECTED = "TOKEN_REUSE_DETECTED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
    SESSION_REVOKED = "SESSION_REVOKED"

    # Groups
    GROUP_CREATED = "GROUP_CREATED"
    GROUP_UPDATED = "GROUP_UPDATED"
    GROUP_DELETED = "GROUP_DELETED"
    GROUP_ARCHIVED = "GROUP_ARCHIVED"
    GROUP_RESTORED = "GROUP_RESTORED"
    GROUP_PUBLISHED = "GROUP_PUBLISHED"
    GROUP_UNPUBLISHED = "GROUP_UNPUBLISHED"
    GROUP_DUPLICATED = "GROUP_DUPLICATED"
    GROUP_SLUG_CHANGED = "GROUP_SLUG_CHANGED"
    GROUP_REORDERED = "GROUP_REORDERED"

    # Links
    LINK_CREATED = "LINK_CREATED"
    LINK_UPDATED = "LINK_UPDATED"
    LINK_DELETED = "LINK_DELETED"
    LINK_REORDERED = "LINK_REORDERED"

    # QR
    QR_CONFIG_UPDATED = "QR_CONFIG_UPDATED"

    # Media
    MEDIA_UPLOADED = "MEDIA_UPLOADED"
    MEDIA_DELETED = "MEDIA_DELETED"

    # Administration
    ROLE_CHANGED = "ROLE_CHANGED"
    USER_SUSPENDED = "USER_SUSPENDED"
    USER_REACTIVATED = "USER_REACTIVATED"
    USER_DELETED = "USER_DELETED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    ORG_SETTINGS_UPDATED = "ORG_SETTINGS_UPDATED"


class ResourceType(str, Enum):
    USER = "USER"
    ORGANIZATION = "ORGANIZATION"
    MEMBERSHIP = "MEMBERSHIP"
    GROUP = "GROUP"
    LINK = "LINK"
    QR_CONFIGURATION = "QR_CONFIGURATION"
    MEDIA = "MEDIA"
    SESSION = "SESSION"


class DotStyle(str, Enum):
    SQUARE = "square"
    ROUNDED = "rounded"
    DOT = "dot"
    CLASSY = "classy"
    DIAMOND = "diamond"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class EyeFrameStyle(str, Enum):
    SQUARE = "square"
    ROUNDED = "rounded"
    CIRCLE = "circle"
    LEAF = "leaf"
    SHIELD = "shield"


class EyeBallStyle(str, Enum):
    SQUARE = "square"
    ROUNDED = "rounded"
    CIRCLE = "circle"
    DIAMOND = "diamond"


class GradientType(str, Enum):
    NONE = "none"
    LINEAR = "linear"
    RADIAL = "radial"


class ErrorCorrection(str, Enum):
    L = "L"  # ~7%
    M = "M"  # ~15%
    Q = "Q"  # ~25%
    H = "H"  # ~30% — required when a logo is embedded


class LogoShape(str, Enum):
    SQUARE = "square"
    ROUNDED = "rounded"
    CIRCLE = "circle"


class FrameStyle(str, Enum):
    NONE = "none"
    SIMPLE = "simple"
    ROUNDED = "rounded"
    BANNER_BOTTOM = "banner_bottom"
    BANNER_TOP = "banner_top"
    TICKET = "ticket"
