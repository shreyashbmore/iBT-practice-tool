import pytest

from app.content.bank import load_dir
from app.content.models import BuildSentenceItem, PracticeSet
from app.features.text import compute
from app.scoring.build_sentence import score_item


def test_all_content_valid():
    sets = load_dir()
    assert {"bas-set-01", "email-01", "discussion-01"} <= set(sets)
    assert len(sets["bas-set-01"].items) == 10


def make_item(**kw):
    base = dict(id="x-1", context="Q?", template="I [] [] it.", answer=["really", "like"])
    return BuildSentenceItem(**{**base, **kw})


def test_item_validation():
    with pytest.raises(ValueError):
        make_item(answer=["really"])                      # wrong slot count
    with pytest.raises(ValueError):
        make_item(distractors=["like"])                   # distractor == answer chunk
    with pytest.raises(ValueError):
        make_item(alternates=[["like", "much"]])          # alternate with other chunks
    with pytest.raises(ValueError):
        PracticeSet(id="s", task="write-an-email", title="t", section="writing", time_limit_s=1,
                    directions="d", items=[make_item()])  # task mismatch


def test_score_item():
    it = make_item(alternates=[["like", "really"]], explanation="adverb before verb")
    assert score_item(it, ["really", "like"]).correct
    assert score_item(it, [" Really ", "LIKE"]).correct      # whitespace/case-insensitive
    assert score_item(it, ["like", "really"]).correct         # accepted alternate
    r = score_item(make_item(), ["like"])
    assert not r.correct and r.your_sentence == "I like ___ it." and r.correct_sentence == "I really like it."
    assert not score_item(make_item(), None).correct
    gap = score_item(make_item(), ["", "like"])                  # first slot left empty
    assert not gap.correct and gap.your_sentence == "I ___ like it."


def test_public_hides_answers(client):
    s = client.get("/api/sets/bas-set-01").json()
    item = s["items"][0]
    assert "answer" not in item and "explanation" not in item
    assert sorted(item["chunks"]) == sorted(["I", "will", "finish it", "before class", "finished"])
    assert item["slots"] == 4
    assert client.get("/api/sets/bas-set-01").json() == s     # deterministic shuffle


def test_list_and_filter(client):
    assert {s["task"] for s in client.get("/api/sets?section=writing").json()} == {
        "build-a-sentence", "write-an-email", "academic-discussion"}
    assert all(s["task"] == "write-an-email" for s in client.get("/api/sets?task=write-an-email").json())
    assert client.get("/api/sets/nope").status_code == 404


def test_submit_build_and_history(client):
    r = client.post("/api/sets/bas-set-01/build-a-sentence/submit", json={
        "answers": {"bas-01-01": ["I", "will", "finish it", "before class"],
                    "bas-01-02": ["meeting", "my", "with", "my advisor"]},
        "time_spent_s": 200})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 1 and body["max_score"] == 10
    assert body["results"][1]["correct_sentence"].startswith("Sorry, my meeting with my advisor")
    saved = client.get(f"/api/responses/{body['response_id']}").json()
    assert saved["score"] == 1 and saved["payload"]["answers"]["bas-01-01"][0] == "I"
    bad = client.post("/api/sets/bas-set-01/build-a-sentence/submit", json={"answers": {"zzz": []}})
    assert bad.status_code == 400


def test_submit_email(client):
    text = ("Dear Ms. Alvarez,\n\nI really hope the trip goes ahead because I have never hiked in the mountains. "
            "Maybe we could post photos from past trips on social media to attract members. "
            "What equipment should we bring?\n\nBest regards,\nSam")
    r = client.post("/api/sets/email-01/text/submit",
                    json={"item_id": "email-01-hiking", "text": text, "time_spent_s": 300})
    assert r.status_code == 200, r.text
    f = r.json()["features"]
    assert f["has_greeting"] and f["has_closing"] and f["paragraph_count"] == 3
    assert f["word_count"] == 40 and f["stimulus_overlap"] < 0.2
    assert client.get("/api/responses?task=write-an-email").json()[0]["text"] == text
    assert client.post("/api/sets/email-01/text/submit",
                       json={"item_id": "nope", "text": "x"}).status_code == 400


def test_copy_detection():
    stim = "Several companies around the world have experimented with a four-day workweek keeping salaries the same"
    f = compute("Several companies around the world have experimented with a four-day workweek.", stim)
    assert f.stimulus_overlap > 0.8
    assert compute("", stim).word_count == 0
