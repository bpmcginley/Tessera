"""Tolerance stack-up for the adjusting mechanism (Monte Carlo).

Each contributor is an engineering ESTIMATE for a small moulded/turned
mechanism, not a measurement; the point is to see which ones matter against
the optical requirement (position within ~0.05-0.1 mm).
Usage: python experiments/mechanism.py"""
import json
import numpy as np

K_SPH, K_CYL = 0.76, 1.51            # dioptres per mm of relative slide (from results/dispense.json)
PITCH_X, PITCH_Y = 0.5, 0.35         # screw pitch (mm); left+right hand threads double the relative travel
rng = np.random.default_rng(0)
N = 200_000
# contributor: (description, 1-sigma or half-range in mm of RELATIVE plate position, distribution)
X = {"thread pitch error (0.3% of up to 6 mm travel)": ("u", 0.018), "thread backlash after spring preload": ("u", 0.010),
     "scale reading / setting (1/30 turn)": ("n", 2 * PITCH_X / 30), "carrier-to-plate seating": ("n", 0.015),
     "thermal growth mismatch (20 K, plastic vs metal screw, 6 mm)": ("u", 0.006)}
Y = {"thread pitch error (0.3% of up to 2 mm travel)": ("u", 0.006), "thread backlash after spring preload": ("u", 0.010),
     "scale reading / setting (1/30 turn)": ("n", 2 * PITCH_Y / 30), "carrier-to-plate seating": ("n", 0.015),
     "cross-talk from x guide straightness (0.1 mm per 20 mm over 6 mm)": ("u", 0.030)}


def draw(spec):
    kind, v = spec
    return rng.uniform(-v, v, N) if kind == "u" else rng.normal(0, v, N)


out = {}
for axis, items, k, pitch in (("sphere (x)", X, K_SPH, PITCH_X), ("cylinder (y)", Y, K_CYL, PITCH_Y)):
    parts = {n: draw(s) for n, s in items.items()}
    tot = sum(parts.values())
    out[axis] = dict(screw_pitch_mm=pitch, dioptres_per_turn=round(2 * pitch * k, 2), position_error_mm_p95=round(float(np.percentile(np.abs(tot), 95)), 3),
                     power_error_D_p95=round(float(np.percentile(np.abs(tot), 95)) * k, 3),
                     contributors_mm_p95={n: round(float(np.percentile(np.abs(v), 95)), 3) for n, v in parts.items()})
# plate rotation about the optical axis from guide clearance: 0.03 mm over a 30 mm guide
out["plate clocking from guide clearance (deg)"] = round(float(np.degrees(0.03 / 30)), 3)
out["requirement"] = "optics tolerate about 0.05-0.1 mm of position error and 0.3 deg of plate clocking (results/tolerance.json, results/dispense.json)"
json.dump(out, open("results/mechanism.json", "w"), indent=1)
print(json.dumps(out, indent=1))
