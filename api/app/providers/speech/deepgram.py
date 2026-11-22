"""Deepgram REST provider (pre-recorded STT + Aura TTS).

Docs: https://developers.deepgram.com/reference/speech-to-text-api/listen
      https://developers.deepgram.com/reference/text-to-speech-api/speak
"""
from __future__ import annotations

import httpx

from .base import SpeechError, STTOptions, Transcript, Word


class DeepgramProvider:
    def __init__(self, api_key: str | None, stt_model: str, tts_voice: str,
                 base_url: str = "https://api.deepgram.com", timeout: float = 60.0) -> None:
        if not api_key:
            raise SpeechError("No Deepgram API key saved", status=400)
        self.stt_model = stt_model
        self.tts_voice = tts_voice
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout,
            headers={"Authorization": f"Token {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _raise(r: httpx.Response) -> None:
        if r.is_success:
            return
        try:
            detail = r.json().get("err_msg") or r.json().get("reason") or r.text
        except Exception:
            detail = r.text
        if r.status_code in (401, 403):
            detail = "Invalid Deepgram API key"
        raise SpeechError(f"Deepgram {r.status_code}: {detail[:300]}", status=r.status_code)

    async def _post(self, path: str, **kw) -> httpx.Response:
        try:
            r = await self._client.post(path, **kw)
        except httpx.HTTPError as e:
            raise SpeechError(f"Could not reach Deepgram: {e}", status=502) from e
        self._raise(r)
        return r

    async def transcribe(self, audio: bytes, mime: str, opts: STTOptions | None = None) -> Transcript:
        opts = opts or STTOptions()
        if not audio:
            raise SpeechError("Empty audio", status=400)
        params = {
            "model": self.stt_model,
            "language": opts.language,
            "punctuate": "true",
            "filler_words": str(opts.filler_words).lower(),
            "smart_format": "false" if opts.verbatim else "true",
        }
        r = await self._post("/v1/listen", params=params, content=audio,
                             headers={"Content-Type": mime or "application/octet-stream"})
        return parse_listen_response(r.json(), self.stt_model)

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        text = text.strip()
        if not text:
            raise SpeechError("Empty text", status=400)
        r = await self._post("/v1/speak", params={"model": voice or self.tts_voice},
                             json={"text": text})
        return r.content

    async def validate_key(self) -> tuple[bool, str]:
        try:
            r = await self._client.get("/v1/projects")
        except httpx.HTTPError as e:
            return False, f"Could not reach Deepgram: {e}"
        if r.is_success:
            n = len(r.json().get("projects", []))
            return True, f"Deepgram key OK ({n} project{'s' if n != 1 else ''})"
        try:
            self._raise(r)
        except SpeechError as e:
            return False, str(e)
        return False, "Unknown error"


def parse_listen_response(data: dict, model: str | None = None) -> Transcript:
    try:
        alt = data["results"]["channels"][0]["alternatives"][0]
    except (KeyError, IndexError, TypeError) as e:
        raise SpeechError("Unexpected Deepgram response shape") from e
    words = [
        Word(word=w.get("word", ""), punctuated=w.get("punctuated_word"),
             start=float(w.get("start", 0)), end=float(w.get("end", 0)),
             confidence=float(w.get("confidence", 0)))
        for w in alt.get("words", [])
    ]
    return Transcript(
        text=alt.get("transcript", ""),
        words=words,
        duration_s=(data.get("metadata") or {}).get("duration"),
        confidence=alt.get("confidence"),
        model=model,
    )
