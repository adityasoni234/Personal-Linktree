"""Password hashing (Argon2id) and password-policy enforcement."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type

from app.core.errors import ValidationError

# OWASP-aligned Argon2id parameters (≈64 MiB, 3 passes). Tunable per deployment
# but never below these values.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# A pre-computed hash used to keep the login path constant-time for unknown
# emails, so response timing cannot be used to enumerate accounts.
_DUMMY_HASH = _hasher.hash("linkhub-timing-equaliser-" + secrets.token_hex(8))

_COMMON_PASSWORDS = frozenset(
    {
        "password", "password1", "password123", "12345678", "123456789", "1234567890",
        "qwertyuiop", "letmein123", "iloveyou1", "admin123", "welcome123", "abc123456",
        "passw0rd", "p@ssw0rd", "changeme123", "linkedin123", "ieeesou123", "linktree123",
        "qwerty123", "football1", "sunshine1", "princess1", "dragon123", "monkey123",
    }
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time verification.

    When `password_hash` is None (unknown account) a dummy verification still
    runs so the endpoint's timing profile does not leak account existence.
    """
    if not password_hash:
        try:
            _hasher.verify(_DUMMY_HASH, password)
        except (VerifyMismatchError, InvalidHashError):
            pass
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash used weaker parameters than the current policy."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def validate_password_strength(password: str, *, email: str | None = None,
                               full_name: str | None = None) -> None:
    """Raise `ValidationError` when the password fails policy.

    Policy: length, character-class variety, no repeated-character padding, not
    a well-known password, and not derived from the user's own identity.
    """
    problems: list[str] = []

    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters long")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"must be at most {MAX_PASSWORD_LENGTH} characters long")
    if password != password.strip():
        problems.append("must not start or end with whitespace")

    classes = sum(
        bool(pattern.search(password))
        for pattern in (
            re.compile(r"[a-z]"),
            re.compile(r"[A-Z]"),
            re.compile(r"[0-9]"),
            re.compile(r"[^A-Za-z0-9]"),
        )
    )
    if classes < 3:
        problems.append(
            "must combine at least three of: lowercase, uppercase, digits, symbols"
        )

    if re.search(r"(.)\1{3,}", password):
        problems.append("must not contain a character repeated four or more times")

    normalised = password.lower()
    if normalised in _COMMON_PASSWORDS:
        problems.append("is too common — choose something less predictable")

    if email:
        local_part = email.split("@")[0].lower()
        if len(local_part) >= 4 and local_part in normalised:
            problems.append("must not contain your email address")
    if full_name:
        for part in full_name.lower().split():
            if len(part) >= 4 and part in normalised:
                problems.append("must not contain your name")
                break

    if problems:
        raise ValidationError(
            "Password " + "; ".join(dict.fromkeys(problems)),
            details={"field": "password", "problems": list(dict.fromkeys(problems))},
        )


def generate_token(nbytes: int = 32) -> str:
    """Cryptographically strong, URL-safe opaque token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Digest used to store tokens at rest — the raw value is never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
