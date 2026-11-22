import httpx
import respx

from app.providers.llm.base import Usage
from app.scoring.writing_judge import FullJudgement, ScoreOnly
from tests.test_objective import shown_answer_positions


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=2048):
        self.calls += 1
        u = Usage(prompt_tokens=10, completion_tokens=5)
        if schema is ScoreOnly:
            return ScoreOnly(score=4, rationale="ok"), u
        return FullJudgement.model_validate({"dimensions": [], "score": 4, "rationale": "ok", "errors": [],
                                             "next_steps": [], "improved_version": "x"}), u


def dg(text):
    words = [{"word": w.lower(), "punctuated_word": w, "start": i * 0.4, "end": i * 0.4 + 0.3, "confidence": 0.95}
             for i, w in enumerate(text.split())]
    return {"metadata": {"duration": 3}, "results": {"channels": [{"alternatives": [{"transcript": text, "words": words}]}]}}


def run_form(client, fid, perfect):
    aid = client.post(f"/api/forms/{fid}/start").json()["attempt_id"]
    st = client.post(f"/api/forms/{fid}/start").json()  # a second, abandoned attempt must not interfere
    router_sets = [s["id"] for s in st["module"]["sets"]]
    answers = {sid: shown_answer_positions(client, sid) for sid in router_sets} if perfect else {}
    nxt = client.post(f"/api/forms/{fid}/attempts/{aid}/submit", json={"stage": "router", "answers": answers}).json()["next"]
    ans2 = {s["id"]: shown_answer_positions(client, s["id"]) for s in nxt["sets"]} if perfect else {}
    return client.post(f"/api/forms/{fid}/attempts/{aid}/submit", json={"stage": nxt["stage"], "answers": ans2}).json()["final"]["response_id"]


@respx.mock
def test_full_mock_flow(client, monkeypatch):
    import app.routers.practice as pr

    assert client.get("/api/mocks").json()[0]["id"] == "mock-01"
    start = client.post("/api/mocks/mock-01/start").json()
    aid = start["attempt_id"]
    assert start["next_section"] == "reading"
    assert client.post(f"/api/mocks/attempts/{aid}/finish").status_code == 409            # nothing done yet

    # out of order is rejected
    assert client.post(f"/api/mocks/attempts/{aid}/sections/writing", json={"response_ids": []}).status_code == 409

    r = client.post(f"/api/mocks/attempts/{aid}/sections/reading", json={"response_ids": [run_form(client, "reading-form-01", True)]})
    assert r.json()["next_section"] == "listening"
    # a response from the wrong section is rejected
    wrong = run_form(client, "reading-form-01", False)
    assert client.post(f"/api/mocks/attempts/{aid}/sections/listening", json={"response_ids": [wrong]}).status_code == 400
    client.post(f"/api/mocks/attempts/{aid}/sections/listening", json={"response_ids": [run_form(client, "listening-form-01", False)]})

    bas = client.post("/api/sets/bas-set-01/build-a-sentence/submit", json={"answers": {
        "bas-01-01": ["I", "will", "finish it", "before class"]}}).json()["response_id"]
    em = client.post("/api/sets/email-01/text/submit", json={"item_id": "email-01-hiking",
                                                            "text": "Dear Ms. Alvarez, I want the trip to happen."}).json()["response_id"]
    di = client.post("/api/sets/discussion-01/text/submit", json={"item_id": "discussion-01-workweek",
                                                                 "text": "I think a four-day week helps people rest."}).json()["response_id"]
    client.post(f"/api/mocks/attempts/{aid}/sections/writing", json={"response_ids": [bas, em, di]})

    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    respx.post("https://api.deepgram.com/v1/listen").mock(return_value=httpx.Response(200, json=dg("Welcome to the student center.")))
    sp = [client.post("/api/sets/lr-set-01/speaking/submit", files={"file": ("a.webm", b"x", "audio/webm")},
                      data={"item_id": "lr-01-01"}).json()["response_id"],
          client.post("/api/sets/interview-01/speaking/submit", files={"file": ("a.webm", b"x", "audio/webm")},
                      data={"item_id": "interview-01-q1"}).json()["response_id"]]
    client.post(f"/api/mocks/attempts/{aid}/sections/speaking", json={"response_ids": sp})

    # finish needs an LLM for the unscored email/discussion/interview
    assert client.post(f"/api/mocks/attempts/{aid}/finish").status_code == 400
    fake = FakeLLM()
    monkeypatch.setattr(pr, "get_llm", lambda: fake)
    res = client.post(f"/api/mocks/attempts/{aid}/finish").json()
    secs = res["sections"]
    assert secs["writing"]["raw"] == 1 + 4 + 4 and secs["writing"]["max"] == 20
    assert secs["speaking"]["raw"] == 5 + 4 and secs["speaking"]["max"] == 55          # unanswered items = 0
    assert secs["reading"]["band"] == 6 and secs["listening"]["band"] == 1
    assert res["estimate"] and 1 <= res["band"] <= 6 and res["cefr"]
    assert fake.calls == 9                                                              # 3 responses × 3 passes
    again = client.post(f"/api/mocks/attempts/{aid}/finish").json()
    assert again == res and fake.calls == 9                                             # cached, no re-scoring
    assert client.get(f"/api/mocks/attempts/{aid}").json()["status"] == "done"

    prog = client.get("/api/progress").json()
    assert prog["mocks"][0]["band"] == res["band"]
    assert "reading-test" in prog["tasks"] and prog["tasks"]["write-an-email"]["last_pct"] == 80.0
