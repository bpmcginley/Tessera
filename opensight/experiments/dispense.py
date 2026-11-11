"""Checks that turn the optical design into a dispensable product concept:
  1. setting table: prescription -> click positions (and how linear the scales are)
  2. accuracy when set by clicks, with play in the mechanism
  3. fit variation (lens closer to / further from the eye)
  4. colour fringing vs an ordinary polycarbonate lens
  5. weight
Usage: python experiments/dispense.py results/design_xxx.json"""
import copy, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import conventional, load
from opensight.evaluate import blur
from opensight.optics import power, trace

path = sys.argv[1]
p = load(path)
rng = np.random.default_rng(1)
out = {}

# 1. scales ----------------------------------------------------------------
sx = np.linspace(-6.2, 6.2, 25); sy = np.linspace(-2.1, 2.1, 15)
M = np.array([p.power(s, 0)["M"] for s in sx]); J = np.array([p.power(0, s)["J45"] for s in sy])
kM, bM = np.polyfit(sx, M, 1); kJ, bJ = np.polyfit(sy, J, 1)
out["scales"] = dict(sphere_D_per_mm=float(kM), sphere_at_centre_D=float(bM), cyl_D_per_mm=float(2 * kJ),
                     sphere_scale_max_nonlinearity_D=float(np.abs(M - (kM * sx + bM)).max()), cyl_scale_max_nonlinearity_D=float(2 * np.abs(J - (kJ * sy + bJ)).max()),
                     click_pitch_mm_per_quarter_dioptre_sphere=float(0.25 / kM), click_pitch_mm_per_quarter_dioptre_cyl=float(0.25 / (2 * kJ)))
rows = ["sphere_equivalent_D,slide_x_mm"] + [f"{m:+.2f},{(m - bM) / kM:+.3f}" for m in np.arange(-6, 3.01, 0.25)]
rows += ["", "cylinder_D,slide_y_mm"] + [f"{c:.2f},{(c / 2 - bJ) / kJ:+.3f}" for c in np.arange(0, 3.01, 0.25)]
open("results/setting_table.csv", "w").write("\n".join(rows) + "\n")

# 2. set by clicks, with play ------------------------------------------------
GZ = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for r, k in ((10.0, 4), (20.0, 8)) for a in np.arange(k) * 2 * np.pi / k]
res = {}
for play, axis_sd in ((0.05, 2.0), (0.10, 3.0), (0.20, 5.0)):
    e_sph, e_cyl, on, fld = [], [], [], []
    for _ in range(60):
        C = rng.choice(np.arange(0, 3.01, 0.25)); Mt = rng.choice(np.arange(-6, 3.01, 0.25)); Jt = C / 2
        s = np.array([(Mt - bM) / kM, (Jt - bJ) / kJ]) + rng.normal(0, play, 2)   # straight-line scales + play
        r = p.power(*s)
        ax = 2 * Jt * abs(np.sin(np.radians(rng.normal(0, axis_sd))))
        e_sph.append(abs(r["M"] - Mt)); e_cyl.append(2 * abs(r["J45"] - Jt))
        on.append(np.hypot(blur(r, Mt, 0, Jt), ax))
        off = p.offsets(*s)
        fld.append(np.mean([np.hypot(blur(power(p.surfaces, off, g, p.z_vertex), Mt, 0, Jt), ax) for g in GZ]))
    res[f"play {play} mm, axis {axis_sd} deg"] = dict(sphere_err_p95=float(np.percentile(e_sph, 95)), cyl_err_p95=float(np.percentile(e_cyl, 95)),
                                                     on_axis_blur_p95=float(np.percentile(on, 95)), field_blur_mean=float(np.mean(fld)), field_blur_p95=float(np.percentile(fld, 95)))
out["set_by_clicks"] = res

# 3. fit: distance from lens to the eye's rotation centre ---------------------
fit = {}
for d in (23.0, 25.0, 27.0, 29.0, 31.0):
    b = []
    for Mt, Jt in ((-6, 0), (-3, 0.75), (-1.5, 1.5), (3, 0)):
        off = p.offsets(*p.solve(Mt, Jt))
        b += [blur(power(p.surfaces, off, g, p.z_vertex, d_rot=d), Mt, 0, Jt) for g in GZ[5:]]   # the 20 degree ring
    fit[f"{d:.0f} mm"] = dict(mean_blur_at_20deg=float(np.mean(b)), worst=float(np.max(b)))
out["fit_distance_to_rotation_centre"] = fit

# 4. colour fringing (blue F line vs red C line; polycarbonate Abbe number 30) --
dn = (p.n - 1) / 30.0


def recolour(surfs, n0, n1):
    s2 = copy.deepcopy(surfs)
    for s in s2:
        if abs(s.n1 - n0) < 1e-9: s.n1 = n1
        if abs(s.n2 - n0) < 1e-9: s.n2 = n1
    return s2


def fringe(surfs, offs, zv, gaze):
    """Angle between blue and red chief rays leaving towards the eye (arcmin)."""
    ax, ay = np.radians(gaze); g = np.array([np.sin(ax) * np.cos(ay), np.sin(ay), np.cos(ax) * np.cos(ay)])
    C = np.array([0, 0, zv + 27.0])
    pc, dc = trace(C[None], -g[None], surfs, offs, reverse=True)
    d = []
    for n1 in (p.n + dn * 0.7, p.n - dn * 0.3):
        _, dd = trace(pc - 5 * (-dc), -dc, recolour(surfs, p.n, n1), offs)
        d.append(dd[0])
    return float(np.degrees(np.arccos(np.clip(d[0] @ d[1], -1, 1))) * 60)


col = {}
for Mt in (-6.0, -3.0, 3.0):
    off = p.offsets(*p.solve(Mt, 0)); cs, tc = conventional(Mt)
    col[f"{Mt:+.0f} D"] = {f"{e} deg": dict(sliding_pair=round(np.mean([fringe(p.surfaces, off, p.z_vertex, (e * np.cos(a), e * np.sin(a))) for a in np.arange(4) * np.pi / 2]), 2),
                                           ordinary_lens=round(np.mean([fringe(cs, {0: (0, 0)}, tc, (e * np.cos(a), e * np.sin(a))) for a in np.arange(4) * np.pi / 2]), 2)) for e in (0, 10, 20)}
out["colour_fringe_arcmin"] = col

# 5. weight -------------------------------------------------------------------
ext = p.radius + 3.2
g = np.linspace(-ext, ext, 201); X, Y = np.meshgrid(g, g); ok = X**2 / ext**2 + Y**2 / (p.radius + 1.2) ** 2 <= 1
da = (g[1] - g[0]) ** 2
t1 = (p.surfaces[1].val(X, Y) + p.surfaces[1].z0) - (p.surfaces[0].val(X, Y) + p.surfaces[0].z0)
t2 = (p.surfaces[3].val(X, Y) + p.surfaces[3].z0) - (p.surfaces[2].val(X, Y) + p.surfaces[2].z0)
out["weight_g_per_eye_both_plates"] = float((t1[ok].sum() + t2[ok].sum()) * da / 1000 * 1.20)
out["stack_thickness_mm_max"] = float((p.surfaces[3].val(X, Y) + p.surfaces[3].z0 - p.surfaces[0].val(X, Y) - p.surfaces[0].z0)[ok].max())
json.dump(out, open("results/dispense.json", "w"), indent=1)
print(json.dumps(out, indent=1))
