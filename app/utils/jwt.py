import hashlib
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import jwt

from app.core import exceptions
from app.core.config import load_settings

settings = load_settings()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(data: dict, type: Literal["access", "refresh"]) -> str:
    if type not in ("access", "refresh"):
        raise ValueError("Unsupported token type")
    lifetime = (
        timedelta(minutes=settings.jwt_access_token_expire_minutes)
        if type == "access"
        else timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    if lifetime.total_seconds() <= 0:
        raise ValueError("Token lifetime must be positive")
    now = datetime.now(UTC)
    # Never mutate a user record or inherit a refresh token's lifetime/identity.
    payload = {
        **data,
        "type": type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_token(
    token: str,
    *,
    expected_type: Literal["access", "refresh"] | None = None,
    allow_expired: bool = False,
) -> dict:
    """Validate signed claims. Expired access tokens are allowed only for cleanup.

    Refresh/logout can verify an expired token's identity before revoking it;
    authorization and refresh-token validation must enforce expiration.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["id", "type", "exp", "iat", "jti"],
                "verify_exp": not allow_expired,
            },
        )
        if (
            not isinstance(payload["id"], str)
            or not payload["id"]
            or not isinstance(payload["jti"], str)
            or not payload["jti"]
            or payload["type"] not in ("access", "refresh")
            or (expected_type is not None and payload["type"] != expected_type)
            or type(payload["iat"]) is not int
            or type(payload["exp"]) is not int
            or payload["exp"] <= payload["iat"]
        ):
            raise jwt.InvalidTokenError("Invalid token claims")
        return payload
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError) as exc:
        raise exceptions.AuthorizationError(
            message="Invalid token", detail="Please sign in again"
        ) from exc
