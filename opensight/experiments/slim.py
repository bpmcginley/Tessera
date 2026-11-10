"""How small can the unit be?  The first layout used plates wider than the window
so the full window stays covered at every setting.  Here the plates are simply
round discs: at strong prescriptions the two discs overlap a little less, which
narrows the sideways field of view slightly but shrinks the whole cell.
Usage: python experiments/slim.py results/design_xxx.json"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import load
from opensight.evaluate import blur
from opensight.optics import power

p = load(sys.argv[1], t0=1.9)
D_ROT, PUPIL, TRAVEL, RIM, CLEAR, WALL, LOCK = 27.0, 2.0, 3.1, 1.2, 0.3, 1.5, 1.5
out = {}
for Rp in (17.0, 16.0, 15.0, 14.0):
    g = np.linspace(-Rp, Rp, 201); X, Y = np.meshgrid(g, g); ok = X**2 + Y**2 <= Rp**2
    da = (g[1] - g[0]) ** 2
    th = [((p.surfaces[i + 1].val(X, Y) + p.surfaces[i + 1].z0) - (p.surfaces[i].val(X, Y) + p.surfaces[i].z0))[ok] for i in (0, 2)]
    row = dict(plate_diameter_mm=2 * Rp, cell_outer_diameter_mm=round(2 * (Rp + RIM + TRAVEL + CLEAR + WALL + LOCK), 1),
               min_thickness_mm=round(float(min(t.min() for t in th)), 2), max_thickness_mm=round(float(max(t.max() for t in th)), 2),
               weight_g_per_eye=round(float(sum(t.sum() for t in th) * da / 1000 * 1.2), 2), field={})
    for M in (-6.0, -4.0, -1.5, 1.0, 3.0):
        sx, sy = p.solve(M, 0.75)
        half_x = Rp - abs(sx) / 2 - PUPIL                      # both discs must cover the 4 mm pupil bundle
        half_y = np.sqrt(max(Rp**2 - (sx / 2) ** 2, 0)) - abs(sy) / 2 - PUPIL
        ax, ay = np.degrees(np.arctan(half_x / D_ROT)), np.degrees(np.arctan(half_y / D_ROT))
        off = p.offsets(sx, sy)
        e = min(ax, 30.0) * 0.95
        b = np.mean([blur(power(p.surfaces, off, (s * e, 0.0), p.z_vertex), M, 0.0, 0.75) for s in (-1, 1)])
        row["field"][f"{M:+.1f} D"] = dict(sideways_deg=round(float(ax), 1), up_down_deg=round(float(ay), 1), blur_at_sideways_edge_D=round(float(b), 3))
    out[f"{2*Rp:.0f} mm discs"] = row
json.dump(out, open("results/slim.json", "w"), indent=1)
for k, r in out.items():
    print(k, "| cell", r["cell_outer_diameter_mm"], "mm | weight", r["weight_g_per_eye"], "g | thickness", r["min_thickness_mm"], "-", r["max_thickness_mm"])
    for m, f in r["field"].items():
        print("    ", m, f)
