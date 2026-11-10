"""Optimise the plate shapes for sharp vision across directions of gaze.

Free parameters: the perspective scale mu of the rear plate, and quartic and
quintic terms shared by both plates (they cancel at zero slide, and act only
when slid) plus small rear-plate-only quartic terms.  Objective: power error
(M, J0, J45) over a grid of prescriptions x gaze directions out to 20 degrees.
Usage: python experiments/optimize.py [A] [gap]"""
import json, os, sys, time
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import Pair, best_tilt
from opensight.optics import power

A = float(sys.argv[1]) if len(sys.argv) > 1 else 6.35e-4
GAP = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
R = 17.0
TILT = best_tilt(A, R)
RX = [(M, J) for M in (-6.0, -3.75, -1.5, 0.75, 3.0) for J in (0.0, 1.5)]
GZ = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for r, k in ((10.0, 4), (20.0, 8)) for a in np.arange(k) * 2 * np.pi / k]
WIDE = os.environ.get("WIDE") == "1"
W = np.ones(len(GZ))
SH = [(4, 0), (2, 2), (0, 4), (5, 0), (3, 2), (1, 4)]
RE = [(4, 0), (2, 2), (0, 4)]
SC = np.array([0.01] + [1e-6] * 3 + [1e-7] * 3 + [1e-6] * 3)
if WIDE:  # also weigh 30 degree gaze, and free more shape terms
    GZ = GZ + [(30 * np.cos(a), 30 * np.sin(a)) for a in np.arange(8) * np.pi / 4]
    W = np.concatenate([W, np.full(8, 0.4)])
    SH = SH + [(6, 0), (4, 2), (2, 4), (0, 6), (7, 0), (5, 2), (3, 4), (1, 6)]
    RE = RE + [(5, 0), (3, 2), (1, 4)]
    SC = np.array([0.01] + [1e-6] * 3 + [1e-7] * 3 + [1e-8] * 4 + [1e-9] * 4 + [1e-6] * 3 + [1e-7] * 3)
NS = len(SH)


def build(x):
    x = np.asarray(x) * SC
    ex = {k: v for k, v in zip(SH, x[1:1 + NS])}
    ex2 = {k: v for k, v in zip(RE, x[1 + NS:])}
    return Pair(A=A, tilt=TILT, t0=2.2, base=-1.5, radius=R, freeform="inner", gap=GAP, mu=1.0 + x[0], extra=ex, extra2=ex2)


def resid(x):
    p = build(x)
    out = []
    for M, J in RX:
        try:
            sx, sy = p.solve(M, J)
        except Exception:
            return np.full(len(RX) * len(GZ) * 3, 10.0)
        off = p.offsets(sx, sy)
        for g, w in zip(GZ, W):
            r = power(p.surfaces, off, g, p.z_vertex)
            out += [w * (r["M"] - M), w * r["J0"], w * (r["J45"] - J)]
    out = np.nan_to_num(np.array(out), nan=10.0, posinf=10.0, neginf=-10.0)
    return np.clip(out, -10, 10)


if __name__ == "__main__":
    x0 = np.zeros(len(SC)); x0[0] = -1.0
    r0 = resid(x0)
    print(f"A={A} gap={GAP} start rms blur component {np.sqrt((r0**2).mean()):.4f} D", flush=True)
    t0 = time.time()
    sol = least_squares(resid, x0, method="lm", diff_step=1e-3, max_nfev=1500)
    r1 = resid(sol.x)
    print(f"done in {time.time()-t0:.0f}s: rms {np.sqrt((r1**2).mean()):.4f} D  x={np.round(sol.x,4).tolist()}", flush=True)
    json.dump(dict(A=A, gap=GAP, tilt=TILT, radius=R, x=sol.x.tolist(), scale=SC.tolist(), shared_terms=SH, rear_terms=RE,
                   rms_before=float(np.sqrt((r0**2).mean())), rms_after=float(np.sqrt((r1**2).mean()))),
              open(f"results/design_A{A:g}_gap{GAP:g}{'_wide' if WIDE else ''}.json", "w"), indent=1)
