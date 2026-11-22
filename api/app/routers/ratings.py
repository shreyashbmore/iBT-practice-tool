"""Blind human rating of saved responses (for the calibration set) and export to eval/data/*.csv."""
from __future__ import annotations

import csv
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.config import ROOT_DIR
from app.content.bank import bank
from app.content.models import DiscussionItem, EmailItem, InterviewItem, ListenRepeatItem
from app.scoring.rubrics import LISTEN_REPEAT_BANDS, RUBRICS

router = APIRouter(prefix="/api/ratings", tags=["human rating"])

RATABLE = ("write-an-email", "academic-discussion", "take-an-interview", "listen-and-repeat")
EXPORT_DIR = ROOT_DIR / "eval" / "private" / "data"   # git-ignored: volunteer data stays local


def _item(r: dict):
    s = bank().get(r["set_id"])
    return next((i for i in s.items if i.id == r["item_id"]), None) if s else None


def _ratable(r: dict) -> bool:
    if r["task"] not in RATABLE or not r["item_id"] or not _item(r):
        return False
    if r["task"] in ("write-an-email", "academic-discussion"):
        return r["text"] is not None
    return "transcript" in r["payload"] or "audio_file" in r["payload"]


def _prompt(item) -> dict:
    if isinstance(item, EmailItem):
        return {"kind": "email", "scenario": item.scenario, "recipient": item.recipient, "points": item.points}
    if isinstance(item, DiscussionItem):
        return {"kind": "discussion", "course": item.course, "professor": item.professor.model_dump(),
                "students": [p.model_dump() for p in item.students]}
    if isinstance(item, InterviewItem):
        return {"kind": "interview", "question": item.question}
    return {"kind": "listen-repeat", "sentence": item.text}


def _rubric(task: str) -> dict:
    if task == "listen-and-repeat":
        return {"bands": {str(k): v for k, v in LISTEN_REPEAT_BANDS.items()}, "labels": {}}
    r = RUBRICS[task]
    return {"bands": {str(k): v for k, v in r.bands.items()}, "labels": {str(k): v for k, v in r.labels.items()},
            "dimensions": [d.model_dump() for d in r.dimensions]}


@router.get("/stats")
def stats() -> dict:
    ratings = db.ratings_by_response()
    out = {}
    for t in RATABLE:
        rs = [r for r in db.list_responses(t, limit=5000) if _ratable(r)]
        n = [len(ratings.get(r["id"], [])) for r in rs]
        out[t] = {"responses": len(rs), "unrated": n.count(0), "rated_once": n.count(1),
                  "rated_twice_or_more": sum(x >= 2 for x in n)}
    return out


@router.get("/next")
def next_item(task: str, rater: str) -> dict:
    """Next response this rater hasn't rated: single-rated ones first (to build double ratings), oldest first."""
    if task not in RATABLE:
        raise HTTPException(400, "Unknown task")
    rater = rater.strip()
    if not rater:
        raise HTTPException(400, "Rater name required")
    ratings = db.ratings_by_response()
    candidates = []
    for r in db.list_responses(task, limit=5000):
        if not _ratable(r):
            continue
        rs = ratings.get(r["id"], [])
        if any(x["rater"] == rater for x in rs) or len(rs) >= 2:
            continue
        candidates.append((0 if len(rs) == 1 else 1, r["created_at"], r))
    if not candidates:
        return {"done": True}
    _, _, r = sorted(candidates, key=lambda c: (c[0], c[1]))[0]
    item = _item(r)
    p = r["payload"]
    # NOTE: never include the machine score — rating must be blind
    return {
        "done": False, "remaining": len(candidates), "response_id": r["id"], "task": task,
        "prompt": _prompt(item), "rubric": _rubric(task),
        "text": r["text"] if task in ("write-an-email", "academic-discussion") else None,
        "transcript": (p.get("transcript") or {}).get("text") if task in ("take-an-interview", "listen-and-repeat") else None,
        "has_audio": "audio_file" in p,
    }


class RatingIn(BaseModel):
    response_id: str
    rater: str = Field(min_length=1, max_length=40)
    score: int = Field(ge=0, le=5)
    note: str | None = Field(default=None, max_length=500)


@router.post("")
def rate(body: RatingIn) -> dict:
    r = db.get_response(body.response_id)
    if not r or not _ratable(r):
        raise HTTPException(404, "Response not found or not ratable")
    db.save_rating(body.response_id, body.rater.strip(), body.score, body.note)
    return {"ok": True}


@router.post("/export")
def export() -> dict:
    ratings = db.ratings_by_response()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for t in RATABLE:
        rows = []
        for r in db.list_responses(t, limit=5000):
            rs = ratings.get(r["id"], [])
            if not rs or not _ratable(r):
                continue
            p = r["payload"]
            rows.append({
                "id": f"app-{r['id'][:12]}", "task": t, "item_id": r["item_id"],
                "response_text": r["text"] if t in ("write-an-email", "academic-discussion") else "",
                "audio_file": f"data/audio/{p['audio_file']}" if p.get("audio_file") else "",
                "transcript_json": json.dumps(p["transcript"]) if p.get("transcript") else "",
                "rater1": rs[0]["score"], "rater2": rs[1]["score"] if len(rs) > 1 else "",
                "source": "app", "notes": f"raters: {', '.join(x['rater'] for x in rs[:2])}",
            })
        path = EXPORT_DIR / f"app_{t}.csv"
        if rows:
            with path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda x: x["id"]))
        rel = path.relative_to(ROOT_DIR) if path.is_relative_to(ROOT_DIR) else path
        out[t] = {"rows": len(rows), "file": str(rel) if rows else None}
    return out
