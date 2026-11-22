"""Speaking: item audio (TTS), recording upload → transcription → scoring, audio playback."""
from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app import db
from app.config import get_settings
from app.content.bank import bank
from app.content.models import InterviewItem, ListeningItem, ListenRepeatItem, PracticeSet
from app.features.speech import SpeechFeatures
from app.features.speech import compute as speech_features
from app.providers.speech.base import SpeechError, STTOptions, Transcript
from app.providers.speech.factory import get_speech
from app.scoring.listen_repeat import ListenRepeatResult
from app.scoring.listen_repeat import score as score_lr

from .speech import audio_response, synthesize_cached

router = APIRouter(prefix="/api", tags=["speaking"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024
EXT = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/mpeg": ".mp3", "audio/wav": ".wav"}


def _item(set_id: str, item_id: str) -> tuple[PracticeSet, ListenRepeatItem | InterviewItem]:
    s = bank().get(set_id)
    item = next((i for i in s.items if i.id == item_id), None) if s else None
    if not isinstance(item, (ListenRepeatItem, InterviewItem)):
        raise HTTPException(404, "Unknown speaking item")
    return s, item


def spoken_text(item: ListenRepeatItem | InterviewItem) -> str:
    return item.text if isinstance(item, ListenRepeatItem) else item.question


@router.get("/sets/{set_id}/items/{item_id}/audio")
async def item_audio(set_id: str, item_id: str) -> Response:
    """The stimulus as audio, so the text never has to reach the browser before the answer.
    Listening scripts are synthesised line by line (one voice per speaker) and concatenated (MP3 frames)."""
    s = bank().get(set_id)
    item = next((i for i in s.items if i.id == item_id), None) if s else None
    if isinstance(item, ListeningItem):
        cfg = get_settings()
        voices = {"female": cfg.deepgram_voice_female, "male": cfg.deepgram_voice_male}
        parts = [await synthesize_cached(l.text, voices[l.voice]) for l in item.lines]
        return audio_response(b"".join(parts))
    _, item = _item(set_id, item_id)
    return audio_response(await synthesize_cached(spoken_text(item)))


class SpeakingOut(BaseModel):
    response_id: str
    task: str
    prompt_text: str                       # revealed after answering
    transcript: Transcript | None = None
    features: SpeechFeatures | None = None
    listen_repeat: ListenRepeatResult | None = None
    error: str | None = None               # transcription failed → retry with /process


async def process(rid: str) -> SpeakingOut:
    r = db.get_response(rid)
    if not r:
        raise HTTPException(404, "Not found")
    s, item = _item(r["set_id"], r["item_id"])
    path = get_settings().data_dir / "audio" / r["payload"]["audio_file"]
    out = SpeakingOut(response_id=rid, task=item.task, prompt_text=spoken_text(item))
    try:
        sp = get_speech()
    except SpeechError as e:
        out.error = f"{e}. Add a Deepgram key in Settings."
        return out
    try:
        t = await sp.transcribe(path.read_bytes(), r["payload"].get("mime", "audio/webm"),
                                STTOptions(verbatim=isinstance(item, ListenRepeatItem)))
    except SpeechError as e:
        out.error = str(e)
        return out
    finally:
        await sp.aclose()
    f = speech_features(t)
    payload = {**r["payload"], "transcript": t.model_dump(), "features": f.model_dump()}
    out.transcript, out.features = t, f
    db.update_payload(rid, payload, text=t.text)
    if isinstance(item, ListenRepeatItem):
        res = score_lr(item.text, t)
        db.update_score(rid, res.score, res.max_score, res.model_dump())
        out.listen_repeat = res
    return out


@router.post("/sets/{set_id}/speaking/submit", response_model=SpeakingOut)
async def submit(set_id: str, file: UploadFile, item_id: str = Form(...), attempt_id: str | None = Form(None),
                 time_spent_s: float | None = Form(None)) -> SpeakingOut:
    s, item = _item(set_id, item_id)
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "Empty recording")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too large")
    mime = (file.content_type or "audio/webm").split(";")[0]
    rid = db.insert_response(set_id=s.id, item_id=item.id, task=s.task, section=s.section, text=None,
                             payload={"attempt_id": attempt_id, "mime": mime, "prompt_text": spoken_text(item)}, time_spent_s=time_spent_s,
                             timed_out=0, score=None, max_score=5, score_json=None)
    audio_dir = get_settings().data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    name = rid + (EXT.get(mime) or mimetypes.guess_extension(mime) or ".bin")
    (audio_dir / name).write_bytes(audio)
    r = db.get_response(rid)
    db.update_payload(rid, {**r["payload"], "audio_file": name})
    return await process(rid)


@router.post("/responses/{rid}/process", response_model=SpeakingOut)
async def reprocess(rid: str) -> SpeakingOut:
    return await process(rid)


@router.get("/responses/{rid}/audio")
def response_audio(rid: str) -> FileResponse:
    r = db.get_response(rid)
    name = (r or {}).get("payload", {}).get("audio_file")
    if not name:
        raise HTTPException(404, "No audio for this response")
    path = get_settings().data_dir / "audio" / name
    if not path.exists():
        raise HTTPException(404, "Audio file missing")
    return FileResponse(path, media_type=r["payload"].get("mime", "audio/webm"))
