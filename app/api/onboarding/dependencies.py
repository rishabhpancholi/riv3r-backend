from fastapi import Depends, Request
from redis.asyncio import Redis
from supabase import AsyncClient

from app.core import dependencies as core_deps
from app.core import exceptions
from app.core.config import load_settings
from app.core.rate_limiter import check_rate_limit, client_ip
from app.repositories import contracts
from app.repositories import supabase as repositories
from app.services.onboarding import OnboardingService


def get_onboarding_repository(
    db: AsyncClient = Depends(core_deps.get_db),
) -> contracts.OnboardingRepository:
    return repositories.SupabaseOnboardingRepository(db)


def get_onboarding_service(
    onboarding_repository: contracts.OnboardingRepository = Depends(
        get_onboarding_repository
    ),
) -> OnboardingService:
    return OnboardingService(onboarding_repository=onboarding_repository)


async def rate_limit_onboarding(
    request: Request,
    cache: Redis = Depends(core_deps.get_cache),
) -> None:
    settings = load_settings()
    if not await check_rate_limit(
        cache,
        key=f"onboarding:{client_ip(request)}",
        max_requests=settings.login_max_requests,
        window_seconds=settings.login_window_seconds,
    ):
        raise exceptions.RateLimitError()
