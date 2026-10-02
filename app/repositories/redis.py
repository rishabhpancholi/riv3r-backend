"""Redis implementation of access-token revocation storage."""

import hashlib
import json
import logging
import math
import time

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisAccessTokenRevocationStore:
    def __init__(self, cache: Redis):
        self.cache = cache

    async def revoke(self, raw_token: str, *, expires_at: int) -> None:
        ttl = math.ceil(expires_at - time.time())
        if ttl <= 0:
            return
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        await self.cache.setex(digest, ttl, "blacklisted")

    async def is_revoked(self, raw_token: str) -> bool:
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        # Older refresh flows wrote raw keys. Read both until those keys expire.
        return bool(await self.cache.exists(digest, raw_token))


class RedisOrganizationUsersCache:
    def __init__(self, cache: Redis, *, ttl: int):
        self.cache = cache
        self.ttl = ttl

    @staticmethod
    def _key(organization_id: str) -> str:
        return f"org_users:{organization_id}"

    async def get(self, organization_id: str) -> list[dict] | None:
        try:
            cached = await self.cache.get(self._key(organization_id))
            if cached is None:
                return None
            value = json.loads(cached)
            return value if isinstance(value, list) else None
        except (TypeError, ValueError, UnicodeDecodeError):
            logger.warning(
                "Ignoring invalid organization users cache for org_id=%s",
                organization_id,
            )
            return None
        except Exception:
            logger.exception(
                "Failed to read organization users cache for org_id=%s",
                organization_id,
            )
            return None

    async def set(self, organization_id: str, users: list[dict]) -> None:
        try:
            await self.cache.setex(
                self._key(organization_id), self.ttl, json.dumps(users)
            )
        except Exception:
            logger.exception(
                "Failed to write organization users cache for org_id=%s",
                organization_id,
            )
