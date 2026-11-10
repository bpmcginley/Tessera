"""MOSAIC core: exact Bayesian engine for adaptive pooled (group) testing.

Model
-----
A cohort of n people, person i infected with independent prior p_i (from a
risk score). A test takes a pool (subset) of size s <= max_pool and returns
positive/negative.  The assay is described by a table

    T[s, k] = P(test positive | k infected samples in a pool of size s)

which captures false positives (k = 0) and dilution (sensitivity falling
with s).  The engine keeps the exact posterior over all 2^n infection states
(bitmasks), so every decision and every reported error rate is exact under
the model -- no approximations in the decoder.
"""
from __future__ import annotations

import numpy as np

_POP16 = np.array([bin(i).count("1") for i in range(1 << 16)], dtype=np.uint8)


def h2(p):
    """Binary entropy in bits (vectorised, safe at 0 and 1)."""
    p = np.asarray(p, dtype=float)
    q = 1.0 - p
    with np.errstate(divide="ignore", invalid="ignore"):
        out = -(np.where(p > 0, p * np.log2(p), 0.0) + np.where(q > 0, q * np.log2(q), 0.0))
    return out


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class Assay:
    """Binary assay with false positives and dilution.

    T[s, k] = P(positive | k infected in pool of size s).
    If `load` is given, the *truth simulator* draws each infected person's
    log10 load once (persistent across tests) and uses the load model
    directly; the decoder still only sees the averaged table T.  That gap
    is a deliberate, honest model mismatch.
    """

    def __init__(self, T, sp, load=None, name="assay"):
        self.T = np.asarray(T, dtype=float)
        self.max_pool = self.T.shape[0] - 1
        self.sp = sp
        self.load = load
        self.name = name

    # ---- constructors -------------------------------------------------
    @classmethod
    def simple(cls, se, sp, max_pool, name=None):
        """No dilution: any pool containing >=1 infected is positive w.p. se."""
        T = np.zeros((max_pool + 1, max_pool + 1))
        T[:, 0] = 1 - sp
        T[:, 1:] = se
        return cls(T, sp, None, name or f"simple(se={se},sp={sp})")

    @classmethod
    def ideal(cls, max_pool):
        return cls.simple(1.0, 1.0, max_pool, "ideal")

    @classmethod
    def from_load(cls, mu, sigma, lod, slope, sp, max_pool, n_mc=200_000, seed=1, name=None):
        """Dilution from a viral/bacterial load model.

        log10 load of an infected sample ~ N(mu, sigma).  A pool of size s
        holds the mean of its members' loads (equal volumes); detection
        probability is sigmoid((log10(pool load) - lod) / slope).
        """
        rng = np.random.default_rng(seed)
        L = 10.0 ** rng.normal(mu, sigma, size=(n_mc, max_pool))
        csum = np.cumsum(L, axis=1)  # csum[:, k-1] = total load of k infected
        T = np.zeros((max_pool + 1, max_pool + 1))
        T[:, 0] = 1 - sp
        for s in range(1, max_pool + 1):
            for k in range(1, s + 1):
                det = _sigmoid((np.log10(csum[:, k - 1] / s) - lod) / slope)
                T[s, k] = 1 - sp * (1 - det.mean())
        load = dict(mu=mu, sigma=sigma, lod=lod, slope=slope)
        return cls(T, sp, load, name or f"load(mu={mu},sigma={sigma},lod={lod})")

    def classes(self, q, n_mc=400_000, seed=2):
        """Discretise an infected person's (persistent) load into q classes.

        Returns (class_prob[q], d[q, max_pool+1]) with d[c, s] = P(a class-c
        sample alone triggers a pool of size s).  Edges are spread over the
        range where dilution actually changes detectability."""
        key = ("classes", q)
        if key not in self.__dict__:
            ld, m = self.load, self.max_pool
            rng = np.random.default_rng(seed)
            L = rng.normal(ld["mu"], ld["sigma"], n_mc)
            edges = np.linspace(ld["lod"] - 0.5, ld["lod"] + np.log10(m) + 0.5, q - 1) if q > 1 else np.array([])
            c = np.searchsorted(edges, L)
            cp = np.bincount(c, minlength=q) / n_mc
            d = np.zeros((q, m + 1))
            for s in range(1, m + 1):
                det = _sigmoid((L - np.log10(s) - ld["lod"]) / ld["slope"])
                d[:, s] = np.bincount(c, weights=det, minlength=q) / np.maximum(np.bincount(c, minlength=q), 1)
            self.__dict__[key] = (cp, d)
        return self.__dict__[key]

    # ---- truth simulator ---------------------------------------------
    def draw_loads(self, rng, n):
        if self.load is None:
            return np.zeros(n)
        return rng.normal(self.load["mu"], self.load["sigma"], size=n)

    def p_positive(self, loads_of_infected, s):
        """True P(positive) for a pool of size s whose infected members have
        the given log10 loads (persistent per person)."""
        k = len(loads_of_infected)
        if k == 0:
            return 1 - self.sp
        if self.load is None:
            return self.T[s, k]
        tot = np.log10(np.sum(10.0 ** np.asarray(loads_of_infected)) / s)
        det = _sigmoid((tot - self.load["lod"]) / self.load["slope"])
        return 1 - self.sp * (1 - det)

    @property
    def se1(self):
        return self.T[1, 1]


class Cohort:
    """Exact posterior over infection states of n people (n <= 16)."""

    def __init__(self, priors, assay, eps=1e-9):
        priors = np.asarray(priors, dtype=float)
        n = len(priors)
        assert 1 <= n <= 16
        self.n, self.priors, self.assay = n, priors, assay
        states = np.arange(1 << n, dtype=np.uint32)
        bits = ((states[:, None] >> np.arange(n)) & 1).astype(bool)
        logp = np.where(bits, np.log(np.clip(priors, 1e-300, 1)), np.log(np.clip(1 - priors, 1e-300, 1))).sum(1)
        w = np.exp(logp)
        if eps > 0:  # drop the negligible tail of many-infected states
            order = np.argsort(-w, kind="stable")
            keep = order[: int(np.searchsorted(np.cumsum(w[order]), 1 - eps) + 1)]
            keep.sort()
            states, bits, w = states[keep], bits[keep], w[keep]
        self.states, self.bits = states, bits.astype(float)
        self.w0 = w / w.sum()

    def marginals(self, w):
        return w @ self.bits

    def catchable(self, w):
        """P(person is infected AND an individual test would detect them)."""
        return (w @ self.bits) * self.assay.se1

    def k_in(self, masks):
        """Number infected in each pool for every state: array [C, S]."""
        masks = np.atleast_1d(np.asarray(masks, dtype=np.uint32))
        return _POP16[self.states[None, :] & masks[:, None]]

    def lik_pos(self, masks):
        masks = np.atleast_1d(np.asarray(masks, dtype=np.uint32))
        sizes = _POP16[masks]
        return self.assay.T[sizes[:, None], self.k_in(masks)]

    def info_gain(self, w, masks):
        """Mutual information (bits) between each pool's outcome and the state."""
        L = self.lik_pos(masks)
        ppos = L @ w
        return h2(ppos) - h2(L) @ w, ppos

    def update(self, w, mask, outcome):
        L = self.lik_pos([mask])[0]
        post = w * (L if outcome else 1 - L)
        tot = post.sum()
        if tot <= 0:  # impossible under model (only with ideal assay + truncation)
            return w.copy(), 0.0
        return post / tot, tot


class LoadCohort(Cohort):
    """Posterior over (who is infected, and each infected person's load class).

    Loads persist across tests, so a low-load case that hides in a pool is
    also harder to catch on retest.  Tracking the load class makes the decoder
    calibrated to that.  Pools combine members by noisy-OR.  States with more
    than K infected (prior mass < eps) are dropped to keep the space sparse."""

    def __init__(self, priors, assay, q=4, eps=1e-4, max_states=60_000):
        from itertools import combinations
        priors = np.asarray(priors, dtype=float)
        n = len(priors)
        self.n, self.priors, self.assay, self.q = n, priors, assay, q
        cp, d = assay.classes(q)
        pmf = np.array([1.0])
        for p in priors:
            pmf = np.convolve(pmf, [1 - p, p])
        K = int(np.searchsorted(np.cumsum(pmf), 1 - eps))
        K = min(K, n)
        total = sum(_ncomb(n, k) * q**k for k in range(K + 1))
        if total > max_states:
            raise MemoryError(f"{total} states > {max_states}")
        blocks = []
        for k in range(K + 1):
            grid = (np.indices((q,) * k).reshape(k, -1).T + 1).astype(np.int8) if k else np.zeros((1, 0), np.int8)
            for comb in combinations(range(n), k):
                b = np.zeros((grid.shape[0], n), np.int8)
                b[:, list(comb)] = grid
                blocks.append(b)
        st = np.vstack(blocks)
        pos = st > 0
        lcp = np.concatenate([[0.0], np.log(np.clip(cp, 1e-300, 1))])
        logp = pos @ np.log(np.clip(priors, 1e-300, 1)) + (~pos) @ np.log(np.clip(1 - priors, 1e-300, 1)) + lcp[st].sum(1)
        w = np.exp(logp)
        self.states, self.bits, self.w0 = st, pos.astype(float), w / w.sum()
        self.dropped = 1 - float(np.cumsum(pmf)[K])
        lq = np.log(np.clip(1 - d, 1e-12, 1))  # [q, m+1]
        self._lq = np.vstack([np.zeros((1, d.shape[1])), lq])  # class 0 = uninfected
        self._LQ = {}
        self._D1 = np.concatenate([[0.0], d[:, 1]])[st]  # [S, n] individual detectability

    def catchable(self, w):
        return w @ self._D1

    def lik_pos(self, masks):
        masks = np.atleast_1d(np.asarray(masks, dtype=np.uint32))
        sizes = _POP16[masks]
        Mb = ((masks[:, None] >> np.arange(self.n)) & 1).astype(float)
        out = np.empty((len(masks), len(self.w0)))
        for s in np.unique(sizes):
            if s not in self._LQ:
                self._LQ[s] = np.ascontiguousarray(self._lq[self.states, s].T)  # [n, S]
            sel = sizes == s
            out[sel] = 1 - self.assay.sp * np.exp(Mb[sel] @ self._LQ[s])
        return out


def _ncomb(n, k):
    from math import comb
    return comb(n, k)


def mask_of(idx):
    m = 0
    for i in idx:
        m |= 1 << int(i)
    return m


def members(mask):
    return [i for i in range(16) if (mask >> i) & 1]
