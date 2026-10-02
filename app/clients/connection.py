from redis.asyncio import Redis
from supabase import AsyncClient, create_async_client

from app.clients.anthropic import AnthropicLLMClient
from app.clients.contracts import EmbeddingsClient, LLMClient
from app.clients.voyage import VoyageEmbeddingsClient
from app.core.config import Settings


class Connection:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        self.db: AsyncClient = await create_async_client(
            supabase_url=self.settings.database_url,
            supabase_key=self.settings.database_key,
        )
        self.cache = Redis(
            host=self.settings.cache_host,
            port=self.settings.cache_port,
            username=self.settings.cache_username,
            password=self.settings.cache_password,
        )
        self._llm_client = AnthropicLLMClient(
            api_key=self.settings.llm_api_key,
            model=self.settings.llm_model,
        )
        self.llm: LLMClient = self._llm_client
        self.embeddings: EmbeddingsClient = VoyageEmbeddingsClient(
            api_key=self.settings.embeddings_api_key,
            model=self.settings.embeddings_model,
        )
        self.fallback_embeddings: EmbeddingsClient = VoyageEmbeddingsClient(
            api_key=self.settings.embeddings_api_key,
            model=self.settings.embeddings_fallback_model,
        )
        self._initialized = True

    async def close(self) -> None:
        if not self._initialized:
            return

        try:
            await self.cache.aclose()
        finally:
            await self._llm_client.close()
            self._initialized = False
