from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from core.config import settings
from core.exceptions import AuthenticationError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


def create_access_token(subject: UUID) -> str:
    """Create a signed, short-lived access JWT for the supplied subject."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_lifetime_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> UUID:
    """Validate an access JWT and return its subject as a UUID."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid access token.")
        return UUID(payload["sub"])
    except AuthenticationError:
        raise
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc


def create_refresh_token() -> str:
    """Generate a cryptographically random opaque refresh token.

    The caller returns the raw token to the client and stores only its hash.
    """
    return token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 digest used to look up a refresh token in storage.

    The raw refresh token is still sent by the client to refresh or logout,
    only the digest is persisted in the database.
    """
    return sha256(token.encode("utf-8")).hexdigest()
