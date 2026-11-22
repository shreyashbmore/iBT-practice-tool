"""Non-secret user preferences persisted in data/settings.json."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.config import get_settings


class LLMPrefs(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_base: str | None = None  # only for ollama / custom endpoints


class SpeechPrefs(BaseModel):
    provider: str = "deepgram"
    stt_model: str | None = None  # None → env default
    tts_voice: str | None = None


class ScoringPrefs(BaseModel):
    samples: int = Field(default=3, ge=1, le=5)  # LLM scoring passes per response (median is used)


class UserSettings(BaseModel):
    llm: LLMPrefs = Field(default_factory=LLMPrefs)
    speech: SpeechPrefs = Field(default_factory=SpeechPrefs)
    scoring: ScoringPrefs = Field(default_factory=ScoringPrefs)


def _path():
    return get_settings().data_dir / "settings.json"


def load() -> UserSettings:
    p = _path()
    if p.exists():
        return UserSettings.model_validate_json(p.read_text())
    return UserSettings()


def save(s: UserSettings) -> UserSettings:
    _path().write_text(json.dumps(s.model_dump(), indent=2))
    return s
