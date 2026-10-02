from abc import ABC, abstractmethod
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from app.core import exceptions
from app.repositories.contracts import OrganizationRepository, PermissionRepository


@dataclass(frozen=True)
class PermissionDecision:
    cross_tenant: bool = False


class PermissionChecker(ABC):
    @abstractmethod
    async def check(self, current_user: dict) -> PermissionDecision:
        """Raise PermissionError when the user does not have access."""


class OrganizationLevelPermissionChecker(PermissionChecker):
    def __init__(
        self,
        organizations: OrganizationRepository,
        *,
        allowed_org_types: Collection[str],
    ):
        self.organizations = organizations
        self.allowed_org_types = frozenset(allowed_org_types)

    async def check(self, current_user: dict) -> PermissionDecision:
        if current_user.get("is_resource") or not current_user.get("org_id"):
            raise exceptions.PermissionError(
                detail="Only organization users can access this endpoint"
            )

        organization = await self.organizations.get_organization_by_id(
            current_user["org_id"]
        )
        if not organization:
            raise exceptions.PermissionError(detail="Organization access is invalid")

        org_type = organization.get("org_type")
        if org_type != "riv3r" and org_type not in self.allowed_org_types:
            raise exceptions.PermissionError(
                detail="Your organization type cannot access this endpoint"
            )

        return PermissionDecision(cross_tenant=org_type == "riv3r")


class UserPermissionChecker(PermissionChecker):
    def __init__(
        self, permissions: PermissionRepository, *, required_permission: str
    ) -> None:
        self.permissions = permissions
        self.required_permission = required_permission

    async def check(self, current_user: dict) -> PermissionDecision:
        user_id = current_user.get("id")
        if not user_id or current_user.get("is_resource"):
            raise exceptions.PermissionError(
                detail="You do not have the required permission"
            )
        if not await self.permissions.has_effective_permission(
            str(user_id), self.required_permission
        ):
            raise exceptions.PermissionError(
                detail=f"Missing required permission: {self.required_permission}"
            )
        return PermissionDecision()


class OrderedPermissionChecker(PermissionChecker):
    """Run dependent authorization checks in order and merge their decisions."""

    def __init__(self, checkers: Sequence[PermissionChecker]) -> None:
        self.checkers = tuple(checkers)

    async def check(self, current_user: dict) -> PermissionDecision:
        cross_tenant = False
        for checker in self.checkers:
            decision = await checker.check(current_user)
            cross_tenant = cross_tenant or decision.cross_tenant
        return PermissionDecision(cross_tenant=cross_tenant)
