"""Local filesystem storage (development and single-node deployments).

The media root lives *outside* the application directory so an uploaded file can
never be reached as source code or a template, and every resolved path is
re-checked against the root to defeat traversal.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.logging import app_logger, security_logger
from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, root: str | None = None, base_url: str | None = None) -> None:
        self.root = Path(root or settings.STORAGE_LOCAL_DIR).resolve()
        self.base_url = (base_url or settings.STORAGE_PUBLIC_BASE_URL).rstrip("/")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # Surface at upload time with a proper API error rather than crashing
            # the process at import time.
            app_logger.error(
                "media_root_unavailable", extra={"path": str(self.root), "error": str(exc)}
            )

    def _resolve(self, key: str) -> Path:
        # Reject anything that looks like traversal before touching the disk.
        if not key or key.startswith("/") or ".." in key.split("/") or "\\" in key:
            security_logger.warning("storage_key_rejected", extra={"key": key[:120]})
            raise ValidationError("Invalid storage key")

        candidate = (self.root / key).resolve()
        # Defence in depth: symlinks and unicode tricks are caught here.
        if not candidate.is_relative_to(self.root):
            security_logger.warning("storage_path_escape", extra={"key": key[:120]})
            raise ValidationError("Invalid storage key")
        return candidate

    async def save(self, key: str, data: bytes, *, content_type: str) -> str:
        path = self._resolve(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write to a temporary file then rename, so a reader never sees a
            # half-written object.
            temporary = path.with_suffix(path.suffix + ".part")
            temporary.write_bytes(data)
            os.replace(temporary, path)
            path.chmod(0o644)

        await asyncio.to_thread(_write)
        app_logger.info("media_stored", extra={"key": key, "bytes": len(data)})
        return self.public_url(key)

    async def load(self, key: str) -> bytes | None:
        path = self._resolve(key)

        def _read() -> bytes | None:
            return path.read_bytes() if path.is_file() else None

        return await asyncio.to_thread(_read)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)

        def _unlink() -> None:
            path.unlink(missing_ok=True)

        await asyncio.to_thread(_unlink)
        app_logger.info("media_deleted", extra={"key": key})

    def public_url(self, key: str) -> str:
        return f"{self.base_url}/{key.lstrip('/')}"
