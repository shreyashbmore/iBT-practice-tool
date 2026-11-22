"""Aggregated history for the progress dashboard."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from app import db

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("")
def progress() -> dict:
    rows = [r for r in db.list_responses(limit=2000) if r["score"] is not None and r["max_score"]]
    by_task: dict[str, list[dict]] = defaultdict(list)
    for r in reversed(rows):   # oldest first
        if r["task"] == "mock-test":
            continue
        by_task[r["task"]].append({"id": r["id"], "date": r["created_at"], "score": r["score"],
                                   "max": r["max_score"], "pct": round(r["score"] / r["max_score"] * 100, 1)})
    tasks = {t: {"attempts": len(v), "last_pct": v[-1]["pct"], "best_pct": max(p["pct"] for p in v),
                 "avg_pct": round(sum(p["pct"] for p in v) / len(v), 1), "history": v[-30:]}
             for t, v in by_task.items()}
    mocks = [{"id": m["id"], "date": m["created_at"], "mock_id": m["mock_id"], "band": m["result"]["band"],
              "cefr": m["result"]["cefr"], "comparable_total": m["result"]["comparable_total"],
              "sections": {s: v["band"] for s, v in m["result"]["sections"].items()}}
             for m in reversed(db.list_mock_attempts(200)) if m["status"] == "done" and m["result"]]
    return {"tasks": tasks, "mocks": mocks}
