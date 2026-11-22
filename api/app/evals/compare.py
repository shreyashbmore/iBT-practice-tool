"""Build eval/results/COMPARISON.md from every eval/results/*.json (the headline table)."""
from __future__ import annotations

import json
import sys

from .run import RESULTS


def main() -> int:
    rows = []
    for f in sorted(RESULTS.glob("*.json")):
        r = json.loads(f.read_text())
        if "vs_gold" not in r:
            continue
        rows.append(r)
    if not rows:
        print("No results yet. Run `python -m app.evals.run --task …` first.")
        return 1
    rows.sort(key=lambda r: (r["task"], -r["vs_gold"]["qwk"]))
    out = ["# Scoring agreement with human raters", "",
           "Gold = consensus of human ratings. Human–human = agreement between two human raters on the same rows "
           "(the practical ceiling).", "",
           "| task | scorer | passes | n | QWK (95% CI) | exact | ±1 | bias | human–human QWK | $/response | p50 latency |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        g = r["vs_gold"]
        ci = f" ({g['qwk_ci95'][0]}–{g['qwk_ci95'][1]})" if "qwk_ci95" in g else ""
        hh = (r.get("human_human") or {}).get("qwk", "—")
        cost = r["cost"]["usd_per_response"]
        demo = " ⚠️demo" if "demo" in r.get("by_source", {}) else ""
        out.append(f"| {r['task']} | {r['provider']} / {r['model']}{demo} | {r['samples']} | {g['n']} | "
                   f"{g['qwk']}{ci} | {g['exact']} | {g['adjacent']} | {g['bias']} | {hh} | "
                   f"{'—' if cost is None else f'${cost:.4f}'} | {r['latency_ms']['p50'] or '—'} ms |")
    (RESULTS / "COMPARISON.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
