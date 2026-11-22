import pytest
from fastapi.testclient import TestClient

import app.secrets.store as store_mod
from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for v in ["DEEPGRAM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
        monkeypatch.delenv(v, raising=False)
    s = get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)
    monkeypatch.setattr(store_mod, "_store",
                        store_mod.SecretStore(store_mod.FileBackend(tmp_path / "secrets.json")))
    yield


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)
