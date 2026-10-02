from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.clients.connection import Connection
from app.core import dependencies
from app.core.config import Settings


def _settings(**overrides: str) -> Settings:
    values = {
        "database_url": "https://database.test",
        "database_key": "database-secret",
        "cache_password": "cache-secret",
        "llm_api_key": "llm-secret",
        "llm_model": "claude-test",
        "embeddings_api_key": "embeddings-secret",
        "embeddings_model": "voyage-test",
        "jwt_secret_key": "jwt-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("field_name", "environment_name"),
    [
        ("llm_api_key", "LLM_API_KEY"),
        ("llm_model", "LLM_MODEL"),
        ("embeddings_api_key", "EMBEDDINGS_API_KEY"),
        ("embeddings_model", "EMBEDDINGS_MODEL"),
    ],
)
def test_ai_settings_are_required(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    environment_name: str,
) -> None:
    monkeypatch.delenv(environment_name, raising=False)
    values = _settings().model_dump()
    values.pop(field_name)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.asyncio
async def test_connection_initializes_once_and_closes_clients() -> None:
    database = object()
    cache = SimpleNamespace(aclose=AsyncMock())
    llm = SimpleNamespace(close=AsyncMock())
    embeddings = object()

    with (
        patch(
            "app.clients.connection.create_async_client",
            new=AsyncMock(return_value=database),
        ) as create_db,
        patch("app.clients.connection.Redis", return_value=cache) as create_cache,
        patch(
            "app.clients.connection.AnthropicLLMClient", return_value=llm
        ) as create_llm,
        patch(
            "app.clients.connection.VoyageEmbeddingsClient",
            return_value=embeddings,
        ) as create_embeddings,
    ):
        connection = Connection(_settings())
        await connection.initialize()
        await connection.initialize()

        assert connection.db is database
        assert connection.cache is cache
        assert connection.llm is llm
        assert connection.embeddings is embeddings
        create_db.assert_awaited_once()
        create_cache.assert_called_once()
        create_llm.assert_called_once_with(
            api_key="llm-secret", model="claude-test"
        )
        create_embeddings.assert_called_once_with(
            api_key="embeddings-secret", model="voyage-test"
        )

        await connection.close()

    cache.aclose.assert_awaited_once()
    llm.close.assert_awaited_once()


def test_ai_dependencies_return_shared_instances() -> None:
    llm = MagicMock()
    embeddings = MagicMock()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                connection=SimpleNamespace(llm=llm, embeddings=embeddings)
            )
        )
    )

    assert dependencies.get_llm(request) is llm
    assert dependencies.get_embeddings(request) is embeddings


@pytest.mark.asyncio
async def test_lifespan_closes_connections_when_application_raises() -> None:
    from app.main import lifespan

    connection = SimpleNamespace(initialize=AsyncMock(), close=AsyncMock())
    application = SimpleNamespace(state=SimpleNamespace())

    with patch("app.main.Connection", return_value=connection):
        with pytest.raises(RuntimeError, match="application failure"):
            async with lifespan(application):
                raise RuntimeError("application failure")

    connection.initialize.assert_awaited_once()
    connection.close.assert_awaited_once()
