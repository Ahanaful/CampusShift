"""Password hashing and short-lived, explicitly validated access tokens."""

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException

from app.core.config import Settings

hasher = PasswordHasher()
# Used to do comparable password work for unknown accounts.
DUMMY_HASH = hasher.hash("unused-authentication-timing-value")


def require_secret(settings: Settings):
    if len(settings.jwt_secret.encode()) < 32:
        raise HTTPException(503, "Authentication is not configured. Set JWT_SECRET to at least 32 bytes.")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_token(user_id: int, settings: Settings) -> dict:
    require_secret(settings)
    now = datetime.now(timezone.utc)
    seconds = settings.jwt_expire_minutes * 60
    token = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=seconds),
         "iss": "campusshift", "aud": "campusshift-web"},
        settings.jwt_secret, algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": seconds}
