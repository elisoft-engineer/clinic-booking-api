from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

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
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_lifetime_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["sub", "exp", "iat"]},
        )
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid access token.")
        return UUID(payload["sub"])
    except AuthenticationError:
        raise
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc
