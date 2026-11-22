from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.providers.llm.base import KeyCheck, LLMError
from app.providers.llm.catalog import PROVIDERS, ProviderInfo
from app.providers.llm.litellm_provider import LiteLLMProvider
from app.providers.speech.base import SpeechError
from app.providers.speech.deepgram import DeepgramProvider
from app.secrets.store import DEEPGRAM, get_store, llm_secret, mask
from app.user_settings import LLMPrefs, ScoringPrefs, SpeechPrefs, UserSettings, load, save

router = APIRouter(prefix="/api", tags=["settings"])


class KeyStatus(BaseModel):
    set: bool
    masked: str | None = None
    source: str | None = None  # env | keychain | file


class SettingsOut(BaseModel):
    settings: UserSettings
    providers: list[ProviderInfo]
    llm_keys: dict[str, KeyStatus]
    deepgram_key: KeyStatus
    defaults: dict[str, str]


def _status(name: str) -> KeyStatus:
    s = get_store()
    v = s.get(name)
    return KeyStatus(set=bool(v), masked=mask(v), source=s.source(name))


def _key_name(name: str) -> str:
    if name == "deepgram":
        return DEEPGRAM
    if name in PROVIDERS and PROVIDERS[name].needs_key:
        return llm_secret(name)
    raise HTTPException(404, f"Unknown key '{name}'")


@router.get("/settings", response_model=SettingsOut)
def get_all() -> SettingsOut:
    cfg = get_settings()
    return SettingsOut(
        settings=load(),
        providers=list(PROVIDERS.values()),
        llm_keys={p: _status(llm_secret(p)) for p, info in PROVIDERS.items() if info.needs_key},
        deepgram_key=_status(DEEPGRAM),
        defaults={"stt_model": cfg.deepgram_stt_model, "tts_voice": cfg.deepgram_tts_voice},
    )


class SettingsIn(BaseModel):
    llm: LLMPrefs | None = None
    speech: SpeechPrefs | None = None
    scoring: ScoringPrefs | None = None


@router.put("/settings", response_model=UserSettings)
def update(body: SettingsIn) -> UserSettings:
    s = load()
    if body.llm:
        if body.llm.provider not in PROVIDERS:
            raise HTTPException(400, "Unknown provider")
        if not body.llm.model.strip():
            raise HTTPException(400, "Model is required")
        s.llm = body.llm
    if body.speech:
        if body.speech.provider != "deepgram":
            raise HTTPException(400, "Only Deepgram is supported for now")
        s.speech = body.speech
    if body.scoring:
        s.scoring = body.scoring
    return save(s)


class KeyIn(BaseModel):
    value: str


@router.put("/keys/{name}", response_model=KeyStatus)
def set_key(name: str, body: KeyIn) -> KeyStatus:
    if not body.value.strip():
        raise HTTPException(400, "Empty key")
    k = _key_name(name)
    get_store().set(k, body.value)
    return _status(k)


@router.delete("/keys/{name}", response_model=KeyStatus)
def delete_key(name: str) -> KeyStatus:
    k = _key_name(name)
    get_store().delete(k)
    return _status(k)


class LLMTestIn(BaseModel):
    """Test unsaved values from the form; anything omitted falls back to saved settings."""
    provider: str | None = None
    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None


@router.post("/keys/test/llm", response_model=KeyCheck)
async def test_llm(body: LLMTestIn | None = None) -> KeyCheck:
    body = body or LLMTestIn()
    prefs = load().llm
    provider = body.provider or prefs.provider
    model = body.model or prefs.model
    key = body.api_key or get_store().get(llm_secret(provider))
    try:
        llm = LiteLLMProvider(provider, model, api_key=key,
                              api_base=body.api_base if body.api_base is not None else prefs.api_base)
    except LLMError as e:
        return KeyCheck(ok=False, message=str(e))
    return await llm.validate_key()


class DGTestIn(BaseModel):
    api_key: str | None = None


@router.post("/keys/test/deepgram", response_model=KeyCheck)
async def test_deepgram(body: DGTestIn | None = None) -> KeyCheck:
    cfg = get_settings()
    key = (body.api_key if body else None) or get_store().get(DEEPGRAM)
    try:
        dg = DeepgramProvider(key, cfg.deepgram_stt_model, cfg.deepgram_tts_voice, cfg.deepgram_base_url)
    except SpeechError as e:
        return KeyCheck(ok=False, message=str(e))
    try:
        ok, msg = await dg.validate_key()
    finally:
        await dg.aclose()
    return KeyCheck(ok=ok, message=msg)
