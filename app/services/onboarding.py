from datetime import UTC, datetime
from uuid import uuid4

from app.api.onboarding import schemas
from app.repositories.contracts import OnboardingRepository
from app.utils import jwt, password


class OnboardingService:
    def __init__(
        self,
        *,
        onboarding_repository: OnboardingRepository,
    ):
        self.onboarding_repository = onboarding_repository

    async def onboard_organization(
        self, organization: schemas.OnboardOrganization
    ) -> dict:
        hashed_password = password.hash_password(organization.owner.password)
        organization_id = str(uuid4())
        owner_id = str(uuid4())
        token_data = {
            "id": owner_id,
            "email": str(organization.owner.email),
            "name": organization.owner.name,
            "phone_number": organization.owner.phone_number,
            "is_resource": False,
            "verification_status": "in_progress",
            "org_id": organization_id,
            "is_owner": True,
        }

        access_token = jwt.create_token(token_data, "access")
        refresh_token = jwt.create_token(token_data, "refresh")
        expires_at = jwt.decode_token(refresh_token, expected_type="refresh")["exp"]
        org = await self.onboarding_repository.onboard_organization(
            {
                "p_organization_id": organization_id,
                "p_company_email": str(organization.company_email),
                "p_registered_name": organization.registered_name,
                "p_website_url": (
                    str(organization.website_url)
                    if organization.website_url
                    else None
                ),
                "p_industry": organization.industry,
                "p_org_type": organization.org_type.value,
                "p_owner_id": owner_id,
                "p_owner_email": str(organization.owner.email),
                "p_owner_password": hashed_password,
                "p_owner_name": organization.owner.name,
                "p_owner_phone_number": organization.owner.phone_number,
                "p_refresh_token": jwt.hash_token(refresh_token),
                "p_refresh_expires_at": datetime.fromtimestamp(
                    expires_at, UTC
                ).isoformat(),
            }
        )

        return {
            "organization": org,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def onboard_resource(self, resource: schemas.OnboardResource) -> dict:
        hashed_password = password.hash_password(resource.password)
        user_id = str(uuid4())
        token_data = {
            "id": user_id,
            "email": str(resource.email),
            "name": resource.name,
            "phone_number": resource.phone_number,
            "is_resource": True,
            "verification_status": "in_progress",
        }
        access_token = jwt.create_token(token_data, "access")
        refresh_token = jwt.create_token(token_data, "refresh")
        expires_at = jwt.decode_token(refresh_token, expected_type="refresh")["exp"]
        user_resource = await self.onboarding_repository.onboard_resource(
            {
                "p_user_id": user_id,
                "p_email": str(resource.email),
                "p_password": hashed_password,
                "p_name": resource.name,
                "p_phone_number": resource.phone_number,
                "p_title": resource.title,
                "p_bio": resource.bio,
                "p_location": resource.location,
                "p_skills": resource.skills,
                "p_experience_years": resource.experience_years,
                "p_portfolio_url": (
                    str(resource.portfolio_url) if resource.portfolio_url else None
                ),
                "p_linked_in_url": (
                    str(resource.linked_in_url) if resource.linked_in_url else None
                ),
                "p_refresh_token": jwt.hash_token(refresh_token),
                "p_refresh_expires_at": datetime.fromtimestamp(
                    expires_at, UTC
                ).isoformat(),
            }
        )

        return {
            "resource": user_resource,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
