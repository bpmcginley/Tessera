"""Policies (what to test next) and exact evaluation of the resulting decision tree."""
from __future__ import annotations

import numpy as np

from .core import Cohort, mask_of, _POP16


class Greedy:
    """Information-greedy adaptive pooling.

    At every step, pool the subset (from a structured candidate family) whose
    outcome carries the most information about the cohort's infection state.
    A person is *resolved* once they are confidently positive (posterior >=
    tau_pos) or no longer worth a test: the chance that they are infected AND
    an individual test would catch it has fallen below tau_neg * se.  (With a
    load-blind decoder this is just "posterior < tau_neg".)  Stop when everyone
    is resolved.

    Candidate family: sort unresolved people by posterior, take every
    contiguous window up to max_pool ("windows"), or every subset ("all",
    small cohorts only, used to check the window family loses nothing).
    """

    def __init__(self, tau_neg=0.01, tau_pos=0.9, max_pool=None, cand="windows", size_penalty=1e-6, call_thr=None):
        self.tau_neg, self.tau_pos = tau_neg, tau_pos
        self.call_thr = min(0.5, tau_pos) if call_thr is None else call_thr
        self.max_pool, self.cand, self.size_penalty = max_pool, cand, size_penalty

    # costs implied by the thresholds (one test costs 1)
    def costs(self, assay):
        c_fn = 1.0 / (self.tau_neg * assay.se1)
        c_fp = 1.0 / ((1 - self.tau_pos) * max(assay.sp, 0.5))
        return c_fn, c_fp

    def unresolved(self, marg, catch):
        return np.flatnonzero((catch > self.tau_neg * self._se1) & (marg < self.tau_pos))

    def candidates(self, cohort, marg, U):
        m = min(self.max_pool or cohort.assay.max_pool, cohort.assay.max_pool, len(U))
        if self.cand == "all":
            base = mask_of(U)
            subs = np.arange(1, 1 << cohort.n, dtype=np.uint32)
            subs = subs[(subs & ~np.uint32(base)) == 0]
            return subs[_POP16[subs] <= m]
        order = U[np.argsort(marg[U], kind="stable")]
        bit = (1 << order).astype(np.int64)
        cs = np.concatenate([[0], np.cumsum(bit)])
        out = [cs[a + s] - cs[a] for s in range(1, m + 1) for a in range(0, len(order) - s + 1)]
        return np.array(out, dtype=np.uint32)

    def ranked(self, cohort, w, marg=None):
        """Candidate pools sorted best-first with their scores."""
        marg = cohort.marginals(w) if marg is None else marg
        self._se1 = cohort.assay.se1
        U = self.unresolved(marg, cohort.catchable(w))
        if len(U) == 0:
            return np.array([], dtype=np.uint32), np.array([])
        C = self.candidates(cohort, marg, U)
        ig, _ = cohort.info_gain(w, C)
        score = ig - self.size_penalty * _POP16[C]
        o = np.argsort(-score, kind="stable")
        return C[o], score[o]

    def act(self, cohort, w, hist=()):
        C, _ = self.ranked(cohort, w)
        return int(C[0]) if len(C) else 0

    def declare(self, marg):
        """Final call per person: positive iff posterior >= call_thr."""
        return marg >= self.call_thr


class Fixed:
    """A hand-specified procedure (used for classical baselines).

    `fn(cohort, hist)` -> pool mask or 0 to stop; `decl(cohort, hist)` -> bool
    array of final calls.  hist is a tuple of (mask, outcome)."""

    def __init__(self, fn, decl):
        self.fn, self.decl = fn, decl

    def act(self, cohort, w, hist=()):
        return self.fn(cohort, hist)


def dorfman(pool_size):
    """Classic two-stage Dorfman: pool, then retest each member of positive pools."""

    def plan(n):
        pools = [list(range(a, min(a + pool_size, n))) for a in range(0, n, pool_size)]
        return pools

    def fn(cohort, hist):
        seq = _dorfman_seq(plan(cohort.n), hist)
        return seq[0]

    def decl(cohort, hist):
        return _dorfman_seq(plan(cohort.n), hist)[1]

    return Fixed(fn, decl)


def _dorfman_seq(pools, hist):
    """Replay history against the Dorfman plan; return (next mask or 0, calls)."""
    n = max(max(p) for p in pools) + 1
    calls = np.zeros(n, dtype=bool)
    h = list(hist)
    pos = 0
    for p in pools:
        if len(p) == 1:
            if pos >= len(h):
                return mask_of(p), calls
            calls[p[0]] = bool(h[pos][1]); pos += 1
            continue
        if pos >= len(h):
            return mask_of(p), calls
        out = h[pos][1]; pos += 1
        if out:
            for i in p:
                if pos >= len(h):
                    return 1 << i, calls
                calls[i] = bool(h[pos][1]); pos += 1
    return 0, calls


class Tree:
    """Lazily built decision tree of a policy on one cohort (cached per history)."""

    def __init__(self, cohort: Cohort, policy, max_depth=60):
        self.cohort, self.policy, self.max_depth = cohort, policy, max_depth
        self.nodes = {}

    def node(self, hist=()):
        nd = self.nodes.get(hist)
        if nd is None:
            c = self.cohort
            w = self.belief(hist)
            a = self.policy.act(c, w, hist) if len(hist) < self.max_depth else 0
            marg = c.marginals(w)
            nd = dict(a=a, marg=marg)
            if a == 0:
                nd["calls"] = self.policy.decl(c, hist) if isinstance(self.policy, Fixed) else self.policy.declare(marg)
                if not isinstance(self.policy, Fixed) and len(hist) >= self.max_depth:
                    nd["calls"] = marg >= 0.5
            else:
                nd["ppos"] = float(c.lik_pos([a])[0] @ w)
            self.nodes[hist] = nd
        return nd

    def belief(self, hist):
        """Posterior after a history, by replay from the prior (nothing cached)."""
        c = self.cohort
        w = c.w0
        if hist:
            L = c.lik_pos([m for m, _ in hist])
            for row, (_, o) in zip(L, hist):
                w = w * (row if o else 1 - row)
            tot = w.sum()
            w = w / tot if tot > 0 else c.w0
        return w

    def evaluate(self, prune=1e-9):
        """Exact expected tests / errors under the model by full expansion."""
        res = dict(tests=0.0, fn=0.0, fp=0.0, depth=0.0, max_depth=0, leaves=0, pruned=0.0)
        stack = [((), 1.0)]
        while stack:
            hist, reach = stack.pop()
            nd = self.node(hist)
            if nd["a"] == 0 or reach < prune:
                marg = nd["marg"] if "marg" in nd else self.cohort.marginals(self.belief(hist))
                calls = nd["calls"] if "calls" in nd else marg >= 0.5
                res["fn"] += reach * float(marg[~calls].sum())
                res["fp"] += reach * float((1 - marg[calls]).sum())
                res["depth"] += reach * len(hist)
                res["max_depth"] = max(res["max_depth"], len(hist))
                res["leaves"] += 1
                if nd["a"] != 0:
                    res["pruned"] += reach
                continue
            res["tests"] += reach
            pp = nd["ppos"]
            if pp > 0:
                stack.append((hist + ((nd["a"], 1),), reach * pp))
            if pp < 1:
                stack.append((hist + ((nd["a"], 0),), reach * (1 - pp)))
        n, tot = self.cohort.n, float(self.cohort.priors.sum())
        res["tests_pp"] = res["tests"] / n
        res["sens"] = 1 - res["fn"] / tot if tot > 0 else 1.0
        res["spec"] = 1 - res["fp"] / (n - tot)
        return res

    def values(self, c_fn, c_fp, prune=1e-7):
        """Exact cost-to-go J = tests + c_fn*FN + c_fp*FP at every node.
        Returns (J_root, [(marginals, J, reach), ...])."""
        out = []

        def rec(hist, reach):
            nd = self.node(hist)
            marg = nd["marg"]
            if nd["a"] == 0 or reach < prune:
                calls = nd["calls"] if "calls" in nd else self.policy.declare(marg)
                j = c_fn * float(marg[~calls].sum()) + c_fp * float((1 - marg[calls]).sum())
            else:
                pp = nd["ppos"]
                j = 1.0
                if pp > 0:
                    j += pp * rec(hist + ((nd["a"], 1),), reach * pp)
                if pp < 1:
                    j += (1 - pp) * rec(hist + ((nd["a"], 0),), reach * (1 - pp))
            out.append((marg, j, reach))
            return j

        return rec((), 1.0), out

    def j_from(self, hist, c_fn, c_fp, prune=1e-4):
        """Exact cost-to-go of this tree's policy starting after `hist` (memoised)."""
        memo = self.__dict__.setdefault("_jmemo", {})

        def rec(h, reach):
            if reach >= 1 and h in memo:
                return memo[h]
            nd = self.node(h)
            marg = nd["marg"]
            if nd["a"] == 0 or reach < prune:
                calls = nd["calls"] if "calls" in nd else self.policy.declare(marg)
                j = c_fn * float(marg[~calls].sum()) + c_fp * float((1 - marg[calls]).sum())
            else:
                pp = nd["ppos"]
                j = 1.0 + (pp * rec(h + ((nd["a"], 1),), reach * pp) if pp > 0 else 0.0) + ((1 - pp) * rec(h + ((nd["a"], 0),), reach * (1 - pp)) if pp < 1 else 0.0)
            if reach >= 1:
                memo[h] = j
            return j

        return rec(hist, 1.0)

    def run(self, rng, infected, loads):
        """Execute on a true cohort (persistent loads). Returns (n_tests, calls, depth)."""
        a = self.cohort.assay
        hist = ()
        while True:
            nd = self.node(hist)
            if nd["a"] == 0:
                return len(hist), nd["calls"], len(hist)
            mem = [i for i in range(self.cohort.n) if (nd["a"] >> i) & 1]
            inf = [loads[i] for i in mem if infected[i]]
            out = int(rng.random() < a.p_positive(inf, len(mem)))
            hist = hist + ((nd["a"], out),)


def entropy_bound(priors, assay=None):
    """Lower bound on expected tests for zero-error identification: sum of H(p_i) bits."""
    from .core import h2
    return float(np.sum(h2(np.asarray(priors))))


class Rollout:
    """Exact one-step policy improvement over a base policy.

    On the first `horizon` steps, take the base policy's top-k candidate pools, compute for each
    the *exact* expected cost of "test this pool, then follow the base policy",
    and pick the cheapest -- or stop if stopping is cheaper.  By the policy
    improvement theorem this is never worse than the base under the model."""

    def __init__(self, base, c_fn, c_fp, topk=4, prune=1e-3, max_depth=30, horizon=3):
        self.horizon = horizon
        self.base, self.c_fn, self.c_fp, self.topk, self.prune, self.max_depth = base, c_fn, c_fp, topk, prune, max_depth
        self.theta = c_fp / (c_fn + c_fp)
        self._trees = {}

    def declare(self, marg):
        return marg >= self.theta

    def act(self, cohort, w, hist=()):
        if len(hist) >= self.horizon:  # lookahead only on the first steps; base policy after
            return self.base.act(cohort, w, hist)
        t = self._trees.get(id(cohort))
        if t is None:
            t = self._trees[id(cohort)] = Tree(cohort, self.base, max_depth=self.max_depth)
        marg = cohort.marginals(w)
        best_j = float(np.minimum(self.c_fn * marg, self.c_fp * (1 - marg)).sum())
        best = 0
        C, _ = self.base.ranked(cohort, w, marg)
        if len(C) == 0:
            return 0
        C = C[: self.topk]
        pp = cohort.lik_pos(C) @ w
        for c, p in zip(C, pp):
            c = int(c)
            j = 1.0
            if p > 0:
                j += p * t.j_from(hist + ((c, 1),), self.c_fn, self.c_fp, self.prune)
            if p < 1 and j < best_j:
                j += (1 - p) * t.j_from(hist + ((c, 0),), self.c_fn, self.c_fp, self.prune)
            if j < best_j - 1e-9:
                best_j, best = j, c
        return best
