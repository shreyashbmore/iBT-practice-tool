import shutil
from types import SimpleNamespace

import httpx
import pytest
import respx

from app.content import bank as bank_mod
from app.content import generator as gen_mod
from app.content.bank import load_dir
from app.content.models import CompleteWordsItem
from app.providers.llm.base import Usage
from app.scoring.objective import score_set


def shown_answer_positions(client, set_id):
    """Use the public (shuffled) view + the real key to build a perfect answer sheet."""
    pub = client.get(f"/api/sets/{set_id}").json()
    real = load_dir()[set_id]
    answers = {}
    for pi, ri in zip(pub["items"], real.items):
        if ri.task == "complete-the-words":
            answers[ri.id] = {gid: ri.split(w)[1] for gid, w in ri.gaps()}
        else:
            answers[ri.id] = {q.id: pq["options"].index(q.options[q.answer]) for q, pq in zip(ri.questions, pi["questions"])}
    return answers


def test_complete_words_public_and_scoring():
    it = CompleteWordsItem(id="t-1", text="The [[library]] is [[open]] today.")
    pub = it.public("s")
    gaps = [g for g in pub["segments"] if g["type"] == "gap"]
    assert gaps == [{"type": "gap", "id": "g1", "prefix": "lib", "length": 4},
                    {"type": "gap", "id": "g2", "prefix": "op", "length": 2}]
    assert "library" not in str(pub)
    from app.scoring.objective import score_item
    r = score_item(it, {"g1": "RARY", "g2": "open"})       # missing part or whole word both accepted
    assert r.score == 2 and r.full_text == "The library is open today."
    assert score_item(it, {"g1": "rari"}).score == 0
    with pytest.raises(ValueError):
        CompleteWordsItem(id="t-2", text="no gaps here")


def test_options_shuffled_but_scored_correctly(client):
    pub = client.get("/api/sets/academic-01").json()
    real = load_dir()["academic-01"].items[0]
    assert sorted(pub["items"][0]["questions"][0]["options"]) == sorted(real.questions[0].options)
    assert "answer" not in str(pub["items"][0]["questions"])
    answers = shown_answer_positions(client, "academic-01")
    r = client.post("/api/sets/academic-01/objective/submit", json={"answers": answers, "time_spent_s": 100}).json()
    assert r["score"] == r["max_score"] == 5
    q = r["items"][0]["questions"][0]
    assert q["options"][q["answer"]] == real.questions[0].options[real.questions[0].answer]


def test_answer_positions_are_balanced():
    sets = load_dir()
    pos = [q.order(f"{s.id}:{i.id}").index(q.answer)
           for s in sets.values() for i in s.items for q in getattr(i, "questions", [])]
    assert len(set(pos)) >= 3   # after shuffling, the key is not stuck in one position


def test_listening_hides_script_and_reveals_after(client):
    pub = client.get("/api/sets/conv-01").json()
    assert "lines" not in pub["items"][0]
    r = client.post("/api/sets/conv-01/objective/submit", json={"answers": {}}).json()
    assert r["score"] == 0 and r["items"][0]["transcript"][0]["speaker"] == "Student"
    assert client.post("/api/sets/email-01/objective/submit", json={"answers": {}}).status_code == 400


@respx.mock
def test_listening_audio_concatenates_lines_with_voices(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    route = respx.post("https://api.deepgram.com/v1/speak").mock(
        side_effect=lambda req: httpx.Response(200, content=req.url.params["model"].encode() + b"|"))
    r = client.get("/api/sets/conv-01/items/conv-01-a/audio")
    assert r.status_code == 200
    assert r.content.startswith(b"aura-2-arcas-en|aura-2-thalia-en|")   # student = male, clerk = female
    assert route.call_count == 7


def test_adaptive_form_routes_up_and_down(client):
    forms = client.get("/api/forms").json()
    assert {f["id"] for f in forms} >= {"reading-form-01", "listening-form-01"}

    # strong router → upper module
    st = client.post("/api/forms/reading-form-01/start").json()
    assert st["module"]["stage"] == "router" and [s["id"] for s in st["module"]["sets"]] == ["cw-01", "daily-01", "academic-01"]
    aid = st["attempt_id"]
    perfect = {sid: shown_answer_positions(client, sid) for sid in ["cw-01", "daily-01", "academic-01"]}
    r = client.post(f"/api/forms/reading-form-01/attempts/{aid}/submit", json={"stage": "router", "answers": perfect}).json()
    assert r["next"]["stage"] == "upper"
    assert client.post(f"/api/forms/reading-form-01/attempts/{aid}/submit",
                       json={"stage": "router", "answers": {}}).status_code == 409   # wrong stage
    fin = client.post(f"/api/forms/reading-form-01/attempts/{aid}/submit", json={"stage": "upper", "answers": {}}).json()["final"]
    assert fin["route"] == "upper" and fin["score"] == r["stage_result"]["score"] and fin["max_score"] > fin["score"]
    assert client.get(f"/api/responses/{fin['response_id']}").json()["task"] == "reading-test"
    assert client.post(f"/api/forms/reading-form-01/attempts/{aid}/submit",
                       json={"stage": "upper", "answers": {}}).status_code == 409   # already done

    # weak router → lower module
    aid2 = client.post("/api/forms/reading-form-01/start").json()["attempt_id"]
    r2 = client.post(f"/api/forms/reading-form-01/attempts/{aid2}/submit", json={"stage": "router", "answers": {}}).json()
    assert r2["next"]["stage"] == "lower" and [s["id"] for s in r2["next"]["sets"]] == ["cw-02", "daily-02"]


# ---------- generation ----------
class GenLLM:
    def __init__(self, solver_ok=True):
        self.solver_ok = solver_ok

    async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=2048):
        u = Usage(prompt_tokens=100, completion_tokens=100, cost_usd=0.001)
        if schema.__name__ == "SolverOut":
            return schema(answers=[{"id": "q1", "choice": 2 if self.solver_ok else 0},
                                   {"id": "q2", "choice": 0}]), u
        return schema.model_validate({
            "title": "Library card renewal",
            "items": [{"genre": "email", "title": "Renew your card",
                       "text": "Dear student, your library card expires on May 1. Renew it online or at the desk.",
                       "questions": [
                           {"id": "q1", "prompt": "When does the card expire?",
                            "options": ["April 1", "April 30", "May 1", "June 1"], "answer": 2},
                           {"id": "q2", "prompt": "How can it be renewed?",
                            "options": ["Online or at the desk", "By phone", "By mail", "It can't"], "answer": 0}]}]}), u


@pytest.fixture
def content_sandbox(tmp_path, monkeypatch):
    items = tmp_path / "content" / "items"
    shutil.copytree(bank_mod.ITEMS_DIR, items)
    monkeypatch.setattr(bank_mod, "ITEMS_DIR", items)
    monkeypatch.setattr(gen_mod, "DRAFTS_DIR", tmp_path / "content" / "drafts")
    bank_mod.reload()
    yield items
    monkeypatch.undo()
    bank_mod.reload()


def test_generate_review_approve(client, monkeypatch, content_sandbox):
    import app.routers.drafts as dr

    assert client.post("/api/drafts/generate", json={"task": "read-daily-life"}).status_code == 400   # no key
    monkeypatch.setattr(dr, "get_llm", lambda: GenLLM())
    d = client.post("/api/drafts/generate", json={"task": "read-daily-life", "cefr": "A2", "topic": "library"}).json()
    assert d["id"].startswith("gen-read-daily-life-") and d["items"][0]["cefr"] == "A2"
    assert d["review"]["qa"] == {"questions_checked": 2, "solver_agreed": 2, "mismatches": [], "warnings": []}
    assert client.get("/api/drafts").json()[0]["id"] == d["id"]
    assert client.get(f"/api/sets/{d['id']}").status_code == 404          # drafts are not playable
    ok = client.post(f"/api/drafts/{d['id']}/approve").json()
    assert ok["approved"] == d["id"]
    assert (content_sandbox / "reading" / "generated" / f"{d['id']}.yaml").exists()
    assert client.get(f"/api/sets/{d['id']}").status_code == 200          # now in the bank
    assert client.get("/api/drafts").json() == []


def test_generate_flags_solver_disagreement_and_discard(client, monkeypatch, content_sandbox):
    import app.routers.drafts as dr

    monkeypatch.setattr(dr, "get_llm", lambda: GenLLM(solver_ok=False))
    d = client.post("/api/drafts/generate", json={"task": "read-daily-life"}).json()
    assert d["review"]["qa"]["mismatches"] == [f"{d['id']}-1/q1"]
    assert client.delete(f"/api/drafts/{d['id']}").json() == {"discarded": d["id"]}
    assert client.get(f"/api/drafts/{d['id']}").status_code == 404
    assert client.get("/api/drafts/..%2F..%2Fsecrets").status_code == 404
    assert client.post("/api/drafts/generate", json={"task": "build-a-sentence"}).status_code == 400


def test_every_spec_produces_a_valid_schema():
    for spec in gen_mod.SPECS.values():
        schema = gen_mod._gen_set_model(spec).model_json_schema()
        assert "items" in schema["properties"]
