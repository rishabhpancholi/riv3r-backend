from datetime import date, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from app.api.projects import dependencies as project_deps
from app.core import dependencies as core_deps
from app.core import exceptions


def override_audit_service(client):
    audit = AsyncMock()
    client.app.dependency_overrides[core_deps.get_audit_service] = lambda: audit
    return audit


def project_payload(**overrides):
    payload = {
        "spoc_user_id": str(uuid4()),
        "title": "API modernization",
        "description": "Modernize the customer API",
        "deadline_date": (date.today() + timedelta(days=30)).isoformat(),
        "budget": "12500.00",
        "currency": "USD",
        "domain": "Software",
        "skill_tags": ["python", "fastapi"],
        "publish_also": False,
    }
    payload.update(overrides)
    return payload


def project_response(payload, *, published=False):
    return {
        "id": str(uuid4()),
        "created_at": "2026-09-28T12:00:00+00:00",
        "updated_at": "2026-09-28T12:00:00+00:00",
        "deleted_at": None,
        "org_id": str(uuid4()),
        "created_by_user_id": str(uuid4()),
        "spoc_user_id": payload["spoc_user_id"],
        "title": payload["title"],
        "description": payload["description"],
        "status": "published" if published else "draft",
        "deadline_date": payload["deadline_date"],
        "budget": payload["budget"],
        "currency": payload["currency"],
        "published_at": "2026-09-28T12:00:00+00:00" if published else None,
        "domain": payload["domain"],
        "skill_tags": payload["skill_tags"],
    }


def test_create_draft_project(client, monkeypatch):
    payload = project_payload()
    create = AsyncMock(return_value=project_response(payload))
    monkeypatch.setattr("app.services.projects.ProjectService.create_project", create)
    user = {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: user
    client.app.dependency_overrides[
        project_deps.get_create_project_permission_checkers
    ] = lambda: ()
    client.app.dependency_overrides[
        project_deps.get_publish_project_permission_checkers
    ] = lambda: ()
    audit = override_audit_service(client)

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["published_at"] is None
    create.assert_awaited_once()
    audit.log.assert_awaited_once()
    assert audit.log.await_args.kwargs == {
        "user_id": user["id"],
        "entity_type": "project",
        "task_type": "project_create",
    }


def test_create_and_publish_project(client, monkeypatch):
    payload = project_payload(publish_also=True)
    create = AsyncMock(return_value=project_response(payload, published=True))
    monkeypatch.setattr("app.services.projects.ProjectService.create_project", create)
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[
        project_deps.get_create_project_permission_checkers
    ] = lambda: ()
    client.app.dependency_overrides[
        project_deps.get_publish_project_permission_checkers
    ] = lambda: ()

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] is not None


def test_project_rejects_invalid_currency(client):
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[
        project_deps.get_create_project_permission_checkers
    ] = lambda: ()
    client.app.dependency_overrides[
        project_deps.get_publish_project_permission_checkers
    ] = lambda: ()
    response = client.post("/api/projects", json=project_payload(currency="usd"))
    assert response.status_code == 400


def test_project_rejects_deadline_that_is_not_in_future(client):
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[
        project_deps.get_create_project_permission_checkers
    ] = lambda: ()

    response = client.post(
        "/api/projects", json=project_payload(deadline_date=date.today().isoformat())
    )

    assert response.status_code == 400


def test_publish_project_returns_updated_project(client, monkeypatch):
    payload = project_payload()
    published = project_response(payload, published=True)
    publish = AsyncMock(return_value=published)
    monkeypatch.setattr(
        "app.services.projects.ProjectService.publish_project", publish
    )
    user = {
        "id": str(uuid4()),
        "org_id": published["org_id"],
        "is_resource": False,
    }
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: user
    client.app.dependency_overrides[
        project_deps.get_create_project_permission_checkers
    ] = lambda: ()
    client.app.dependency_overrides[
        project_deps.get_publish_project_permission_checkers
    ] = lambda: ()
    audit = override_audit_service(client)

    response = client.post(f"/api/projects/{published['id']}/publish")

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] is not None
    publish.assert_awaited_once()
    audit.log.assert_awaited_once()
    assert audit.log.await_args.kwargs == {
        "user_id": user["id"],
        "entity_type": "project",
        "task_type": "project_publish",
    }


def test_publish_non_draft_project_returns_conflict(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.projects.ProjectService.publish_project",
        AsyncMock(
            side_effect=exceptions.StateError(
                "Only draft projects can be published"
            )
        ),
    )
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[
        project_deps.get_create_project_permission_checkers
    ] = lambda: ()
    client.app.dependency_overrides[
        project_deps.get_publish_project_permission_checkers
    ] = lambda: ()
    audit = override_audit_service(client)

    response = client.post(f"/api/projects/{uuid4()}/publish")

    assert response.status_code == 409
    assert response.json()["message"] == "Only draft projects can be published"
    audit.log.assert_not_awaited()


def test_get_project(client, monkeypatch):
    payload = project_payload()
    project = project_response(payload)
    get_project = AsyncMock(return_value=project)
    monkeypatch.setattr(
        "app.services.projects.ProjectService.get_project", get_project
    )
    user = {"id": str(uuid4()), "org_id": project["org_id"], "is_resource": False}
    checker = AsyncMock()
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: user
    client.app.dependency_overrides[
        project_deps.get_read_project_permission_checker
    ] = lambda: checker

    response = client.get(f"/api/projects/{project['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == project["id"]
    get_project.assert_awaited_once_with(project["id"], user, checker)


def test_list_projects_parses_exact_and_text_query_parameters(client, monkeypatch):
    payload = project_payload()
    project = project_response(payload)
    list_projects = AsyncMock(
        return_value={
            "items": [project],
            "page": 2,
            "page_size": 10,
            "total": 11,
            "total_pages": 2,
        }
    )
    monkeypatch.setattr(
        "app.services.projects.ProjectService.list_projects", list_projects
    )
    user = {"id": str(uuid4()), "org_id": str(uuid4()), "is_resource": False}
    checker = AsyncMock()
    org_id = uuid4()
    spoc_user_id = uuid4()
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: user
    client.app.dependency_overrides[
        project_deps.get_read_project_permission_checker
    ] = lambda: checker

    response = client.get(
        "/api/projects",
        params=[
            ("page", "2"),
            ("page_size", "10"),
            ("org_id", str(org_id)),
            ("spoc_user_id", str(spoc_user_id)),
            ("status", "published"),
            ("title", " API "),
            ("skill_tags", " Python "),
            ("skill_tags", "FASTAPI"),
            ("sort_by", "published_at"),
            ("sort_order", "asc"),
        ],
    )

    assert response.status_code == 200
    query = list_projects.await_args.args[0]
    assert query.org_id == org_id
    assert query.spoc_user_id == spoc_user_id
    assert query.status.value == "published"
    assert query.title == "API"
    assert query.skill_tags == ["python", "fastapi"]


def test_list_projects_rejects_invalid_exact_filters(client):
    client.app.dependency_overrides[core_deps.get_current_user] = lambda: {
        "id": str(uuid4()),
        "org_id": str(uuid4()),
        "is_resource": False,
    }
    client.app.dependency_overrides[
        project_deps.get_read_project_permission_checker
    ] = lambda: AsyncMock()

    assert client.get("/api/projects?org_id=invalid").status_code == 400
    assert client.get("/api/projects?spoc_user_id=invalid").status_code == 400
    assert client.get("/api/projects?status=unknown").status_code == 400
