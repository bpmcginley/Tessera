"""Recursive self-improvement: fitted policy iteration on exact decision trees.

Generation 0 is the information-greedy policy.  We expand its trees exactly,
read off the true cost-to-go J at every node, and fit a small additive value
function  V(belief) ~ sum_i g(marginal_i).  Generation k+1 then picks, at each
step, the pool minimising  1 + E[V_k(next belief)]  (one-step lookahead on the
previous generation's value) and stops when stopping is cheaper.  Each
generation is scored *exactly* (no Monte Carlo noise), so improvement is a
measured fact, not a guess.
"""
from __future__ import annotations

import numpy as np

from .core import _POP16
from .policy import Greedy

KNOTS = np.linspace(-9.0, 7.0, 33)  # logit(marginal) grid


def _logit(m):
    m = np.clip(m, 1e-12, 1 - 1e-12)
    return np.log(m / (1 - m))


def _hat(m):
    """Linear-interpolation basis: array [..., n] -> [..., n, K] (two nonzeros each)."""
    x = np.clip((_logit(m) - KNOTS[0]) / (KNOTS[1] - KNOTS[0]), 0, len(KNOTS) - 1 - 1e-9)
    i = x.astype(int)
    f = x - i
    B = np.zeros(m.shape + (len(KNOTS),))
    np.put_along_axis(B, i[..., None], (1 - f)[..., None], -1)
    np.put_along_axis(B, (i + 1)[..., None], f[..., None], -1)
    return B


class ValueGreedy(Greedy):
    """One-step lookahead on a fitted additive value function g."""

    def __init__(self, c_fn, c_fp, g, max_pool=None, r_min=0.02, tau_pos_cap=None):
        self.c_fn, self.c_fp, self.g = c_fn, c_fp, np.asarray(g)
        self.max_pool, self.r_min, self.cand = max_pool, r_min, "windows"
        self.theta = c_fp / (c_fn + c_fp)

    def stop_risk(self, m):
        return np.minimum(self.c_fn * m, self.c_fp * (1 - m))

    def V(self, m):
        x = np.clip((_logit(m) - KNOTS[0]) / (KNOTS[1] - KNOTS[0]), 0, len(KNOTS) - 1 - 1e-9)
        i = x.astype(int)
        f = x - i
        g = self.g[i] * (1 - f) + self.g[i + 1] * f
        return np.minimum(np.maximum(g, 0), self.stop_risk(m)).sum(-1)

    def unresolved(self, marg, catch=None):
        return np.flatnonzero(self.stop_risk(marg) > self.r_min)

    def act(self, cohort, w, hist=()):
        marg = cohort.marginals(w)
        U = self.unresolved(marg)
        if len(U) == 0:
            return 0
        C = self.candidates(cohort, marg, U)
        L = cohort.lik_pos(C)
        ppos = L @ w
        Lw = L * w
        mpos = (Lw @ cohort.bits) / np.maximum(ppos, 1e-300)[:, None]
        mneg = ((w - Lw) @ cohort.bits) / np.maximum(1 - ppos, 1e-300)[:, None]
        score = 1 + ppos * self.V(np.clip(mpos, 0, 1)) + (1 - ppos) * self.V(np.clip(mneg, 0, 1)) + 1e-6 * _POP16[C]
        b = int(np.argmin(score))
        return 0 if score[b] >= self.stop_risk(marg).sum() else int(C[b])

    def declare(self, marg):
        return marg > self.theta


def fit_g(samples, c_fn, c_fp, ridge=1e-3):
    """Weighted ridge regression of exact cost-to-go on the additive basis,
    shrunk toward the stop risk where data are thin."""
    M = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    wt = np.sqrt(np.array([s[2] for s in samples]))
    X = _hat(M).sum(1)
    pk = 1 / (1 + np.exp(-KNOTS))
    g0 = np.minimum(c_fn * pk, c_fp * (1 - pk))
    A = (X * wt[:, None]).T @ (X * wt[:, None]) + ridge * np.eye(len(KNOTS))
    b = (X * wt[:, None]).T @ (y * wt) + ridge * g0
    g = np.linalg.solve(A, b)
    return np.clip(g, 0, g0)
