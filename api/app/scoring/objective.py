"""Machine scoring for Reading & Listening: 1 point per question / per Complete-the-Words gap."""
from __future__ import annotations

from pydantic import BaseModel

from app.content.models import CompleteWordsItem, ListeningItem, PracticeSet, ReadingItem


class QuestionResult(BaseModel):
    id: str
    correct: bool
    chosen: int | str | None = None
    answer: int | str
    prompt: str | None = None
    options: list[str] | None = None
    explanation: str | None = None


class ItemResult(BaseModel):
    item_id: str
    task: str
    score: int
    max_score: int
    questions: list[QuestionResult]
    transcript: list[dict] | None = None   # listening script, revealed after answering
    full_text: str | None = None           # completed C-test text


class ObjectiveResult(BaseModel):
    set_id: str
    score: int
    max_score: int
    items: list[ItemResult]


def _norm(s: str) -> str:
    return s.strip().lower().replace("’", "'")


def score_item(item, answers: dict, seed: str = "") -> ItemResult:
    """`answers` use the option positions the user SAW (shuffled with `seed`); results are reported the same way."""
    answers = answers or {}
    qs: list[QuestionResult] = []
    if isinstance(item, CompleteWordsItem):
        for gid, word in item.gaps():
            prefix, missing = item.split(word)
            given = str(answers.get(gid, "") or "")
            # accept either just the missing letters or the whole word
            ok = _norm(given) == _norm(missing) or _norm(given) == _norm(word)
            qs.append(QuestionResult(id=gid, correct=ok, chosen=given, answer=word))
        full = item.text.replace("[[", "").replace("]]", "")
        return ItemResult(item_id=item.id, task=item.task, score=sum(q.correct for q in qs), max_score=len(qs),
                          questions=qs, full_text=full)
    if isinstance(item, (ReadingItem, ListeningItem)):
        for q in item.questions:
            order = q.order(f"{seed}:{item.id}")          # displayed position → original index
            chosen = answers.get(q.id)
            chosen = chosen if isinstance(chosen, int) and not isinstance(chosen, bool) else None
            if chosen is not None and not 0 <= chosen < len(order):
                chosen = None
            shown_answer = order.index(q.answer)
            qs.append(QuestionResult(id=q.id, correct=chosen == shown_answer, chosen=chosen, answer=shown_answer,
                                     prompt=q.prompt, options=[q.options[i] for i in order],
                                     explanation=q.explanation))
        return ItemResult(item_id=item.id, task=item.task, score=sum(q.correct for q in qs), max_score=len(qs),
                          questions=qs, transcript=item.transcript() if isinstance(item, ListeningItem) else None)
    raise ValueError(f"{item.id} is not an objective item")


def score_set(s: PracticeSet, answers: dict[str, dict]) -> ObjectiveResult:
    items = [score_item(i, answers.get(i.id, {}), seed=s.id) for i in s.items]
    return ObjectiveResult(set_id=s.id, score=sum(i.score for i in items), max_score=sum(i.max_score for i in items),
                           items=items)
