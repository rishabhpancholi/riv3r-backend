from collections.abc import Sequence
from typing import Any

from voyageai import AsyncClient


class VoyageEmbeddingsClient:
    """Provider-neutral retrieval embeddings backed by Voyage AI."""

    def __init__(
        self,
        api_key: str,
        model: str,
        output_dimension: int = 1024,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._output_dimension = output_dimension
        self._client = client or AsyncClient(api_key=api_key)

    async def embed_query(self, text: str) -> list[float]:
        response = await self._client.embed(
            [text],
            model=self._model,
            input_type="query",
            output_dimension=self._output_dimension,
            output_dtype="float",
        )
        return response.embeddings[0]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        document_batch = list(texts)
        if not document_batch:
            return []

        response = await self._client.embed(
            document_batch,
            model=self._model,
            input_type="document",
            output_dimension=self._output_dimension,
            output_dtype="float",
        )
        return response.embeddings
