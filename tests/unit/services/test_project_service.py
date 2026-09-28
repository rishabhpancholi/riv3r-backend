from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.api.projects.schemas import CreateProject
from app.core import exceptions
from app.core.permissions import PermissionChecker, PermissionDecision
from app.services.projects import ProjectService
from tests.repository_fakes import repository_mocks


def project_payload(**overrides):
    payload = {
        "spoc_user_id": "d7e34e0e-e12d-4fd7-9370-a76217e10724",
        "title": "API modernization",
        "description": "Modernize the customer API",
        "deadline_date": (date.today() + timedelta(days=30)).isoformat(),
        "budget": "12500.00",
        "currency": "USD",
        "domain": "Software",
        "skill_tags": ["python", "fastapi"],
    }
    payload.update(overrides)
    return CreateProject(**payload)


@pytest.fixture
def setup():
    repo = repository_mocks()
    repo.memberships.check_org_membership = AsyncMock(return_value=True)
    repo.projects.store_project = AsyncMock(side_effect=lambda value: value)
    checker = AsyncMock(spec=PermissionChecker)
    checker.check = AsyncMock(return_value=PermissionDecision())
    service = ProjectService(projects=repo.projects, memberships=repo.memberships)
    user = {"id": "user-1", "org_id": "org-1", "is_resource": False}
    return service, repo, checker, user


@pytest.mark.asyncio
async def test_create_draft_project_uses_database_status_default(setup):
    service, repo, checker, user = setup
    result = await service.create_project(project_payload(), user, [checker])

    checker.check.assert_awaited_once_with(user)
    repo.memberships.check_org_membership.assert_awaited_once()
    stored = repo.projects.store_project.call_args.args[0]
    assert stored["org_id"] == "org-1"
    assert stored["created_by_user_id"] == "user-1"
    assert "status" not in stored
    assert "published_at" not in stored
    assert result == stored


@pytest.mark.asyncio
async def test_create_and_publish_project_sets_publication_fields(setup):
    service, repo, checker, user = setup
    await service.create_project(
        project_payload(publish_also=True), user, [checker]
    )

    stored = repo.projects.store_project.call_args.args[0]
    assert stored["status"] == "published"
    assert stored["published_at"]


@pytest.mark.asyncio
async def test_rejects_spoc_outside_organization(setup):
    service, repo, checker, user = setup
    repo.memberships.check_org_membership.return_value = False

    with pytest.raises(exceptions.PermissionError):
        await service.create_project(project_payload(), user, [checker])

    repo.projects.store_project.assert_not_awaited()


@pytest.mark.asyncio
async def test_riv3r_cross_tenant_access_skips_spoc_membership_check(setup):
    service, repo, checker, user = setup
    checker.check.return_value = PermissionDecision(cross_tenant=True)

    await service.create_project(project_payload(), user, [checker])

    repo.memberships.check_org_membership.assert_not_awaited()
    repo.projects.store_project.assert_awaited_once()


def draft_project(**overrides):
    project = {"id": "project-1", "org_id": "org-1", "status": "draft"}
    project.update(overrides)
    return project


@pytest.mark.asyncio
async def test_client_publishes_own_draft_project(setup):
    service, repo, checker, user = setup
    repo.projects.get_project_by_id = AsyncMock(return_value=draft_project())
    repo.projects.publish_draft = AsyncMock(
        return_value=draft_project(status="published", published_at="now")
    )

    result = await service.publish_project("project-1", user, [checker])

    assert result["status"] == "published"
    repo.projects.publish_draft.assert_awaited_once()
    assert repo.projects.publish_draft.call_args.kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_riv3r_publishes_cross_tenant_project(setup):
    service, repo, checker, user = setup
    checker.check.return_value = PermissionDecision(cross_tenant=True)
    repo.projects.get_project_by_id = AsyncMock(
        return_value=draft_project(org_id="another-org")
    )
    repo.projects.publish_draft = AsyncMock(
        return_value=draft_project(status="published", published_at="now")
    )

    await service.publish_project("project-1", user, [checker])

    assert repo.projects.publish_draft.call_args.kwargs["organization_id"] is None


@pytest.mark.asyncio
async def test_publish_missing_project_returns_not_found(setup):
    service, repo, checker, user = setup
    repo.projects.get_project_by_id = AsyncMock(return_value=None)

    with pytest.raises(exceptions.NotFoundError):
        await service.publish_project("missing", user, [checker])


@pytest.mark.asyncio
async def test_client_cannot_publish_another_tenants_project(setup):
    service, repo, checker, user = setup
    repo.projects.get_project_by_id = AsyncMock(
        return_value=draft_project(org_id="another-org")
    )

    with pytest.raises(exceptions.PermissionError):
        await service.publish_project("project-1", user, [checker])


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["published", "closed", "cancelled"])
async def test_only_draft_projects_can_be_published(setup, status):
    service, repo, checker, user = setup
    repo.projects.get_project_by_id = AsyncMock(
        return_value=draft_project(status=status)
    )

    with pytest.raises(
        exceptions.StateError,
        match="Only draft projects can be published",
    ):
        await service.publish_project("project-1", user, [checker])


@pytest.mark.asyncio
async def test_losing_concurrent_publish_returns_conflict(setup):
    service, repo, checker, user = setup
    repo.projects.get_project_by_id = AsyncMock(
        side_effect=[draft_project(), draft_project(status="published")]
    )
    repo.projects.publish_draft = AsyncMock(return_value=None)

    with pytest.raises(exceptions.StateError):
        await service.publish_project("project-1", user, [checker])

    assert repo.projects.get_project_by_id.await_count == 2
