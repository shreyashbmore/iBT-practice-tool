from app.config import get_settings
from app.secrets.store import DEEPGRAM, get_store
from app.user_settings import load

from .deepgram import DeepgramProvider


def get_speech() -> DeepgramProvider:
    cfg = get_settings()
    prefs = load().speech
    return DeepgramProvider(
        api_key=get_store().get(DEEPGRAM),
        stt_model=prefs.stt_model or cfg.deepgram_stt_model,
        tts_voice=prefs.tts_voice or cfg.deepgram_tts_voice,
        base_url=cfg.deepgram_base_url,
    )
