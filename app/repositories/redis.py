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


class RedisProjectCache:
    def __init__(self, cache: Redis, *, ttl: int):
        self.cache = cache
        self.ttl = ttl

    @staticmethod
    def _detail_version_key(project_id: str) -> str:
        return f"project:version:{project_id}"

    @staticmethod
    def _detail_key(project_id: str, version: str) -> str:
        return f"project:{project_id}:{version}"

    @staticmethod
    def _version_key(scope: str) -> str:
        return f"projects:list:version:{scope}"

    async def _version(self, scope: str) -> str:
        value = await self.cache.get(self._version_key(scope))
        if isinstance(value, bytes):
            value = value.decode()
        return str(value or "0")

    async def _list_key(self, scope: str, query: dict) -> str:
        version = await self._version(scope)
        canonical = json.dumps(query, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"projects:list:{scope}:{version}:{digest}"

    async def get_detail(self, project_id: str) -> tuple[str | None, dict | None]:
        try:
            version = await self.cache.get(self._detail_version_key(project_id))
            if isinstance(version, bytes):
                version = version.decode()
            key = self._detail_key(project_id, str(version or "0"))
            cached = await self.cache.get(key)
            if cached is None:
                return key, None
            value = json.loads(cached)
            return key, value if isinstance(value, dict) else None
        except (TypeError, ValueError, UnicodeDecodeError):
            logger.warning("Ignoring invalid project cache for id=%s", project_id)
            return None, None
        except Exception:
            logger.exception("Failed to read project cache for id=%s", project_id)
            return None, None

    async def set_detail(self, cache_key: str, project: dict) -> None:
        try:
            await self.cache.setex(cache_key, self.ttl, json.dumps(project))
        except Exception:
            logger.exception("Failed to write project cache key=%s", cache_key)

    async def get_list(
        self, scope: str, query: dict
    ) -> tuple[str | None, dict | None]:
        try:
            key = await self._list_key(scope, query)
            cached = await self.cache.get(key)
            if cached is None:
                return key, None
            value = json.loads(cached)
            return key, value if isinstance(value, dict) else None
        except (TypeError, ValueError, UnicodeDecodeError):
            logger.warning("Ignoring invalid project-list cache for scope=%s", scope)
            return None, None
        except Exception:
            logger.exception("Failed to read project-list cache for scope=%s", scope)
            return None, None

    async def set_list(self, cache_key: str, result: dict) -> None:
        try:
            await self.cache.setex(cache_key, self.ttl, json.dumps(result))
        except Exception:
            logger.exception("Failed to write project-list cache key=%s", cache_key)

    async def invalidate(self, project_id: str | None, organization_id: str) -> None:
        try:
            if project_id is not None:
                version = await self.cache.get(self._detail_version_key(project_id))
                if isinstance(version, bytes):
                    version = version.decode()
                old_key = self._detail_key(project_id, str(version or "0"))
                await self.cache.incr(self._detail_version_key(project_id))
                await self.cache.delete(old_key)
            await self.cache.incr(self._version_key(f"org:{organization_id}"))
            await self.cache.incr(self._version_key("global"))
        except Exception:
            logger.exception(
                "Failed to invalidate project cache for org_id=%s", organization_id
            )
