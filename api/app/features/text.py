"""Cheap, deterministic text features for Writing responses (fed to the LLM judge in week 3)."""
from __future__ import annotations

import re
import statistics

from pydantic import BaseModel

_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
_SENT = re.compile(r"[^.!?]+[.!?]*")
GREETINGS = re.compile(r"^\s*(dear|hi|hello|good (morning|afternoon|evening)|to whom)\b", re.I)
CLOSINGS = re.compile(r"\b(regards|sincerely|best|thank you|thanks|cheers|yours)\b[^\n]*\n?\s*\S*\s*$", re.I)


class TextFeatures(BaseModel):
    word_count: int
    sentence_count: int
    paragraph_count: int
    mean_sentence_len: float
    sentence_len_sd: float
    type_token_ratio: float
    long_word_ratio: float         # words with ≥ 7 letters
    stimulus_overlap: float        # share of response 4-grams copied from the prompt (0–1)
    has_greeting: bool
    has_closing: bool


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _ngrams(ws: list[str], n: int = 4) -> set[tuple[str, ...]]:
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def compute(text: str, stimulus: str = "") -> TextFeatures:
    ws = words(text)
    sents = [s for s in (m.strip() for m in _SENT.findall(text)) if words(s)]
    lens = [len(words(s)) for s in sents]
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    resp_ng = _ngrams(ws)
    overlap = len(resp_ng & _ngrams(words(stimulus))) / len(resp_ng) if resp_ng else 0.0
    return TextFeatures(
        word_count=len(ws),
        sentence_count=len(sents),
        paragraph_count=len(paras),
        mean_sentence_len=round(statistics.mean(lens), 1) if lens else 0.0,
        sentence_len_sd=round(statistics.pstdev(lens), 1) if len(lens) > 1 else 0.0,
        type_token_ratio=round(len(set(ws)) / len(ws), 3) if ws else 0.0,
        long_word_ratio=round(sum(len(w) >= 7 for w in ws) / len(ws), 3) if ws else 0.0,
        stimulus_overlap=round(overlap, 3),
        has_greeting=bool(GREETINGS.search(text)),
        has_closing=bool(CLOSINGS.search(text.strip())),
    )
