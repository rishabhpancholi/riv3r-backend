import uuid
from unittest.mock import AsyncMock

from app.core import exceptions


def org_payload(**overrides):
    payload = {
        "company_email": "acme@example.com",
        "registered_name": "Acme Inc",
        "website_url": "https://acme.com",
        "industry": "software",
        "org_type": "client",
        "owner": {
            "email": "owner@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "StrongPass1!",
            "phone_number": "+14155552671",
        },
    }
    payload.update(overrides)
    return payload


def resource_payload(**overrides):
    payload = {
        "email": "dev@example.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "password": "StrongPass1!",
        "phone_number": "+14155552672",
        "title": "Software Engineer",
        "bio": "Backend developer",
        "location": "Remote",
        "skills": ["python", "fastapi"],
        "experience_years": 5,
        "portfolio_url": "https://portfolio.com",
        "linked_in_url": "https://linkedin.com/in/janesmith",
    }
    payload.update(overrides)
    return payload


def org_response():
    return {
        "id": str(uuid.uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "deleted_at": None,
        "company_email": "acme@example.com",
        "registered_name": "Acme Inc",
        "website_url": "https://acme.com",
        "industry": "software",
        "verification_status": "in_progress",
        "org_type": "client",
        "owner": {
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
        },
    }


def resource_response():
    return {
        "id": str(uuid.uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "deleted_at": None,
        "email": "dev@example.com",
        "name": "Jane Smith",
        "verification_status": "in_progress",
        "phone_number": "+14155552672",
        "is_resource": True,
        "org_id": None,
        "title": "Software Engineer",
        "bio": "Backend developer",
        "location": "Remote",
        "skills": ["python", "fastapi"],
        "experience_years": 5,
        "portfolio_url": "https://portfolio.com",
        "linked_in_url": "https://linkedin.com/in/janesmith",
        "is_available": True,
    }


def test_onboard_organization_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.onboarding.OnboardingService.onboard_organization",
        AsyncMock(
            return_value={
                "organization": org_response(),
                "access_token": "org-access-token",
                "refresh_token": "org-refresh-token",
            }
        ),
    )

    response = client.post("/api/onboarding/organization", json=org_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["company_email"] == "acme@example.com"
    assert body["org_type"] == "client"
    assert body["owner"]["email"] == "owner@example.com"

    set_cookies = response.headers.get_list("set-cookie")
    assert any(
        "access_token=org-access-token" in c and "HttpOnly" in c
        for c in set_cookies
    )
    assert any(
        "refresh_token=org-refresh-token" in c and "HttpOnly" in c
        for c in set_cookies
    )


def test_onboard_organization_validation_error(client, monkeypatch):
    payload = org_payload()
    payload["owner"]["password"] = "weak"

    response = client.post("/api/onboarding/organization", json=payload)

    assert response.status_code == 400


def test_onboard_organization_requires_same_domain(client, monkeypatch):
    payload = org_payload()
    payload["owner"]["email"] = "owner@other.com"

    response = client.post("/api/onboarding/organization", json=payload)

    assert response.status_code == 400


def test_onboard_organization_duplicate_company_email(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.onboarding.OnboardingService.onboard_organization",
        AsyncMock(
            side_effect=exceptions.DuplicateError(
                "company email", "acme@example.com"
            )
        ),
    )

    response = client.post("/api/onboarding/organization", json=org_payload())

    assert response.status_code == 409
    assert response.json()["message"].startswith("Company email")


def test_onboard_resource_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.onboarding.OnboardingService.onboard_resource",
        AsyncMock(
            return_value={
                "resource": resource_response(),
                "access_token": "res-access-token",
                "refresh_token": "res-refresh-token",
            }
        ),
    )

    response = client.post("/api/onboarding/resource", json=resource_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "dev@example.com"
    assert body["title"] == "Software Engineer"
    assert body["skills"] == ["python", "fastapi"]

    set_cookies = response.headers.get_list("set-cookie")
    assert any(
        "access_token=res-access-token" in c and "HttpOnly" in c
        for c in set_cookies
    )
    assert any(
        "refresh_token=res-refresh-token" in c and "HttpOnly" in c
        for c in set_cookies
    )


def test_onboard_resource_rejects_same_portfolio_and_linkedin(client, monkeypatch):
    payload = resource_payload(
        portfolio_url="https://same.com", linked_in_url="https://same.com"
    )

    response = client.post("/api/onboarding/resource", json=payload)

    assert response.status_code == 400
