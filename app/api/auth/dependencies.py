from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core import dependencies as core_deps
from app.core import exceptions
from app.core.config import load_settings
from app.core.rate_limiter import check_rate_limit, client_ip
from app.repositories import contracts
from app.services.auth import AuthService


def get_auth_service(
    users: contracts.UserRepository = Depends(core_deps.get_users),
    refresh_tokens: contracts.RefreshTokenRepository = Depends(
        core_deps.get_refresh_tokens
    ),
    revocations: contracts.AccessTokenRevocationStore = Depends(
        core_deps.get_revocations
    ),
) -> AuthService:
    return AuthService(
        users=users, refresh_tokens=refresh_tokens, revocations=revocations
    )


async def rate_limit_login(
    request: Request,
    cache: Redis = Depends(core_deps.get_cache),
) -> None:
    settings = load_settings()
    if not await check_rate_limit(
        cache,
        key=client_ip(request),
        max_requests=settings.login_max_requests,
        window_seconds=settings.login_window_seconds,
    ):
        raise exceptions.RateLimitError()
