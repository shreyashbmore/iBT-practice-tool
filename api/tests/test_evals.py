import csv
import json
import shutil

import pytest

from app.config import ROOT_DIR
from app.evals import compare, dataset, run, tune_lr
from app.providers.llm.base import Usage
from app.scoring.writing_judge import FullJudgement, ScoreOnly


@pytest.fixture
def eval_dir(tmp_path, monkeypatch):
    d = tmp_path / "eval"
    (d / "data").mkdir(parents=True)
    shutil.copy(ROOT_DIR / "eval" / "data" / "demo.csv", d / "data" / "demo.csv")
    monkeypatch.setattr(dataset, "EVAL_DIR", d)
    monkeypatch.setattr(run, "RUNS", d / "runs")
    monkeypatch.setattr(run, "RESULTS", d / "results")
    monkeypatch.setattr(run, "CACHE", d / "cache")
    monkeypatch.setattr(compare, "RESULTS", d / "results")
    monkeypatch.setattr(tune_lr, "RESULTS", d / "results")
    dataset.prompt_sets.cache_clear()
    yield d
    dataset.prompt_sets.cache_clear()


class EchoLLM:
    """Scores emails by length so the run has realistic variation; counts calls."""
    calls = 0

    def __init__(self, *a, **kw):
        pass

    async def complete_json(self, messages, schema, *, temperature=0.0, max_tokens=2048):
        EchoLLM.calls += 1
        text = messages[1]["content"].split("<response>")[1]
        n = len(text.split())
        score = 5 if n > 90 else 4 if n > 50 else 3 if n > 30 else 2 if n > 12 else 1
        u = Usage(prompt_tokens=100, completion_tokens=20, cost_usd=0.001)
        if schema is ScoreOnly:
            return ScoreOnly(score=score, rationale="x"), u
        return FullJudgement.model_validate({"dimensions": [], "score": score, "rationale": "x", "errors": [],
                                             "next_steps": [], "improved_version": "x"}), u


def test_dataset_validation(eval_dir):
    rows = dataset.load_rows(exclude_sources=None)
    assert {r.task for r in rows} == {"write-an-email", "listen-and-repeat"}
    assert dataset.load_rows(exclude_sources={"demo"}) == []
    bad = eval_dir / "data" / "bad.csv"
    with bad.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(dataset.COLUMNS)
        w.writerow(["x1", "write-an-email", "no-such-item", "hi", "", "", "3", "", "self", ""])
        w.writerow(["x2", "take-an-interview", "interview-01-q1", "", "missing.webm", "", "9", "", "self", ""])
    with pytest.raises(ValueError) as e:
        dataset.load_rows()
    msg = str(e.value)
    assert "no-such-item" in msg and "ratings must be 0–5" in msg


def test_writing_run_resume_and_compare(eval_dir, monkeypatch):
    monkeypatch.setattr(run, "LiteLLMProvider", EchoLLM)
    EchoLLM.calls = 0
    args = ["--task", "write-an-email", "--provider", "openai", "--model", "fake-1", "--include-demo",
            "--samples", "3", "--repeats", "2"]
    assert run.main(args) == 0
    first_calls = EchoLLM.calls
    assert first_calls == 5 * 3 * 2            # 6 rows, blank one is guarded (no LLM), × 3 passes × 2 repeats
    key = run.run_key("write-an-email", "openai", "fake-1", 3)
    res = json.loads((eval_dir / "results" / f"{key}.json").read_text())
    assert res["n_scored"] == 6 and res["vs_gold"]["n"] == 6
    assert res["human_human"]["n"] == 6
    assert res["consistency"]["test_retest"]["exact"] == 1.0
    assert res["consistency"]["guarded_zero_rate"] == pytest.approx(1 / 6, abs=1e-3)
    assert "⚠️" in (eval_dir / "results" / f"{key}.md").read_text()      # demo warning shown
    assert run.main(args) == 0 and EchoLLM.calls == first_calls          # resumed from cache
    assert compare.main() == 0
    table = (eval_dir / "results" / "COMPARISON.md").read_text()
    assert "openai / fake-1 ⚠️demo" in table


def test_lr_run_and_tuning(eval_dir):
    # add enough synthetic L&R rows for tuning
    target = "the library is open every day until midnight".split()
    with (eval_dir / "data" / "extra.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(dataset.COLUMNS)
        for i in range(12):
            said = target[: max(1, len(target) - i)]
            words = [{"word": x, "start": k * 0.4, "end": k * 0.4 + 0.3, "confidence": 0.9} for k, x in enumerate(said)]
            gold = 5 if i == 0 else 4 if i == 1 else 3 if i <= 3 else 2 if i <= 5 else 1
            w.writerow([f"syn-{i}", "listen-and-repeat", "lr-01-02", "", "",
                        json.dumps({"text": " ".join(said), "words": words}), gold, "", "synthetic", ""])
    assert run.main(["--task", "listen-and-repeat"]) == 0
    assert tune_lr.main(["--seed", "1"]) == 0
    t = json.loads((eval_dir / "results" / "listen-repeat-tuning.json").read_text())
    assert t["n_train"] + t["n_test"] == 12
    assert t["tuned"]["train"]["qwk"] >= t["default"]["train"]["qwk"]
