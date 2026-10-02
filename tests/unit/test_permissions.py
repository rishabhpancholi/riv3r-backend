from unittest.mock import AsyncMock

import pytest

from app.core import exceptions
from app.api.projects import dependencies as project_dependencies
from app.api.users import dependencies as user_dependencies
from app.core.permissions import (
    OrderedPermissionChecker,
    OrganizationLevelPermissionChecker,
    PermissionDecision,
    UserPermissionChecker,
)


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


@pytest.mark.asyncio
async def test_user_permission_checker_accepts_effective_permission():
    permissions = AsyncMock()
    permissions.has_effective_permission.return_value = True
    checker = UserPermissionChecker(
        permissions, required_permission="projects.create"
    )

    decision = await checker.check(
        {"id": "user-1", "org_id": "org-1", "is_resource": False}
    )

    assert decision == PermissionDecision()
    permissions.has_effective_permission.assert_awaited_once_with(
        "user-1", "projects.create"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user",
    [
        {"id": "user-1", "org_id": "org-1", "is_resource": False},
        {"id": "resource-1", "org_id": None, "is_resource": True},
    ],
)
async def test_user_permission_checker_rejects_missing_or_ineligible_grant(user):
    permissions = AsyncMock()
    permissions.has_effective_permission.return_value = False
    checker = UserPermissionChecker(permissions, required_permission="users.view")

    with pytest.raises(exceptions.PermissionError):
        await checker.check(user)

    if user["is_resource"]:
        permissions.has_effective_permission.assert_not_awaited()


@pytest.mark.asyncio
async def test_ordered_checker_stops_before_permission_lookup_on_org_denial():
    organization_checker = AsyncMock()
    organization_checker.check.side_effect = exceptions.PermissionError(
        detail="Organization denied"
    )
    user_permission_checker = AsyncMock()
    checker = OrderedPermissionChecker(
        (organization_checker, user_permission_checker)
    )

    with pytest.raises(exceptions.PermissionError):
        await checker.check({"id": "user-1"})

    user_permission_checker.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_ordered_checker_preserves_cross_tenant_decision():
    organization_checker = AsyncMock()
    organization_checker.check.return_value = PermissionDecision(cross_tenant=True)
    user_permission_checker = AsyncMock()
    user_permission_checker.check.return_value = PermissionDecision()

    decision = await OrderedPermissionChecker(
        (organization_checker, user_permission_checker)
    ).check({"id": "user-1"})

    assert decision.cross_tenant is True


def test_feature_dependencies_require_the_correct_permission_keys():
    organizations = AsyncMock()
    permissions = AsyncMock()

    create = project_dependencies.get_create_project_permission_checkers(
        organizations, permissions
    )[0]
    publish = project_dependencies.get_publish_project_permission_checkers(
        organizations, permissions
    )[0]
    users = user_dependencies.get_list_users_permission_checker(
        organizations, permissions
    )

    assert create.checkers[1].required_permission == "projects.create"
    assert publish.checkers[1].required_permission == "projects.publish"
    assert users.checkers[1].required_permission == "users.view"
