from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.users import dependencies as users_deps
from app.core import dependencies as core_deps
from app.core import exceptions
from tests.repository_fakes import repository_mocks


def response_user(org_id: str) -> dict:
    return {
        "id": str(uuid4()),
        "name": "Alex Example",
        "email": "alex@example.com",
        "phone_number": None,
        "verification_status": "approved",
        "org_id": org_id,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def use_real_users_dependencies(client):
    repo = repository_mocks()
    repo.organization_users_cache.get.return_value = None
    repo.users.list_organization_users.return_value = []
    client.app.dependency_overrides[core_deps.get_users] = lambda: repo.users
    client.app.dependency_overrides[
        core_deps.get_organizations
    ] = lambda: repo.organizations
    client.app.dependency_overrides[
        users_deps.get_organization_users_cache
    ] = lambda: repo.organization_users_cache
    client.app.dependency_overrides[core_deps.get_permissions] = lambda: repo.permissions
    return repo


@pytest.mark.parametrize("org_type", ["client", "agency"])
def test_organization_user_with_users_view_can_list_own_users(client, org_type):
    org_id = str(uuid4())
    repo = use_real_users_dependencies(client)
    repo.organizations.get_organization_by_id.return_value = {
        "id": org_id,
        "org_type": org_type,
    }
    repo.permissions.has_effective_permission.return_value = True
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": org_id,
        "is_resource": False,
    }

    response = client.get("/api/users")

    assert response.status_code == 200
    repo.users.list_organization_users.assert_awaited_once_with(org_id)


def test_agency_without_users_view_is_forbidden(client):
    org_id = str(uuid4())
    repo = use_real_users_dependencies(client)
    repo.organizations.get_organization_by_id.return_value = {
        "id": org_id,
        "org_type": "agency",
    }
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": org_id,
        "is_resource": False,
    }

    response = client.get("/api/users")

    assert response.status_code == 403
    repo.organization_users_cache.get.assert_not_awaited()


def test_riv3r_can_list_another_organizations_users(client):
    caller_org_id = str(uuid4())
    target_org_id = str(uuid4())
    repo = use_real_users_dependencies(client)
    repo.organizations.get_organization_by_id.side_effect = [
        {"id": caller_org_id, "org_type": "riv3r"},
        {"id": target_org_id, "org_type": "client"},
    ]
    repo.permissions.has_effective_permission.return_value = True
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": caller_org_id,
        "is_resource": False,
    }

    response = client.get(f"/api/users?org_id={target_org_id}")

    assert response.status_code == 200
    repo.users.list_organization_users.assert_awaited_once_with(target_org_id)


def test_resource_user_is_forbidden_before_cache_access(client):
    repo = use_real_users_dependencies(client)
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": None,
        "is_resource": True,
    }

    response = client.get("/api/users")

    assert response.status_code == 403
    repo.organization_users_cache.get.assert_not_awaited()


def test_list_users_returns_safe_profile_list(client):
    org_id = str(uuid4())
    current_user = {"id": str(uuid4()), "org_id": org_id, "is_resource": False}
    service = AsyncMock()
    service.list_organization_users.return_value = [response_user(org_id)]
    checker = AsyncMock()
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: current_user
    client.app.dependency_overrides[users_deps.get_users_service] = lambda: service
    client.app.dependency_overrides[
        users_deps.get_list_users_permission_checker
    ] = lambda: checker

    response = client.get("/api/users")

    assert response.status_code == 200
    assert set(response.json()[0]) == {
        "id",
        "name",
        "email",
        "phone_number",
        "verification_status",
        "org_id",
        "created_at",
        "updated_at",
    }
    service.list_organization_users.assert_awaited_once_with(
        current_user, None, checker
    )


def test_list_users_passes_explicit_organization(client):
    target_org_id = str(uuid4())
    current_user = {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    service = AsyncMock()
    service.list_organization_users.return_value = []
    checker = AsyncMock()
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: current_user
    client.app.dependency_overrides[users_deps.get_users_service] = lambda: service
    client.app.dependency_overrides[
        users_deps.get_list_users_permission_checker
    ] = lambda: checker

    response = client.get(f"/api/users?org_id={target_org_id}")

    assert response.status_code == 200
    assert response.json() == []
    service.list_organization_users.assert_awaited_once_with(
        current_user, target_org_id, checker
    )


def test_list_users_rejects_invalid_organization_id(client):
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }

    response = client.get("/api/users?org_id=not-a-uuid")

    assert response.status_code == 400


def test_list_users_returns_permission_error(client):
    service = AsyncMock()
    service.list_organization_users.side_effect = exceptions.PermissionError(
        detail="You cannot view users from another organization"
    )
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[users_deps.get_users_service] = lambda: service

    response = client.get(f"/api/users?org_id={uuid4()}")

    assert response.status_code == 403
