from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.clients.anthropic import AnthropicLLMClient
from app.clients.contracts import ChatMessage
from app.clients.voyage import VoyageEmbeddingsClient


@pytest.mark.asyncio
async def test_anthropic_client_translates_messages_and_returns_text() -> None:
    sdk = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    content=[
                        SimpleNamespace(type="text", text="Hello"),
                        SimpleNamespace(type="tool_use"),
                        SimpleNamespace(type="text", text=" world"),
                    ]
                )
            )
        ),
        close=AsyncMock(),
    )
    client = AnthropicLLMClient("secret", "claude-test", client=sdk)

    result = await client.generate(
        [
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello"),
        ],
        system_prompt="Be concise",
        max_tokens=250,
    )

    assert result == "Hello world"
    sdk.messages.create.assert_awaited_once_with(
        model="claude-test",
        max_tokens=250,
        system="Be concise",
        messages=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
    )


@pytest.mark.asyncio
async def test_anthropic_client_omits_absent_system_prompt_and_closes() -> None:
    sdk = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(content=[]))
        ),
        close=AsyncMock(),
    )
    client = AnthropicLLMClient("secret", "claude-test", client=sdk)

    await client.generate([])
    await client.close()

    assert "system" not in sdk.messages.create.await_args.kwargs
    sdk.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_voyage_client_uses_retrieval_input_types() -> None:
    sdk = SimpleNamespace(
        embed=AsyncMock(
            side_effect=[
                SimpleNamespace(embeddings=[[0.1, 0.2]]),
                SimpleNamespace(embeddings=[[0.3], [0.4]]),
            ]
        )
    )
    client = VoyageEmbeddingsClient("secret", "voyage-test", client=sdk)

    assert await client.embed_query("question") == [0.1, 0.2]
    assert await client.embed_documents(("one", "two")) == [[0.3], [0.4]]
    assert sdk.embed.await_args_list[0].kwargs == {
        "model": "voyage-test",
        "input_type": "query",
    }
    assert sdk.embed.await_args_list[1].kwargs == {
        "model": "voyage-test",
        "input_type": "document",
    }


@pytest.mark.asyncio
async def test_voyage_client_skips_empty_document_batch() -> None:
    sdk = SimpleNamespace(embed=AsyncMock())
    client = VoyageEmbeddingsClient("secret", "voyage-test", client=sdk)

    assert await client.embed_documents([]) == []
    sdk.embed.assert_not_awaited()
