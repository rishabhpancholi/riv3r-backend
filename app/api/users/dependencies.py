from fastapi import Depends
from redis.asyncio import Redis

from app.core import dependencies as core_deps
from app.core.config import load_settings
from app.core.permissions import OrganizationLevelPermissionChecker, PermissionChecker
from app.repositories import contracts
from app.repositories.redis import RedisOrganizationUsersCache
from app.services.users import UsersService


def get_organization_users_cache(
    cache: Redis = Depends(core_deps.get_cache),
) -> contracts.OrganizationUsersCache:
    return RedisOrganizationUsersCache(cache, ttl=load_settings().cache_ttl)


def get_users_service(
    users: contracts.UserRepository = Depends(core_deps.get_users),
    organizations: contracts.OrganizationRepository = Depends(
        core_deps.get_organizations
    ),
    cache: contracts.OrganizationUsersCache = Depends(get_organization_users_cache),
) -> UsersService:
    return UsersService(users=users, organizations=organizations, cache=cache)


def get_list_users_permission_checker(
    organizations: contracts.OrganizationRepository = Depends(
        core_deps.get_organizations
    ),
) -> PermissionChecker:
    return OrganizationLevelPermissionChecker(
        organizations, allowed_org_types={"client", "agency"}
    )
