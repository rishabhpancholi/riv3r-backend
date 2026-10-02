from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.users import dependencies as deps
from app.api.users.views import OrganizationUser
from app.core import dependencies as core_deps
from app.core.permissions import PermissionChecker
from app.services.users import UsersService

users_router = APIRouter(prefix="/api/users", tags=["Users"])


@users_router.get("", response_model=list[OrganizationUser])
async def list_organization_users(
    org_id: Annotated[
        UUID | None,
        Query(description="Organization to list; only RIV3R may select another one"),
    ] = None,
    current_user: dict = Depends(core_deps.get_current_user),
    users_service: UsersService = Depends(deps.get_users_service),
    permission_checker: PermissionChecker = Depends(
        deps.get_list_users_permission_checker
    ),
) -> list[OrganizationUser]:
    return await users_service.list_organization_users(
        current_user,
        str(org_id) if org_id is not None else None,
        permission_checker,
    )
