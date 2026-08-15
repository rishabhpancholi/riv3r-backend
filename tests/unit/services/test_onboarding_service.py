import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.onboarding.schemas import OnboardOrganization, OnboardResource
from app.core import exceptions
from app.repositories import db_service
from app.services import onboarding


def org_payload():
    return {
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


def resource_payload():
    return {
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


def org_row():
    return {
        "id": str(uuid.uuid4()),
        "company_email": "acme@example.com",
        "registered_name": "Acme Inc",
        "website_url": "https://acme.com",
        "industry": "software",
        "org_type": "client",
    }


def user_row(**overrides):
    user = {
        "id": str(uuid.uuid4()),
        "email": "owner@example.com",
        "name": "John Doe",
        "password": "hashed-password",
        "phone_number": "+14155552671",
        "is_verified": False,
        "is_resource": False,
    }
    user.update(overrides)
    return user


def resource_row():
    return {
        "id": str(uuid.uuid4()),
        "title": "Software Engineer",
        "bio": "Backend developer",
        "location": "Remote",
        "skills": ["python", "fastapi"],
        "experience_years": 5,
        "portfolio_url": "https://portfolio.com",
        "linked_in_url": "https://linkedin.com/in/janesmith",
        "is_available": True,
    }


@pytest.fixture
def repo(monkeypatch):
    mock = MagicMock()
    mock.check_email_in_db = AsyncMock(return_value=False)
    mock.check_user_with_phone_number = AsyncMock(return_value=False)
    mock.check_website_url_in_db = AsyncMock(return_value=False)
    mock.store_organization = AsyncMock(return_value=org_row())
    mock.store_user = AsyncMock(return_value=user_row())
    mock.store_org_membership = AsyncMock()
    mock.store_resource = AsyncMock(return_value=resource_row())
    mock.store_refresh_token = AsyncMock()

    monkeypatch.setattr(db_service, "DBRepository", lambda db: mock)
    return mock


def test_onboard_organization_success(repo):
    service = onboarding.OnboardingService(AsyncMock())

    result = asyncio.run(
        service.onboard_organization(OnboardOrganization(**org_payload()))
    )

    assert result["access_token"]
    assert result["refresh_token"]
    assert result["organization"]["company_email"] == "acme@example.com"
    assert result["organization"]["owner"]["email"] == "owner@example.com"

    stored_org = repo.store_organization.call_args[0][0]
    assert stored_org["company_email"] == "acme@example.com"
    assert stored_org["website_url"] == "https://acme.com/"
    assert "owner" not in stored_org

    stored_user = repo.store_user.call_args[0][0]
    assert stored_user["email"] == "owner@example.com"
    assert stored_user["is_resource"] is False
    assert stored_user["org_id"] == result["organization"]["id"]
    assert stored_user["password"] != "StrongPass1!"

    repo.store_org_membership.assert_awaited_once()
    repo.store_refresh_token.assert_awaited_once()


def test_onboard_organization_duplicate_company_email(repo):
    repo.check_email_in_db = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(AsyncMock())

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_organization(OnboardOrganization(**org_payload())))

    repo.store_organization.assert_not_awaited()


def test_onboard_organization_duplicate_phone_number(repo):
    repo.check_user_with_phone_number = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(AsyncMock())

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_organization(OnboardOrganization(**org_payload())))

    repo.store_organization.assert_not_awaited()


def test_onboard_organization_duplicate_website(repo):
    repo.check_website_url_in_db = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(AsyncMock())

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_organization(OnboardOrganization(**org_payload())))

    repo.store_organization.assert_not_awaited()


def test_onboard_resource_success(repo):
    repo.store_user = AsyncMock(
        return_value=user_row(email="dev@example.com", name="Jane Smith", is_resource=True)
    )
    service = onboarding.OnboardingService(AsyncMock())

    result = asyncio.run(
        service.onboard_resource(OnboardResource(**resource_payload()))
    )

    assert result["access_token"]
    assert result["refresh_token"]
    assert result["resource"]["email"] == "dev@example.com"
    assert result["resource"]["title"] == "Software Engineer"

    stored_user = repo.store_user.call_args[0][0]
    assert stored_user["is_resource"] is True
    assert stored_user["password"] != "StrongPass1!"

    stored_resource = repo.store_resource.call_args[0][0]
    assert stored_resource["user_id"] == result["resource"]["id"]
    assert stored_resource["portfolio_url"] == "https://portfolio.com/"
    assert stored_resource["linked_in_url"] == "https://linkedin.com/in/janesmith"

    repo.store_refresh_token.assert_awaited_once()


def test_onboard_resource_duplicate_email(repo):
    repo.check_email_in_db = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(AsyncMock())

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_resource(OnboardResource(**resource_payload())))

    repo.store_user.assert_not_awaited()
