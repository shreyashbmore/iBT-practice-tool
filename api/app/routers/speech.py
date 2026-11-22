import hashlib

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.features.speech import SpeechFeatures, compute
from app.providers.speech.base import SpeechError, STTOptions, Transcript
from app.providers.speech.factory import get_speech

router = APIRouter(prefix="/api/speech", tags=["speech"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024


class TranscribeOut(BaseModel):
    transcript: Transcript
    features: SpeechFeatures


def _speech():
    try:
        return get_speech()
    except SpeechError as e:
        raise HTTPException(e.status or 400, str(e)) from e


@router.post("/transcribe", response_model=TranscribeOut)
async def transcribe(file: UploadFile, verbatim: bool = Form(False)) -> TranscribeOut:
    audio = await file.read()
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too large")
    sp = _speech()
    try:
        t = await sp.transcribe(audio, file.content_type or "audio/webm", STTOptions(verbatim=verbatim))
    except SpeechError as e:
        raise HTTPException(e.status if e.status and e.status < 500 else 502, str(e)) from e
    finally:
        await sp.aclose()
    return TranscribeOut(transcript=t, features=compute(t))


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str | None = None


async def synthesize_cached(text: str, voice: str | None = None) -> bytes:
    """Deepgram TTS with an on-disk cache keyed by (voice, text)."""
    sp = _speech()
    voice = voice or sp.tts_voice
    cache_dir = get_settings().data_dir / "tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / (hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest() + ".mp3")
    try:
        if not path.exists():
            path.write_bytes(await sp.synthesize(text, voice))
    except SpeechError as e:
        raise HTTPException(e.status if e.status and e.status < 500 else 502, str(e)) from e
    finally:
        await sp.aclose()
    return path.read_bytes()


def audio_response(data: bytes) -> Response:
    return Response(data, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/tts")
async def tts(body: TTSIn) -> Response:
    return audio_response(await synthesize_cached(body.text, body.voice))
