import logging
from time import perf_counter
from typing import Optional, Literal

from fastapi import Request
from supabase import AsyncClient

from app.repositories import db_service

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: AsyncClient):
        self.db_service = db_service.DBRepository(db)

    async def _resolve_actor(self, user_id: str) -> Literal["user", "admin"]:
        try:
            user = await self.db_service.get_user_with_id(user_id)
            if not user or user.get("is_resource"):
                return "user"

            if user.get("org_id"):
                org = await self.db_service.get_organization_by_id(user["org_id"])
                if org and org.get("org_type") == "riv3r":
                    return "admin"
        except Exception:
            logger.exception(
                "Failed to resolve actor for user_id=%s, falling back to 'user'",
                user_id,
            )

        return "user"

    async def log(
        self,
        request: Request,
        *,
        user_id: Optional[str],
        entity_type: str,
        task_type: str,
        actor: Optional[Literal["user", "admin"]] = None,
    ) -> None:
        start_time = getattr(request.state, "start_time", None)
        time_taken_ms = (perf_counter() - start_time) * 1000 if start_time else None

        if not actor:
            actor = await self._resolve_actor(user_id)

        audit_log = {
            "user_id": user_id,
            "actor": actor,
            "entity_type": entity_type,
            "task_type": task_type,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "request_id": getattr(request.state, "request_id", None),
            "time_taken_ms": time_taken_ms,
        }

        try:
            await self.db_service.store_audit_log(audit_log)
        except Exception:
            logger.exception(
                "Failed to persist audit log for task_type=%s user_id=%s",
                task_type,
                user_id,
            )
