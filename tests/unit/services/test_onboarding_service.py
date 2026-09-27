import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from app.api.onboarding.schemas import OnboardOrganization, OnboardResource
from app.core import exceptions
from app.services import onboarding
from tests.repository_fakes import repository_mocks


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
        "verification_status": "in_progress",
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
def repo():
    mock = repository_mocks()
    mock.duplicates.check_email_in_db = AsyncMock(return_value=False)
    mock.users.check_user_with_phone_number = AsyncMock(return_value=False)
    mock.duplicates.check_website_url_in_db = AsyncMock(return_value=False)
    mock.organizations.store_organization = AsyncMock(return_value=org_row())
    mock.users.store_user = AsyncMock(return_value=user_row())
    mock.memberships.store_org_membership = AsyncMock()
    mock.resources.store_resource = AsyncMock(return_value=resource_row())
    mock.refresh_tokens.store_refresh_token = AsyncMock()

    return mock


def test_onboard_organization_success(repo):
    service = onboarding.OnboardingService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        refresh_tokens=repo.refresh_tokens,
        duplicates=repo.duplicates,
    )

    result = asyncio.run(
        service.onboard_organization(OnboardOrganization(**org_payload()))
    )

    assert result["access_token"]
    assert result["refresh_token"]
    assert result["organization"]["company_email"] == "acme@example.com"
    assert result["organization"]["owner"]["email"] == "owner@example.com"

    stored_org = repo.organizations.store_organization.call_args[0][0]
    assert stored_org["company_email"] == "acme@example.com"
    assert stored_org["website_url"] == "https://acme.com/"
    assert stored_org["verification_status"] == "in_progress"
    assert "owner" not in stored_org

    stored_user = repo.users.store_user.call_args[0][0]
    assert stored_user["email"] == "owner@example.com"
    assert stored_user["is_resource"] is False
    assert stored_user["verification_status"] == "in_progress"
    assert stored_user["org_id"] == result["organization"]["id"]
    assert stored_user["password"] != "StrongPass1!"

    repo.memberships.store_org_membership.assert_awaited_once()
    repo.refresh_tokens.store_refresh_token.assert_awaited_once()


def test_onboard_organization_duplicate_company_email(repo):
    repo.duplicates.check_email_in_db = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        refresh_tokens=repo.refresh_tokens,
        duplicates=repo.duplicates,
    )

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_organization(OnboardOrganization(**org_payload())))

    repo.organizations.store_organization.assert_not_awaited()


def test_onboard_organization_duplicate_phone_number(repo):
    repo.users.check_user_with_phone_number = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        refresh_tokens=repo.refresh_tokens,
        duplicates=repo.duplicates,
    )

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_organization(OnboardOrganization(**org_payload())))

    repo.organizations.store_organization.assert_not_awaited()


def test_onboard_organization_duplicate_website(repo):
    repo.duplicates.check_website_url_in_db = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        refresh_tokens=repo.refresh_tokens,
        duplicates=repo.duplicates,
    )

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_organization(OnboardOrganization(**org_payload())))

    repo.organizations.store_organization.assert_not_awaited()


def test_onboard_resource_success(repo):
    repo.users.store_user = AsyncMock(
        return_value=user_row(
            email="dev@example.com", name="Jane Smith", is_resource=True
        )
    )
    service = onboarding.OnboardingService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        refresh_tokens=repo.refresh_tokens,
        duplicates=repo.duplicates,
    )

    result = asyncio.run(
        service.onboard_resource(OnboardResource(**resource_payload()))
    )

    assert result["access_token"]
    assert result["refresh_token"]
    assert result["resource"]["email"] == "dev@example.com"
    assert result["resource"]["title"] == "Software Engineer"

    stored_user = repo.users.store_user.call_args[0][0]
    assert stored_user["is_resource"] is True
    assert stored_user["verification_status"] == "in_progress"
    assert stored_user["password"] != "StrongPass1!"

    stored_resource = repo.resources.store_resource.call_args[0][0]
    assert stored_resource["user_id"] == result["resource"]["id"]
    assert stored_resource["portfolio_url"] == "https://portfolio.com/"
    assert stored_resource["linked_in_url"] == "https://linkedin.com/in/janesmith"

    repo.refresh_tokens.store_refresh_token.assert_awaited_once()


def test_onboard_resource_duplicate_email(repo):
    repo.duplicates.check_email_in_db = AsyncMock(return_value=True)
    service = onboarding.OnboardingService(
        users=repo.users,
        organizations=repo.organizations,
        memberships=repo.memberships,
        resources=repo.resources,
        refresh_tokens=repo.refresh_tokens,
        duplicates=repo.duplicates,
    )

    with pytest.raises(exceptions.DuplicateError):
        asyncio.run(service.onboard_resource(OnboardResource(**resource_payload())))

    repo.users.store_user.assert_not_awaited()
