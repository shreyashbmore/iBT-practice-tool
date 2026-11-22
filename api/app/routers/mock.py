"""Full mock test: Reading → Listening → Writing → Speaking, then estimated bands for every section."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db
from app.content.bank import bank, forms, mocks
from app.content.models import MockTest
from app.scoring.bands import SECTIONS, OverallBand, adaptive_percent, overall, section_band

from .practice import score_rubric

router = APIRouter(prefix="/api/mocks", tags=["mock test"])


def _mock(mid: str) -> MockTest:
    m = mocks().get(mid)
    if not m:
        raise HTTPException(404, f"Unknown mock test '{mid}'")
    return m


def _attempt(aid: str) -> tuple[dict, MockTest]:
    a = db.get_mock_attempt(aid)
    if not a:
        raise HTTPException(404, "Unknown attempt")
    return a, _mock(a["mock_id"])


def _next_section(a: dict) -> str | None:
    return next((s for s in SECTIONS if s not in a["sections"]), None)


def _plan(m: MockTest) -> dict:
    return {
        "id": m.id, "title": m.title, "description": m.description, "sections": list(SECTIONS),
        "reading": m.reading, "listening": m.listening,
        "writing": m.writing.model_dump(), "speaking": m.speaking.model_dump(),
    }


@router.get("")
def list_mocks() -> list[dict]:
    return [_plan(m) for m in mocks().values()]


@router.get("/attempts")
def attempts() -> list[dict]:
    return db.list_mock_attempts()


@router.post("/{mid}/start")
def start(mid: str) -> dict:
    m = _mock(mid)
    aid = db.create_mock_attempt(m.id)
    return {"attempt_id": aid, "plan": _plan(m), "next_section": SECTIONS[0]}


@router.get("/attempts/{aid}")
def get_attempt(aid: str) -> dict:
    a, m = _attempt(aid)
    return {**a, "plan": _plan(m), "next_section": _next_section(a)}


class SectionIn(BaseModel):
    response_ids: list[str]


def _allowed_sets(m: MockTest, section: str) -> set[str]:
    if section in ("reading", "listening"):
        return {getattr(m, section)}
    return set(getattr(m, section).model_dump().values())


@router.post("/attempts/{aid}/sections/{section}")
def record_section(aid: str, section: str, body: SectionIn) -> dict:
    a, m = _attempt(aid)
    if a["status"] == "done":
        raise HTTPException(409, "This mock test is already finished")
    expected = _next_section(a)
    if section != expected:
        raise HTTPException(409, f"Expected section '{expected}', got '{section}'")
    allowed = _allowed_sets(m, section)
    for rid in body.response_ids:
        r = db.get_response(rid)
        if not r or r["set_id"] not in allowed:
            raise HTTPException(400, f"Response {rid} does not belong to the {section} section of this test")
    if section in ("reading", "listening") and len(body.response_ids) != 1:
        raise HTTPException(400, f"{section} needs exactly one section-test response")
    sections = {**a["sections"], section: {"response_ids": body.response_ids}}
    db.update_mock_attempt(aid, sections)
    return {"next_section": _next_section({**a, "sections": sections})}


def _adaptive_band(section: str, rid: str):
    r = db.get_response(rid)
    sj = r["score_json"] or {}
    st = sj.get("stages", [])
    if len(st) != 2:
        return section_band(section, 0, 1)
    pct = adaptive_percent(st[0]["score"], st[0]["max_score"], st[1]["score"], st[1]["max_score"], sj.get("route", "lower"))
    return section_band(section, r["score"] or 0, r["max_score"] or 1, pct=pct)


@router.post("/attempts/{aid}/finish", response_model=OverallBand)
async def finish(aid: str) -> OverallBand:
    a, m = _attempt(aid)
    if a["status"] == "done" and a["result"]:
        return OverallBand(**a["result"])
    missing = [s for s in SECTIONS if s not in a["sections"]]
    if missing:
        raise HTTPException(409, f"Sections not completed yet: {', '.join(missing)}")

    responses = {s: [db.get_response(r) for r in a["sections"][s]["response_ids"]] for s in ("writing", "speaking")}
    # LLM-score any rubric response that hasn't been scored yet (feedback is hidden during the mock)
    to_score = [r["id"] for s in responses.values() for r in s
                if r and r["task"] in ("write-an-email", "academic-discussion", "take-an-interview")
                and r["score"] is None and (r["task"] != "take-an-interview" or "transcript" in r["payload"])]
    for rid in to_score:   # sequential: kinder to provider rate limits
        await score_rubric(rid)
    responses = {s: [db.get_response(r) for r in a["sections"][s]["response_ids"]] for s in ("writing", "speaking")}

    out = {"reading": _adaptive_band("reading", a["sections"]["reading"]["response_ids"][0]),
           "listening": _adaptive_band("listening", a["sections"]["listening"]["response_ids"][0])}

    # Writing: 10 × Build a Sentence (1) + Email (5) + Discussion (5) = 20
    w = {r["task"]: r for r in responses["writing"] if r}
    bas_max = len(bank()[m.writing.build_sentence].items)
    w_raw = sum((w.get(t) or {}).get("score") or 0 for t in ("build-a-sentence", "write-an-email", "academic-discussion"))
    out["writing"] = section_band("writing", w_raw, bas_max + 10)

    # Speaking: every item 0–5; unanswered / untranscribed items count 0
    lr, iv = bank()[m.speaking.listen_repeat], bank()[m.speaking.interview]
    best: dict[str, float] = {}
    for r in responses["speaking"]:
        if r and r["item_id"]:
            best[r["item_id"]] = max(best.get(r["item_id"], 0), r["score"] or 0)
    s_max = 5 * (len(lr.items) + len(iv.items))
    out["speaking"] = section_band("speaking", sum(best.values()), s_max)

    result = overall(out)
    db.update_mock_attempt(aid, a["sections"], status="done", result=result.model_dump())
    db.insert_response(set_id=m.id, item_id=None, task="mock-test", section="all", text=None,
                       payload={"attempt_id": aid}, time_spent_s=None, timed_out=0,
                       score=result.band, max_score=6, score_json=result.model_dump())
    return result
