from fastapi import Depends, Request
from redis.asyncio import Redis
from supabase import AsyncClient

from app.clients.contracts import EmbeddingsClient, LLMClient
from app.core import exceptions
from app.repositories import contracts
from app.repositories import supabase as repositories
from app.repositories.redis import RedisAccessTokenRevocationStore
from app.services.audit import AuditService
from app.services.duplicates import DuplicateChecker
from app.utils import jwt


def get_db(request: Request) -> AsyncClient:
    return request.app.state.connection.db


def get_cache(request: Request) -> Redis:
    return request.app.state.connection.cache


def get_llm(request: Request) -> LLMClient:
    return request.app.state.connection.llm


def get_embeddings(request: Request) -> EmbeddingsClient:
    return request.app.state.connection.embeddings


def get_fallback_embeddings(request: Request) -> EmbeddingsClient:
    return request.app.state.connection.fallback_embeddings


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


def get_resources(
    db: AsyncClient = Depends(get_db),
) -> contracts.ResourceRepository:
    return repositories.SupabaseResourceRepository(db)


def get_refresh_tokens(
    db: AsyncClient = Depends(get_db),
) -> contracts.RefreshTokenRepository:
    return repositories.SupabaseRefreshTokenRepository(db)


def get_audit_logs(
    db: AsyncClient = Depends(get_db),
) -> contracts.AuditLogRepository:
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


def get_audit_service(
    users: contracts.UserRepository = Depends(get_users),
    organizations: contracts.OrganizationRepository = Depends(get_organizations),
    audit_logs: contracts.AuditLogRepository = Depends(get_audit_logs),
) -> AuditService:
    return AuditService(
        users=users, organizations=organizations, audit_logs=audit_logs
    )


async def get_current_user(
    request: Request,
    users: contracts.UserRepository = Depends(get_users),
    memberships: contracts.MembershipRepository = Depends(get_memberships),
    revocations: contracts.AccessTokenRevocationStore = Depends(get_revocations),
) -> dict:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise exceptions.AuthorizationError(
            detail="Please make sure you are logged in"
        )

    payload = jwt.decode_token(access_token, expected_type="access")
    if await revocations.is_revoked(access_token):
        raise exceptions.AuthorizationError(
            detail="Please make sure you are logged in"
        )

    user = await users.get_user_with_id(payload["id"])
    if not user:
        raise exceptions.AuthorizationError(detail="Please sign in again")
    user.pop("password", None)

    if not user.get("is_resource"):
        membership = await memberships.get_org_membership(user["id"])
        user["is_owner"] = membership["is_owner"] if membership else None

    return user
