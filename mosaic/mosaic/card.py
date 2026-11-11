"""Render a policy's decision tree as a bench 'card' a technician can follow."""
from __future__ import annotations

from .core import members

LET = "ABCDEFGHIJKLMNOP"


def _names(mask):
    return "".join(LET[i] for i in members(mask))


def render(tree, max_depth=6, min_reach=0.002):
    """Indented text protocol. Branches rarer than min_reach are summarised."""
    n = tree.cohort.n
    out = [f"Cohort of {n} samples ({LET[:n]}), prior risk each {tree.cohort.priors[0]:.3g}"]

    def rec(hist, reach, ind):
        nd = tree.node(hist)
        pad = "  " * ind
        if nd["a"] == 0:
            pos = "".join(LET[i] for i in range(n) if nd["calls"][i])
            out.append(f"{pad}STOP. Report positive: {pos or 'none'}; all others negative.")
            return
        if len(hist) >= max_depth or reach < min_reach:
            out.append(f"{pad}(rare branch, {reach:.2%} of cohorts: continue with the software)")
            return
        s = bin(nd["a"]).count("1")
        out.append(f"{pad}Test {'sample' if s == 1 else 'pool'} {_names(nd['a'])}")
        pp = nd["ppos"]
        out.append(f"{pad}- if NEGATIVE ({1-pp:.0%}):")
        rec(hist + ((nd["a"], 0),), reach * (1 - pp), ind + 2)
        out.append(f"{pad}- if POSITIVE ({pp:.0%}):")
        rec(hist + ((nd["a"], 1),), reach * pp, ind + 2)

    rec((), 1.0, 0)
    return "\n".join(out)
