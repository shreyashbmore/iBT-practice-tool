import httpx
import respx

from app.features.speech import compute
from app.providers.speech.base import Transcript, Word

DG_RESPONSE = {
    "metadata": {"duration": 4.0},
    "results": {"channels": [{"alternatives": [{
        "transcript": "um I like studying in the library",
        "confidence": 0.93,
        "words": [
            {"word": "um", "start": 0.0, "end": 0.3, "confidence": 0.9},
            {"word": "i", "punctuated_word": "I", "start": 0.4, "end": 0.5, "confidence": 0.99},
            {"word": "like", "start": 0.5, "end": 0.8, "confidence": 0.98},
            {"word": "studying", "start": 2.0, "end": 2.5, "confidence": 0.5},
            {"word": "in", "start": 2.5, "end": 2.6, "confidence": 0.97},
            {"word": "the", "start": 2.6, "end": 2.7, "confidence": 0.97},
            {"word": "library", "punctuated_word": "library.", "start": 2.7, "end": 3.3, "confidence": 0.95},
        ]}]}]},
}


def test_features():
    t = Transcript(text="", words=[Word(**{**w, "punctuated": w.get("punctuated_word")})
                                   for w in DG_RESPONSE["results"]["channels"][0]["alternatives"][0]["words"]])
    f = compute(t)
    assert f.word_count == 6
    assert f.filler_count == 1
    assert f.pauses_over_1s == 1 and f.longest_pause_s == 1.2
    assert f.low_confidence_words == ["studying"]
    assert compute(Transcript(text="", words=[])).wpm == 0


@respx.mock
def test_transcribe_endpoint(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    route = respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(200, json=DG_RESPONSE))
    r = client.post("/api/speech/transcribe", files={"file": ("a.webm", b"abc", "audio/webm")},
                    data={"verbatim": "true"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transcript"]["text"].startswith("um I like")
    assert body["features"]["filler_count"] == 1
    req = route.calls[0].request
    assert req.headers["Authorization"] == "Token dg-test-key-12345"
    assert "smart_format=false" in str(req.url) and "filler_words=true" in str(req.url)


def test_transcribe_without_key(client):
    r = client.post("/api/speech/transcribe", files={"file": ("a.webm", b"abc", "audio/webm")})
    assert r.status_code == 400 and "Deepgram" in r.json()["detail"]


@respx.mock
def test_tts_cached(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    route = respx.post("https://api.deepgram.com/v1/speak").mock(
        return_value=httpx.Response(200, content=b"ID3mp3bytes"))
    for _ in range(2):
        r = client.post("/api/speech/tts", json={"text": "Hello there"})
        assert r.status_code == 200 and r.content == b"ID3mp3bytes"
    assert route.call_count == 1


@respx.mock
def test_deepgram_bad_key(client):
    respx.get("https://api.deepgram.com/v1/projects").mock(return_value=httpx.Response(401, json={}))
    r = client.post("/api/keys/test/deepgram", json={"api_key": "bad"})
    assert r.json()["ok"] is False and "Invalid Deepgram" in r.json()["message"]


@respx.mock
def test_network_error_is_502(client):
    client.put("/api/keys/deepgram", json={"value": "dg-test-key-12345"})
    respx.post("https://api.deepgram.com/v1/speak").mock(side_effect=httpx.ConnectError("boom"))
    r = client.post("/api/speech/tts", json={"text": "Hello"})
    assert r.status_code == 502 and "Could not reach Deepgram" in r.json()["detail"]
