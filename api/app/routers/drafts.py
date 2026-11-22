"""Content generation & review. Local-only admin endpoints (the API binds to 127.0.0.1)."""
from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from app.content import bank as bank_mod
from app.content.generator import SPECS, draft_path, generate, list_drafts, save_draft
from app.content.models import CEFR, PracticeSet
from app.providers.llm.base import LLMError
from app.providers.llm.factory import get_llm
from app.user_settings import load as load_prefs

router = APIRouter(prefix="/api/drafts", tags=["content review"])


@router.get("/tasks")
def tasks() -> list[dict]:
    return [{"task": s.task, "label": s.label, "section": s.section, "count": s.count, "guidance": s.guidance}
            for s in SPECS.values()]


class GenerateIn(BaseModel):
    task: str
    cefr: CEFR = "B1"
    topic: str | None = None


def _summary(s: PracticeSet) -> dict:
    return {**s.summary(), "review": s.review}


@router.post("/generate")
async def gen(body: GenerateIn) -> dict:
    if body.task not in SPECS:
        raise HTTPException(400, f"Generation not supported for '{body.task}'")
    try:
        llm = get_llm()
    except LLMError as e:
        raise HTTPException(400, f"{e}. Add a key in Settings.") from e
    try:
        s = await generate(llm, body.task, body.cefr, (body.topic or "").strip() or None, load_prefs().llm.model)
    except LLMError as e:
        raise HTTPException(502, f"Generation failed: {e}") from e
    except ValidationError as e:
        raise HTTPException(422, f"The model produced an invalid item: {e.errors()[0].get('msg')}") from e
    save_draft(s)
    return s.model_dump(exclude_none=True)


@router.get("")
def drafts() -> list[dict]:
    return [_summary(s) for s in list_drafts()]


@router.get("/{did}")
def draft(did: str) -> dict:
    p = draft_path(did)
    if not p:
        raise HTTPException(404, "Draft not found")
    return yaml.safe_load(p.read_text())


@router.post("/{did}/approve")
def approve(did: str) -> dict:
    p = draft_path(did)
    if not p:
        raise HTTPException(404, "Draft not found")
    s = PracticeSet.model_validate(yaml.safe_load(p.read_text()))
    s.review = {**(s.review or {}), "status": "approved"}
    dest_dir = bank_mod.ITEMS_DIR / s.section / "generated"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{s.id}.yaml"
    dest.write_text(yaml.safe_dump(s.model_dump(exclude_none=True), sort_keys=False, allow_unicode=True, width=110))
    try:
        bank_mod.reload()
    except bank_mod.ContentError as e:
        dest.unlink(missing_ok=True)
        bank_mod.reload()
        raise HTTPException(422, str(e)) from e
    p.unlink()
    return {"approved": s.id, "path": str(dest.relative_to(bank_mod.ITEMS_DIR.parent.parent))}


@router.delete("/{did}")
def discard(did: str) -> dict:
    p = draft_path(did)
    if not p:
        raise HTTPException(404, "Draft not found")
    p.unlink()
    return {"discarded": did}
