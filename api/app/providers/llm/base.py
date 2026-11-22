from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class KeyCheck(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    async def complete_text(self, messages: list[dict], *, max_tokens: int = 1024,
                            temperature: float = 0.0) -> tuple[str, Usage]: ...

    async def complete_json(self, messages: list[dict], schema: type[T], *,
                            temperature: float = 0.0, max_tokens: int = 2048) -> tuple[T, Usage]: ...

    async def validate_key(self) -> KeyCheck: ...
