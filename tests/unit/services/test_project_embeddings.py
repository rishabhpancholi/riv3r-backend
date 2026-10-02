import math
from unittest.mock import AsyncMock

import pytest

from app.services.project_embeddings import (
    EMBEDDING_DIMENSION,
    ProjectEmbeddingGenerator,
)


def project(**overrides) -> dict:
    value = {
        "title": "API modernization",
        "description": "Modernize the customer API",
        "domain": "Software",
        "skill_tags": ["python", "fastapi"],
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_primary_embedding_is_validated_and_returned():
    embeddings = AsyncMock()
    fallback_embeddings = AsyncMock()
    embeddings.embed_documents.return_value = [[0.25] * EMBEDDING_DIMENSION]
    generator = ProjectEmbeddingGenerator(
        embeddings=embeddings,
        fallback_embeddings=fallback_embeddings,
        primary_model="voyage-4",
        fallback_model="voyage-4-lite",
    )

    result = await generator.generate(project())

    assert result is not None
    assert result.model == "voyage-4"
    assert result.vector == [0.25] * EMBEDDING_DIMENSION
    document = embeddings.embed_documents.await_args.args[0][0]
    assert document == (
        "Title: API modernization\n"
        "Description: Modernize the customer API\n"
        "Domain: Software\n"
        "Skills: fastapi, python"
    )
    fallback_embeddings.embed_documents.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary_result",
    [
        [[0.1]],
        [[float("nan")] * EMBEDDING_DIMENSION],
        [[0.0] * EMBEDDING_DIMENSION],
        [],
    ],
)
async def test_invalid_primary_embedding_uses_fallback_model(primary_result):
    embeddings = AsyncMock()
    fallback_embeddings = AsyncMock()
    embeddings.embed_documents.return_value = primary_result
    fallback_embeddings.embed_documents.return_value = [
        [0.2] * EMBEDDING_DIMENSION
    ]
    generator = ProjectEmbeddingGenerator(
        embeddings=embeddings,
        fallback_embeddings=fallback_embeddings,
        primary_model="voyage-4",
        fallback_model="voyage-4-lite",
    )

    result = await generator.generate(project())

    assert result is not None
    assert result.model == "voyage-4-lite"
    assert len(result.vector) == EMBEDDING_DIMENSION
    assert all(math.isfinite(value) for value in result.vector)
    fallback_embeddings.embed_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_failure_uses_lower_voyage_model_once():
    embeddings = AsyncMock()
    fallback_embeddings = AsyncMock()
    embeddings.embed_documents.side_effect = RuntimeError("provider unavailable")
    fallback_embeddings.embed_documents.return_value = [
        [0.2] * EMBEDDING_DIMENSION
    ]
    generator = ProjectEmbeddingGenerator(
        embeddings=embeddings,
        fallback_embeddings=fallback_embeddings,
        primary_model="voyage-4",
        fallback_model="voyage-4-lite",
    )

    result = await generator.generate(project())

    assert result is not None
    assert result.model == "voyage-4-lite"
    embeddings.embed_documents.assert_awaited_once()
    fallback_embeddings.embed_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_total_embedding_failure_returns_none():
    embeddings = AsyncMock()
    fallback_embeddings = AsyncMock()
    embeddings.embed_documents.side_effect = RuntimeError("provider unavailable")
    fallback_embeddings.embed_documents.side_effect = RuntimeError(
        "fallback unavailable"
    )
    generator = ProjectEmbeddingGenerator(
        embeddings=embeddings,
        fallback_embeddings=fallback_embeddings,
        primary_model="voyage-4",
        fallback_model="voyage-4-lite",
    )

    assert await generator.generate(project()) is None
    embeddings.embed_documents.assert_awaited_once()
    fallback_embeddings.embed_documents.assert_awaited_once()
