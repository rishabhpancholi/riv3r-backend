import jwt
import hashlib
from typing import Literal

from app.core.config import load_settings

settings = load_settings()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(data: dict, type: Literal["access", "refresh"]) -> str:
    data.update({"type": type})
    token = jwt.encode(data, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return token


def decode_token(token: str) -> dict:
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
