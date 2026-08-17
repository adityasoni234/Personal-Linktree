"""ORM models.

Importing this package registers every mapper on `Base.metadata`, which is what
Alembic autogenerate and the test fixtures rely on.
"""

from app.db.base import Base
from app.models.analytics import AnalyticsEvent
from app.models.audit import AuditLog
from app.models.enums import (
    AnalyticsEventType,
    AuditAction,
    DeviceType,
    DotStyle,
    ErrorCorrection,
    EyeBallStyle,
    EyeFrameStyle,
    FrameStyle,
    GradientType,
    LogoShape,
    MediaKind,
    ResourceType,
    Role,
    UserStatus,
)
from app.models.group import Group
from app.models.link import Link
from app.models.media import Media
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.qr import QRConfiguration
from app.models.session import PasswordResetToken, UserSession
from app.models.user import User

__all__ = [
    "AnalyticsEvent",
    "AnalyticsEventType",
    "AuditAction",
    "AuditLog",
    "Base",
    "DeviceType",
    "DotStyle",
    "ErrorCorrection",
    "EyeBallStyle",
    "EyeFrameStyle",
    "FrameStyle",
    "GradientType",
    "Group",
    "Link",
    "LogoShape",
    "Media",
    "MediaKind",
    "Membership",
    "Organization",
    "PasswordResetToken",
    "QRConfiguration",
    "ResourceType",
    "Role",
    "User",
    "UserSession",
    "UserStatus",
]
