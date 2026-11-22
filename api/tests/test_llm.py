from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.providers.llm.base import LLMError
from app.providers.llm.litellm_provider import LiteLLMProvider, extract_json


def _resp(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
                           usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))


class Out(BaseModel):
    score: int
    reason: str


def test_extract_json_variants():
    assert extract_json('{"a":1}') == {"a": 1}
    assert extract_json('```json\n{"a":1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": {"b": 2}} hope it helps') == {"a": {"b": 2}}


def test_requires_key():
    with pytest.raises(LLMError):
        LiteLLMProvider("openai", "gpt-4o-mini", api_key=None)
    LiteLLMProvider("ollama", "llama3.1")  # no key needed


async def test_complete_json_repairs_once(monkeypatch):
    import litellm

    replies = iter(['{"score": "bad"}', '{"score": 4, "reason": "ok"}'])
    calls = []

    async def fake(**kw):
        calls.append(kw)
        return _resp(next(replies))

    monkeypatch.setattr(litellm, "acompletion", fake)
    p = LiteLLMProvider("openai", "gpt-4o-mini", api_key="sk-x")
    out, usage = await p.complete_json([{"role": "user", "content": "score it"}], Out)
    assert out.score == 4 and len(calls) == 2
    assert usage.prompt_tokens == 20
    assert calls[0]["model"] == "openai/gpt-4o-mini"


async def test_validate_key_auth_error(monkeypatch, client):
    import litellm

    class AuthenticationError(Exception):
        pass

    async def fake(**kw):
        raise AuthenticationError("401 bad key")

    monkeypatch.setattr(litellm, "acompletion", fake)
    r = client.post("/api/keys/test/llm", json={"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-bad"})
    assert r.json() == {"ok": False, "message": "Invalid API key (authentication failed).", "latency_ms": None}


def test_test_llm_without_key(client):
    r = client.post("/api/keys/test/llm", json={"provider": "anthropic", "model": "claude-x"})
    assert r.json()["ok"] is False and "No API key" in r.json()["message"]
