import asyncio

from app.api.auth import schemas
from app.core import exceptions
from app.repositories.contracts import (
    AccessTokenRevocationStore,
    RefreshTokenRepository,
    UserRepository,
)
from app.utils import jwt, password


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        revocations: AccessTokenRevocationStore,
    ):
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.revocations = revocations

    async def login_user(self, credentials: schemas.LoginUser) -> dict:
        existing_user = await self.users.get_user_with_email(credentials.email)
        if not existing_user:
            raise exceptions.AuthorizationError(
                message="Invalid credentials", detail="Please check your credentials"
            )

        if not password.verify_password(
            credentials.password, existing_user["password"]
        ):
            raise exceptions.AuthorizationError(
                message="Invalid credentials", detail="Please check your credentials"
            )

        existing_user.pop("password")

        access_token = jwt.create_token(existing_user, "access")
        refresh_token = jwt.create_token(existing_user, "refresh")

        hashed_refresh_token = jwt.hash_token(refresh_token)

        await self.refresh_tokens.store_refresh_token(
            existing_user["id"],
            hashed_refresh_token,
            expires_at=jwt.decode_token(refresh_token, expected_type="refresh")["exp"],
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": existing_user,
        }

    async def logout_user(
        self,
        access_token: str,
        refresh_token: str,
    ):
        access = jwt.decode_token(
            access_token, expected_type="access", allow_expired=True
        )
        refresh = jwt.decode_token(
            refresh_token, expected_type="refresh", allow_expired=True
        )
        if access["id"] != refresh["id"]:
            raise exceptions.AuthorizationError(detail="Token users do not match")
        hashed_refresh_token = jwt.hash_token(refresh_token)

        db_ops = [
            self.refresh_tokens.blacklist_refresh_token(hashed_refresh_token),
            self.revocations.revoke(access_token, expires_at=access["exp"]),
        ]

        await asyncio.gather(*db_ops)

    async def refresh(
        self,
        refresh_token: str,
        access_token: str,
    ):
        payload = jwt.decode_token(refresh_token, expected_type="refresh")
        access = jwt.decode_token(
            access_token, expected_type="access", allow_expired=True
        )
        if access["id"] != payload["id"]:
            raise exceptions.AuthorizationError(detail="Token users do not match")
        hashed_refresh_token = jwt.hash_token(refresh_token)

        if not await self.refresh_tokens.check_refresh_token_valid(
            hashed_refresh_token
        ):
            raise exceptions.AuthorizationError(
                message="Invalid refresh token",
                detail="Please check your refresh token",
            )

        await self.revocations.revoke(access_token, expires_at=access["exp"])

        fresh_access_token = jwt.create_token(payload, "access")

        return {
            "fresh_access_token": fresh_access_token,
        }
