from unittest.mock import AsyncMock

import pytest

from app.core import exceptions
from app.core.permissions import OrganizationLevelPermissionChecker


@pytest.mark.asyncio
@pytest.mark.parametrize("org_type", ["client", "riv3r"])
async def test_project_organization_types_are_allowed(org_type):
    organizations = AsyncMock()
    organizations.get_organization_by_id.return_value = {"org_type": org_type}
    checker = OrganizationLevelPermissionChecker(
        organizations, allowed_org_types={"client"}
    )

    decision = await checker.check({"org_id": "org-1", "is_resource": False})
    assert decision.cross_tenant is (org_type == "riv3r")


@pytest.mark.asyncio
async def test_riv3r_is_allowed_without_being_explicitly_configured():
    organizations = AsyncMock()
    organizations.get_organization_by_id.return_value = {"org_type": "riv3r"}
    checker = OrganizationLevelPermissionChecker(
        organizations, allowed_org_types=set()
    )

    decision = await checker.check({"org_id": "org-1", "is_resource": False})
    assert decision.cross_tenant is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user,organization",
    [
        ({"org_id": None, "is_resource": True}, None),
        ({"org_id": "org-1", "is_resource": False}, {"org_type": "agency"}),
    ],
)
async def test_disallowed_organization_access_is_rejected(user, organization):
    organizations = AsyncMock()
    organizations.get_organization_by_id.return_value = organization
    checker = OrganizationLevelPermissionChecker(
        organizations, allowed_org_types={"client"}
    )

    with pytest.raises(exceptions.PermissionError):
        await checker.check(user)
