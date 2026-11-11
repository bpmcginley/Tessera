"""Correctness checks: closed forms, brute-force Bayes, and model-vs-simulation agreement."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.core import Assay, Cohort, LoadCohort, h2
from mosaic.policy import Greedy, Tree, dorfman


def test_dorfman_closed_form():
    for p, s in [(0.05, 5), (0.1, 4), (0.02, 8)]:
        r = Tree(Cohort([p] * s, Assay.ideal(16), eps=0), dorfman(s)).evaluate(prune=0)
        assert abs(r["tests_pp"] - (1 / s + 1 - (1 - p) ** s)) < 1e-12
        assert r["sens"] == 1 and r["spec"] == 1


def test_bayes_update_bruteforce():
    rng = np.random.default_rng(0)
    pri = rng.uniform(0.02, 0.4, 5)
    a = Assay.simple(0.9, 0.97, 8)
    c = Cohort(pri, a, eps=0)
    w, mask = c.w0, 0b01101
    w, _ = c.update(w, mask, 1)
    num = np.zeros(5); den = 0.0
    for st in range(32):
        x = [(st >> i) & 1 for i in range(5)]
        pr = np.prod([pri[i] if x[i] else 1 - pri[i] for i in range(5)])
        k = sum(x[i] for i in (0, 2, 3))
        lik = 0.9 if k else 0.03
        den += pr * lik; num += pr * lik * np.array(x)
    assert np.allclose(c.marginals(w), num / den)


def test_greedy_near_entropy_and_lossless():
    p, n = 0.05, 12
    r = Tree(Cohort([p] * n, Assay.ideal(16), eps=0), Greedy(1e-9, 1 - 1e-9)).evaluate()
    assert r["sens"] > 1 - 1e-6 and r["spec"] > 1 - 1e-6
    assert h2(p) <= r["tests_pp"] < 1.06 * h2(p)          # never beats Shannon; within 6%


def test_model_matches_simulation():
    """Exact tree evaluation must agree with Monte Carlo when the simulator obeys the model."""
    a = Assay.simple(0.9, 0.98, 8)
    c = Cohort([0.08] * 6, a)
    t = Tree(c, Greedy(0.02, 0.9), max_depth=20); ex = t.evaluate(prune=0)
    rng = np.random.default_rng(1); tests = fn = tot = 0
    for _ in range(20000):
        inf = rng.random(6) < 0.08
        k, calls, _ = t.run(rng, inf, np.zeros(6))
        tests += k; fn += (inf & ~calls).sum(); tot += inf.sum()
    assert abs(tests / 20000 / 6 - ex["tests_pp"]) < 0.01
    assert abs((1 - fn / tot) - ex["sens"]) < 0.02


def test_load_cohort_reduces_to_table_when_one_class():
    a = Assay.from_load(4.0, 1.4, 2.2, 0.3, 0.99, 8)
    lc = LoadCohort([0.05] * 6, a, q=1, eps=0)
    L = lc.lik_pos([0b000001])[0]
    one = (lc.states[:, 0] > 0)
    assert np.allclose(L[one], a.T[1, 1], atol=5e-3) and np.allclose(L[~one], 0.01)
    assert abs(lc.w0.sum() - 1) < 1e-12 and np.allclose(lc.marginals(lc.w0), 0.05)


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
