from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass

from app.core import exceptions
from app.repositories.contracts import OrganizationRepository


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
