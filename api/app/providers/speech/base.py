from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class Word(BaseModel):
    word: str                 # normalized token as recognised
    punctuated: str | None = None
    start: float
    end: float
    confidence: float


class Transcript(BaseModel):
    text: str
    words: list[Word]
    duration_s: float | None = None
    confidence: float | None = None
    model: str | None = None


class STTOptions(BaseModel):
    verbatim: bool = False      # True for Listen & Repeat: no smart formatting
    filler_words: bool = True
    language: str = "en"


class SpeechError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SpeechProvider(Protocol):
    async def transcribe(self, audio: bytes, mime: str, opts: STTOptions | None = None) -> Transcript: ...
    async def synthesize(self, text: str, voice: str | None = None) -> bytes: ...
    async def validate_key(self) -> tuple[bool, str]: ...
