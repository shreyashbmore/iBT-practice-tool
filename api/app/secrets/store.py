"""Local secret storage: env var > OS keychain > data/secrets.json (0600).

Secrets are never returned to the client in full; use `mask()`.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)
SERVICE = "ibt-practice"


class _Backend(Protocol):
    name: str

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class KeyringBackend:
    name = "keychain"

    def __init__(self) -> None:
        import keyring  # noqa: WPS433
        from keyring.backends import fail

        kr = keyring.get_keyring()
        if isinstance(kr, fail.Keyring) or "null" in type(kr).__name__.lower():
            raise RuntimeError("no usable keyring backend")
        self._kr = keyring

    def get(self, key: str) -> str | None:
        return self._kr.get_password(SERVICE, key)

    def set(self, key: str, value: str) -> None:
        self._kr.set_password(SERVICE, key, value)

    def delete(self, key: str) -> None:
        try:
            self._kr.delete_password(SERVICE, key)
        except Exception:  # not found
            pass


class FileBackend:
    name = "file"

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text() or "{}")

    def _write(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._read().get(key)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            d = self._read()
            d[key] = value
            self._write(d)

    def delete(self, key: str) -> None:
        with self._lock:
            d = self._read()
            d.pop(key, None)
            self._write(d)


# Secret names used across the app
DEEPGRAM = "deepgram"


def llm_secret(provider: str) -> str:
    return f"llm:{provider}"


ENV_VARS = {
    DEEPGRAM: "DEEPGRAM_API_KEY",
    llm_secret("openai"): "OPENAI_API_KEY",
    llm_secret("anthropic"): "ANTHROPIC_API_KEY",
    llm_secret("gemini"): "GEMINI_API_KEY",
    llm_secret("groq"): "GROQ_API_KEY",
    llm_secret("mistral"): "MISTRAL_API_KEY",
    llm_secret("openrouter"): "OPENROUTER_API_KEY",
}


class SecretStore:
    def __init__(self, backend: _Backend) -> None:
        self.backend = backend

    def get(self, key: str) -> str | None:
        env = ENV_VARS.get(key)
        if env and os.environ.get(env):
            return os.environ[env]
        return self.backend.get(key)

    def source(self, key: str) -> str | None:
        env = ENV_VARS.get(key)
        if env and os.environ.get(env):
            return "env"
        return self.backend.name if self.backend.get(key) else None

    def set(self, key: str, value: str) -> None:
        self.backend.set(key, value.strip())

    def delete(self, key: str) -> None:
        self.backend.delete(key)


def mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:3]}…{value[-4:]}"


_store: SecretStore | None = None


def get_store() -> SecretStore:
    global _store
    if _store is None:
        from app.config import get_settings

        try:
            backend: _Backend = KeyringBackend()
        except Exception as e:  # pragma: no cover - depends on host
            log.warning("Keychain unavailable (%s); using data/secrets.json", e)
            backend = FileBackend(get_settings().data_dir / "secrets.json")
        _store = SecretStore(backend)
    return _store
