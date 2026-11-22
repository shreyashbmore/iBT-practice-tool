"""Delivery features from word timestamps (used by Interview scoring and mic check)."""
from __future__ import annotations

from pydantic import BaseModel

from app.providers.speech.base import Transcript

FILLERS = {"uh", "um", "uhm", "erm", "er", "ah", "hmm", "mm", "mhm"}


class SpeechFeatures(BaseModel):
    word_count: int
    speaking_time_s: float          # first word start → last word end
    wpm: float                      # words / speaking time
    articulation_rate_wpm: float    # words / (speaking time − long pauses)
    pauses_over_0_5s: int
    pauses_over_1s: int
    mean_pause_s: float
    longest_pause_s: float
    filler_count: int
    fillers_per_min: float
    mean_confidence: float
    low_confidence_words: list[str]  # pronunciation proxy


def compute(t: Transcript, low_conf: float = 0.6, pause_gap: float = 0.5) -> SpeechFeatures:
    ws = t.words
    if not ws:
        return SpeechFeatures(word_count=0, speaking_time_s=0, wpm=0, articulation_rate_wpm=0,
                              pauses_over_0_5s=0, pauses_over_1s=0, mean_pause_s=0, longest_pause_s=0,
                              filler_count=0, fillers_per_min=0, mean_confidence=0, low_confidence_words=[])
    fillers = [w for w in ws if w.word.lower().strip(".,") in FILLERS]
    lexical = [w for w in ws if w not in fillers]
    span = max(ws[-1].end - ws[0].start, 1e-6)
    gaps = [max(0.0, b.start - a.end) for a, b in zip(ws, ws[1:])]
    pauses = [g for g in gaps if g >= pause_gap]
    phonation = max(span - sum(pauses), 1e-6)
    n = len(lexical)
    return SpeechFeatures(
        word_count=n,
        speaking_time_s=round(span, 2),
        wpm=round(n / span * 60, 1),
        articulation_rate_wpm=round(n / phonation * 60, 1),
        pauses_over_0_5s=len(pauses),
        pauses_over_1s=sum(g >= 1.0 for g in gaps),
        mean_pause_s=round(sum(pauses) / len(pauses), 2) if pauses else 0.0,
        longest_pause_s=round(max(gaps, default=0.0), 2),
        filler_count=len(fillers),
        fillers_per_min=round(len(fillers) / span * 60, 1),
        mean_confidence=round(sum(w.confidence for w in lexical) / n, 3) if n else 0.0,
        low_confidence_words=[w.punctuated or w.word for w in lexical if w.confidence < low_conf],
    )
