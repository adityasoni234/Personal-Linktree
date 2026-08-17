"""Media schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.enums import MediaKind
from app.schemas.common import ORMModel


class MediaOut(ORMModel):
    id: uuid.UUID
    kind: MediaKind
    public_url: str
    content_type: str
    size_bytes: int
    width: int | None
    height: int | None
    original_filename: str | None
    created_at: datetime
