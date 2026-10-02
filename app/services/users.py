import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.core import exceptions
from app.core.permissions import PermissionChecker
from app.repositories.contracts import (
    OrganizationRepository,
    OrganizationUsersCache,
    UserRepository,
)

logger = logging.getLogger(__name__)


class OrganizationUser(BaseModel):
    id: UUID
    name: str
    email: str
    phone_number: str | None = None
    verification_status: Literal["in_progress", "approved", "rejected"]
    org_id: UUID
    created_at: datetime
    updated_at: datetime


class UsersService:
    def __init__(
        self,
        *,
        users: UserRepository,
        organizations: OrganizationRepository,
        cache: OrganizationUsersCache,
    ) -> None:
        self.users = users
        self.organizations = organizations
        self.cache = cache

    async def list_organization_users(
        self,
        current_user: dict,
        requested_organization_id: str | None,
        permission_checker: PermissionChecker,
    ) -> list[OrganizationUser]:
        decision = await permission_checker.check(current_user)
        current_organization_id = current_user["org_id"]
        target_organization_id = (
            requested_organization_id or current_organization_id
        )

        if (
            not decision.cross_tenant
            and target_organization_id != current_organization_id
        ):
            raise exceptions.PermissionError(
                detail="You cannot view users from another organization"
            )

        if decision.cross_tenant and requested_organization_id is not None:
            organization = await self.organizations.get_organization_by_id(
                target_organization_id
            )
            if not organization:
                raise exceptions.NotFoundError("organization")

        cached = await self.cache.get(target_organization_id)
        if cached is not None:
            try:
                return [OrganizationUser.model_validate(user) for user in cached]
            except ValidationError:
                logger.warning(
                    "Ignoring invalid organization users payload for org_id=%s",
                    target_organization_id,
                )

        rows = await self.users.list_organization_users(target_organization_id)
        result = [OrganizationUser.model_validate(user) for user in rows]
        await self.cache.set(
            target_organization_id,
            [user.model_dump(mode="json") for user in result],
        )
        return result
