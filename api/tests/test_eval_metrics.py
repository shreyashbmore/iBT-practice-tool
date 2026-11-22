import pytest

from app.evals.metrics import adjacent, bootstrap_ci, consensus, exact, pearson, qwk, summarize


def test_qwk_known_values():
    assert qwk([0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5]) == pytest.approx(1.0)
    # sklearn.metrics.cohen_kappa_score([1,2,3,4],[1,2,4,4],weights="quadratic") = 0.91666…
    assert qwk([1, 2, 3, 4], [1, 2, 4, 4]) == pytest.approx(0.916667, abs=1e-5)
    # sklearn: cohen_kappa_score([0,1,2,3],[3,2,1,0],weights="quadratic") = -1.0
    assert qwk([0, 1, 2, 3], [3, 2, 1, 0]) == pytest.approx(-1.0)
    assert qwk([3, 3, 3], [3, 3, 3]) == 1.0          # degenerate: no disagreement possible


def test_agreement_and_consensus():
    h, m = [1, 2, 3, 4, 5], [1, 3, 3, 2, 5]
    assert exact(h, m) == 0.6 and adjacent(h, m) == 0.8
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert consensus(3, 4) == 4 and consensus(3, None) == 3 and consensus(None, None) is None


def test_summary_and_ci():
    h = [0, 1, 2, 3, 4, 5] * 3
    m = [0, 1, 2, 3, 4, 5] * 2 + [1, 1, 2, 4, 4, 5]
    s = summarize(h, m)
    assert s["n"] == 18 and 0.8 < s["qwk"] < 1 and s["bias"] > 0
    lo, hi = s["qwk_ci95"]
    assert lo <= s["qwk"] <= hi
    assert sum(map(sum, s["confusion"])) == 18
    assert bootstrap_ci([1, 2], [1, 2], n=20)[0] <= 1


def test_qwk_matches_sklearn_if_available():
    sk = pytest.importorskip("sklearn.metrics")
    import random
    r = random.Random(1)
    for _ in range(100):
        a = [r.randint(0, 5) for _ in range(30)]
        b = [min(5, max(0, x + r.randint(-2, 2))) for x in a]
        assert qwk(a, b) == pytest.approx(sk.cohen_kappa_score(a, b, weights="quadratic"), abs=1e-9)
