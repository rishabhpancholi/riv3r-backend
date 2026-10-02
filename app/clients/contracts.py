from dataclasses import dataclass
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class LLMClient(Protocol):
    async def generate(
        self,
        messages: Sequence[ChatMessage],
        system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> str: ...


class EmbeddingsClient(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
