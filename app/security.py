"""Password hashing and JSON Web Token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"
PBKDF2_ROUNDS = 240_000


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password with PBKDF2-SHA256 and a random salt."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(),
                                 PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored PBKDF2 hash in constant time."""
    try:
        _, rounds, salt, expected = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(),
                                 int(rounds))
    return hmac.compare_digest(digest.hex(), expected)


def create_token(subject: str, role: str, secret: str,
                 ttl_minutes: int = 30) -> str:
    """Issue a signed access token."""
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "role": role, "iat": now,
               "exp": now + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> dict:
    """Validate a token and return its claims.

    Raises jwt.InvalidTokenError when the token is expired, tampered with or
    signed with another key.
    """
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
