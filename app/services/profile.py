import asyncio
from supabase import AsyncClient
from fastapi import status

from app.api.profile import schemas
from app.repositories import db_service
from app.core import exceptions
from app.utils import password, validators as vals


class ProfileService:
    def __init__(self, db: AsyncClient):
        self.db_service = db_service.DBRepository(db)

    async def update_organization(
        self,
        organization_id: str,
        organization: schemas.UpdateOrganization,
        current_user: dict,
    ) -> dict:
        if not await self.db_service.check_org_ownership(
            organization_id, current_user["id"]
        ):
            raise exceptions.PermissionError(
                detail="Only the organization owner can update the organization",
            )

        existing, owner = await asyncio.gather(
            self.db_service.get_organization_by_id(organization_id),
            self.db_service.get_user_with_id(current_user["id"]),
        )
        if not existing:
            raise exceptions.NotFoundError("organization")

        org_updates = organization.model_dump(exclude_none=True, mode="json")

        db_checks, errors = [], []
        if (
            org_updates.get("company_email")
            and org_updates["company_email"] != existing["company_email"]
        ):
            db_checks.append(
                self.db_service.check_email_in_db(org_updates["company_email"])
            )
            errors.append(("company email", org_updates["company_email"]))
        if (
            org_updates.get("website_url")
            and org_updates["website_url"] != existing["website_url"]
        ):
            db_checks.append(
                self.db_service.check_website_url_in_db(org_updates["website_url"])
            )
            errors.append(("website url", org_updates["website_url"]))

        checks = await asyncio.gather(*db_checks) if db_checks else []
        for found, (entity, value) in zip(checks, errors):
            if found:
                raise exceptions.DuplicateError(entity, value)

        existing = await self.db_service.update_organization(
            organization_id, org_updates
        )

        owner.pop("password", None)
        existing.update({"owner": owner})

        return existing

    async def update_user(
        self,
        user_updates: schemas.UpdateUser,
        current_user: dict,
    ) -> dict:
        user = await self.db_service.get_user_with_id(current_user["id"])
        if not user:
            raise exceptions.NotFoundError("user")

        updates = user_updates.model_dump(
            exclude={"name"}, exclude_none=True, mode="json"
        )

        db_checks, errors = [], []
        if updates.get("email") and updates["email"] != user["email"]:
            db_checks.append(self.db_service.check_email_in_db(updates["email"]))
            errors.append(("user email", updates["email"]))
        if updates.get("phone_number") and updates["phone_number"] != user.get(
            "phone_number"
        ):
            db_checks.append(
                self.db_service.check_user_with_phone_number(
                    updates["phone_number"]
                )
            )
            errors.append(("phone number", updates["phone_number"]))

        needs_domain_check = (
            updates.get("email")
            and updates["email"] != user["email"]
            and not user["is_resource"]
            and user.get("org_id")
        )
        tasks = db_checks.copy()
        if needs_domain_check:
            tasks.append(self.db_service.get_organization_by_id(user["org_id"]))

        results = await asyncio.gather(*tasks) if tasks else []

        for found, (entity, value) in zip(results[: len(errors)], errors):
            if found:
                raise exceptions.DuplicateError(entity, value)

        if needs_domain_check:
            org = results[-1]
            if org:
                try:
                    vals.validate_same_domain(org["company_email"], updates["email"])
                except ValueError as e:
                    raise exceptions.Riv3rException(
                        message="Invalid email domain",
                        detail=str(e),
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

        if "password" in updates:
            updates["password"] = password.hash_password(updates.pop("password"))
        if "first_name" in updates or "last_name" in updates:
            first = updates.pop("first_name", user["name"].split(" ")[0])
            last = updates.pop(
                "last_name", " ".join(user["name"].split(" ")[1:])
            )
            updates["name"] = f"{first} {last}".strip()

        updated = await self.db_service.update_user(user["id"], updates)
        updated.pop("password", None)

        return updated

    async def update_resource(
        self,
        user_id: str,
        resource: schemas.UpdateResource,
        current_user: dict,
    ) -> dict:
        if not current_user.get("is_resource"):
            raise exceptions.PermissionError(
                detail="Only resources can update their profile",
            )
        if user_id != current_user["id"]:
            raise exceptions.PermissionError(
                detail="You can only update your own resource details",
            )

        user, existing_resource = await asyncio.gather(
            self.db_service.get_user_with_id(user_id),
            self.db_service.get_resource_by_user_id(user_id),
        )
        if not user:
            raise exceptions.NotFoundError("user")
        if not existing_resource:
            raise exceptions.NotFoundError("resource")

        resource_updates = resource.model_dump(exclude_none=True, mode="json")

        db_checks, errors = [], []
        if resource_updates.get("portfolio_url") and resource_updates[
            "portfolio_url"
        ] != existing_resource.get("portfolio_url"):
            db_checks.append(
                self.db_service.check_website_url_in_db(
                    resource_updates["portfolio_url"]
                )
            )
            errors.append(("portfolio url", resource_updates["portfolio_url"]))
        if resource_updates.get("linked_in_url") and resource_updates[
            "linked_in_url"
        ] != existing_resource.get("linked_in_url"):
            db_checks.append(
                self.db_service.check_website_url_in_db(
                    resource_updates["linked_in_url"]
                )
            )
            errors.append(("linkedin url", resource_updates["linked_in_url"]))

        checks = await asyncio.gather(*db_checks) if db_checks else []
        for found, (entity, value) in zip(checks, errors):
            if found:
                raise exceptions.DuplicateError(entity, value)

        existing_resource = await self.db_service.update_resource(
            user_id, resource_updates
        )

        fields = ["id", "created_at", "updated_at", "deleted_at"]
        resource_data = {
            k: v for k, v in existing_resource.items() if k not in fields
        }

        user.pop("password", None)

        return user | resource_data
