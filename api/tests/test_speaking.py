import httpx
import respx

from app.features.speech import compute
from app.providers.llm.base import Usage
from app.providers.speech.base import Transcript, Word
from app.scoring import speaking_judge
from app.scoring.writing_judge import FullJudgement, ScoreOnly


def dg_json(text: str, conf: float = 0.95):
    words = [{"word": w.lower().strip(".,?"), "punctuated_word": w, "start": i * 0.4, "end": i * 0.4 + 0.3,
              "confidence": conf} for i, w in enumerate(text.split())]
    return {"metadata": {"duration": 5.0},
            "results": {"channels": [{"alternatives": [{"transcript": text, "confidence": conf, "words": words}]}]}}


def test_public_set_hides_spoken_text(client):
    s = client.get("/api/sets/lr-set-01").json()
    assert s["scene"].startswith("Orientation day")
    assert all("text" not in i for i in s["items"]) and s["items"][0]["response_time_s"] >= 8
    q = client.get("/api/sets/interview-01").json()["items"][0]
    assert "question" not in q and q["response_time_s"] == 45


@respx.mock
def test_item_audio_uses_tts_cache(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    speak = respx.post("https://api.deepgram.com/v1/speak").mock(return_value=httpx.Response(200, content=b"MP3"))
    for _ in range(2):
        r = client.get("/api/sets/lr-set-01/items/lr-01-01/audio")
        assert r.status_code == 200 and r.content == b"MP3"
    assert speak.call_count == 1
    assert b"Welcome to the student center." in speak.calls[0].request.content
    assert client.get("/api/sets/lr-set-01/items/nope/audio").status_code == 404


@respx.mock
def test_listen_repeat_submit_scores_and_stores(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    listen = respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(200, json=dg_json("Welcome to the student center.")))
    r = client.post("/api/sets/lr-set-01/speaking/submit",
                    files={"file": ("a.webm", b"OPUSDATA", "audio/webm;codecs=opus")},
                    data={"item_id": "lr-01-01", "attempt_id": "att1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["listen_repeat"]["score"] == 5 and body["prompt_text"] == "Welcome to the student center."
    assert "smart_format=false" in str(listen.calls[0].request.url)
    saved = client.get(f"/api/responses/{body['response_id']}").json()
    assert saved["score"] == 5 and saved["payload"]["attempt_id"] == "att1"
    audio = client.get(f"/api/responses/{body['response_id']}/audio")
    assert audio.status_code == 200 and audio.content == b"OPUSDATA"


@respx.mock
def test_transcription_failure_can_be_retried(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    route = respx.post("https://api.deepgram.com/v1/listen")
    route.mock(return_value=httpx.Response(500, json={"err_msg": "boom"}))
    body = client.post("/api/sets/lr-set-01/speaking/submit", files={"file": ("a.webm", b"X", "audio/webm")},
                       data={"item_id": "lr-01-02"}).json()
    assert body["error"] and body["listen_repeat"] is None
    route.mock(return_value=httpx.Response(200, json=dg_json("The library is open every day.")))
    again = client.post(f"/api/responses/{body['response_id']}/process").json()
    assert again["error"] is None and again["listen_repeat"]["score"] < 5


def test_submit_without_key_keeps_audio(client):
    body = client.post("/api/sets/lr-set-01/speaking/submit", files={"file": ("a.webm", b"X", "audio/webm")},
                       data={"item_id": "lr-01-01"}).json()
    assert "Deepgram" in body["error"]
    assert client.get(f"/api/responses/{body['response_id']}/audio").status_code == 200


class FakeLLM:
    def __init__(self):
        self.messages = []

    async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=2048):
        self.messages.append(messages)
        u = Usage(prompt_tokens=10, completion_tokens=5)
        if schema is ScoreOnly:
            return ScoreOnly(score=4, rationale="ok"), u
        return FullJudgement.model_validate({
            "dimensions": [{"id": "fluency", "level": "adequate", "comment": "Some pauses.",
                            "evidence": ["I usually study in the library"]},
                           {"id": "relevance", "level": "strong", "comment": "On topic.", "evidence": []}],
            "score": 4, "rationale": "Clear.", "errors": [], "next_steps": ["Use connectors."],
            "improved_version": "I usually study..."}), u


@respx.mock
def test_interview_flow(client, monkeypatch):
    import app.routers.practice as pr

    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    respx.post("https://api.deepgram.com/v1/listen").mock(return_value=httpx.Response(
        200, json=dg_json("I usually study in the library, uh, because it is quiet and I can focus.")))
    body = client.post("/api/sets/interview-01/speaking/submit", files={"file": ("a.webm", b"X", "audio/webm")},
                       data={"item_id": "interview-01-q1"}).json()
    assert body["listen_repeat"] is None and body["features"]["filler_count"] == 1
    assert body["prompt_text"].startswith("Thanks for joining us")
    fake = FakeLLM()
    monkeypatch.setattr(pr, "get_llm", lambda: fake)
    r = client.post(f"/api/responses/{body['response_id']}/score")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["score"] == 4 and out["rubric_version"] == "speaking-2026.1"
    assert [d["id"] for d in out["dimensions"]] == ["relevance", "fluency"]
    assert out["dimensions"][1]["evidence"] == ["I usually study in the library"]
    prompt = fake.messages[0][1]["content"]
    assert "INTERVIEWER'S QUESTION" in prompt and "fillers=1" in prompt


def test_interview_guards_and_annotation():
    words = [Word(word="i", punctuated="I", start=0, end=0.2, confidence=0.9),
             Word(word="don't", punctuated="don't", start=0.3, end=0.5, confidence=0.9),
             Word(word="know", punctuated="know.", start=0.6, end=0.8, confidence=0.9)]
    t = Transcript(text="I don't know.", words=words)
    assert speaking_judge.guard(t, compute(t)) == "dont_know"
    t2 = Transcript(text="", words=[])
    assert speaking_judge.guard(t2, compute(t2)) == "no_response"
    t3 = Transcript(text="x", words=[Word(word="library", start=0, end=0.5, confidence=0.3),
                                     Word(word="quiet", start=2.0, end=2.4, confidence=0.9)])
    assert speaking_judge.annotate(t3) == "{library?} [pause 1.5s] quiet"
