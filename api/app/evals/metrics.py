"""Agreement metrics for integer rubric scores (stdlib only)."""
from __future__ import annotations

import math
import random
from collections import Counter


def qwk(a: list[int], b: list[int], lo: int = 0, hi: int = 5) -> float:
    """Quadratic weighted kappa (Cohen 1968). 1 = perfect, 0 = chance agreement."""
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty score lists")
    k = hi - lo + 1
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x - lo][y - lo] += 1
    n = len(a)
    ha, hb = Counter(x - lo for x in a), Counter(y - lo for y in b)
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            exp = ha[i] * hb[j] / n
            num += w * obs[i][j]
            den += w * exp
    return 1.0 if den == 0 else 1 - num / den


def exact(a: list[int], b: list[int]) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a)


def adjacent(a: list[int], b: list[int], tol: int = 1) -> float:
    return sum(abs(x - y) <= tol for x, y in zip(a, b)) / len(a)


def pearson(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 2:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def bias(machine: list[float], human: list[float]) -> float:
    """Mean (machine − human). Positive = machine scores higher."""
    return sum(m - h for m, h in zip(machine, human)) / len(machine)


def mae(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def confusion(a: list[int], b: list[int], lo: int = 0, hi: int = 5) -> list[list[int]]:
    """rows = human score, columns = machine score."""
    k = hi - lo + 1
    m = [[0] * k for _ in range(k)]
    for h, x in zip(a, b):
        m[h - lo][x - lo] += 1
    return m


def bootstrap_ci(a: list[int], b: list[int], stat=qwk, n: int = 1000, seed: int = 7, alpha: float = 0.05,
                 **kw) -> tuple[float, float]:
    """Percentile bootstrap CI over items."""
    rnd = random.Random(seed)
    idx = list(range(len(a)))
    vals = []
    for _ in range(n):
        s = [rnd.choice(idx) for _ in idx]
        try:
            vals.append(stat([a[i] for i in s], [b[i] for i in s], **kw))
        except (ValueError, ZeroDivisionError):
            continue
    vals.sort()
    if not vals:
        return (float("nan"), float("nan"))
    return vals[int(alpha / 2 * len(vals))], vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]


def consensus(r1: int | None, r2: int | None) -> int | None:
    """Gold score from up to two raters: the single rating, or the mean rounded half up."""
    vals = [r for r in (r1, r2) if r is not None]
    if not vals:
        return None
    return int(math.floor(sum(vals) / len(vals) + 0.5))


def summarize(human: list[int], machine: list[int], lo: int = 0, hi: int = 5, ci: bool = True) -> dict:
    out = {
        "n": len(human),
        "qwk": round(qwk(human, machine, lo, hi), 3),
        "exact": round(exact(human, machine), 3),
        "adjacent": round(adjacent(human, machine), 3),
        "pearson": None if (p := pearson(human, machine)) is None else round(p, 3),
        "bias": round(bias(machine, human), 3),
        "mae": round(mae(machine, human), 3),
        "confusion": confusion(human, machine, lo, hi),
    }
    if ci and len(human) >= 10:
        a, b = bootstrap_ci(human, machine, lo=lo, hi=hi)
        out["qwk_ci95"] = [round(a, 3), round(b, 3)]
    return out
