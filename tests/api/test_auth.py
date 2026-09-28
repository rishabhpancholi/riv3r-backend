import uuid
from unittest.mock import AsyncMock

from app.core import dependencies as deps
from app.core import exceptions
from app.utils import jwt
from tests.repository_fakes import MemoryRevocations, repository_mocks


def login_payload(**overrides):
    payload = {"email": "owner@example.com", "password": "StrongPass1!"}
    payload.update(overrides)
    return payload


def user_response():
    return {
        "id": str(uuid.uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "deleted_at": None,
        "email": "owner@example.com",
        "name": "John Doe",
        "verification_status": "in_progress",
        "phone_number": "+14155552671",
        "is_resource": False,
        "org_id": "some-org-id",
        "is_owner": True,
    }


def test_login_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth.AuthService.login_user",
        AsyncMock(
            return_value={
                "user": user_response(),
                "access_token": "login-access-token",
                "refresh_token": "login-refresh-token",
            }
        ),
    )

    response = client.post("/api/auth/login", json=login_payload())

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"

    set_cookies = response.headers.get_list("set-cookie")
    assert any(
        "access_token=login-access-token" in c and "HttpOnly" in c for c in set_cookies
    )
    assert any(
        "refresh_token=login-refresh-token" in c and "HttpOnly" in c
        for c in set_cookies
    )


def test_login_invalid_credentials(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth.AuthService.login_user",
        AsyncMock(
            side_effect=exceptions.AuthorizationError(
                message="Invalid credentials",
                detail="Please check your credentials",
            )
        ),
    )

    response = client.post("/api/auth/login", json=login_payload())

    assert response.status_code == 401


def test_login_validation_error(client, monkeypatch):
    response = client.post(
        "/api/auth/login", json={"email": "not-an-email", "password": "x"}
    )

    assert response.status_code == 400


def test_logout_without_cookies(client, monkeypatch):
    response = client.post("/api/auth/logout")

    assert response.status_code == 401


def test_logout_success(client, monkeypatch):
    monkeypatch.setattr("app.services.auth.AuthService.logout_user", AsyncMock())

    client.cookies.set("access_token", "x")
    client.cookies.set("refresh_token", "y")
    response = client.post("/api/auth/logout")

    assert response.status_code == 204


def test_refresh_without_cookies(client, monkeypatch):
    response = client.post("/api/auth/refresh")

    assert response.status_code == 401


def test_refresh_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth.AuthService.refresh",
        AsyncMock(return_value={"fresh_access_token": "fresh-access-token"}),
    )

    client.cookies.set("access_token", "x")
    client.cookies.set("refresh_token", "y")
    response = client.post("/api/auth/refresh")

    assert response.status_code == 204
    assert response.cookies.get("access_token") == "fresh-access-token"


def test_me_without_token(client, monkeypatch):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_success(client, monkeypatch):
    user = user_response()
    client.app.dependency_overrides[deps.get_current_user] = lambda: user

    client.cookies.set("access_token", "x")
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_me_returns_fresh_user_from_db(client, monkeypatch):
    fresh_user = user_response()
    repo = repository_mocks()
    repo.users.get_user_with_id.return_value = {
        **fresh_user,
        "password": "hashed-password",
    }
    repo.memberships.get_org_membership.return_value = {
        "organization_id": "some-org-id",
        "is_owner": True,
    }
    repo.revocations.is_revoked.return_value = False
    client.app.dependency_overrides[deps.get_users] = lambda: repo.users
    client.app.dependency_overrides[deps.get_memberships] = lambda: repo.memberships
    client.app.dependency_overrides[deps.get_revocations] = lambda: repo.revocations

    client.cookies.set(
        "access_token", jwt.create_token({"id": fresh_user["id"]}, "access")
    )
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "in_progress"
    assert body["is_owner"] is True
    assert "password" not in body

    repo.users.get_user_with_id.assert_awaited_once()


def test_logout_revokes_access_for_subsequent_authentication(client):
    revocations = MemoryRevocations()
    client.app.dependency_overrides[deps.get_revocations] = lambda: revocations
    access = jwt.create_token({"id": "user-1"}, "access")
    refresh = jwt.create_token({"id": "user-1"}, "refresh")
    client.cookies.set("access_token", access)
    client.cookies.set("refresh_token", refresh)
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    # Replay the cookie after logout, as a stolen token could be replayed.
    client.cookies.set("access_token", access)
    assert client.get("/api/auth/me").status_code == 401
