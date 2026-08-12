from redis.asyncio import Redis

from app.core.config import load_settings

settings = load_settings()

class CacheRepository:
    def __init__(self, cache: Redis):
        self.cache = cache

    async def blacklist_access_token(self, access_token: str):
        await self.cache.setex(access_token, settings.cache_ttl, "blacklisted")

    async def check_access_token_valid(self, access_token: str)-> bool:
        return await self.cache.get(access_token) != "blacklisted"
