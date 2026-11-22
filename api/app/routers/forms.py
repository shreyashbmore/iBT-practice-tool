"""Multistage adaptive section tests (Reading / Listening): router module → lower or upper module."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.content.bank import bank, forms
from app.content.models import SectionForm
from app.scoring.bands import SectionBand, adaptive_percent, section_band
from app.scoring.objective import ObjectiveResult, score_set

router = APIRouter(prefix="/api/forms", tags=["section tests"])

Stage = Literal["router", "lower", "upper"]


def _form(fid: str) -> SectionForm:
    f = forms().get(fid)
    if not f:
        raise HTTPException(404, f"Unknown form '{fid}'")
    return f


def _module(form: SectionForm, stage: Stage) -> dict:
    sets = [bank()[sid] for sid in getattr(form, stage)]
    return {"stage": stage, "time_limit_s": sum(s.time_limit_s for s in sets), "sets": [s.public() for s in sets]}


def _n_questions(sids: list[str]) -> int:
    return sum(score_set(bank()[sid], {}).max_score for sid in sids)


@router.get("")
def list_forms() -> list[dict]:
    return [{"id": f.id, "section": f.section, "title": f.title,
             "router_questions": _n_questions(f.router),
             "est_minutes": round((sum(bank()[s].time_limit_s for s in f.router)
                                   + max(sum(bank()[s].time_limit_s for s in f.lower),
                                         sum(bank()[s].time_limit_s for s in f.upper))) / 60)}
            for f in forms().values()]


@router.post("/{fid}/start")
def start(fid: str) -> dict:
    form = _form(fid)
    aid = db.create_form_attempt(form.id)
    return {"attempt_id": aid, "form": {"id": form.id, "title": form.title, "section": form.section,
                                        "directions": form.directions}, "module": _module(form, "router")}


class StageSubmit(BaseModel):
    stage: Stage
    answers: dict[str, dict[str, dict[str, int | str | None]]]   # set_id → item_id → {qid → answer}
    time_spent_s: float | None = Field(default=None, ge=0)


class StageResult(BaseModel):
    stage: Stage
    score: int
    max_score: int
    sets: list[ObjectiveResult]


class FinalResult(BaseModel):
    response_id: str
    route: Literal["lower", "upper"]
    score: int
    max_score: int
    percent: float
    stages: list[StageResult]
    band: SectionBand | None = None


def _score_stage(form: SectionForm, stage: Stage, answers: dict) -> StageResult:
    res = [score_set(bank()[sid], answers.get(sid, {})) for sid in getattr(form, stage)]
    return StageResult(stage=stage, score=sum(r.score for r in res), max_score=sum(r.max_score for r in res), sets=res)


@router.post("/{fid}/attempts/{aid}/submit")
def submit(fid: str, aid: str, body: StageSubmit) -> dict:
    form = _form(fid)
    att = db.get_form_attempt(aid)
    if not att or att["form_id"] != fid:
        raise HTTPException(404, "Unknown attempt")
    expected = att["stage"]
    if expected == "done":
        raise HTTPException(409, "This attempt is already finished")
    if body.stage != expected:
        raise HTTPException(409, f"Expected stage '{expected}', got '{body.stage}'")

    result = _score_stage(form, body.stage, body.answers)
    results = {**att["results"], body.stage: {**result.model_dump(), "time_spent_s": body.time_spent_s}}

    if body.stage == "router":
        pct = result.score / result.max_score if result.max_score else 0
        route = "upper" if pct >= form.upper_threshold else "lower"
        db.update_form_attempt(aid, route, route, results)
        return {"stage_result": {"stage": "router", "score": result.score, "max_score": result.max_score},
                "next": _module(form, route)}

    route = body.stage
    stages = [StageResult(**{k: v for k, v in results["router"].items() if k != "time_spent_s"}), result]
    score, max_score = sum(s.score for s in stages), sum(s.max_score for s in stages)
    pct = adaptive_percent(stages[0].score, stages[0].max_score, stages[1].score, stages[1].max_score, route)
    band = section_band(form.section, score, max_score, pct=pct)
    rid = db.insert_response(
        set_id=form.id, item_id=None, task=f"{form.section}-test", section=form.section, text=None,
        payload={"attempt_id": aid, "route": route},
        time_spent_s=sum((results[s].get("time_spent_s") or 0) for s in ("router", route)),
        timed_out=0, score=score, max_score=max_score,
        score_json={"route": route, "stages": [s.model_dump() for s in stages], "band": band.model_dump()},
    )
    db.update_form_attempt(aid, "done", route, results)
    final = FinalResult(response_id=rid, route=route, score=score, max_score=max_score,
                        percent=round(score / max_score * 100, 1) if max_score else 0.0, stages=stages, band=band)
    return {"final": final.model_dump()}
