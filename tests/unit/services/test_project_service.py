from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.api.projects.schemas import CreateProject, ProjectListQuery
from app.core import exceptions
from app.core.permissions import PermissionChecker, PermissionDecision
from app.services.projects import ProjectService
from app.services.project_embeddings import GeneratedEmbedding, ProjectEmbeddingGenerator
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
    embedding_generator = AsyncMock(spec=ProjectEmbeddingGenerator)
    embedding_generator.generate.return_value = GeneratedEmbedding(
        vector=[0.1] * 1024, model="voyage-4"
    )
    service = ProjectService(
        projects=repo.projects,
        memberships=repo.memberships,
        organizations=repo.organizations,
        cache=repo.project_cache,
        embedding_generator=embedding_generator,
    )
    user = {"id": "user-1", "org_id": "org-1", "is_resource": False}
    return service, repo, checker, user, embedding_generator


@pytest.mark.asyncio
async def test_create_draft_project_uses_database_status_default(setup):
    service, repo, checker, user, embedding_generator = setup
    result = await service.create_project(project_payload(), user, [checker])

    checker.check.assert_awaited_once_with(user)
    repo.memberships.check_org_membership.assert_awaited_once()
    stored = repo.projects.store_project.call_args.args[0]
    assert stored["org_id"] == "org-1"
    assert stored["created_by_user_id"] == "user-1"
    assert "status" not in stored
    assert "published_at" not in stored
    assert "project_embeddings" not in stored
    embedding_generator.generate.assert_not_awaited()
    assert result == stored


@pytest.mark.asyncio
async def test_create_and_publish_project_sets_publication_fields(setup):
    service, repo, checker, user, embedding_generator = setup
    await service.create_project(
        project_payload(publish_also=True), user, [checker]
    )

    stored = repo.projects.store_project.call_args.args[0]
    assert stored["status"] == "published"
    assert stored["published_at"]
    assert stored["project_embeddings"] == [0.1] * 1024
    assert stored["embedding_model"] == "voyage-4"
    assert stored["embedded_at"]
    embedding_generator.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejects_spoc_outside_organization(setup):
    service, repo, checker, user, _ = setup
    repo.memberships.check_org_membership.return_value = False

    with pytest.raises(exceptions.PermissionError):
        await service.create_project(project_payload(), user, [checker])

    repo.projects.store_project.assert_not_awaited()


@pytest.mark.asyncio
async def test_riv3r_cross_tenant_access_skips_spoc_membership_check(setup):
    service, repo, checker, user, _ = setup
    checker.check.return_value = PermissionDecision(cross_tenant=True)

    await service.create_project(project_payload(), user, [checker])

    repo.memberships.check_org_membership.assert_not_awaited()
    repo.projects.store_project.assert_awaited_once()


def draft_project(**overrides):
    project = {
        "id": "project-1",
        "org_id": "org-1",
        "status": "draft",
        "title": "API modernization",
        "description": "Modernize the API",
        "domain": "Software",
        "skill_tags": ["python"],
    }
    project.update(overrides)
    return project


@pytest.mark.asyncio
async def test_client_publishes_own_draft_project(setup):
    service, repo, checker, user, embedding_generator = setup
    repo.projects.get_project_by_id = AsyncMock(return_value=draft_project())
    repo.projects.publish_draft = AsyncMock(
        return_value=draft_project(status="published", published_at="now")
    )

    result = await service.publish_project("project-1", user, [checker])

    assert result["status"] == "published"
    repo.projects.publish_draft.assert_awaited_once()
    assert repo.projects.publish_draft.call_args.kwargs["organization_id"] == "org-1"
    assert repo.projects.publish_draft.call_args.kwargs["embedding"] == [0.1] * 1024
    assert repo.projects.publish_draft.call_args.kwargs["embedding_model"] == "voyage-4"
    assert repo.projects.publish_draft.call_args.kwargs["embedded_at"]
    embedding_generator.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_riv3r_publishes_cross_tenant_project(setup):
    service, repo, checker, user, _ = setup
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
    service, repo, checker, user, embedding_generator = setup
    repo.projects.get_project_by_id = AsyncMock(return_value=None)

    with pytest.raises(exceptions.NotFoundError):
        await service.publish_project("missing", user, [checker])
    embedding_generator.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_client_cannot_publish_another_tenants_project(setup):
    service, repo, checker, user, embedding_generator = setup
    repo.projects.get_project_by_id = AsyncMock(
        return_value=draft_project(org_id="another-org")
    )

    with pytest.raises(exceptions.PermissionError):
        await service.publish_project("project-1", user, [checker])
    embedding_generator.generate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["published", "closed", "cancelled"])
async def test_only_draft_projects_can_be_published(setup, status):
    service, repo, checker, user, embedding_generator = setup
    repo.projects.get_project_by_id = AsyncMock(
        return_value=draft_project(status=status)
    )

    with pytest.raises(
        exceptions.StateError,
        match="Only draft projects can be published",
    ):
        await service.publish_project("project-1", user, [checker])
    embedding_generator.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_losing_concurrent_publish_returns_conflict(setup):
    service, repo, checker, user, _ = setup
    repo.projects.get_project_by_id = AsyncMock(
        side_effect=[draft_project(), draft_project(status="published")]
    )
    repo.projects.publish_draft = AsyncMock(return_value=None)

    with pytest.raises(exceptions.StateError):
        await service.publish_project("project-1", user, [checker])

    assert repo.projects.get_project_by_id.await_count == 2


@pytest.mark.asyncio
async def test_immediate_publication_fails_open_without_embedding(setup):
    service, repo, checker, user, embedding_generator = setup
    embedding_generator.generate.return_value = None

    await service.create_project(
        project_payload(publish_also=True), user, [checker]
    )

    stored = repo.projects.store_project.call_args.args[0]
    assert stored["status"] == "published"
    assert "project_embeddings" not in stored
    assert "embedding_model" not in stored
    assert "embedded_at" not in stored


@pytest.mark.asyncio
async def test_draft_publication_fails_open_without_embedding(setup):
    service, repo, checker, user, embedding_generator = setup
    embedding_generator.generate.return_value = None
    repo.projects.get_project_by_id.return_value = draft_project()
    repo.projects.publish_draft.return_value = draft_project(status="published")

    result = await service.publish_project("project-1", user, [checker])

    assert result["status"] == "published"
    assert repo.projects.publish_draft.call_args.kwargs["embedding"] is None
    assert repo.projects.publish_draft.call_args.kwargs["embedding_model"] is None
    assert repo.projects.publish_draft.call_args.kwargs["embedded_at"] is None


def readable_project(**overrides):
    project = {
        "id": "d7e34e0e-e12d-4fd7-9370-a76217e10724",
        "created_at": "2026-10-01T12:00:00+00:00",
        "updated_at": "2026-10-01T12:00:00+00:00",
        "deleted_at": None,
        "org_id": "11111111-1111-4111-8111-111111111111",
        "created_by_user_id": "22222222-2222-4222-8222-222222222222",
        "spoc_user_id": "33333333-3333-4333-8333-333333333333",
        "title": "API modernization",
        "description": "Modernize the API",
        "status": "draft",
        "deadline_date": "2027-01-01",
        "budget": "12500.00",
        "currency": "USD",
        "published_at": None,
        "domain": "Software",
        "skill_tags": ["python"],
    }
    project.update(overrides)
    return project


@pytest.mark.asyncio
async def test_client_detail_uses_tenant_scoped_lookup(setup):
    service, repo, checker, _, _ = setup
    user = {
        "id": "user-1",
        "org_id": "11111111-1111-4111-8111-111111111111",
        "is_resource": False,
    }
    repo.project_cache.get_detail.return_value = ("project:detail:0", None)
    repo.projects.get_visible_project.return_value = readable_project()

    result = await service.get_project(readable_project()["id"], user, checker)

    assert result["title"] == "API modernization"
    repo.projects.get_visible_project.assert_awaited_once_with(
        readable_project()["id"], user["org_id"]
    )
    repo.project_cache.set_detail.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_detail_foreign_cached_project_is_not_found(setup):
    service, repo, checker, user, _ = setup
    repo.project_cache.get_detail.return_value = (
        "project:cached:0",
        readable_project(),
    )

    with pytest.raises(exceptions.NotFoundError):
        await service.get_project(readable_project()["id"], user, checker)

    repo.projects.get_visible_project.assert_not_awaited()


@pytest.mark.asyncio
async def test_client_cannot_supply_organization_filter(setup):
    service, _, checker, user, _ = setup

    with pytest.raises(exceptions.PermissionError):
        await service.list_projects(
            ProjectListQuery(org_id="11111111-1111-4111-8111-111111111111"),
            user,
            checker,
        )


@pytest.mark.asyncio
async def test_riv3r_list_uses_exact_filters_and_pagination(setup):
    service, repo, checker, user, _ = setup
    checker.check.return_value = PermissionDecision(cross_tenant=True)
    org_id = "11111111-1111-4111-8111-111111111111"
    spoc_id = "33333333-3333-4333-8333-333333333333"
    repo.organizations.get_organization_by_id.return_value = {"id": org_id}
    repo.project_cache.get_list.return_value = ("projects:list:org:key", None)
    repo.projects.list_projects.return_value = ([readable_project()], 21)
    query = ProjectListQuery(
        page=2,
        page_size=10,
        org_id=org_id,
        spoc_user_id=spoc_id,
        status="draft",
        title="API",
        skill_tags=["PYTHON"],
        sort_by="published_at",
        sort_order="asc",
    )

    result = await service.list_projects(query, user, checker)

    assert result["total"] == 21
    assert result["total_pages"] == 3
    assert result["page"] == 2
    assert repo.projects.list_projects.await_args.kwargs == {
        "organization_id": org_id,
        "spoc_user_id": spoc_id,
        "status": "draft",
        "title": "API",
        "description": None,
        "domain": None,
        "skill_tags": ["python"],
        "sort_by": "published_at",
        "sort_order": "asc",
        "offset": 10,
        "limit": 10,
    }
    repo.project_cache.set_list.assert_awaited_once()


def test_create_project_normalizes_skill_tags():
    project = project_payload(skill_tags=[" Python ", "FASTAPI", "python"])
    assert project.skill_tags == ["python", "fastapi"]


def test_create_project_rejects_empty_skill_tag():
    with pytest.raises(ValueError, match="Skill tags cannot be empty"):
        project_payload(skill_tags=["  "])
