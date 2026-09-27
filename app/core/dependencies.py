from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core import exceptions
from app.core.config import load_settings
from app.core.rate_limiter import check_rate_limit, client_ip
from app.repositories import contracts
from app.repositories import supabase as repositories
from app.repositories.redis import RedisAccessTokenRevocationStore
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.duplicates import DuplicateChecker
from app.services.onboarding import OnboardingService
from app.services.profile import ProfileService
from app.utils import jwt
from supabase import AsyncClient


def get_db(request: Request) -> AsyncClient:
    return request.app.state.connection.db


def get_cache(request: Request) -> Redis:
    return request.app.state.connection.cache


def get_users(db: AsyncClient = Depends(get_db)) -> contracts.UserRepository:
    return repositories.SupabaseUserRepository(db)


def get_organizations(
    db: AsyncClient = Depends(get_db),
) -> contracts.OrganizationRepository:
    return repositories.SupabaseOrganizationRepository(db)


def get_memberships(
    db: AsyncClient = Depends(get_db),
) -> contracts.MembershipRepository:
    return repositories.SupabaseMembershipRepository(db)


def get_resources(db: AsyncClient = Depends(get_db)) -> contracts.ResourceRepository:
    return repositories.SupabaseResourceRepository(db)


def get_refresh_tokens(
    db: AsyncClient = Depends(get_db),
) -> contracts.RefreshTokenRepository:
    return repositories.SupabaseRefreshTokenRepository(db)


def get_audit_logs(db: AsyncClient = Depends(get_db)) -> contracts.AuditLogRepository:
    return repositories.SupabaseAuditLogRepository(db)


def get_revocations(
    cache: Redis = Depends(get_cache),
) -> contracts.AccessTokenRevocationStore:
    return RedisAccessTokenRevocationStore(cache)


def get_duplicates(
    users: contracts.UserRepository = Depends(get_users),
    organizations: contracts.OrganizationRepository = Depends(get_organizations),
    resources: contracts.ResourceRepository = Depends(get_resources),
) -> DuplicateChecker:
    return DuplicateChecker(
        email_checks=(organizations.email_exists, users.email_exists),
        url_checks=(
            organizations.website_exists,
            resources.portfolio_exists,
            resources.linkedin_exists,
        ),
    )


def get_auth_service(
    users: contracts.UserRepository = Depends(get_users),
    refresh_tokens: contracts.RefreshTokenRepository = Depends(get_refresh_tokens),
    revocations: contracts.AccessTokenRevocationStore = Depends(get_revocations),
) -> AuthService:
    return AuthService(
        users=users, refresh_tokens=refresh_tokens, revocations=revocations
    )


def get_onboarding_service(
    users: contracts.UserRepository = Depends(get_users),
    organizations: contracts.OrganizationRepository = Depends(get_organizations),
    memberships: contracts.MembershipRepository = Depends(get_memberships),
    resources: contracts.ResourceRepository = Depends(get_resources),
    refresh_tokens: contracts.RefreshTokenRepository = Depends(get_refresh_tokens),
    duplicates: DuplicateChecker = Depends(get_duplicates),
) -> OnboardingService:
    return OnboardingService(
        users=users,
        organizations=organizations,
        memberships=memberships,
        resources=resources,
        refresh_tokens=refresh_tokens,
        duplicates=duplicates,
    )


def get_profile_service(
    users: contracts.UserRepository = Depends(get_users),
    organizations: contracts.OrganizationRepository = Depends(get_organizations),
    memberships: contracts.MembershipRepository = Depends(get_memberships),
    resources: contracts.ResourceRepository = Depends(get_resources),
    duplicates: DuplicateChecker = Depends(get_duplicates),
) -> ProfileService:
    return ProfileService(
        users=users,
        organizations=organizations,
        memberships=memberships,
        resources=resources,
        duplicates=duplicates,
    )


def get_audit_service(
    users: contracts.UserRepository = Depends(get_users),
    organizations: contracts.OrganizationRepository = Depends(get_organizations),
    audit_logs: contracts.AuditLogRepository = Depends(get_audit_logs),
) -> AuditService:
    return AuditService(users=users, organizations=organizations, audit_logs=audit_logs)


async def get_current_user(
    request: Request,
    users: contracts.UserRepository = Depends(get_users),
    memberships: contracts.MembershipRepository = Depends(get_memberships),
    revocations: contracts.AccessTokenRevocationStore = Depends(get_revocations),
) -> dict:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise exceptions.AuthorizationError(detail="Please make sure you are logged in")

    payload = jwt.decode_token(access_token, expected_type="access")

    if await revocations.is_revoked(access_token):
        raise exceptions.AuthorizationError(detail="Please make sure you are logged in")

    user = await users.get_user_with_id(payload["id"])
    if not user:
        raise exceptions.AuthorizationError(detail="Please sign in again")
    user.pop("password", None)

    if not user.get("is_resource"):
        membership = await memberships.get_org_membership(user["id"])
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


async def rate_limit_onboarding(
    request: Request,
    cache: Redis = Depends(get_cache),
) -> None:
    settings = load_settings()

    if not await check_rate_limit(
        cache,
        key=f"onboarding:{client_ip(request)}",
        max_requests=settings.login_max_requests,
        window_seconds=settings.login_window_seconds,
    ):
        raise exceptions.RateLimitError()
