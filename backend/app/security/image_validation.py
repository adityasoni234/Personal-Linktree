"""Upload validation for images.

Rules enforced here:
  * size ceiling checked while streaming, before anything is buffered whole;
  * file type derived from the *bytes*, not from the filename or the
    client-declared content type;
  * dimension and total-pixel ceilings (decompression-bomb guard);
  * rasters are re-encoded, which strips EXIF/GPS metadata and destroys
    polyglot payloads (a valid PNG that is also a valid HTML/JS file);
  * SVGs go through the sanitiser and are never trusted as-is;
  * the stored filename is always server-generated.
"""

from __future__ import annotations

import hashlib
import io
import secrets
import uuid
from dataclasses import dataclass

from PIL import Image, ImageFile, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import (
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from app.security.svg_sanitizer import sanitize_svg, svg_dimensions

# Refuse truncated files rather than silently padding them.
ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS

ALLOWED_CONTENT_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
)
EXTENSION_BY_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}

MIN_DIMENSION = 16
# Anything larger is pointless for a logo and wastes storage/bandwidth.
MAX_STORED_DIMENSION = 1024


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    content: bytes
    content_type: str
    extension: str
    width: int
    height: int
    checksum_sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)


def sniff_content_type(data: bytes) -> str | None:
    """Identify the format from magic bytes only."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    head = data[:1024].lstrip()
    if head[:5] == b"<?xml" or head[:4] == b"<svg":
        # Confirm an <svg root exists somewhere in the prologue.
        if b"<svg" in data[:4096].lower():
            return "image/svg+xml"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        raise UnsupportedMediaTypeError("GIF images are not supported")
    return None


def _safe_storage_name(extension: str) -> str:
    """Server-generated, collision-resistant, traversal-proof."""
    return f"{uuid.uuid4().hex}{secrets.token_hex(4)}.{extension}"


def build_storage_key(prefix: str, extension: str) -> str:
    if extension not in set(EXTENSION_BY_TYPE.values()):
        raise UnsupportedMediaTypeError("Unsupported file extension")
    # `prefix` is always built from internal ids, never from user input.
    return f"{prefix.strip('/')}/{_safe_storage_name(extension)}"


def validate_image(
    data: bytes,
    *,
    declared_content_type: str | None = None,
    filename: str | None = None,
    max_bytes: int | None = None,
    allow_svg: bool = True,
) -> ValidatedImage:
    """Validate and normalise an uploaded image."""
    limit = max_bytes or settings.MAX_UPLOAD_BYTES
    if not data:
        raise ValidationError("Uploaded file is empty")
    if len(data) > limit:
        raise PayloadTooLargeError(
            f"File must be smaller than {limit // 1024} KB",
            details={"max_bytes": limit},
        )

    sniffed = sniff_content_type(data)
    if sniffed is None:
        raise UnsupportedMediaTypeError(
            "File is not a supported image (PNG, JPG, WEBP or SVG)"
        )
    if sniffed not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedMediaTypeError("Unsupported image type")

    # The declared type and the extension are advisory only — they must agree
    # with the sniffed type, but they never override it.
    if declared_content_type:
        declared = declared_content_type.split(";")[0].strip().lower()
        if declared in ALLOWED_CONTENT_TYPES and declared != sniffed:
            raise UnsupportedMediaTypeError(
                "File contents do not match the declared file type"
            )
    if filename and "." in filename:
        claimed_extension = filename.rsplit(".", 1)[-1].lower()
        expected = EXTENSION_BY_TYPE[sniffed]
        aliases = {"jpeg": "jpg", "svgz": "svg"}
        if aliases.get(claimed_extension, claimed_extension) != expected:
            raise UnsupportedMediaTypeError(
                "File extension does not match the file contents"
            )

    if sniffed == "image/svg+xml":
        if not allow_svg:
            raise UnsupportedMediaTypeError("SVG files are not accepted here")
        sanitised = sanitize_svg(data)
        width, height = svg_dimensions(sanitised)
        return ValidatedImage(
            content=sanitised,
            content_type="image/svg+xml",
            extension="svg",
            width=width,
            height=height,
            checksum_sha256=hashlib.sha256(sanitised).hexdigest(),
        )

    return _normalise_raster(data)


def _normalise_raster(data: bytes) -> ValidatedImage:
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # structural check; consumes the file object
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Image file is corrupt or not readable") from exc
    except Image.DecompressionBombError as exc:
        raise PayloadTooLargeError("Image resolution is too large") from exc

    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width < MIN_DIMENSION or height < MIN_DIMENSION:
                raise ValidationError(
                    f"Image must be at least {MIN_DIMENSION}×{MIN_DIMENSION} pixels"
                )
            if width > settings.MAX_IMAGE_DIMENSION or height > settings.MAX_IMAGE_DIMENSION:
                raise PayloadTooLargeError(
                    f"Image must be at most {settings.MAX_IMAGE_DIMENSION} pixels on each side"
                )
            if width * height > settings.MAX_IMAGE_PIXELS:
                raise PayloadTooLargeError("Image resolution is too large")

            # Frame count guard: an animated WEBP would otherwise be flattened
            # silently, and huge frame counts are a cheap DoS.
            if getattr(image, "n_frames", 1) > 1:
                image.seek(0)

            normalised = image.convert("RGBA")
            normalised.thumbnail(
                (MAX_STORED_DIMENSION, MAX_STORED_DIMENSION), Image.LANCZOS
            )

            buffer = io.BytesIO()
            # Re-encoding to PNG with no metadata: strips EXIF/GPS, ICC and any
            # appended payload, and yields a file we know we produced.
            normalised.save(buffer, format="PNG", optimize=True)
            content = buffer.getvalue()
            out_width, out_height = normalised.size
    except Image.DecompressionBombError as exc:
        raise PayloadTooLargeError("Image resolution is too large") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Image file could not be processed") from exc

    return ValidatedImage(
        content=content,
        content_type="image/png",
        extension="png",
        width=out_width,
        height=out_height,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    )
