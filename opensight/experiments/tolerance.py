"""Manufacturing and assembly tolerance Monte Carlo.

Each trial perturbs the build, then lets the wearer re-adjust the two slides
(as they would in use) and measures blur over the +/-20 degree field.
Usage: python experiments/tolerance.py results/design_xxx.json [trials]"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import load
from opensight.evaluate import blur
from opensight.optics import Poly, power

TOL = dict(cubic_mismatch=0.005,   # relative error of one plate's cubic coefficient (1 sigma)
           gap_mm=0.10,            # air gap error
           index=0.002,            # refractive index error
           clocking_deg=0.3,       # one plate rotated about the optical axis
           tilt_deg=0.5,           # one plate tilted
           slide_mm=0.05,          # residual positioning error after the wearer adjusts
           axis_deg=3.0)           # error in the wearer's cell rotation
GZ = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for r, k in ((10.0, 4), (20.0, 8)) for a in np.arange(k) * 2 * np.pi / k]
RX = [(-5.0, 0.0), (-2.0, 1.0), (2.0, 0.5)]


def trial(path, rng, only=None):
    g = lambda k: rng.normal(0, TOL[k]) if only in (None, k) else 0.0
    p = load(path)
    dA = p.A * g("cubic_mismatch")
    p.surfaces[2].poly = p.surfaces[2].poly + Poly({(3, 0): dA / 3, (1, 2): dA})
    dg = g("gap_mm")
    for s in p.surfaces[2:]:
        s.z0 += dg
    p.z_vertex += dg
    dn = g("index")
    p.surfaces[0].n2 += dn; p.surfaces[1].n1 += dn
    cz, ty = np.radians(g("clocking_deg")), np.radians(g("tilt_deg"))
    Rz = np.array([[np.cos(cz), -np.sin(cz), 0], [np.sin(cz), np.cos(cz), 0], [0, 0, 1]])
    Ry = np.array([[np.cos(ty), 0, np.sin(ty)], [0, 1, 0], [-np.sin(ty), 0, np.cos(ty)]])
    Rm, piv = Rz @ Ry, np.array([0.0, 0.0, -p.gap / 2])
    out = []
    for M, J in RX:
        base = p.offsets(0, 0)
        def pw(sx, sy, gz=(0, 0)):
            o = p.offsets(sx, sy)
            return power(p.surfaces, {0: (o[0][0], o[0][1], Rm, piv), 1: o[1]}, gz, p.z_vertex)
        k = 2000.0 * p.A * (p.n - 1)
        s = np.array([(M + 1.5) / k, J / k])
        for _ in range(5):  # the wearer re-adjusts both slides for best on-axis focus
            r = pw(*s); h = 1e-3
            a, b = pw(s[0] + h, s[1]), pw(s[0], s[1] + h)
            Jm = np.array([[(a["M"] - r["M"]) / h, (b["M"] - r["M"]) / h], [(a["J45"] - r["J45"]) / h, (b["J45"] - r["J45"]) / h]])
            s = s - np.linalg.solve(Jm, [r["M"] - M, r["J45"] - J])
        s = s + np.array([g("slide_mm"), g("slide_mm")])
        da = np.radians(g("axis_deg"))
        ax_err = 2 * abs(J) * abs(np.sin(da))  # cross-cylinder left by an axis error
        bl = [np.hypot(blur(pw(s[0], s[1], gz), M, 0.0, J), ax_err) for gz in GZ]
        out.append((bl[0], float(np.mean(bl)), float(np.max(bl))))
    return np.array(out)


if __name__ == "__main__":
    path = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    rng = np.random.default_rng(0)
    nominal = trial(path, np.random.default_rng(0), only="none")
    allv = np.array([trial(path, rng) for _ in range(n)])
    res = dict(design=path, tolerances=TOL, trials=n, prescriptions=RX,
               nominal=dict(on_axis=nominal[:, 0].tolist(), field_mean=nominal[:, 1].tolist(), field_max=nominal[:, 2].tolist()),
               on_axis_p50=float(np.median(allv[:, :, 0])), on_axis_p95=float(np.percentile(allv[:, :, 0], 95)),
               field_mean_p50=float(np.median(allv[:, :, 1])), field_mean_p95=float(np.percentile(allv[:, :, 1], 95)),
               field_max_p95=float(np.percentile(allv[:, :, 2], 95)), single={})
    for k in TOL:
        v = np.array([trial(path, rng, only=k) for _ in range(40)])
        res["single"][k] = float(np.percentile(v[:, :, 1], 95))
    json.dump(res, open("results/tolerance.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("tolerances", "prescriptions")}, indent=1))
