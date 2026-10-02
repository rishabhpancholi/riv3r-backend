from collections.abc import Sequence
from typing import Any

from anthropic import AsyncAnthropic

from app.clients.contracts import ChatMessage


class AnthropicLLMClient:
    """Provider-neutral text generation backed by Anthropic."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._client = client or AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        }
        if system_prompt is not None:
            request["system"] = system_prompt

        response = await self._client.messages.create(**request)
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )

    async def close(self) -> None:
        await self._client.close()
