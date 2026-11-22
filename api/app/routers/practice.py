from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.content.bank import bank
from app.content.models import BuildSentenceItem, DiscussionItem, EmailItem, InterviewItem, PracticeSet
from app.features.speech import SpeechFeatures
from app.providers.speech.base import Transcript
from app.scoring import speaking_judge
from app.content.models import OBJECTIVE_TASKS
from app.scoring.objective import ObjectiveResult, score_set
from app.features.text import TextFeatures
from app.features.text import compute as text_features
from app.providers.llm.base import LLMError
from app.providers.llm.factory import get_llm
from app.scoring.build_sentence import BuildSentenceResult, score_item
from app.scoring.writing_judge import WritingScore, judge
from app.user_settings import load as load_prefs

router = APIRouter(prefix="/api", tags=["practice"])


def _set(set_id: str) -> PracticeSet:
    s = bank().get(set_id)
    if not s:
        raise HTTPException(404, f"Unknown set '{set_id}'")
    return s


@router.get("/sets")
def list_sets(task: str | None = None, section: str | None = None) -> list[dict]:
    return [s.summary() for s in bank().values()
            if (task is None or s.task == task) and (section is None or s.section == section)]


@router.get("/sets/{set_id}")
def get_set(set_id: str) -> dict:
    return _set(set_id).public()


# ---------- Build a Sentence ----------
class BuildSubmit(BaseModel):
    answers: dict[str, list[str]]          # item_id → chunks in slot order
    time_spent_s: float | None = Field(default=None, ge=0)
    timed_out: bool = False


class BuildOut(BaseModel):
    response_id: str
    score: int
    max_score: int
    results: list[BuildSentenceResult]


@router.post("/sets/{set_id}/build-a-sentence/submit", response_model=BuildOut)
def submit_build(set_id: str, body: BuildSubmit) -> BuildOut:
    s = _set(set_id)
    if s.task != "build-a-sentence":
        raise HTTPException(400, "Not a Build a Sentence set")
    unknown = set(body.answers) - {i.id for i in s.items}
    if unknown:
        raise HTTPException(400, f"Unknown item ids: {sorted(unknown)}")
    results = [score_item(i, body.answers.get(i.id)) for i in s.items if isinstance(i, BuildSentenceItem)]
    score = sum(r.correct for r in results)
    rid = db.insert_response(
        set_id=s.id, item_id=None, task=s.task, section=s.section, text=None,
        payload={"answers": body.answers}, time_spent_s=body.time_spent_s, timed_out=int(body.timed_out),
        score=score, max_score=len(results), score_json={"results": [r.model_dump() for r in results]},
    )
    return BuildOut(response_id=rid, score=score, max_score=len(results), results=results)


# ---------- Reading & Listening (objective) ----------
class ObjectiveSubmit(BaseModel):
    answers: dict[str, dict[str, int | str | None]]   # item_id → {question/gap id → option index or text}
    time_spent_s: float | None = Field(default=None, ge=0)
    timed_out: bool = False


class ObjectiveOut(ObjectiveResult):
    response_id: str


@router.post("/sets/{set_id}/objective/submit", response_model=ObjectiveOut)
def submit_objective(set_id: str, body: ObjectiveSubmit) -> ObjectiveOut:
    s = _set(set_id)
    if s.task not in OBJECTIVE_TASKS:
        raise HTTPException(400, "Not a Reading/Listening set")
    res = score_set(s, body.answers)
    rid = db.insert_response(
        set_id=s.id, item_id=None, task=s.task, section=s.section, text=None,
        payload={"answers": body.answers}, time_spent_s=body.time_spent_s, timed_out=int(body.timed_out),
        score=res.score, max_score=res.max_score, score_json=res.model_dump(),
    )
    return ObjectiveOut(response_id=rid, **res.model_dump())


# ---------- Email / Academic Discussion ----------
class TextSubmit(BaseModel):
    item_id: str
    text: str = Field(max_length=10000)
    time_spent_s: float | None = Field(default=None, ge=0)
    timed_out: bool = False


class TextOut(BaseModel):
    response_id: str
    features: TextFeatures
    scored: bool = False   # LLM rubric scoring arrives in week 3


def stimulus_text(item: EmailItem | DiscussionItem) -> str:
    if isinstance(item, EmailItem):
        return " ".join([item.scenario, *item.points])
    return " ".join([item.professor.text, *(p.text for p in item.students)])


@router.post("/sets/{set_id}/text/submit", response_model=TextOut)
def submit_text(set_id: str, body: TextSubmit) -> TextOut:
    s = _set(set_id)
    item = next((i for i in s.items if i.id == body.item_id), None)
    if not isinstance(item, (EmailItem, DiscussionItem)):
        raise HTTPException(400, "Item is not an Email or Academic Discussion item")
    feats = text_features(body.text, stimulus_text(item))
    rid = db.insert_response(
        set_id=s.id, item_id=item.id, task=s.task, section=s.section, text=body.text,
        payload={"features": feats.model_dump()}, time_spent_s=body.time_spent_s,
        timed_out=int(body.timed_out), score=None, max_score=5, score_json=None,
    )
    return TextOut(response_id=rid, features=feats)


# ---------- History ----------
@router.get("/responses")
def responses(task: str | None = None, limit: int = 50) -> list[dict]:
    return db.list_responses(task, min(max(limit, 1), 200))


@router.get("/responses/{rid}")
def response(rid: str) -> dict:
    r = db.get_response(rid)
    if not r:
        raise HTTPException(404, "Not found")
    return r


# ---------- Rubric scoring (Email / Academic Discussion) ----------
@router.post("/responses/{rid}/score", response_model=WritingScore)
async def score_response(rid: str) -> WritingScore:
    """LLM rubric scoring for Email, Academic Discussion and Take an Interview responses."""
    return await score_rubric(rid)


async def score_rubric(rid: str) -> WritingScore:
    r = db.get_response(rid)
    if not r:
        raise HTTPException(404, "Not found")
    s = bank().get(r["set_id"])
    item = next((i for i in s.items if i.id == r["item_id"]), None) if s else None
    if not isinstance(item, (EmailItem, DiscussionItem, InterviewItem)):
        raise HTTPException(400, "This response can't be rubric-scored (item missing or not a rubric-scored task)")
    if isinstance(item, InterviewItem) and "transcript" not in r["payload"]:
        raise HTTPException(409, "This recording hasn't been transcribed yet")
    prefs = load_prefs()
    try:
        llm = get_llm()
    except LLMError as e:
        raise HTTPException(400, f"{e}. Add a key in Settings.") from e
    try:
        if isinstance(item, InterviewItem):
            result = await speaking_judge.judge(
                llm, item, s.scene, Transcript(**r["payload"]["transcript"]),
                SpeechFeatures(**r["payload"]["features"]), samples=prefs.scoring.samples,
                provider=prefs.llm.provider, model=prefs.llm.model)
        else:
            text = r["text"] or ""
            result = await judge(llm, item, text, text_features(text, stimulus_text(item)),
                                 samples=prefs.scoring.samples, provider=prefs.llm.provider, model=prefs.llm.model)
    except LLMError as e:
        raise HTTPException(502, f"Scoring failed: {e}") from e
    db.update_score(rid, result.score, result.max_score, result.model_dump())
    return result
