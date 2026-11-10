"""Remaining optical checks: lens off-centre or tilted on the face, a wider
prescription range, and thinner plates.  Lens is set once to the prescription
(not re-adjusted).  Usage: python experiments/fit_checks.py results/design_xxx.json"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import load
from opensight.evaluate import blur
from opensight.optics import power

path = sys.argv[1]
p = load(path)
RING = lambda r, k=8: [(r * np.cos(a), r * np.sin(a)) for a in np.arange(k) * 2 * np.pi / k]
GZ = [(0.0, 0.0)] + RING(10.0, 4) + RING(20.0)
RX = [(-6.0, 0.0), (-3.0, 0.75), (-1.5, 1.5), (3.0, 0.0)]


def stats(pp, rx=RX, **kw):
    on, fld = [], []
    for M, J in rx:
        off = pp.offsets(*pp.solve(M, J))
        b = [blur(power(pp.surfaces, off, g, pp.z_vertex, **kw), M, 0.0, J) for g in GZ]
        on.append(b[0]); fld.append(np.mean(b))
    return dict(on_axis_mean=round(float(np.mean(on)), 3), on_axis_worst=round(float(np.max(on)), 3), field_mean=round(float(np.mean(fld)), 3), field_worst_rx=round(float(np.max(fld)), 3))


out = {"nominal": stats(p)}
out["decentered"] = {f"{dx:+.0f} mm x, {dy:+.0f} mm y": stats(p, decenter=(dx, dy)) for dx, dy in ((2, 0), (4, 0), (-4, 0), (0, 3), (0, -3), (3, 3))}
out["tilted"] = {f"pantoscopic {a} deg, wrap {b} deg": stats(p, tilt_deg=(a, b)) for a, b in ((5, 0), (10, 0), (0, 5), (8, 5))}
wide = {}
for M in (-8.0, -7.0, 4.0, 5.0):
    try:
        wide[f"{M:+.0f} D"] = dict(slide_mm=round(float(p.solve(M, 0)[0]), 2), **stats(p, rx=[(M, 0.0), (M, 1.0)]))
    except Exception as e:
        wide[f"{M:+.0f} D"] = "failed: " + str(e)[:60]
out["wider_range_same_plates"] = wide
thin = {}
for t0 in (2.2, 1.9, 1.7):
    q = load(path, t0=t0)
    (a, _), (c, _) = q.thickness()
    ext = q.radius + 3.2
    g = np.linspace(-ext, ext, 161); X, Y = np.meshgrid(g, g); ok = X**2 / ext**2 + Y**2 / (q.radius + 1.2) ** 2 <= 1
    vol = sum(((q.surfaces[i + 1].val(X, Y) + q.surfaces[i + 1].z0) - (q.surfaces[i].val(X, Y) + q.surfaces[i].z0))[ok].sum() for i in (0, 2)) * (g[1] - g[0]) ** 2
    thin[f"centre thickness {t0} mm"] = dict(min_thickness_mm=round(min(a, c), 2), weight_g_per_eye=round(float(vol / 1000 * 1.2), 2), **stats(q))
out["thinner_plates_no_reoptimisation"] = thin
json.dump(out, open("results/fit_checks.json", "w"), indent=1)
print(json.dumps(out, indent=1))
