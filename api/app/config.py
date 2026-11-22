from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Process-level config (env / .env). User choices live in data/settings.json."""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    data_dir: Path = ROOT_DIR / "data"

    deepgram_stt_model: str = "nova-3"
    deepgram_tts_voice: str = "aura-2-thalia-en"
    deepgram_voice_female: str = "aura-2-thalia-en"   # listening scripts (verify names in Deepgram docs)
    deepgram_voice_male: str = "aura-2-arcas-en"
    deepgram_base_url: str = "https://api.deepgram.com"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
