"""Password hashing (Argon2id) and JWT access/refresh tokens.

- Passwords are never stored, only an Argon2id hash (slow on purpose, salted automatically).
- An access token (short-lived) is sent with every request.
- A refresh token (long-lived) is only used to get a new access token.
  Each token carries a "type" claim so one kind cannot be used in place of the other.
"""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"

_hasher = PasswordHasher()  # argon2-cffi uses the Argon2id variant by default


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Checked against when the e-mail does not exist, so a failed login takes about the same
# time whether or not the account exists (makes guessing valid e-mails harder).
DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


class TokenError(Exception):
    """The token is missing, expired, tampered with, or of the wrong type."""


def _create_token(user_id: int, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "type": token_type, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(user_id, ACCESS, timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, REFRESH, timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired token") from exc
    if payload["type"] != expected_type:
        raise TokenError("wrong token type")
    return payload
