import uuid
from unittest.mock import AsyncMock

from app.api.auth.routes import deps
from app.core import exceptions


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
        "is_verified": False,
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
        "access_token=login-access-token" in c and "HttpOnly" in c
        for c in set_cookies
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
    monkeypatch.setattr(
        "app.services.auth.AuthService.logout_user", AsyncMock()
    )

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
