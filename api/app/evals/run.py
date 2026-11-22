"""Run a scorer over the calibration set and report agreement with human raters.

  python -m app.evals.run --task write-an-email [--provider openai --model gpt-4.1-mini]
                          [--samples 3] [--repeats 2] [--limit 50] [--include-demo] [--concurrency 3]

Results: eval/results/<run>.json + .md. Predictions are cached in eval/runs/<run>/ so an interrupted
run resumes and re-running only computes what's missing. Speaking transcripts are cached in
eval/cache/transcripts/ so every LLM provider is compared on identical transcripts.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.features.speech import compute as speech_features
from app.features.text import compute as text_features
from app.providers.llm.litellm_provider import LiteLLMProvider
from app.providers.speech.base import STTOptions, Transcript
from app.providers.speech.factory import get_speech
from app.routers.practice import stimulus_text
from app.scoring import listen_repeat, speaking_judge, writing_judge
from app.secrets.store import get_store, llm_secret
from app.user_settings import load as load_prefs

from .dataset import EVAL_DIR, TASKS, EvalRow, human_agreement, item_index, load_rows
from .metrics import exact, qwk, summarize

RUNS = EVAL_DIR / "runs"
RESULTS = EVAL_DIR / "results"
CACHE = EVAL_DIR / "cache" / "transcripts"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", s.lower()).strip("-")


async def get_transcript(row: EvalRow, verbatim: bool) -> Transcript:
    if row.transcript_json:
        return Transcript(**json.loads(row.transcript_json))
    audio = row.audio_path().read_bytes()
    sp = get_speech()
    key = hashlib.sha256(audio + f"|{sp.stt_model}|{verbatim}".encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        await sp.aclose()
        return Transcript(**json.loads(path.read_text()))
    try:
        mime = {".webm": "audio/webm", ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
                ".ogg": "audio/ogg"}.get(row.audio_path().suffix.lower(), "application/octet-stream")
        t = await sp.transcribe(audio, mime, STTOptions(verbatim=verbatim))
    finally:
        await sp.aclose()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(t.model_dump_json())
    return t


async def predict(row: EvalRow, llm, samples: int, provider: str, model: str) -> dict:
    s, item = item_index()[row.item_id]
    t0 = time.perf_counter()
    if row.task in ("write-an-email", "academic-discussion"):
        text = row.response_text or ""
        r = await writing_judge.judge(llm, item, text, text_features(text, stimulus_text(item)),
                                      samples=samples, provider=provider, model=model)
    elif row.task == "take-an-interview":
        t = await get_transcript(row, verbatim=False)
        r = await speaking_judge.judge(llm, item, s.scene, t, speech_features(t), samples=samples,
                                       provider=provider, model=model)
    else:
        t = await get_transcript(row, verbatim=True)
        lr = listen_repeat.score(item.text, t)
        return {"score": lr.score, "samples": [lr.score], "confidence": "high", "guard": None,
                "cost_usd": 0.0, "latency_ms": int((time.perf_counter() - t0) * 1000), "transcript": lr.transcript}
    return {"score": r.score, "samples": r.samples, "confidence": r.confidence, "guard": r.guard,
            "cost_usd": r.usage.cost_usd, "tokens": r.usage.prompt_tokens + r.usage.completion_tokens,
            "latency_ms": r.latency_ms}


def run_key(task: str, provider: str, model: str, samples: int) -> str:
    if task == "listen-and-repeat":
        th = listen_repeat.DEFAULT.model_dump_json().encode()
        return f"{task}__rules__{hashlib.sha1(th).hexdigest()[:8]}"
    pv = speaking_judge.PROMPT_VERSION if task == "take-an-interview" else writing_judge.PROMPT_VERSION
    return f"{task}__{slug(provider)}-{slug(model)}__s{samples}__p{pv}"


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def report(task: str, key: str, rows: list[EvalRow], preds: dict[tuple[str, int], dict], meta: dict) -> dict:
    first = [(r, preds[(r.id, 0)]) for r in rows if (r.id, 0) in preds]
    human = [r.gold for r, _ in first]
    machine = [p["score"] for _, p in first]
    out: dict = {"run": key, "task": task, **meta, "n_rows": len(rows), "n_scored": len(first),
                 "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if len(first) < 2:
        out["error"] = "not enough scored rows"
        return out
    out["vs_gold"] = summarize(human, machine)
    for rk in ("rater1", "rater2"):
        pairs = [(getattr(r, rk), p["score"]) for r, p in first if getattr(r, rk) is not None]
        if len(pairs) >= 2:
            out[f"vs_{rk}"] = summarize([a for a, _ in pairs], [b for _, b in pairs], ci=False)
    hh = human_agreement([r for r, _ in first])
    if hh:
        out["human_human"] = hh
    # consistency
    spreads = [max(p["samples"]) - min(p["samples"]) for _, p in first if len(p.get("samples") or []) > 1]
    out["consistency"] = {
        "mean_within_run_spread": round(statistics.mean(spreads), 3) if spreads else None,
        "low_confidence_rate": round(sum(p.get("confidence") == "low" for _, p in first) / len(first), 3),
        "guarded_zero_rate": round(sum(bool(p.get("guard")) for _, p in first) / len(first), 3),
    }
    re_pairs = [(preds[(r.id, 0)]["score"], preds[(r.id, 1)]["score"]) for r in rows if (r.id, 1) in preds]
    if len(re_pairs) >= 2:
        a, b = [x for x, _ in re_pairs], [y for _, y in re_pairs]
        out["consistency"]["test_retest"] = {"n": len(re_pairs), "exact": round(exact(a, b), 3),
                                             "qwk": round(qwk(a, b), 3)}
    costs = [p["cost_usd"] for _, p in first if p.get("cost_usd") is not None]
    lat = [p["latency_ms"] for _, p in first if p.get("latency_ms") is not None]
    out["cost"] = {"usd_per_response": round(statistics.mean(costs), 5) if costs else None,
                   "usd_total": round(sum(p.get("cost_usd") or 0 for p in preds.values()), 4)}
    out["latency_ms"] = {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95)}
    by_src: dict[str, dict] = {}
    for src in sorted({r.source for r, _ in first}):
        sub = [(r.gold, p["score"]) for r, p in first if r.source == src]
        if len(sub) >= 2:
            by_src[src] = summarize([a for a, _ in sub], [b for _, b in sub], ci=False)
            by_src[src].pop("confusion")
    out["by_source"] = by_src
    out["worst"] = sorted(({"id": r.id, "gold": r.gold, "machine": p["score"]} for r, p in first),
                          key=lambda d: -abs(d["gold"] - d["machine"]))[:10]
    return out


def to_markdown(res: dict) -> str:
    if "error" in res:
        return f"# {res['run']}\n\n{res['error']}\n"
    g = res["vs_gold"]
    lines = [f"# Eval · {res['task']}", "",
             f"- Run: `{res['run']}` · {res['generated_at']}",
             f"- Scorer: {res.get('provider')} / {res.get('model')} · passes per response: {res.get('samples')}",
             f"- Rows scored: {res['n_scored']} / {res['n_rows']} · sources: {', '.join(res['by_source']) or '—'}",
             "", "## Agreement with human raters (gold = rater consensus)", "",
             "| metric | machine vs gold | human vs human |", "|---|---|---|"]
    hh = res.get("human_human") or {}
    ci = f" (95% CI {g['qwk_ci95'][0]}–{g['qwk_ci95'][1]})" if "qwk_ci95" in g else ""
    for m, label in [("qwk", "QWK"), ("exact", "Exact agreement"), ("adjacent", "Within ±1"),
                     ("pearson", "Pearson r"), ("bias", "Mean bias (machine − human)"), ("mae", "MAE")]:
        lines.append(f"| {label} | {g[m]}{ci if m == 'qwk' else ''} | {hh.get(m, '—')} |")
    lines += ["", f"n = {g['n']} (machine) · {hh.get('n', 0)} double-rated (human–human ceiling)", "",
              "## Confusion matrix (rows = gold 0–5, columns = machine 0–5)", "", "| | " +
              " | ".join(str(i) for i in range(6)) + " |", "|---" * 7 + "|"]
    for i, row in enumerate(g["confusion"]):
        lines.append(f"| **{i}** | " + " | ".join(str(v) for v in row) + " |")
    c = res["consistency"]
    lines += ["", "## Consistency & cost", "",
              f"- Mean spread between scoring passes: {c['mean_within_run_spread']}",
              f"- Low-confidence rate: {c['low_confidence_rate']} · deterministic zero (guards): {c['guarded_zero_rate']}"]
    if "test_retest" in c:
        lines.append(f"- Test–retest (two full runs): exact {c['test_retest']['exact']}, QWK {c['test_retest']['qwk']} "
                     f"(n = {c['test_retest']['n']})")
    lines += [f"- Cost per response: ${res['cost']['usd_per_response']} · total ${res['cost']['usd_total']}",
              f"- Latency p50 {res['latency_ms']['p50']} ms · p95 {res['latency_ms']['p95']} ms", ""]
    if res["by_source"]:
        lines += ["## By source", "", "| source | n | QWK | exact | ±1 | bias |", "|---|---|---|---|---|---|"]
        for s, v in res["by_source"].items():
            lines.append(f"| {s} | {v['n']} | {v['qwk']} | {v['exact']} | {v['adjacent']} | {v['bias']} |")
        lines.append("")
    lines += ["## Largest disagreements", "", "| row | gold | machine |", "|---|---|---|"]
    lines += [f"| {w['id']} | {w['gold']} | {w['machine']} |" for w in res["worst"]]
    if any(src == "demo" for src in res["by_source"]):
        lines += ["", "> ⚠️ Includes `demo` rows written by the developer — not valid evidence of accuracy."]
    return "\n".join(lines) + "\n"


async def main_async(a: argparse.Namespace) -> int:
    prefs = load_prefs()
    provider = a.provider or prefs.llm.provider
    model = a.model or prefs.llm.model
    exclude = None if a.include_demo else {"demo"}
    rows = load_rows(a.task, sources=set(a.source) if a.source else None, exclude_sources=exclude)
    if a.limit:
        rows = rows[: a.limit]
    if not rows:
        print("No rows for this task. Add data to eval/data/ (see eval/README.md) or use --include-demo.")
        return 1
    is_lr = a.task == "listen-and-repeat"
    llm = None
    if not is_lr:
        llm = LiteLLMProvider(provider, model, api_key=get_store().get(llm_secret(provider)),
                              api_base=prefs.llm.api_base if provider == prefs.llm.provider else None)
    key = run_key(a.task, provider, model, a.samples)
    run_dir = RUNS / key
    run_dir.mkdir(parents=True, exist_ok=True)
    pred_file = run_dir / "predictions.jsonl"
    preds: dict[tuple[str, int], dict] = {}
    if pred_file.exists():
        for line in pred_file.read_text().splitlines():
            d = json.loads(line)
            preds[(d["row_id"], d["repeat"])] = d
    todo = [(r, k) for k in range(a.repeats) for r in rows if (r.id, k) not in preds]
    print(f"{key}: {len(rows)} rows × {a.repeats} repeat(s); {len(todo)} to score, {len(preds)} cached")

    sem = asyncio.Semaphore(a.concurrency)
    lock = asyncio.Lock()
    failures = 0

    async def one(r: EvalRow, k: int):
        nonlocal failures
        async with sem:
            try:
                p = await predict(r, llm, a.samples, provider, model)
            except Exception as e:  # keep going; report at the end
                failures += 1
                print(f"  ✗ {r.id}: {e}")
                return
        d = {"row_id": r.id, "repeat": k, **p}
        async with lock:
            preds[(r.id, k)] = d
            with pred_file.open("a") as fh:
                fh.write(json.dumps(d) + "\n")
            print(f"  ✓ {r.id} (repeat {k}) → {p['score']}  [{len(preds)}]")

    await asyncio.gather(*(one(r, k) for r, k in todo))
    meta = {"provider": "rules" if is_lr else provider, "model": "listen-repeat-rules-v1" if is_lr else model,
            "samples": 1 if is_lr else a.samples, "repeats": a.repeats, "failures": failures,
            "rubric_version": None if is_lr else ("speaking-2026.1" if a.task == "take-an-interview" else "writing-2026.1")}
    res = report(a.task, key, rows, preds, meta)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{key}.json").write_text(json.dumps(res, indent=2))
    (RESULTS / f"{key}.md").write_text(to_markdown(res))
    if "vs_gold" in res:
        g = res["vs_gold"]
        print(f"\nQWK {g['qwk']} {g.get('qwk_ci95', '')} · exact {g['exact']} · ±1 {g['adjacent']} · bias {g['bias']}"
              f"\n→ {RESULTS / (key + '.md')}")
    return 0 if failures == 0 else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=TASKS)
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=1, help="2 = also measure test–retest consistency")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--source", action="append", help="only rows from this source (repeatable)")
    ap.add_argument("--include-demo", action="store_true")
    ap.add_argument("--concurrency", type=int, default=3)
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
