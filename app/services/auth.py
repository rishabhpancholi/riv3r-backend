import asyncio
from supabase import AsyncClient
from redis.asyncio import Redis

from app.api.auth import schemas
from app.repositories import db_service, cache_service
from app.core import exceptions
from app.utils import password, jwt

class AuthService:
    def __init__(self, db: AsyncClient, cache: Redis = None):
        self.db_service = db_service.DBRepository(db)

        if cache:
            self.cache_service = cache_service.CacheRepository(cache)

    async def login_user(
        self, credentials:schemas.LoginUser
    )-> dict:
        existing_user = await self.db_service.get_user_with_email(credentials.email)
        if not existing_user: 
            raise exceptions.AuthorizationError(message="Invalid credentials", detail="Please check your credentials")

        if not password.verify_password(credentials.password, existing_user["password"]):
            raise exceptions.AuthorizationError(message="Invalid credentials", detail="Please check your credentials")

        existing_user.pop("password")

        access_token = jwt.create_token(existing_user, "access")
        refresh_token = jwt.create_token(existing_user, "refresh")

        hashed_refresh_token = jwt.hash_token(refresh_token)

        await self.db_service.store_refresh_token(existing_user["id"], hashed_refresh_token)

        return {"access_token": access_token, "refresh_token": refresh_token, "user": existing_user}

        
    async def logout_user(
            self,
            access_token: str,
            refresh_token: str,
    ):
       hashed_refresh_token = jwt.hash_token(refresh_token)
       hashed_access_token = jwt.hash_token(access_token)

       db_ops = [
           self.db_service.blacklist_refresh_token(hashed_refresh_token),
           self.cache_service.blacklist_access_token(hashed_access_token),
       ]

       await asyncio.gather(*db_ops)

    async def refresh(
              self, 
              refresh_token: str, 
              access_token: str,
    ):
        hashed_refresh_token = jwt.hash_token(refresh_token)

        if not await self.db_service.check_refresh_token_valid(hashed_refresh_token):
            raise exceptions.AuthorizationError(message="Invalid refresh token", detail="Please check your refresh token")

        await self.cache_service.blacklist_access_token(access_token)

        payload = jwt.decode_token(refresh_token)
        payload.pop("type")

        fresh_access_token = jwt.create_token(payload, "access")

        return {
            "fresh_access_token": fresh_access_token,
        }