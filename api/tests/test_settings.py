import os
import stat

from app.secrets.store import mask


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_settings_defaults_and_catalog(client):
    d = client.get("/api/settings").json()
    assert d["settings"]["llm"]["provider"] == "openai"
    ids = {p["id"] for p in d["providers"]}
    assert {"openai", "anthropic", "gemini", "ollama"} <= ids
    assert d["deepgram_key"]["set"] is False
    assert "ollama" not in d["llm_keys"]


def test_save_key_is_masked_and_file_is_private(client, tmp_path):
    r = client.put("/api/keys/openai", json={"value": "sk-abcdefghijklmnop1234"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"set": True, "masked": "sk-…1234", "source": "file"}
    assert "abcdefghijklmnop" not in client.get("/api/settings").text
    mode = stat.S_IMODE(os.stat(tmp_path / "secrets.json").st_mode)
    assert mode == 0o600
    assert client.delete("/api/keys/openai").json()["set"] is False


def test_env_overrides(client, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-env-key-123456")
    assert client.get("/api/settings").json()["deepgram_key"]["source"] == "env"


def test_unknown_key_404(client):
    assert client.put("/api/keys/nope", json={"value": "x"}).status_code == 404


def test_update_settings(client):
    r = client.put("/api/settings", json={"llm": {"provider": "anthropic", "model": "claude-sonnet-4-5"}})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["settings"]["llm"]["provider"] == "anthropic"
    assert client.put("/api/settings", json={"llm": {"provider": "x", "model": "y"}}).status_code == 400
    assert client.put("/api/settings", json={"speech": {"provider": "whisper"}}).status_code == 400


def test_mask():
    assert mask(None) is None
    assert mask("short") == "•••••"
