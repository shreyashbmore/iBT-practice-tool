"""Build a Sentence: 1 point if the chunks fill the slots in the key order (or an accepted alternate)."""
from __future__ import annotations

from pydantic import BaseModel

from app.content.models import BuildSentenceItem


class BuildSentenceResult(BaseModel):
    item_id: str
    correct: bool
    submitted: list[str]
    your_sentence: str
    correct_sentence: str
    explanation: str | None = None


def _norm(seq: list[str]) -> list[str]:
    return [" ".join(c.split()).lower() for c in seq]


def score_item(item: BuildSentenceItem, submitted: list[str] | None) -> BuildSentenceResult:
    submitted = list(submitted or [])
    accepted = [_norm(item.answer), *(_norm(a) for a in item.alternates)]
    correct = _norm(submitted) in accepted
    n = len(item.answer)
    filled = [c.strip() or "___" for c in submitted[:n]] + ["___"] * (n - len(submitted[:n]))
    return BuildSentenceResult(
        item_id=item.id,
        correct=correct,
        submitted=submitted,
        your_sentence=item.full_sentence(filled),
        correct_sentence=item.full_sentence(),
        explanation=item.explanation,
    )
