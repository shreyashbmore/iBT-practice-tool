"""Tune Listen & Repeat thresholds on human-rated data with a held-out split (no automatic code changes).

  python -m app.evals.tune_lr [--test-share 0.3] [--seed 7] [--include-demo]
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import random
import sys

from app.scoring import listen_repeat as lr

from .dataset import item_index, load_rows
from .metrics import qwk, summarize
from .run import RESULTS, get_transcript

GRID = {
    "low_conf": [0.4, 0.5, 0.6],
    "min_content_for_one_miss": [4, 6, 8],
    "max_minor_for_4": [1, 2, 3],
    "ratio_for_3": [0.4, 0.5, 0.6],
    "ratio_for_2": [0.25, 1 / 3, 0.4],
}


async def main_async(a) -> int:
    rows = load_rows("listen-and-repeat", exclude_sources=None if a.include_demo else {"demo"})
    if len(rows) < 10:
        print(f"Need at least 10 rated Listen & Repeat rows (have {len(rows)}).")
        return 1
    idx = item_index()
    data = [(r, idx[r.item_id][1].text, await get_transcript(r, verbatim=True)) for r in rows]
    rnd = random.Random(a.seed)
    rnd.shuffle(data)
    cut = max(1, int(len(data) * (1 - a.test_share)))
    train, test = data[:cut], data[cut:]

    def evaluate(th, subset):
        h = [r.gold for r, _, _ in subset]
        m = [lr.score(text, t, th).score for _, text, t in subset]
        return h, m

    best, best_q = lr.DEFAULT, -2.0
    for combo in itertools.product(*GRID.values()):
        th = lr.Thresholds(**dict(zip(GRID, combo)))
        if th.ratio_for_2 >= th.ratio_for_3:
            continue
        q = qwk(*evaluate(th, train))
        if q > best_q + 1e-9:
            best, best_q = th, q

    res = {"n_train": len(train), "n_test": len(test), "seed": a.seed,
           "default": {"thresholds": lr.DEFAULT.model_dump(),
                       "train": summarize(*evaluate(lr.DEFAULT, train), ci=False),
                       "test": summarize(*evaluate(lr.DEFAULT, test), ci=False) if len(test) > 1 else None},
           "tuned": {"thresholds": best.model_dump(),
                     "train": summarize(*evaluate(best, train), ci=False),
                     "test": summarize(*evaluate(best, test), ci=False) if len(test) > 1 else None}}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "listen-repeat-tuning.json").write_text(json.dumps(res, indent=2))
    d, t = res["default"], res["tuned"]
    print(f"train n={len(train)}  test n={len(test)}")
    print(f"default  train QWK {d['train']['qwk']}  test QWK {d['test']['qwk'] if d['test'] else '—'}")
    print(f"tuned    train QWK {t['train']['qwk']}  test QWK {t['test']['qwk'] if t['test'] else '—'}")
    print("Tuned thresholds:", json.dumps(best.model_dump()))
    print("Adopt them only if the TEST score improves; then edit Thresholds defaults in "
          "api/app/scoring/listen_repeat.py (this changes the scorer version hash).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test-share", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--include-demo", action="store_true")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
