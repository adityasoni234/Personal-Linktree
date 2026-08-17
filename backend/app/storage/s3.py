"""S3-compatible object storage (production).

Works with AWS S3, Cloudflare R2, MinIO and DigitalOcean Spaces. boto3 is
synchronous, so every call is dispatched to a worker thread.
"""

from __future__ import annotations

import asyncio
from functools import cached_property
from typing import Any

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import app_logger
from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        self.bucket = settings.STORAGE_BUCKET
        self.base_url = settings.STORAGE_PUBLIC_BASE_URL.rstrip("/")
        if not self.bucket:
            raise ValueError("STORAGE_BUCKET must be configured for the s3 backend")

    @cached_property
    def _client(self) -> Any:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ServiceUnavailableError("Object storage client is unavailable") from exc

        return boto3.client(
            "s3",
            region_name=settings.STORAGE_REGION,
            endpoint_url=settings.STORAGE_ENDPOINT_URL,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=15,
            ),
        )

    async def save(self, key: str, data: bytes, *, content_type: str) -> str:
        def _put() -> None:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
                # Stops a browser from ever sniffing an uploaded asset into
                # something executable.
                ContentDisposition="inline",
            )

        try:
            await asyncio.to_thread(_put)
        except Exception as exc:  # noqa: BLE001
            app_logger.error("s3_put_failed", extra={"key": key, "error": str(exc)})
            raise ServiceUnavailableError("Could not store the uploaded file") from exc

        app_logger.info("media_stored", extra={"key": key, "bytes": len(data)})
        return self.public_url(key)

    async def load(self, key: str) -> bytes | None:
        def _get() -> bytes | None:
            try:
                response = self._client.get_object(Bucket=self.bucket, Key=key)
            except Exception:  # noqa: BLE001 - treat every failure as "missing"
                return None
            return response["Body"].read()

        return await asyncio.to_thread(_get)

    async def delete(self, key: str) -> None:
        def _delete() -> None:
            self._client.delete_object(Bucket=self.bucket, Key=key)

        try:
            await asyncio.to_thread(_delete)
        except Exception as exc:  # noqa: BLE001
            app_logger.warning("s3_delete_failed", extra={"key": key, "error": str(exc)})

    def public_url(self, key: str) -> str:
        return f"{self.base_url}/{key.lstrip('/')}"
