import asyncio
from supabase import AsyncClient

from app.api.onboarding import schemas
from app.repositories import db_service
from app.core import exceptions
from app.utils import password, jwt


class OnboardingService:
    def __init__(self, db: AsyncClient):
        self.db_service = db_service.DBRepository(db)

    async def onboard_organization(
        self, organization: schemas.OnboardOrganization
    ) -> dict:
        db_checks = [
            self.db_service.check_email_in_db(organization.company_email),
            self.db_service.check_email_in_db(organization.owner.email),
        ]
        if organization.owner.phone_number:
            db_checks.append(
                self.db_service.check_user_with_phone_number(
                    organization.owner.phone_number
                )
            )
        if organization.website_url:
            db_checks.append(
                self.db_service.check_website_url_in_db(organization.website_url)
            )

        checks = await asyncio.gather(
            *db_checks,
        )

        if checks[0]:
            raise exceptions.DuplicateError("company email", organization.company_email)
        if checks[1]:
            raise exceptions.DuplicateError("user email", organization.email)
        if len(checks) >= 3 and checks[2]:
            raise exceptions.DuplicateError(
                "phone number", organization.owner.phone_number
            )
        if len(checks) >= 4 and checks[3]:
            raise exceptions.DuplicateError("website url", organization.website_url)

        hashed_password = password.hash_password(organization.owner.password)

        organization_dict = organization.model_dump(exclude={"owner"}, mode="json")
        organization_dict.update({"verification_status": "in_progress"})
        owner_dict = organization.owner.model_dump(exclude={"first_name", "last_name"})
        owner_dict.update(
            {"password": hashed_password, "is_resource": False, "verification_status": "in_progress"}
        )

        org = await self.db_service.store_organization(organization_dict)
        owner_dict.update({"org_id": org["id"]})
        owner = await self.db_service.store_user(owner_dict)
        org.update({"owner": owner})

        owner.pop("password")

        token_data = owner | {"org_id": org["id"], "is_owner": True}

        access_token = jwt.create_token(token_data, "access")
        refresh_token = jwt.create_token(token_data, "refresh")

        hashed_refresh_token = jwt.hash_token(refresh_token)

        insert_tasks = [
            self.db_service.store_org_membership(org["id"], owner["id"]),
            self.db_service.store_refresh_token(owner["id"], hashed_refresh_token),
        ]

        await asyncio.gather(*insert_tasks)

        return {
            "organization": org,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def onboard_resource(
        self, resource: schemas.OnboardResource
    )-> dict:
        db_checks = [
            self.db_service.check_email_in_db(resource.email),
        ]
        if resource.phone_number:
            db_checks.append(
                self.db_service.check_user_with_phone_number(
                    resource.phone_number
                )
            )
        if resource.portfolio_url:
            db_checks.append(
                self.db_service.check_website_url_in_db(resource.portfolio_url)
            )
        if resource.linked_in_url:
            db_checks.append(
                self.db_service.check_website_url_in_db(resource.linked_in_url)
            )

        checks = await asyncio.gather(
            *db_checks,
        )

        if checks[0]:
            raise exceptions.DuplicateError("user email", resource.email)
        if len(checks) >= 2 and checks[1]:
            raise exceptions.DuplicateError(
                "phone number", resource.phone_number
            )
        if len(checks) >= 3 and checks[2]:
            raise exceptions.DuplicateError(
                "portfolio url", resource.portfolio_url
            )
        if len(checks) >= 4 and checks[3]:
            raise exceptions.DuplicateError(
                "linkedin url", resource.linked_in_url
            )
        
        hashed_password = password.hash_password(resource.password)

        user_dict = resource.model_dump(exclude={"title", "skills", "bio", "location", "first_name", "last_name", "experience_years", "portfolio_url", "linked_in_url"})
        user_dict.update({"password": hashed_password, "is_resource": True, "verification_status": "in_progress"})
        resource_dict = resource.model_dump(exclude={"email", "first_name", "last_name", "name", "password", "phone_number"}, mode="json")

        user = await self.db_service.store_user(user_dict)
        resource_dict.update({"user_id": user["id"]})
        reso = await self.db_service.store_resource(resource_dict)

        fields = ["id", "created_at", "updated_at", "deleted_at"]
        reso = {k: v for k, v in reso.items() if k not in fields}
        user_resource = user | reso

        user_resource.pop("password")

        access_token = jwt.create_token(user_resource, "access")
        refresh_token = jwt.create_token(user_resource, "refresh")

        hashed_refresh_token = jwt.hash_token(refresh_token)
  
        await self.db_service.store_refresh_token(user_resource["id"], hashed_refresh_token)

        return {
            "resource": user_resource,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }