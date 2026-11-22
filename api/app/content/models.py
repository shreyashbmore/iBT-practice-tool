"""Item-bank schema. One YAML file = one practice set (see content/items/).

Client-facing views strip answer keys (`public()`), so answers never reach the browser before submission.
"""
from __future__ import annotations

import random
import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

CEFR = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
SLOT = "[]"


class ItemBase(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")
    cefr: CEFR | None = None
    tags: list[str] = []


# ---------- Writing: Build a Sentence ----------
class BuildSentenceItem(ItemBase):
    task: Literal["build-a-sentence"] = "build-a-sentence"
    speaker: str = "Classmate"
    context: str                       # message the test taker responds to
    template: str                      # response with "[]" slots, e.g. "Yes, [] [] the report."
    answer: list[str]                  # chunks in slot order
    distractors: list[str] = []        # extra chunks that don't belong
    alternates: list[list[str]] = []   # other accepted slot orders
    explanation: str | None = None

    @model_validator(mode="after")
    def _check(self):
        n = self.template.count(SLOT)
        if n == 0:
            raise ValueError(f"{self.id}: template has no {SLOT} slots")
        for seq in [self.answer, *self.alternates]:
            if len(seq) != n:
                raise ValueError(f"{self.id}: needs {n} chunks, got {len(seq)}")
            if sorted(seq) != sorted(self.answer):
                raise ValueError(f"{self.id}: alternate uses different chunks than the answer")
        if set(self.distractors) & set(self.answer):
            raise ValueError(f"{self.id}: a distractor is also an answer chunk")
        return self

    def full_sentence(self, chunks: list[str] | None = None) -> str:
        parts = self.template.split(SLOT)
        chunks = chunks if chunks is not None else self.answer
        out = parts[0]
        for c, p in zip(chunks, parts[1:]):
            out += c + p
        return re.sub(r"\s+", " ", out).strip()

    def public(self, seed: str) -> dict:
        chunks = [*self.answer, *self.distractors]
        rnd = random.Random(seed + self.id)
        while True:  # shuffle, but never present the answer already in order
            rnd.shuffle(chunks)
            if chunks[: len(self.answer)] != self.answer or len(chunks) < 3:
                break
        return {"id": self.id, "task": self.task, "speaker": self.speaker, "context": self.context,
                "template": self.template, "chunks": chunks, "slots": self.template.count(SLOT)}


# ---------- Writing: Email ----------
class EmailItem(ItemBase):
    task: Literal["write-an-email"] = "write-an-email"
    scenario: str
    recipient: str
    points: list[str] = Field(min_length=2, max_length=4)   # "In your email, do the following"
    subject: str | None = None

    def public(self, seed: str) -> dict:
        return self.model_dump()


# ---------- Writing: Academic Discussion ----------
class Post(BaseModel):
    name: str
    text: str


class DiscussionItem(ItemBase):
    task: Literal["academic-discussion"] = "academic-discussion"
    course: str
    professor: Post
    students: list[Post] = Field(min_length=2, max_length=2)

    def public(self, seed: str) -> dict:
        return self.model_dump()


# ---------- Speaking: Listen and Repeat ----------
class ListenRepeatItem(ItemBase):
    task: Literal["listen-and-repeat"] = "listen-and-repeat"
    text: str                          # the sentence to repeat (never sent to the client before answering)
    response_time_s: int | None = None  # default derived from length

    def response_seconds(self) -> int:
        if self.response_time_s:
            return self.response_time_s
        n = len(self.text.split())
        return max(8, min(20, round(n * 0.6) + 5))   # approximation; adjust to official timing

    def public(self, seed: str) -> dict:
        return {"id": self.id, "task": self.task, "response_time_s": self.response_seconds()}


# ---------- Speaking: Take an Interview ----------
class InterviewItem(ItemBase):
    task: Literal["take-an-interview"] = "take-an-interview"
    question: str                      # spoken by the interviewer (TTS); shown only after answering
    response_time_s: int = 45          # approximation; confirm against official practice test

    def public(self, seed: str) -> dict:
        return {"id": self.id, "task": self.task, "response_time_s": self.response_time_s}


# ---------- Objective questions (Reading & Listening) ----------
class Question(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")
    prompt: str
    options: list[str] = Field(min_length=2, max_length=5)
    answer: int                                    # index into options
    explanation: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if not 0 <= self.answer < len(self.options):
            raise ValueError(f"question {self.id}: answer index out of range")
        if len(set(self.options)) != len(self.options):
            raise ValueError(f"question {self.id}: duplicate options")
        return self

    def order(self, seed: str) -> list[int]:
        """Deterministic option shuffle (removes authoring bias toward one answer position)."""
        idx = list(range(len(self.options)))
        random.Random(f"{seed}:{self.id}").shuffle(idx)
        return idx

    def public(self, seed: str) -> dict:
        return {"id": self.id, "prompt": self.prompt, "options": [self.options[i] for i in self.order(seed)]}


def _check_question_ids(item_id: str, qs: list[Question]) -> None:
    ids = [q.id for q in qs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{item_id}: duplicate question ids")


# ---------- Reading: Complete the Words (C-test) ----------
_GAP = re.compile(r"\[\[([A-Za-z'’\-]+)\]\]")


class CompleteWordsItem(ItemBase):
    """`text` marks each damaged word as [[word]]; the first half (len // 2 letters) stays visible."""
    task: Literal["complete-the-words"] = "complete-the-words"
    title: str | None = None
    text: str

    @model_validator(mode="after")
    def _check(self):
        gaps = self.gaps()
        if not gaps:
            raise ValueError(f"{self.id}: no [[word]] gaps in text")
        if any(len(w) < 2 for _, w in gaps):
            raise ValueError(f"{self.id}: gap words need at least 2 letters")
        return self

    def gaps(self) -> list[tuple[str, str]]:
        return [(f"g{i + 1}", m.group(1)) for i, m in enumerate(_GAP.finditer(self.text))]

    @staticmethod
    def split(word: str) -> tuple[str, str]:
        k = max(1, len(word) // 2)
        return word[:k], word[k:]

    def public(self, seed: str) -> dict:
        segs: list[dict] = []
        pos, i = 0, 0
        for m in _GAP.finditer(self.text):
            if m.start() > pos:
                segs.append({"type": "text", "text": self.text[pos:m.start()]})
            i += 1
            prefix, missing = self.split(m.group(1))
            segs.append({"type": "gap", "id": f"g{i}", "prefix": prefix, "length": len(missing)})
            pos = m.end()
        if pos < len(self.text):
            segs.append({"type": "text", "text": self.text[pos:]})
        return {"id": self.id, "task": self.task, "title": self.title, "segments": segs}


# ---------- Reading: Daily Life / Academic Passage ----------
class ReadingItem(ItemBase):
    task: Literal["read-daily-life", "read-academic-passage"]
    title: str | None = None
    genre: str | None = None          # e.g. "email", "notice", "menu" (daily life)
    text: str
    questions: list[Question] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self):
        _check_question_ids(self.id, self.questions)
        return self

    def public(self, seed: str) -> dict:
        return {"id": self.id, "task": self.task, "title": self.title, "genre": self.genre, "text": self.text,
                "questions": [q.public(f"{seed}:{self.id}") for q in self.questions]}


# ---------- Listening ----------
class Line(BaseModel):
    speaker: str
    voice: Literal["female", "male"] = "female"
    text: str


class ListeningItem(ItemBase):
    task: Literal["listen-choose-response", "listen-conversation", "listen-announcement", "listen-academic-talk"]
    context: str | None = None        # shown on screen, e.g. "Two students in the library"
    lines: list[Line] = Field(min_length=1)
    questions: list[Question] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self):
        _check_question_ids(self.id, self.questions)
        return self

    def transcript(self) -> list[dict]:
        return [l.model_dump() for l in self.lines]

    def public(self, seed: str) -> dict:
        # the script is NOT sent before answering; audio comes from /items/{id}/audio
        return {"id": self.id, "task": self.task, "context": self.context,
                "questions": [q.public(f"{seed}:{self.id}") for q in self.questions]}


Item = Annotated[Union[BuildSentenceItem, EmailItem, DiscussionItem, ListenRepeatItem, InterviewItem,
                       CompleteWordsItem, ReadingItem, ListeningItem],
                 Field(discriminator="task")]
TaskId = Literal["build-a-sentence", "write-an-email", "academic-discussion", "listen-and-repeat",
                 "take-an-interview", "complete-the-words", "read-daily-life", "read-academic-passage",
                 "listen-choose-response", "listen-conversation", "listen-announcement", "listen-academic-talk"]
OBJECTIVE_TASKS = {"complete-the-words", "read-daily-life", "read-academic-passage", "listen-choose-response",
                   "listen-conversation", "listen-announcement", "listen-academic-talk"}


class PracticeSet(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")
    task: TaskId
    title: str
    section: Literal["reading", "listening", "writing", "speaking"]
    time_limit_s: int = Field(gt=0)
    directions: str
    scene: str | None = None            # shared context shown on screen (e.g. who is speaking, where)
    items: list[Item] = Field(min_length=1)
    source: str = "original"
    review: dict | None = None          # generation/QA metadata for LLM-drafted sets

    @model_validator(mode="before")
    @classmethod
    def _inherit_task(cls, data):
        """Items may omit `task`; they inherit it from the set."""
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            data = {**data, "items": [{"task": data.get("task"), **i} if isinstance(i, dict) else i
                                      for i in data["items"]]}
        return data

    @model_validator(mode="after")
    def _check(self):
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: duplicate item ids")
        bad = [i.id for i in self.items if i.task != self.task]
        if bad:
            raise ValueError(f"{self.id}: items {bad} don't match set task {self.task}")
        return self

    def summary(self) -> dict:
        return {"id": self.id, "task": self.task, "title": self.title, "section": self.section,
                "time_limit_s": self.time_limit_s, "n_items": len(self.items)}

    def public(self) -> dict:
        return {**self.summary(), "directions": self.directions, "scene": self.scene,
                "items": [i.public(seed=self.id) for i in self.items]}


class SectionForm(BaseModel):
    """Multistage adaptive form: router module, then a lower or upper module."""
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")
    section: Literal["reading", "listening"]
    title: str
    directions: str
    router: list[str] = Field(min_length=1)
    lower: list[str] = Field(min_length=1)
    upper: list[str] = Field(min_length=1)
    upper_threshold: float = Field(default=0.6, gt=0, lt=1)


class MockWriting(BaseModel):
    build_sentence: str
    email: str
    discussion: str


class MockSpeaking(BaseModel):
    listen_repeat: str
    interview: str


class MockTest(BaseModel):
    """A full test: adaptive Reading + Listening forms, then Writing and Speaking sets (2026 order)."""
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")
    title: str
    description: str = ""
    reading: str
    listening: str
    writing: MockWriting
    speaking: MockSpeaking
