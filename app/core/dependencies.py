from fastapi import Depends, Request
from redis.asyncio import Redis
from supabase import AsyncClient

from app.core import exceptions
from app.core.config import load_settings
from app.core.rate_limiter import check_rate_limit, client_ip
from app.repositories import cache_service, db_service
from app.utils import jwt


def get_db(request: Request) -> AsyncClient:
    return request.app.state.connection.db


def get_cache(request: Request) -> Redis:
    return request.app.state.connection.cache


async def get_current_user(
    request: Request,
    db: AsyncClient = Depends(get_db),
    cache: Redis = Depends(get_cache),
) -> dict:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise exceptions.AuthorizationError(
            detail="Please make sure you are logged in"
        )

    if not await cache_service.CacheRepository(
        cache
    ).check_access_token_valid(access_token):
        raise exceptions.AuthorizationError(
            detail="Please make sure you are logged in"
        )

    payload = jwt.decode_token(access_token)

    repository = db_service.DBRepository(db)
    user = await repository.get_user_with_id(payload["id"])
    user.pop("password", None)

    if not user.get("is_resource"):
        membership = await repository.get_org_membership(user["id"])
        user["is_owner"] = membership["is_owner"] if membership else None

    return user


async def rate_limit_login(
    request: Request,
    cache: Redis = Depends(get_cache),
) -> None:
    settings = load_settings()

    if not await check_rate_limit(
        cache,
        key=client_ip(request),
        max_requests=settings.login_max_requests,
        window_seconds=settings.login_window_seconds,
    ):
        raise exceptions.RateLimitError()
