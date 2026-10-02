from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core import exceptions
from app.core.permissions import PermissionDecision
from app.services.users import UsersService
from tests.repository_fakes import repository_mocks


def user_row(organization_id: str, **overrides) -> dict:
    row = {
        "id": str(uuid4()),
        "name": "Alex Example",
        "email": "alex@example.com",
        "phone_number": "+919876543210",
        "verification_status": "approved",
        "org_id": organization_id,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    row.update(overrides)
    return row


def setup_service():
    repo = repository_mocks()
    service = UsersService(
        users=repo.users,
        organizations=repo.organizations,
        cache=repo.organization_users_cache,
    )
    checker = SimpleNamespace(check=AsyncMock())
    return service, repo, checker


@pytest.mark.asyncio
async def test_same_tenant_cache_hit_skips_database():
    service, repo, checker = setup_service()
    org_id = str(uuid4())
    checker.check.return_value = PermissionDecision()
    repo.organization_users_cache.get.return_value = [user_row(org_id)]

    result = await service.list_organization_users(
        {"id": str(uuid4()), "org_id": org_id}, None, checker
    )

    assert result[0].name == "Alex Example"
    repo.users.list_organization_users.assert_not_awaited()
    repo.organization_users_cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_privileged_user_cannot_request_another_tenant():
    service, repo, checker = setup_service()
    checker.check.return_value = PermissionDecision()

    with pytest.raises(exceptions.PermissionError):
        await service.list_organization_users(
            {"id": str(uuid4()), "org_id": str(uuid4())},
            str(uuid4()),
            checker,
        )

    repo.organization_users_cache.get.assert_not_awaited()
    repo.users.list_organization_users.assert_not_awaited()


@pytest.mark.asyncio
async def test_riv3r_missing_target_is_checked_before_cache():
    service, repo, checker = setup_service()
    checker.check.return_value = PermissionDecision(cross_tenant=True)
    repo.organizations.get_organization_by_id.return_value = None

    with pytest.raises(exceptions.NotFoundError):
        await service.list_organization_users(
            {"id": str(uuid4()), "org_id": str(uuid4())},
            str(uuid4()),
            checker,
        )

    repo.organization_users_cache.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_miss_reads_database_and_populates_cache():
    service, repo, checker = setup_service()
    org_id = str(uuid4())
    row = user_row(org_id)
    checker.check.return_value = PermissionDecision(cross_tenant=True)
    repo.organizations.get_organization_by_id.return_value = {"id": org_id}
    repo.organization_users_cache.get.return_value = None
    repo.users.list_organization_users.return_value = [row]

    result = await service.list_organization_users(
        {"id": str(uuid4()), "org_id": str(uuid4())}, org_id, checker
    )

    serialized = [user.model_dump(mode="json") for user in result]
    assert serialized[0]["id"] == row["id"]
    assert serialized[0]["org_id"] == org_id
    repo.users.list_organization_users.assert_awaited_once_with(org_id)
    repo.organization_users_cache.set.assert_awaited_once_with(org_id, serialized)


@pytest.mark.asyncio
async def test_invalid_cached_payload_is_replaced_from_database():
    service, repo, checker = setup_service()
    org_id = str(uuid4())
    checker.check.return_value = PermissionDecision()
    repo.organization_users_cache.get.return_value = [{"password": "unsafe"}]
    repo.users.list_organization_users.return_value = []

    result = await service.list_organization_users(
        {"id": str(uuid4()), "org_id": org_id}, None, checker
    )

    assert result == []
    repo.users.list_organization_users.assert_awaited_once_with(org_id)
    repo.organization_users_cache.set.assert_awaited_once_with(org_id, [])


@pytest.mark.asyncio
async def test_database_failure_propagates_without_cache_write():
    service, repo, checker = setup_service()
    org_id = str(uuid4())
    checker.check.return_value = PermissionDecision()
    repo.organization_users_cache.get.return_value = None
    repo.users.list_organization_users.side_effect = RuntimeError("database down")

    with pytest.raises(RuntimeError, match="database down"):
        await service.list_organization_users(
            {"id": str(uuid4()), "org_id": org_id}, None, checker
        )

    repo.organization_users_cache.set.assert_not_awaited()
