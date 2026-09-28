import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from app.api.onboarding.schemas import OnboardOrganization, OnboardResource
from app.core import exceptions
from app.services import onboarding
from app.utils import jwt
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
        "website_url": "https://acme.com/",
        "industry": "software",
        "org_type": "client",
        "owner": {
            "id": str(uuid.uuid4()),
            "email": "owner@example.com",
            "name": "John Doe",
            "is_resource": False,
        },
    }


def resource_row():
    return {
        "id": str(uuid.uuid4()),
        "email": "dev@example.com",
        "name": "Jane Smith",
        "is_resource": True,
        "title": "Software Engineer",
        "skills": ["python", "fastapi"],
    }


@pytest.fixture
def repo():
    mock = repository_mocks()
    mock.onboarding.onboard_organization = AsyncMock(return_value=org_row())
    mock.onboarding.onboard_resource = AsyncMock(return_value=resource_row())
    return mock


def test_onboard_organization_uses_one_atomic_rpc(repo):
    service = onboarding.OnboardingService(onboarding_repository=repo.onboarding)
    result = asyncio.run(
        service.onboard_organization(OnboardOrganization(**org_payload()))
    )

    assert result["organization"]["company_email"] == "acme@example.com"
    params = repo.onboarding.onboard_organization.call_args.args[0]
    assert params["p_owner_id"]
    assert params["p_organization_id"]
    assert params["p_owner_password"] != "StrongPass1!"
    assert params["p_refresh_token"] != result["refresh_token"]
    assert (
        jwt.decode_token(result["access_token"], expected_type="access")["id"]
        == params["p_owner_id"]
    )
    assert (
        jwt.decode_token(result["access_token"], expected_type="access")["org_id"]
        == params["p_organization_id"]
    )


def test_onboard_resource_uses_one_atomic_rpc(repo):
    service = onboarding.OnboardingService(onboarding_repository=repo.onboarding)
    result = asyncio.run(
        service.onboard_resource(OnboardResource(**resource_payload()))
    )

    assert result["resource"]["title"] == "Software Engineer"
    params = repo.onboarding.onboard_resource.call_args.args[0]
    assert params["p_user_id"]
    assert params["p_password"] != "StrongPass1!"
    assert params["p_refresh_token"] != result["refresh_token"]
    assert (
        jwt.decode_token(result["access_token"], expected_type="access")["id"]
        == params["p_user_id"]
    )


@pytest.mark.parametrize("method", ["onboard_organization", "onboard_resource"])
def test_rpc_errors_propagate_without_follow_up_writes(repo, method):
    getattr(repo.onboarding, method).side_effect = exceptions.DuplicateError(
        "user email", "taken@example.com"
    )
    service = onboarding.OnboardingService(onboarding_repository=repo.onboarding)

    with pytest.raises(exceptions.DuplicateError):
        if method == "onboard_organization":
            asyncio.run(
                service.onboard_organization(OnboardOrganization(**org_payload()))
            )
        else:
            asyncio.run(
                service.onboard_resource(OnboardResource(**resource_payload()))
            )

    getattr(repo.onboarding, method).assert_awaited_once()
