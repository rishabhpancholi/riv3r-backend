"""Redis implementation of access-token revocation storage."""

import hashlib
import math
import time

from redis.asyncio import Redis


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
