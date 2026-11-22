from app.secrets.store import get_store, llm_secret
from app.user_settings import load

from .litellm_provider import LiteLLMProvider


def get_llm() -> LiteLLMProvider:
    prefs = load().llm
    key = get_store().get(llm_secret(prefs.provider))
    return LiteLLMProvider(prefs.provider, prefs.model, api_key=key, api_base=prefs.api_base)
