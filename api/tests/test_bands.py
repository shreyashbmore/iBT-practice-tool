import pytest

from app.scoring.bands import adaptive_percent, band_for_percent, cefr, overall, round_half, section_band


def test_round_half_matches_ets_examples():
    assert round_half(5.125) == 5.0     # ETS: average 5.125 → 5
    assert round_half(5.25) == 5.5      # ETS: average 5.25 → 5.5
    assert round_half(4.74) == 4.5


@pytest.mark.parametrize("section,pct,band", [
    ("reading", 1.0, 6), ("reading", 0.9, 5.5), ("reading", 0.6, 4), ("reading", 0.0, 1),
    ("writing", 0.5, 3.5), ("speaking", 0.8, 4.5), ("speaking", 0.85, 5), ("listening", 0.7, 4.5),
])
def test_band_for_percent(section, pct, band):
    assert band_for_percent(section, pct)[1] == band


def test_adaptive_lower_route_is_capped():
    upper = adaptive_percent(10, 10, 10, 10, "upper")
    lower = adaptive_percent(10, 10, 10, 10, "lower")
    assert upper == 1.0 and lower == pytest.approx(0.8)
    assert section_band("reading", 20, 20, pct=lower).band < 6


def test_overall_and_comparable_total():
    secs = {s: section_band(s, r, 1) for s, r in [("reading", 1.0), ("listening", 0.9), ("writing", 0.8), ("speaking", 0.7)]}
    o = overall(secs)
    bands = [secs[s].band for s in ("reading", "listening", "writing", "speaking")]
    assert o.band == round_half(sum(bands) / 4)
    assert o.cefr == cefr(o.band) and 0 <= o.comparable_total <= 120
    assert overall({"reading": section_band("reading", 1, 1)}).comparable_total == 117   # midpoint 114–120


def test_section_test_reports_band(client):
    aid = client.post("/api/forms/reading-form-01/start").json()["attempt_id"]
    client.post(f"/api/forms/reading-form-01/attempts/{aid}/submit", json={"stage": "router", "answers": {}})
    fin = client.post(f"/api/forms/reading-form-01/attempts/{aid}/submit", json={"stage": "lower", "answers": {}}).json()["final"]
    assert fin["band"]["band"] == 1 and fin["band"]["cefr"] == "A1"
