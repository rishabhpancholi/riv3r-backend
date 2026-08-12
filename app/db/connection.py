from supabase import create_async_client
from redis.asyncio import Redis
from app.core.config import Settings


class Connection:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def init_db(self):
        self.db = await create_async_client(
            supabase_url=self.settings.database_url,
            supabase_key=self.settings.database_key,
        )

    def init_cache(self):
        self.cache = Redis(
            host=self.settings.cache_host,
            port=self.settings.cache_port,
            username=self.settings.cache_username,
            password=self.settings.cache_password,
        )

    async def close_cache(self):
        await self.cache.close()
