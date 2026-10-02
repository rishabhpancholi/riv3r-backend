import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real

from app.clients.contracts import EmbeddingsClient

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 1024
@dataclass(frozen=True, slots=True)
class GeneratedEmbedding:
    vector: list[float]
    model: str


class ProjectEmbeddingGenerator:
    def __init__(
        self,
        *,
        embeddings: EmbeddingsClient,
        fallback_embeddings: EmbeddingsClient,
        primary_model: str,
        fallback_model: str,
    ) -> None:
        self.embeddings = embeddings
        self.fallback_embeddings = fallback_embeddings
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    @staticmethod
    def build_document(project: Mapping) -> str:
        skills = sorted(
            (str(skill).strip() for skill in project.get("skill_tags", [])),
            key=str.casefold,
        )
        return "\n".join(
            (
                f"Title: {project['title']}",
                f"Description: {project['description']}",
                f"Domain: {project['domain']}",
                f"Skills: {', '.join(skills)}",
            )
        )

    @staticmethod
    def _validated_vector(vector: Sequence[Real]) -> list[float]:
        if len(vector) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Expected {EMBEDDING_DIMENSION} embedding dimensions, "
                f"received {len(vector)}"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, Real)
            for value in vector
        ):
            raise ValueError("Embedding contains a non-numeric value")
        normalized = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in normalized):
            raise ValueError("Embedding contains a non-finite value")
        if not any(normalized):
            raise ValueError("Embedding contains only zero values")
        return normalized

    async def _generate_with(
        self,
        client: EmbeddingsClient,
        model: str,
        document: str,
    ) -> GeneratedEmbedding:
        vectors = await client.embed_documents([document])
        if len(vectors) != 1:
            raise ValueError("Embedding provider returned an unexpected batch size")
        return GeneratedEmbedding(
            vector=self._validated_vector(vectors[0]),
            model=model,
        )

    async def generate(self, project: Mapping) -> GeneratedEmbedding | None:
        try:
            document = self.build_document(project)
        except Exception:
            logger.exception(
                "Project embedding document construction failed; "
                "publishing without an embedding"
            )
            return None

        try:
            return await self._generate_with(
                self.embeddings,
                self.primary_model,
                document,
            )
        except Exception:
            logger.exception(
                "Primary project embedding failed; trying fallback model=%s",
                self.fallback_model,
            )

        try:
            return await self._generate_with(
                self.fallback_embeddings,
                self.fallback_model,
                document,
            )
        except Exception:
            logger.exception(
                "Fallback project embedding failed for model=%s; "
                "publishing without an embedding",
                self.fallback_model,
            )
            return None
