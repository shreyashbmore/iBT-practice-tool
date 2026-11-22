"""LLM content generation → validation → automatic QA → human review (drafts) → approve into the bank.

Drafts live in content/drafts/ and are never served for practice until approved.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, create_model

from app.config import ROOT_DIR
from app.providers.llm.base import LLMProvider, Usage

from .models import (BuildSentenceItem, CompleteWordsItem, DiscussionItem, EmailItem, InterviewItem, ListeningItem,
                     ListenRepeatItem, PracticeSet, ReadingItem)

DRAFTS_DIR = ROOT_DIR / "content" / "drafts"


class TaskSpec(BaseModel):
    task: str
    label: str
    section: str
    cls: Any
    count: int = 1                 # items per generated set
    time_limit_s: int
    directions: str
    guidance: str
    has_scene: bool = False


SPECS: dict[str, TaskSpec] = {s.task: s for s in [
    TaskSpec(task="complete-the-words", label="Complete the Words", section="reading", cls=CompleteWordsItem,
             time_limit_s=180, directions="Fill in the missing letters to complete the words in the paragraph.",
             guidance="One paragraph of 70–110 words. Keep the first sentence intact. Then mark exactly 10 words as "
                      "[[word]] — roughly every second word in the following sentences. Only words of 2+ letters; "
                      "no proper nouns, numbers or hyphenated words."),
    TaskSpec(task="read-daily-life", label="Read in Daily Life", section="reading", cls=ReadingItem,
             time_limit_s=240, directions="Read the text and answer the questions.",
             guidance="A realistic everyday text (email, notice, schedule, advertisement, text-message chain or menu) "
                      "of 80–150 words, with genre set. 3 multiple-choice questions, 4 options each, exactly one "
                      "correct; plausible distractors; short explanation citing the text."),
    TaskSpec(task="read-academic-passage", label="Read an Academic Passage", section="reading", cls=ReadingItem,
             time_limit_s=420, directions="Read the passage and answer the questions.",
             guidance="An introductory university-level passage of 180–260 words in 2 paragraphs, with a title. "
                      "5 questions, 4 options each: main idea, factual detail, vocabulary or reference, "
                      "NOT/EXCEPT, inference. Exactly one correct answer each; explanation citing the passage."),
    TaskSpec(task="listen-choose-response", label="Listen and Choose a Response", section="listening",
             cls=ListeningItem, count=4, time_limit_s=150,
             directions="You will hear a person speak. Choose the best response. You will hear each one only once.",
             guidance="Each item: ONE spoken line (question or statement, 6–16 words) in a campus or everyday "
                      "situation, with speaker and voice. One question with prompt 'Choose the best response.' and "
                      "4 reply options: one natural correct reply; distractors use repeated-word traps, wrong tense "
                      "or irrelevant content."),
    TaskSpec(task="listen-conversation", label="Listen to a Conversation", section="listening", cls=ListeningItem,
             time_limit_s=240,
             directions="Listen to the conversation. Then answer the questions. You will hear it only once.",
             guidance="A natural conversation of 120–220 words between 2 speakers (e.g. student and staff member), "
                      "6–10 turns, one voice per speaker (female/male), with a short context line. 4 questions, "
                      "4 options: purpose, two details, one inference."),
    TaskSpec(task="listen-announcement", label="Listen to an Announcement", section="listening", cls=ListeningItem,
             time_limit_s=180,
             directions="Listen to the announcement. Then answer the questions. You will hear it only once.",
             guidance="One speaker, a campus or public announcement of 70–130 words in one line, with context. "
                      "3–4 questions, 4 options: main purpose, details, an implication."),
    TaskSpec(task="listen-academic-talk", label="Listen to an Academic Talk", section="listening", cls=ListeningItem,
             time_limit_s=240,
             directions="Listen to part of a lecture. Then answer the questions. You will hear it only once.",
             guidance="A professor's mini-lecture of 180–260 words split into 2–4 lines (paragraphs), single "
                      "speaker and voice, with context naming the class. 4 questions, 4 options: main idea, detail, "
                      "'why does the professor mention…', inference."),
    TaskSpec(task="write-an-email", label="Write an Email", section="writing", cls=EmailItem, time_limit_s=420,
             directions="Read the situation and write an email. You have 7 minutes. Address all of the points below.",
             guidance="A realistic situation (40–80 words) requiring an email to a named recipient, a subject line, "
                      "and exactly 3 points to address (e.g. explain, suggest, ask)."),
    TaskSpec(task="academic-discussion", label="Academic Discussion", section="writing", cls=DiscussionItem,
             time_limit_s=600,
             directions="Your professor is teaching a class. Write a post responding to the professor's question. "
                        "Express and support your opinion. An effective response contains at least 100 words. "
                        "You have 10 minutes.",
             guidance="A course name; a professor post of 60–90 words ending with an open question; two student "
                      "posts of 40–60 words each taking different positions with one reason each."),
    TaskSpec(task="take-an-interview", label="Take an Interview", section="speaking", cls=InterviewItem, count=4,
             time_limit_s=300, has_scene=True,
             directions="The interviewer will ask you four questions. Answer each one right after the beep. "
                        "You have about 45 seconds per answer. There is no preparation time.",
             guidance="A scene (who is interviewing and why). 4 spoken questions on that theme, getting harder: "
                      "personal experience → preference with reasons → past event → opinion on an abstract issue."),
    TaskSpec(task="listen-and-repeat", label="Listen and Repeat", section="speaking", cls=ListenRepeatItem, count=7,
             time_limit_s=300, has_scene=True,
             directions="You will hear a speaker say a sentence. After the beep, repeat exactly what you heard.",
             guidance="A scene (a campus setting and who is speaking). 7 sentences a person in that scene would say, "
                      "increasing in length from about 4 to 18 words and in grammatical complexity."),
]}


class Solved(BaseModel):
    id: str
    choice: int


class SolverOut(BaseModel):
    answers: list[Solved]


def _gen_item_model(cls):
    skip = {"id", "task", "tags", "response_time_s"}
    fields = {n: (f.annotation, f) for n, f in cls.model_fields.items() if n not in skip}
    return create_model(f"{cls.__name__}Gen", **fields)


def _gen_set_model(spec: TaskSpec):
    item = _gen_item_model(spec.cls)
    fields: dict[str, Any] = {
        "title": (str, Field(description="Short title, 2–6 words")),
        "items": (list[item], Field(min_length=spec.count, max_length=spec.count)),
    }
    if spec.has_scene:
        fields["scene"] = (str, Field(description="One sentence shown on screen describing the situation"))
    return create_model(f"{spec.cls.__name__}SetGen", **fields)


SYSTEM = """You write ORIGINAL practice material for an English proficiency test that follows the 2026 TOEFL iBT task
formats. Never reproduce or paraphrase official ETS test items. Content must be factually accurate, culturally
neutral, and appropriate for adult learners. Each multiple-choice question must have exactly one defensible answer;
`answer` is the 0-based index of the correct option. Use stable lowercase ids for questions (q1, q2, …)."""


def _add(total: Usage, u: Usage) -> None:
    total.prompt_tokens += u.prompt_tokens
    total.completion_tokens += u.completion_tokens
    if u.cost_usd is not None:
        total.cost_usd = (total.cost_usd or 0) + u.cost_usd


async def generate(llm: LLMProvider, task: str, cefr: str, topic: str | None, model_name: str | None = None
                   ) -> PracticeSet:
    spec = SPECS[task]
    schema = _gen_set_model(spec)
    user = (f"TASK TYPE: {spec.label}\nTARGET CEFR LEVEL: {cefr}\nTOPIC: {topic or 'your choice (campus or academic)'}\n"
            f"REQUIREMENTS: {spec.guidance}\nWrite {spec.count} item(s).")
    total = Usage()
    out, u = await llm.complete_json([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                                     schema, temperature=0.8, max_tokens=4000)
    _add(total, u)
    data = out.model_dump()
    sid = f"gen-{task}-{uuid.uuid4().hex[:6]}"
    items = [{**it, "id": f"{sid}-{i + 1}", "task": task, "cefr": it.get("cefr") or cefr}
             for i, it in enumerate(data["items"])]
    raw = {"id": sid, "task": task, "section": spec.section, "title": f"{spec.label} · {data['title']}",
           "time_limit_s": spec.time_limit_s, "directions": spec.directions, "scene": data.get("scene"),
           "items": items, "source": "generated"}
    s = PracticeSet.model_validate(raw)          # runs all item validators
    qa = await quality_check(llm, s, total)
    s.review = {"status": "draft", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": model_name, "cefr": cefr, "topic": topic, "qa": qa,
                "usage": total.model_dump()}
    return s


async def quality_check(llm: LLMProvider, s: PracticeSet, total: Usage) -> dict:
    """Independent re-solve of every multiple-choice question without the key; disagreements are flagged."""
    warnings: list[str] = []
    checked = agreed = 0
    mismatches: list[str] = []
    for it in s.items:
        qs = getattr(it, "questions", None)
        if isinstance(it, CompleteWordsItem) and len(it.gaps()) < 8:
            warnings.append(f"{it.id}: only {len(it.gaps())} gaps")
        if not qs:
            continue
        material = it.text if isinstance(it, ReadingItem) else "\n".join(f"{l.speaker}: {l.text}" for l in it.lines)
        listing = "\n\n".join(f"[{q.id}] {q.prompt}\n" + "\n".join(f"  {k}. {o}" for k, o in enumerate(q.options))
                              for q in qs)
        try:
            solved, u = await llm.complete_json(
                [{"role": "system", "content": "You are a careful test taker. Answer each question using only the "
                                               "material. Give the 0-based option index."},
                 {"role": "user", "content": f"MATERIAL:\n{material}\n\nQUESTIONS:\n{listing}"}],
                SolverOut, temperature=0.0, max_tokens=800)
        except Exception as e:  # QA must never block a draft
            warnings.append(f"{it.id}: solver check failed ({e})")
            continue
        _add(total, u)
        got = {a.id: a.choice for a in solved.answers}
        for q in qs:
            checked += 1
            if got.get(q.id) == q.answer:
                agreed += 1
            else:
                mismatches.append(f"{it.id}/{q.id}")
    return {"questions_checked": checked, "solver_agreed": agreed, "mismatches": mismatches, "warnings": warnings}


# ---------- draft storage ----------
def _dump(s: PracticeSet) -> str:
    return yaml.safe_dump(s.model_dump(exclude_none=True), sort_keys=False, allow_unicode=True, width=110)


def save_draft(s: PracticeSet) -> None:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    (DRAFTS_DIR / f"{s.id}.yaml").write_text(_dump(s))


def list_drafts() -> list[PracticeSet]:
    if not DRAFTS_DIR.exists():
        return []
    out = []
    for f in sorted(DRAFTS_DIR.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append(PracticeSet.model_validate(yaml.safe_load(f.read_text())))
        except ValidationError:
            continue
    return out


def draft_path(did: str):
    p = DRAFTS_DIR / f"{did}.yaml"
    if not p.resolve().is_relative_to(DRAFTS_DIR.resolve()) or not p.exists():
        return None
    return p
