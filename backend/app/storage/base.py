"""Storage backend interface.

Keys are always server-generated (`app.security.image_validation.build_storage_key`);
no backend ever receives a user-supplied path component.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, key: str, data: bytes, *, content_type: str) -> str:
        """Persist `data` and return its public URL."""

    @abstractmethod
    async def load(self, key: str) -> bytes | None:
        """Read an object back, or None when it does not exist."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove an object. Missing objects are not an error."""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Stable URL for an object."""
