"""Calibration dataset: CSV rows of (prompt item, response, human ratings).

Files: eval/data/*.csv and eval/private/data/*.csv (git-ignored, for ETS-derived material).
Columns:
  id              unique row id
  task            write-an-email | academic-discussion | take-an-interview | listen-and-repeat
  item_id         an item in content/items/ or eval/(private/)prompts/
  response_text   writing tasks
  audio_file      speaking tasks: path relative to the repo root (or absolute)
  transcript_json speaking tasks, optional: a Deepgram-style Transcript JSON (skips transcription)
  rater1, rater2  integer 0–5 (rater2 may be empty)
  source          ets-sample | volunteer | self | demo | app …
  notes           free text
"""
from __future__ import annotations

import csv
import json
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, field_validator

from app.config import ROOT_DIR
from app.content.bank import bank, load_dir
from app.content.models import DiscussionItem, EmailItem, InterviewItem, ListenRepeatItem, PracticeSet

from .metrics import consensus, summarize

EVAL_DIR = ROOT_DIR / "eval"
TASKS = ("write-an-email", "academic-discussion", "take-an-interview", "listen-and-repeat")
COLUMNS = ["id", "task", "item_id", "response_text", "audio_file", "transcript_json", "rater1", "rater2", "source",
           "notes"]


class EvalRow(BaseModel):
    id: str
    task: str
    item_id: str
    response_text: str | None = None
    audio_file: str | None = None
    transcript_json: str | None = None
    rater1: int | None = None
    rater2: int | None = None
    source: str = "unknown"
    notes: str | None = None
    file: str | None = None

    @field_validator("rater1", "rater2", mode="before")
    @classmethod
    def _int(cls, v):
        if v in (None, ""):
            return None
        v = int(float(v))
        if not 0 <= v <= 5:
            raise ValueError("ratings must be 0–5")
        return v

    @field_validator("response_text", "audio_file", "transcript_json", "notes", mode="before")
    @classmethod
    def _blank(cls, v):
        return None if v in (None, "") else v

    @property
    def gold(self) -> int | None:
        return consensus(self.rater1, self.rater2)

    def audio_path(self) -> Path | None:
        if not self.audio_file:
            return None
        p = Path(self.audio_file)
        return p if p.is_absolute() else ROOT_DIR / p


def data_files() -> list[Path]:
    return sorted([*(EVAL_DIR / "data").glob("*.csv"), *(EVAL_DIR / "private" / "data").glob("*.csv")])


@lru_cache
def prompt_sets() -> dict[str, PracticeSet]:
    sets = dict(bank())
    for d in (EVAL_DIR / "prompts", EVAL_DIR / "private" / "prompts"):
        if d.exists():
            sets.update(load_dir(d))
    return sets


def item_index() -> dict[str, tuple[PracticeSet, object]]:
    return {it.id: (s, it) for s in prompt_sets().values() for it in s.items}


ITEM_TYPES = {"write-an-email": EmailItem, "academic-discussion": DiscussionItem,
              "take-an-interview": InterviewItem, "listen-and-repeat": ListenRepeatItem}


def load_rows(task: str | None = None, sources: set[str] | None = None, exclude_sources: set[str] | None = None,
              files: list[Path] | None = None) -> list[EvalRow]:
    rows: list[EvalRow] = []
    errors: list[str] = []
    seen: set[str] = set()
    idx = item_index()
    for f in files or data_files():
        with f.open(newline="", encoding="utf-8") as fh:
            for n, raw in enumerate(csv.DictReader(fh), start=2):
                where = f"{f.name}:{n}"
                try:
                    r = EvalRow(**{k: raw.get(k) for k in COLUMNS}, file=f.name)
                except Exception as e:
                    errors.append(f"{where}: {e}")
                    continue
                if r.id in seen:
                    errors.append(f"{where}: duplicate id {r.id}")
                seen.add(r.id)
                if r.task not in TASKS:
                    errors.append(f"{where}: unknown task {r.task}")
                    continue
                if r.item_id not in idx or not isinstance(idx[r.item_id][1], ITEM_TYPES[r.task]):
                    errors.append(f"{where}: item '{r.item_id}' not found for {r.task}")
                    continue
                # writing: an empty response_text is allowed (a blank answer should score 0)
                if r.task in ("take-an-interview", "listen-and-repeat"):
                    if not r.transcript_json and not r.audio_file:
                        errors.append(f"{where}: audio_file or transcript_json is required for speaking tasks")
                    elif r.audio_file and not r.transcript_json and not r.audio_path().exists():
                        errors.append(f"{where}: audio file not found: {r.audio_file}")
                    if r.transcript_json:
                        try:
                            json.loads(r.transcript_json)
                        except json.JSONDecodeError:
                            errors.append(f"{where}: transcript_json is not valid JSON")
                if r.gold is None:
                    errors.append(f"{where}: at least rater1 is required")
                rows.append(r)
    if errors:
        raise ValueError("Invalid eval data:\n" + "\n".join(errors))
    if task:
        rows = [r for r in rows if r.task == task]
    if sources:
        rows = [r for r in rows if r.source in sources]
    if exclude_sources:
        rows = [r for r in rows if r.source not in exclude_sources]
    return rows


def human_agreement(rows: list[EvalRow]) -> dict | None:
    pairs = [(r.rater1, r.rater2) for r in rows if r.rater1 is not None and r.rater2 is not None]
    if len(pairs) < 2:
        return None
    return summarize([a for a, _ in pairs], [b for _, b in pairs], ci=len(pairs) >= 10)


def main() -> int:
    try:
        rows = load_rows()
    except ValueError as e:
        print(e)
        return 1
    if not rows:
        print("No eval data yet. See eval/README.md.")
        return 0
    for t in TASKS:
        rs = [r for r in rows if r.task == t]
        if not rs:
            continue
        by_src: dict[str, int] = {}
        for r in rs:
            by_src[r.source] = by_src.get(r.source, 0) + 1
        dist = [sum(r.gold == k for r in rs) for k in range(6)]
        hh = human_agreement(rs)
        print(f"{t}: {len(rs)} rows {by_src} · gold 0–5 distribution {dist} · double-rated "
              f"{sum(r.rater2 is not None for r in rs)}"
              + (f" · human–human QWK {hh['qwk']} exact {hh['exact']}" if hh else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
