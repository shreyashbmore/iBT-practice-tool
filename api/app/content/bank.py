"""Loads and validates every practice set under content/items/ (cached; call reload() after edits)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.config import ROOT_DIR

from .models import MockTest, PracticeSet, SectionForm

ITEMS_DIR = ROOT_DIR / "content" / "items"
FORMS_DIR = ROOT_DIR / "content" / "forms"
MOCKS_DIR = ROOT_DIR / "content" / "mocks"


class ContentError(RuntimeError):
    pass


def load_dir(path: Path | None = None) -> dict[str, PracticeSet]:
    path = path or ITEMS_DIR
    sets: dict[str, PracticeSet] = {}
    item_ids: dict[str, str] = {}
    errors: list[str] = []
    for f in sorted(path.rglob("*.yaml")):
        try:
            s = PracticeSet.model_validate(yaml.safe_load(f.read_text()))
        except Exception as e:
            errors.append(f"{f.relative_to(path)}: {e}")
            continue
        if s.id in sets:
            errors.append(f"{f.name}: duplicate set id {s.id}")
        for it in s.items:
            if it.id in item_ids:
                errors.append(f"{f.name}: item id {it.id} already used in {item_ids[it.id]}")
            item_ids[it.id] = s.id
        sets[s.id] = s
    if errors:
        raise ContentError("Invalid content:\n" + "\n".join(errors))
    return sets


@lru_cache
def bank() -> dict[str, PracticeSet]:
    return load_dir()


def load_forms(path: Path | None = None, sets: dict[str, PracticeSet] | None = None) -> dict[str, SectionForm]:
    path = path or FORMS_DIR
    sets = sets if sets is not None else bank()
    out: dict[str, SectionForm] = {}
    errors: list[str] = []
    for f in sorted(path.glob("*.yaml")) if path.exists() else []:
        try:
            form = SectionForm.model_validate(yaml.safe_load(f.read_text()))
        except Exception as e:
            errors.append(f"forms/{f.name}: {e}")
            continue
        for stage in ("router", "lower", "upper"):
            for sid in getattr(form, stage):
                if sid not in sets:
                    errors.append(f"forms/{f.name}: {stage} set '{sid}' not found")
                elif sets[sid].section != form.section:
                    errors.append(f"forms/{f.name}: set '{sid}' is not a {form.section} set")
        out[form.id] = form
    if errors:
        raise ContentError("Invalid forms:\n" + "\n".join(errors))
    return out


@lru_cache
def forms() -> dict[str, SectionForm]:
    return load_forms()


EXPECTED_TASKS = {
    ("writing", "build_sentence"): "build-a-sentence", ("writing", "email"): "write-an-email",
    ("writing", "discussion"): "academic-discussion", ("speaking", "listen_repeat"): "listen-and-repeat",
    ("speaking", "interview"): "take-an-interview",
}


def load_mocks(path: Path | None = None) -> dict[str, MockTest]:
    path = path or MOCKS_DIR
    sets, fs = bank(), forms()
    out: dict[str, MockTest] = {}
    errors: list[str] = []
    for f in sorted(path.glob("*.yaml")) if path.exists() else []:
        try:
            m = MockTest.model_validate(yaml.safe_load(f.read_text()))
        except Exception as e:
            errors.append(f"mocks/{f.name}: {e}")
            continue
        for sec in ("reading", "listening"):
            fid = getattr(m, sec)
            if fid not in fs or fs[fid].section != sec:
                errors.append(f"mocks/{f.name}: {sec} form '{fid}' not found")
        for (sec, key), task in EXPECTED_TASKS.items():
            sid = getattr(getattr(m, sec), key)
            if sid not in sets or sets[sid].task != task:
                errors.append(f"mocks/{f.name}: {sec}.{key} must be a {task} set (got '{sid}')")
        out[m.id] = m
    if errors:
        raise ContentError("Invalid mocks:\n" + "\n".join(errors))
    return out


@lru_cache
def mocks() -> dict[str, MockTest]:
    return load_mocks()


def reload() -> dict[str, PracticeSet]:
    bank.cache_clear()
    forms.cache_clear()
    mocks.cache_clear()
    b = bank()
    forms()
    mocks()
    return b
