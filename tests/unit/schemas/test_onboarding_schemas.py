import pytest
from pydantic import ValidationError

from app.api.onboarding.schemas import (
    OnboardOrganization,
    OnboardResource,
    OnboardUser,
)


def owner_payload(**overrides):
    payload = {
        "email": "owner@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "password": "StrongPass1!",
        "phone_number": "+14155552671",
    }
    payload.update(overrides)
    return payload


def org_payload(**overrides):
    payload = {
        "company_email": "acme@example.com",
        "registered_name": "Acme Inc",
        "website_url": "https://acme.com",
        "industry": "software",
        "org_type": "client",
        "owner": owner_payload(),
    }
    payload.update(overrides)
    return payload


def test_onboard_user_computes_name():
    user = OnboardUser(**owner_payload())

    assert user.name == "John Doe"


def test_onboard_user_rejects_weak_password():
    with pytest.raises(ValidationError):
        OnboardUser(**owner_payload(password="weak"))


def test_onboard_user_rejects_invalid_phone_number():
    with pytest.raises(ValidationError):
        OnboardUser(**owner_payload(phone_number="not-a-phone"))


def test_onboard_organization_valid():
    org = OnboardOrganization(**org_payload())

    assert org.company_email == "acme@example.com"
    assert org.owner.name == "John Doe"


def test_onboard_organization_requires_same_domain():
    with pytest.raises(ValidationError):
        OnboardOrganization(**org_payload(owner=owner_payload(email="owner@other.com")))


def test_onboard_organization_rejects_invalid_org_type():
    with pytest.raises(ValidationError):
        OnboardOrganization(**org_payload(org_type="partner"))


def test_onboard_resource_valid():
    resource = OnboardResource(
        email="dev@example.com",
        first_name="Jane",
        last_name="Smith",
        password="StrongPass1!",
        phone_number="+14155552672",
        title="Software Engineer",
        skills=["python", "fastapi"],
        experience_years=5,
        portfolio_url="https://portfolio.com",
        linked_in_url="https://linkedin.com/in/janesmith",
    )

    assert resource.name == "Jane Smith"
    assert resource.skills == ["python", "fastapi"]


def test_onboard_resource_rejects_same_portfolio_and_linkedin():
    with pytest.raises(ValidationError):
        OnboardResource(
            email="dev@example.com",
            first_name="Jane",
            last_name="Smith",
            password="StrongPass1!",
            title="Software Engineer",
            skills=["python"],
            experience_years=5,
            portfolio_url="https://same.com",
            linked_in_url="https://same.com",
        )
