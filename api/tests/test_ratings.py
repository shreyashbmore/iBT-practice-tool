from app.evals import dataset


def test_blind_double_rating_and_export(client, monkeypatch, tmp_path):
    import app.routers.ratings as rt

    monkeypatch.setattr(rt, "EXPORT_DIR", tmp_path / "private" / "data")
    rid = client.post("/api/sets/email-01/text/submit",
                      json={"item_id": "email-01-hiking", "text": "Dear Ms. Alvarez, please keep the trip."}).json()["response_id"]
    # pretend it was AI-scored: the score must never be shown to raters
    from app import db
    db.update_score(rid, 4, 5, {"score": 4})

    assert client.get("/api/ratings/next?task=write-an-email&rater=").status_code == 400
    a = client.get("/api/ratings/next", params={"task": "write-an-email", "rater": "Asha"}).json()
    assert a["response_id"] == rid and a["prompt"]["kind"] == "email" and "5" in a["rubric"]["bands"]
    assert "score" not in a and "score_json" not in str(a) and a["text"].startswith("Dear")
    assert client.post("/api/ratings", json={"response_id": rid, "rater": "Asha", "score": 3}).json()["ok"]
    assert client.get("/api/ratings/next", params={"task": "write-an-email", "rater": "Asha"}).json()["done"]
    b = client.get("/api/ratings/next", params={"task": "write-an-email", "rater": "Ben"}).json()
    assert b["response_id"] == rid
    client.post("/api/ratings", json={"response_id": rid, "rater": "Ben", "score": 4, "note": "polite"})
    assert client.get("/api/ratings/next", params={"task": "write-an-email", "rater": "Cy"}).json()["done"]  # 2 ratings max
    assert client.post("/api/ratings", json={"response_id": rid, "rater": "x", "score": 7}).status_code == 422

    st = client.get("/api/ratings/stats").json()["write-an-email"]
    assert st == {"responses": 1, "unrated": 0, "rated_once": 0, "rated_twice_or_more": 1}

    out = client.post("/api/ratings/export").json()
    assert out["write-an-email"]["rows"] == 1 and out["listen-and-repeat"]["rows"] == 0
    rows = dataset.load_rows(files=[tmp_path / "private" / "data" / "app_write-an-email.csv"])
    assert rows[0].rater1 == 3 and rows[0].rater2 == 4 and rows[0].gold == 4 and rows[0].source == "app"
