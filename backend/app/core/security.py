"""Password hashing and token generation using only the standard library.

Passwords use PBKDF2-HMAC-SHA256 with a per-password random salt, encoded as
`pbkdf2_sha256$iterations$salt_hex$hash_hex`. Session tokens are opaque, URL-safe
random strings; only their SHA-256 hash is persisted so a database leak does not
expose live tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 240_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = encoded.split("$")
        if algo != _ALGO:
            return False
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def generate_token() -> str:
    """Return a fresh opaque session token to hand to the client."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the stored, non-reversible form of a session token."""
    return hashlib.sha256(token.encode()).hexdigest()


def slugify(value: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base or "workspace"
