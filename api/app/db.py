"""Tiny SQLite layer (stdlib). One row per submitted response; scores are filled in by scorers."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
  id           TEXT PRIMARY KEY,
  created_at   TEXT NOT NULL,
  set_id       TEXT NOT NULL,
  item_id      TEXT,              -- NULL for whole-set responses (e.g. a Build a Sentence set)
  task         TEXT NOT NULL,
  section      TEXT NOT NULL,
  text         TEXT,
  payload      TEXT NOT NULL DEFAULT '{}',   -- task-specific JSON (answers, features, …)
  time_spent_s REAL,
  timed_out    INTEGER NOT NULL DEFAULT 0,
  score        REAL,
  max_score    REAL,
  score_json   TEXT                           -- scorer output (rubric dimensions, feedback)
);
CREATE INDEX IF NOT EXISTS ix_responses_task ON responses(task, created_at);
CREATE TABLE IF NOT EXISTS form_attempts (
  id          TEXT PRIMARY KEY,
  created_at  TEXT NOT NULL,
  form_id     TEXT NOT NULL,
  stage       TEXT NOT NULL,            -- router | lower | upper | done
  route       TEXT,                     -- lower | upper
  results     TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS mock_attempts (
  id          TEXT PRIMARY KEY,
  created_at  TEXT NOT NULL,
  mock_id     TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'in_progress',   -- in_progress | done
  sections    TEXT NOT NULL DEFAULT '{}',            -- section → {"response_ids": [...]}
  result      TEXT                                   -- OverallBand JSON when done
);
CREATE TABLE IF NOT EXISTS ratings (
  response_id TEXT NOT NULL,
  rater       TEXT NOT NULL,
  score       INTEGER NOT NULL,
  note        TEXT,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (response_id, rater)
);
"""


@contextmanager
def connect():
    path = get_settings().data_dir / "practice.db"
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def insert_response(**fields: Any) -> str:
    rid = uuid.uuid4().hex
    row = {
        "id": rid,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "payload": json.dumps(fields.pop("payload", {})),
        "score_json": json.dumps(fields["score_json"]) if fields.get("score_json") is not None else None,
        **{k: v for k, v in fields.items() if k != "score_json"},
    }
    cols = ", ".join(row)
    with connect() as con:
        con.execute(f"INSERT INTO responses ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
    return rid


def _decode(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["payload"] = json.loads(d["payload"] or "{}")
    d["score_json"] = json.loads(d["score_json"]) if d["score_json"] else None
    d["timed_out"] = bool(d["timed_out"])
    return d


def get_response(rid: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM responses WHERE id = ?", (rid,)).fetchone()
    return _decode(r) if r else None


def list_responses(task: str | None = None, limit: int = 50) -> list[dict]:
    q, args = "SELECT * FROM responses", []
    if task:
        q += " WHERE task = ?"
        args.append(task)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with connect() as con:
        return [_decode(r) for r in con.execute(q, args).fetchall()]


def update_payload(rid: str, payload: dict, text: str | None = None) -> None:
    with connect() as con:
        if text is None:
            con.execute("UPDATE responses SET payload = ? WHERE id = ?", (json.dumps(payload), rid))
        else:
            con.execute("UPDATE responses SET payload = ?, text = ? WHERE id = ?", (json.dumps(payload), text, rid))


def update_score(rid: str, score: float | None, max_score: float | None, score_json: dict | None) -> None:
    with connect() as con:
        con.execute("UPDATE responses SET score = ?, max_score = ?, score_json = ? WHERE id = ?",
                    (score, max_score, json.dumps(score_json) if score_json is not None else None, rid))


def create_form_attempt(form_id: str) -> str:
    aid = uuid.uuid4().hex
    with connect() as con:
        con.execute("INSERT INTO form_attempts (id, created_at, form_id, stage) VALUES (?, ?, ?, 'router')",
                    (aid, datetime.now(timezone.utc).isoformat(timespec="seconds"), form_id))
    return aid


def get_form_attempt(aid: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM form_attempts WHERE id = ?", (aid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["results"] = json.loads(d["results"] or "{}")
    return d


def update_form_attempt(aid: str, stage: str, route: str | None, results: dict) -> None:
    with connect() as con:
        con.execute("UPDATE form_attempts SET stage = ?, route = ?, results = ? WHERE id = ?",
                    (stage, route, json.dumps(results), aid))


def create_mock_attempt(mock_id: str) -> str:
    aid = uuid.uuid4().hex
    with connect() as con:
        con.execute("INSERT INTO mock_attempts (id, created_at, mock_id) VALUES (?, ?, ?)",
                    (aid, datetime.now(timezone.utc).isoformat(timespec="seconds"), mock_id))
    return aid


def _mock_row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["sections"] = json.loads(d["sections"] or "{}")
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def get_mock_attempt(aid: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM mock_attempts WHERE id = ?", (aid,)).fetchone()
    return _mock_row(r) if r else None


def list_mock_attempts(limit: int = 50) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT * FROM mock_attempts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_mock_row(r) for r in rows]


def update_mock_attempt(aid: str, sections: dict, status: str = "in_progress", result: dict | None = None) -> None:
    with connect() as con:
        con.execute("UPDATE mock_attempts SET sections = ?, status = ?, result = ? WHERE id = ?",
                    (json.dumps(sections), status, json.dumps(result) if result is not None else None, aid))


def save_rating(response_id: str, rater: str, score: int, note: str | None) -> None:
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO ratings (response_id, rater, score, note, created_at) VALUES (?, ?, ?, ?, ?)",
                    (response_id, rater, score, note, datetime.now(timezone.utc).isoformat(timespec="seconds")))


def ratings_by_response() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    with connect() as con:
        for r in con.execute("SELECT * FROM ratings ORDER BY created_at"):
            out.setdefault(r["response_id"], []).append(dict(r))
    return out
