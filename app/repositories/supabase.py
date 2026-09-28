"""Supabase adapters for the domain repository contracts."""

from datetime import UTC, datetime

from supabase import AsyncClient
from postgrest.exceptions import APIError

from app.core import exceptions


class SupabaseUserRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def check_user_with_phone_number(self, phone_number: str) -> bool:
        users = self.db.table("users")
        res = await users.select("*").eq("phone_number", phone_number).execute()
        return True if res.data else False

    async def get_user_with_email(self, email: str) -> dict | None:
        users = self.db.table("users")
        res = await users.select("*").eq("email", email).execute()
        return res.data[0] if res.data else None

    async def get_user_with_id(self, user_id: str) -> dict | None:
        users = self.db.table("users")
        res = await users.select("*").eq("id", user_id).execute()
        return res.data[0] if res.data else None

    async def update_user(self, user_id: str, user: dict) -> dict:
        users = self.db.table("users")
        res = await users.update(user).eq("id", user_id).execute()
        return res.data[0]

    async def email_exists(self, value: str) -> bool:
        result = await self.db.table("users").select("*").eq("email", value).execute()
        return bool(result.data)


class SupabaseOrganizationRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def get_organization_by_id(self, organization_id: str) -> dict | None:
        organizations = self.db.table("organizations")
        res = await organizations.select("*").eq("id", organization_id).execute()
        return res.data[0] if res.data else None

    async def update_organization(
        self, organization_id: str, organization: dict
    ) -> dict:
        organizations = self.db.table("organizations")
        res = (
            await organizations.update(organization).eq("id", organization_id).execute()
        )
        return res.data[0]

    async def email_exists(self, value: str) -> bool:
        result = (
            await self.db.table("organizations")
            .select("*")
            .eq("company_email", value)
            .execute()
        )
        return bool(result.data)

    async def website_exists(self, value: str) -> bool:
        result = (
            await self.db.table("organizations")
            .select("*")
            .eq("website_url", value)
            .execute()
        )
        return bool(result.data)


class SupabaseMembershipRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def get_org_membership(self, user_id: str) -> dict | None:
        organization_members = self.db.table("organization_members")
        res = await organization_members.select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None

    async def check_org_ownership(self, organization_id: str, user_id: str) -> bool:
        organization_members = self.db.table("organization_members")
        res = (
            await organization_members.select("*")
            .eq("organization_id", organization_id)
            .eq("user_id", user_id)
            .eq("is_owner", True)
            .execute()
        )
        return True if res.data else False

class SupabaseResourceRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def get_resource_by_user_id(self, user_id: str) -> dict | None:
        resources = self.db.table("resources")
        res = await resources.select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None

    async def update_by_user_id(self, user_id: str, resource: dict) -> dict:
        resources = self.db.table("resources")
        res = await resources.update(resource).eq("user_id", user_id).execute()
        return res.data[0]

    async def portfolio_exists(self, value: str) -> bool:
        result = (
            await self.db.table("resources")
            .select("*")
            .eq("portfolio_url", value)
            .execute()
        )
        return bool(result.data)

    async def linkedin_exists(self, value: str) -> bool:
        result = (
            await self.db.table("resources")
            .select("*")
            .eq("linked_in_url", value)
            .execute()
        )
        return bool(result.data)


class SupabaseRefreshTokenRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def store_refresh_token(
        self, user_id: str, refresh_token: str, *, expires_at: int
    ) -> None:
        expiration = datetime.fromtimestamp(expires_at, UTC).isoformat()
        refresh_tokens = self.db.table("refresh_tokens")
        res = (
            await refresh_tokens.select("*")
            .eq("refresh_token", refresh_token)
            .execute()
        )
        if res.data:
            await (
                refresh_tokens.update(
                    {
                        "is_blacklisted": False,
                        "expires_at": expiration,
                    }
                )
                .eq("refresh_token", refresh_token)
                .execute()
            )
            return
        await refresh_tokens.insert(
            {
                "user_id": user_id,
                "refresh_token": refresh_token,
                "expires_at": expiration,
            }
        ).execute()

    async def blacklist_refresh_token(self, refresh_token: str) -> None:
        refresh_tokens = self.db.table("refresh_tokens")
        await (
            refresh_tokens.update({"is_blacklisted": True})
            .eq("refresh_token", refresh_token)
            .execute()
        )

    async def check_refresh_token_valid(self, refresh_token: str) -> bool:
        refresh_tokens = self.db.table("refresh_tokens")
        res = (
            await refresh_tokens.select("is_blacklisted, expires_at")
            .eq("refresh_token", refresh_token)
            .execute()
        )
        if (
            not res.data
            or res.data[0]["is_blacklisted"]
            or datetime.now(UTC) >= datetime.fromisoformat(res.data[0]["expires_at"])
        ):
            return False
        return True


class SupabaseAuditLogRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def store_audit_log(self, audit_log: dict) -> dict:
        audit_logs = self.db.table("audit_logs")
        res = await audit_logs.insert(audit_log).execute()
        return res.data[0]


class SupabaseOnboardingRepository:
    _duplicate_entities = {
        "company_email": "company email",
        "owner_email": "user email",
        "email": "user email",
        "phone_number": "phone number",
        "website_url": "website url",
        "portfolio_url": "portfolio url",
        "linked_in_url": "linkedin url",
    }

    def __init__(self, db: AsyncClient):
        self.db = db

    async def _execute(self, function: str, params: dict) -> dict:
        try:
            response = await self.db.rpc(function, params).execute()
        except APIError as error:
            field = error.details
            if error.code == "23505" and field in self._duplicate_entities:
                value = params[f"p_{field}"]
                raise exceptions.DuplicateError(
                    self._duplicate_entities[field], value
                ) from error
            raise
        return response.data

    async def onboard_organization(self, params: dict) -> dict:
        return await self._execute("onboard_organization_atomic", params)

    async def onboard_resource(self, params: dict) -> dict:
        return await self._execute("onboard_resource_atomic", params)
