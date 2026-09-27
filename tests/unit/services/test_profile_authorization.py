import pytest

from app.core import exceptions
from app.services.profile import ProfileService
from tests.repository_fakes import repository_mocks


@pytest.mark.asyncio
async def test_non_owner_cannot_update_organization():
    repo = repository_mocks()
    service = ProfileService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        duplicates=repo.duplicates,
    )
    service.memberships.check_org_ownership.return_value = False

    with pytest.raises(exceptions.PermissionError):
        await service.update_organization("other-org", None, {"id": "user-a"})

    service.memberships.check_org_ownership.assert_awaited_once_with(
        "other-org", "user-a"
    )
    service.organizations.update_organization.assert_not_awaited()


@pytest.mark.asyncio
async def test_resource_cannot_update_another_users_profile():
    repo = repository_mocks()
    service = ProfileService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        duplicates=repo.duplicates,
    )

    with pytest.raises(exceptions.PermissionError):
        await service.update_resource(
            "user-b", None, {"id": "user-a", "is_resource": True}
        )

    service.users.get_user_with_id.assert_not_awaited()
    service.resources.update_by_user_id.assert_not_awaited()
