"""Whole-programme simulation: a population with risk scores, a testing strategy,
and a truth simulator with persistent per-person loads.

Everything here is *synthetic but parameterised*: prevalence, how good the risk
score is (AUC), and the assay's dilution behaviour are explicit knobs.
"""
from __future__ import annotations

import math

import numpy as np

from .core import Assay, Cohort, LoadCohort
from .policy import Greedy, Tree

SQRT2 = math.sqrt(2.0)


def _phi_inv(q):
    # Acklam's rational approximation of the normal quantile (no scipy needed)
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    if q < 0.02425:
        t = math.sqrt(-2 * math.log(q))
        return (((((c[0] * t + c[1]) * t + c[2]) * t + c[3]) * t + c[4]) * t + c[5]) / ((((d[0] * t + d[1]) * t + d[2]) * t + d[3]) * t + 1)
    if q > 1 - 0.02425:
        return -_phi_inv(1 - q)
    t = q - 0.5
    r = t * t
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * t / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def population(rng, N, prev, auc, miscal=(0.0, 1.0)):
    """Draw N people. Binormal risk score with the given AUC; return
    (prior, infected) where prior is the calibrated P(infected | score).

    miscal=(shift, slope) distorts the *reported* prior on the logit scale
    (truth unchanged) to test robustness to a badly calibrated risk model."""
    dprime = SQRT2 * _phi_inv(auc) if auc > 0.5 else 0.0
    inf = rng.random(N) < prev
    x = rng.normal(0, 1, N) + dprime * inf
    logit = math.log(prev / (1 - prev)) + dprime * x - dprime * dprime / 2
    logit = miscal[0] + miscal[1] * logit
    return 1 / (1 + np.exp(-logit)), inf


DEFAULT_EDGES = np.array([0, 0.001, 0.002, 0.004, 0.007, 0.012, 0.02, 0.035, 0.06, 0.1, 0.16, 0.25, 0.4, 0.6, 1.0001])


class Result(dict):
    def finish(self, N, n_inf):
        self["tests_pp"] = self["tests"] / N
        self["sens"] = self["tp"] / max(n_inf, 1)
        self["spec"] = 1 - self["fp"] / max(N - n_inf, 1)
        self["ppv"] = self["tp"] / max(self["tp"] + self["fp"], 1)
        return self


def _test(rng, assay, loads, inf, idx):
    return rng.random() < assay.p_positive(loads[idx][inf[idx]], len(idx))


# ---------------------------------------------------------------- baselines
def run_individual(rng, assay, p, inf, loads, triage=0.0):
    """Test everyone with prior >= triage individually (triage=0: everyone)."""
    r = Result(tests=0, tp=0, fp=0)
    for i in np.flatnonzero(p >= triage):
        r["tests"] += 1
        if _test(rng, assay, loads, inf, np.array([i])):
            r["tp" if inf[i] else "fp"] += 1
    return r.finish(len(p), inf.sum())


def _dorfman_group(rng, assay, inf, loads, idx, r):
    if len(idx) == 1:
        r["tests"] += 1
        if _test(rng, assay, loads, inf, idx):
            r["tp" if inf[idx[0]] else "fp"] += 1
        return
    r["tests"] += 1
    if _test(rng, assay, loads, inf, idx):
        for i in idx:
            r["tests"] += 1
            if _test(rng, assay, loads, inf, np.array([i])):
                r["tp" if inf[i] else "fp"] += 1


def run_dorfman(rng, assay, p, inf, loads, s):
    """Uniform two-stage Dorfman pooling with pool size s, random grouping."""
    r = Result(tests=0, tp=0, fp=0)
    order = rng.permutation(len(p))
    for a in range(0, len(p), s):
        _dorfman_group(rng, assay, inf, loads, order[a : a + s], r)
    return r.finish(len(p), inf.sum())


def dorfman_cost(assay, pbar, s):
    """Model-expected tests per person for Dorfman pool size s at prevalence pbar."""
    if s == 1:
        return 1.0
    k = np.arange(s + 1)
    from math import comb
    pk = np.array([comb(s, j) * pbar**j * (1 - pbar) ** (s - j) for j in k])
    return 1 / s + float(pk @ assay.T[s, : s + 1])


def run_informative_dorfman(rng, assay, p, inf, loads, triage=0.0, max_pool=None):
    """Risk-ordered Dorfman: skip prior < triage, sort the rest by risk, and
    give each risk band the pool size that minimises expected tests."""
    m = max_pool or assay.max_pool
    r = Result(tests=0, tp=0, fp=0)
    idx = np.flatnonzero(p >= triage)
    idx = idx[np.argsort(p[idx])]
    a = 0
    while a < len(idx):
        look = idx[a : a + m]
        pbar = float(p[look].mean())
        s = min(range(1, m + 1), key=lambda s: dorfman_cost(assay, pbar, s))
        _dorfman_group(rng, assay, inf, loads, idx[a : a + s], r)
        a += s
    return r.finish(len(p), inf.sum())


# ---------------------------------------------------------------- MOSAIC
class Mosaic:
    """Risk-stratified adaptive pooling.

    People are binned by prior; each bin is processed in cohorts of size n
    that share one decision tree (a 'card'), built lazily and cached."""

    def __init__(self, assay, policy_factory=None, n=12, edges=DEFAULT_EDGES, tau_neg=0.01, tau_pos=0.8, eps=1e-9, q=0, max_states=40_000):
        self.assay, self.n, self.edges = assay, n, np.asarray(edges)
        self.policy_factory = policy_factory or (lambda: Greedy(tau_neg, tau_pos))
        self.eps, self.q, self.max_states = eps, q, max_states
        self.trees = {}
        self.sizes = {}

    def cohort(self, size, pbar):
        if self.q == 0:
            return Cohort([pbar] * size, self.assay, eps=self.eps)
        return LoadCohort([pbar] * size, self.assay, q=self.q, max_states=self.max_states)

    def size_for(self, stratum, pbar):
        """Largest cohort size <= n whose state space fits the budget."""
        if stratum not in self.sizes:
            n = self.n
            while n > 1:
                try:
                    self.cohort(n, pbar); break
                except MemoryError:
                    n -= 1
            self.sizes[stratum] = n
        return self.sizes[stratum]

    def tree(self, stratum, size, pbar):
        key = (stratum, size)
        if key not in self.trees:
            self.trees[key] = Tree(self.cohort(size, pbar), self.policy_factory())
        return self.trees[key]

    def run(self, rng, p, inf, loads, strata_p=None):
        """strata_p: optional per-stratum prior to use (else the bin mean of p)."""
        r = Result(tests=0, tp=0, fp=0, depth=0.0, cohorts=0, max_depth=0)
        b = np.searchsorted(self.edges, p, side="right") - 1
        for s in np.unique(b):
            idx = np.flatnonzero(b == s)
            pbar = float(p[idx].mean()) if strata_p is None else strata_p[s]
            idx = rng.permutation(idx)
            n = self.size_for(int(s), pbar)
            for a in range(0, len(idx), n):
                g = idx[a : a + n]
                t, calls, d = self.tree(int(s), len(g), pbar).run(rng, inf[g], loads[g])
                r["tests"] += t
                r["tp"] += int((calls & inf[g]).sum())
                r["fp"] += int((calls & ~inf[g]).sum())
                r["depth"] += d
                r["cohorts"] += 1
                r["max_depth"] = max(r["max_depth"], d)
        r["mean_rounds"] = r["depth"] / max(r["cohorts"], 1)
        return r.finish(len(p), inf.sum())


SCENARIOS = {
    # name: (prevalence, risk-score AUC, assay kwargs, max_pool)
    "tb_triage": dict(prev=0.10, auc=0.85, load=dict(mu=4.0, sigma=1.4, lod=2.2, slope=0.3), sp=0.99, max_pool=8),
    "community": dict(prev=0.01, auc=0.85, load=dict(mu=4.0, sigma=1.4, lod=2.2, slope=0.3), sp=0.99, max_pool=16),
    "no_risk_info": dict(prev=0.03, auc=0.5, load=dict(mu=4.0, sigma=1.4, lod=2.2, slope=0.3), sp=0.99, max_pool=16),
    "pcr_high_load": dict(prev=0.02, auc=0.75, load=dict(mu=6.0, sigma=1.8, lod=2.5, slope=0.3), sp=0.998, max_pool=16),
}


def make_assay(sc):
    return Assay.from_load(sp=sc["sp"], max_pool=sc["max_pool"], **sc["load"])
