from __future__ import annotations

import json
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .base import KeyCheck, LLMError, Usage
from .catalog import PROVIDERS

T = TypeVar("T", bound=BaseModel)

_JSON_RE = re.compile(r"\{.*\}", re.S)


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply (tolerates ```json fences / prose)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        if not m:
            raise
        return json.loads(m.group(0))


class LiteLLMProvider:
    def __init__(self, provider: str, model: str, api_key: str | None = None,
                 api_base: str | None = None, timeout: float = 60.0) -> None:
        if provider not in PROVIDERS:
            raise LLMError(f"Unknown provider '{provider}'")
        info = PROVIDERS[provider]
        if info.needs_key and not api_key:
            raise LLMError(f"No API key saved for {info.label}")
        self.info = info
        self.model_id = f"{info.litellm_prefix}/{model}"
        self.api_key = api_key
        self.api_base = api_base or info.default_api_base
        self.timeout = timeout

    async def _call(self, messages: list[dict], **kw):
        import litellm  # heavy import; keep lazy

        litellm.drop_params = True  # ignore params a provider does not support
        litellm.suppress_debug_info = True
        try:
            return await litellm.acompletion(
                model=self.model_id, messages=messages, api_key=self.api_key,
                api_base=self.api_base, timeout=self.timeout, **kw,
            )
        except Exception as e:  # litellm maps provider errors to its own types
            raise LLMError(_friendly(e)) from e

    @staticmethod
    def _usage(resp) -> Usage:
        u = getattr(resp, "usage", None)
        cost = None
        try:
            import litellm

            cost = litellm.completion_cost(completion_response=resp)
        except Exception:
            pass
        return Usage(
            prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(u, "completion_tokens", 0) or 0,
            cost_usd=cost,
        )

    async def complete_text(self, messages, *, max_tokens=1024, temperature=0.0):
        resp = await self._call(messages, max_tokens=max_tokens, temperature=temperature)
        return resp.choices[0].message.content or "", self._usage(resp)

    async def complete_json(self, messages, schema: type[T], *, temperature=0.0, max_tokens=2048):
        sys = {
            "role": "system",
            "content": "Reply with ONE JSON object only, no prose, matching this JSON schema:\n"
            + json.dumps(schema.model_json_schema()),
        }
        msgs = [sys, *messages]
        total = Usage()
        last_err = ""
        for attempt in range(2):  # 1 repair retry
            resp = await self._call(msgs, max_tokens=max_tokens, temperature=temperature,
                                    response_format={"type": "json_object"})
            u = self._usage(resp)
            total.prompt_tokens += u.prompt_tokens
            total.completion_tokens += u.completion_tokens
            if u.cost_usd is not None:
                total.cost_usd = (total.cost_usd or 0) + u.cost_usd
            text = resp.choices[0].message.content or ""
            try:
                return schema.model_validate(extract_json(text)), total
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = str(e)[:800]
                msgs = [*msgs, {"role": "assistant", "content": text},
                        {"role": "user", "content": f"That was invalid: {last_err}\nReturn corrected JSON only."}]
        raise LLMError(f"Model did not return valid JSON: {last_err}")

    async def validate_key(self) -> KeyCheck:
        t = time.perf_counter()
        try:
            text, _ = await self.complete_text(
                [{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=5)
        except LLMError as e:
            return KeyCheck(ok=False, message=str(e))
        ms = int((time.perf_counter() - t) * 1000)
        return KeyCheck(ok=True, message=f"Connected to {self.model_id} (replied '{text.strip()[:20]}')",
                        latency_ms=ms)


def _friendly(e: Exception) -> str:
    name = type(e).__name__
    msg = str(e)
    if "Authentication" in name or "401" in msg:
        return "Invalid API key (authentication failed)."
    if "NotFound" in name or "404" in msg:
        return "Model not found for this provider — check the model id."
    if "RateLimit" in name or "429" in msg:
        return "Rate limited or out of credit (429)."
    if "Timeout" in name:
        return "Request timed out."
    if "APIConnection" in name or "Connection" in msg:
        return "Could not reach the provider (network / api_base)."
    return f"{name}: {msg[:300]}"
