"""Estimated band conversion (see content/band_tables.yaml for the method and sources)."""
from __future__ import annotations

import math
from functools import lru_cache

import yaml
from pydantic import BaseModel

from app.config import ROOT_DIR

TABLES = ROOT_DIR / "content" / "band_tables.yaml"
SECTIONS = ("reading", "listening", "writing", "speaking")


@lru_cache
def tables() -> dict:
    t = yaml.safe_load(TABLES.read_text())
    t["old_scale_min"] = {s: {float(b): v for b, v in m.items()} for s, m in t["old_scale_min"].items()}
    t["total_ranges"] = {float(b): r for b, r in t["total_ranges"].items()}
    t["cefr"] = {float(b): c for b, c in t["cefr"].items()}
    return t


class SectionBand(BaseModel):
    section: str
    raw: float
    max: float
    percent: float
    old_scale: int
    band: float
    cefr: str


class OverallBand(BaseModel):
    band: float
    cefr: str
    comparable_total: int
    sections: dict[str, SectionBand]
    version: str
    estimate: bool = True


def round_half(x: float) -> float:
    """Nearest 0.5, halves rounded up (5.25 → 5.5, 5.125 → 5.0) as in ETS's examples."""
    return math.floor(x * 2 + 0.5) / 2


def cefr(band: float) -> str:
    return tables()["cefr"][float(math.floor(band))]


def band_for_percent(section: str, pct: float) -> tuple[int, float]:
    pct = min(max(pct, 0.0), 1.0)
    old = round(pct * 30)
    for b, lo in sorted(tables()["old_scale_min"][section].items(), reverse=True):
        if old >= lo:
            return old, b
    return old, 1.0


def section_band(section: str, raw: float, max_: float, pct: float | None = None) -> SectionBand:
    pct = (raw / max_ if max_ else 0.0) if pct is None else pct
    old, b = band_for_percent(section, pct)
    return SectionBand(section=section, raw=raw, max=max_, percent=round(pct * 100, 1), old_scale=old, band=b,
                       cefr=cefr(b))


def adaptive_percent(router_score: int, router_max: int, mod_score: int, mod_max: int, route: str) -> float:
    a = tables()["adaptive"]
    w = 1.0 if route == "upper" else a["lower_module_weight"]
    rp = router_score / router_max if router_max else 0
    mp = mod_score / mod_max if mod_max else 0
    return a["router_weight"] * rp + (1 - a["router_weight"]) * mp * w


def overall(sections: dict[str, SectionBand]) -> OverallBand:
    bands = [sections[s].band for s in SECTIONS if s in sections]
    ob = round_half(sum(bands) / len(bands)) if bands else 1.0
    lo, hi = tables()["total_ranges"][ob]
    return OverallBand(band=ob, cefr=cefr(ob), comparable_total=int(math.floor((lo + hi) / 2 + 0.5)),
                       sections=sections, version=tables()["version"])
