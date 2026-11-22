"""Supported LLM providers (all routed through LiteLLM).

`models` are suggestions only; any model id the provider accepts can be typed in Settings.
Check each provider's docs for current model names.
"""
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    id: str
    label: str
    litellm_prefix: str
    needs_key: bool = True
    needs_api_base: bool = False
    default_api_base: str | None = None
    key_url: str | None = None
    models: list[str] = []


PROVIDERS: dict[str, ProviderInfo] = {
    p.id: p
    for p in [
        ProviderInfo(id="openai", label="OpenAI", litellm_prefix="openai",
                     key_url="https://platform.openai.com/api-keys",
                     models=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"]),
        ProviderInfo(id="anthropic", label="Anthropic (Claude)", litellm_prefix="anthropic",
                     key_url="https://console.anthropic.com/settings/keys",
                     models=["claude-sonnet-4-5", "claude-haiku-4-5"]),
        ProviderInfo(id="gemini", label="Google Gemini", litellm_prefix="gemini",
                     key_url="https://aistudio.google.com/apikey",
                     models=["gemini-2.5-flash", "gemini-2.5-pro"]),
        ProviderInfo(id="groq", label="Groq", litellm_prefix="groq",
                     key_url="https://console.groq.com/keys",
                     models=["llama-3.3-70b-versatile"]),
        ProviderInfo(id="mistral", label="Mistral", litellm_prefix="mistral",
                     key_url="https://console.mistral.ai/api-keys",
                     models=["mistral-large-latest", "mistral-small-latest"]),
        ProviderInfo(id="openrouter", label="OpenRouter", litellm_prefix="openrouter",
                     key_url="https://openrouter.ai/keys",
                     models=["openai/gpt-4.1-mini", "anthropic/claude-sonnet-4.5"]),
        ProviderInfo(id="ollama", label="Ollama (local)", litellm_prefix="ollama_chat",
                     needs_key=False, needs_api_base=True,
                     default_api_base="http://localhost:11434",
                     models=["llama3.1", "qwen2.5"]),
    ]
}
