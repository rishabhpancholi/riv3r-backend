import asyncio
from supabase import AsyncClient
from datetime import datetime, timedelta, UTC

class DBRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def check_email_in_db(self, email: str) -> bool:
        organizations = self.db.table("organizations")
        users = self.db.table("users")

        db_ops = [
            organizations.select("*").eq("company_email", email).execute(),
            users.select("*").eq("email", email).execute(),
        ]

        org_res, user_res = await asyncio.gather(*db_ops)

        return True if org_res.data or user_res.data else False

    async def check_website_url_in_db(self, website_url: str) -> bool:
        organizations = self.db.table("organizations")
        resources = self.db.table("resources")
        
        db_ops = [
            organizations.select("*").eq("website_url", website_url).execute(),
            resources.select("*").eq("portfolio_url", website_url).execute(),
            resources.select("*").eq("linked_in_url", website_url).execute(),
        ]

        org_res, resources_portfolio_res, resources_linkedin_res = await asyncio.gather(*db_ops)

        res = org_res.data or resources_portfolio_res.data or resources_linkedin_res.data

        return True if res else False

    async def check_user_with_phone_number(self, phone_number: str) -> bool:
        users = self.db.table("users")
        res = await users.select("*").eq("phone_number", phone_number).execute()

        return True if res.data else False

    async def get_user_with_email(self, email: str) -> dict:
        users = self.db.table("users")
        res = await users.select("*").eq("email", email).execute()

        return res.data[0] if res.data else None

    async def get_user_with_id(self, user_id: str) -> dict:
        users = self.db.table("users")
        res = await users.select("*").eq("id", user_id).execute()

        return res.data[0] if res.data else None

    async def get_organization_by_id(self, organization_id: str) -> dict:
        organizations = self.db.table("organizations")
        res = await organizations.select("*").eq("id", organization_id).execute()

        return res.data[0] if res.data else None

    async def get_resource_by_user_id(self, user_id: str) -> dict:
        resources = self.db.table("resources")
        res = await resources.select("*").eq("user_id", user_id).execute()

        return res.data[0] if res.data else None

    async def get_org_membership(self, user_id: str) -> dict:
        organization_members = self.db.table("organization_members")
        res = (
            await organization_members.select("*")
            .eq("user_id", user_id)
            .execute()
        )

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

    async def update_organization(self, organization_id: str, organization: dict) -> dict:
        organizations = self.db.table("organizations")
        res = await organizations.update(organization).eq("id", organization_id).execute()

        return res.data[0]

    async def update_user(self, user_id: str, user: dict) -> dict:
        users = self.db.table("users")
        res = await users.update(user).eq("id", user_id).execute()

        return res.data[0]

    async def update_resource(self, resource_id: str, resource: dict) -> dict:
        resources = self.db.table("resources")
        res = await resources.update(resource).eq("user_id", resource_id).execute()

        return res.data[0]

    async def store_organization(self, organization: dict) -> dict:
        organizations = self.db.table("organizations")
        res = await organizations.insert(organization).execute()

        return res.data[0]

    async def store_user(self, user: dict) -> dict:
        users = self.db.table("users")
        res = await users.insert(user).execute()

        return res.data[0]

    async def store_org_membership(self, organization_id: str, user_id: str):
        organization_members = self.db.table("organization_members")
        await organization_members.insert(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "is_owner": True,
            }
        ).execute()

    async def store_audit_log(self, audit_log: dict) -> dict:
        audit_logs = self.db.table("audit_logs")
        res = await audit_logs.insert(audit_log).execute()

        return res.data[0]

    async def store_refresh_token(self, user_id: str, refresh_token: str):
        refresh_tokens = self.db.table("refresh_tokens")

        res = await refresh_tokens.select("*").eq("refresh_token", refresh_token).execute()
        if res.data:
            seven_days_later = datetime.now(UTC)+timedelta(days=7)
            await refresh_tokens.update({"is_blacklisted": False, "expires_at": seven_days_later.isoformat()}).eq("refresh_token", refresh_token).execute()
            return
        
        await refresh_tokens.insert(
            {"user_id": user_id, "refresh_token": refresh_token}
        ).execute()

    async def store_resource(self, resource: dict) -> dict:
        resources = self.db.table("resources")
        res = await resources.insert(resource).execute()

        return res.data[0]

    async def blacklist_refresh_token(self, refresh_token: str):
        refresh_tokens = self.db.table("refresh_tokens")
        await refresh_tokens.update({"is_blacklisted": True}).eq("refresh_token", refresh_token).execute()

    async def check_refresh_token_valid(self, refresh_token: str)-> bool:
        refresh_tokens = self.db.table("refresh_tokens")
        res = await refresh_tokens.select("is_blacklisted, expires_at").eq("refresh_token", refresh_token).execute()

        if not res.data or res.data[0]["is_blacklisted"] or datetime.now(UTC) > datetime.fromisoformat(res.data[0]["expires_at"]):
            return False

        return True
