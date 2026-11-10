"""Compare designs across directions of gaze, check knob independence, and
export the plate shapes.  Usage: python experiments/report.py results/design_xxx.json"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import Pair, best_tilt, conventional, load
from opensight.evaluate import blur
from opensight.optics import power

path = sys.argv[1]
opt = load(path)
plain = Pair(A=opt.A, tilt=opt.tilt, t0=opt.t0, base=-1.5, radius=opt.radius, freeform="inner", gap=opt.gap)
ECC = [0, 5, 10, 15, 20, 25, 30]
AZ = np.arange(8) * np.pi / 4
SPH = [-6.0, -4.0, -2.0, 2.0, 3.0]
FULL = [(M, J) for M in SPH for J in (0.0, 0.75, 1.5)]


def pair_curve(p, rx):
    out = np.zeros((len(rx), len(ECC)))
    for i, (M, J) in enumerate(rx):
        off = p.offsets(*p.solve(M, J))
        for k, e in enumerate(ECC):
            out[i, k] = np.mean([blur(power(p.surfaces, off, (e * np.cos(a), e * np.sin(a)), p.z_vertex), M, 0.0, J) for a in AZ])
    return out


def conv_curve(front):
    out = np.zeros((len(SPH), len(ECC)))
    for i, M in enumerate(SPH):
        s, tc = conventional(M, front)
        M0 = power(s, {0: (0, 0)}, (0, 0), tc)["M"]
        for k, e in enumerate(ECC):
            out[i, k] = np.mean([blur(power(s, {0: (0, 0)}, (e * np.cos(a), e * np.sin(a)), tc), M0, 0.0, 0.0) for a in AZ])
    return out


curves = {"Plain sliding pair (as usually described)": pair_curve(plain, FULL), "Optimised sliding pair (this work)": pair_curve(opt, FULL),
          "Ordinary lens, flat front": conv_curve(None), "Ordinary lens, curved (meniscus)": conv_curve(4.0)}
# knob independence on axis
knob = []
for sx in (-6, -3, 0, 3, 6):
    for sy in (0, 1, 2):
        r = opt.power(sx, sy)
        knob.append(dict(slide_x=sx, slide_y=sy, M=round(float(r["M"]), 3), J0=round(float(r["J0"]), 3), J45=round(float(r["J45"]), 3), prism=round(float(r["prism"]), 2)))
t1, t2 = opt.thickness()
rep = dict(design=path, eccentricity_deg=ECC, mean_blur_D={k: v.mean(0).round(3).tolist() for k, v in curves.items()},
           worst_blur_D={k: v.max(0).round(3).tolist() for k, v in curves.items()}, knob_table=knob,
           thickness_mm=dict(front=t1, rear=t2), slide_for_M_minus6=np.round(opt.solve(-6, 0), 2).tolist(), slide_for_M_plus3=np.round(opt.solve(3, 0), 2).tolist(),
           slide_for_cyl_3D=np.round(opt.solve(-1.5, 1.5), 2).tolist())
json.dump(rep, open("results/report.json", "w"), indent=1)

# plate shapes for manufacture: sag of the two facing freeform surfaces
ext = opt.radius + 3.2
g = np.arange(-20.0, 20.01, 0.5)
X, Y = np.meshgrid(g, g)
for name, srf in (("front_plate_inner_face", opt.surfaces[1]), ("rear_plate_inner_face", opt.surfaces[2])):
    np.savetxt(f"results/{name}_sag_mm.csv", np.column_stack([X.ravel(), Y.ravel(), srf.val(X, Y).ravel()]), delimiter=",", header="x_mm,y_mm,sag_mm", comments="", fmt="%.5f")
json.dump(dict(units="mm", material="polycarbonate n=1.586", centre_thickness=opt.t0, air_gap=opt.gap, window_radius=opt.radius,
               front_plate=dict(outer_face="flat", inner_face={f"x^{i} y^{j}": c for (i, j), c in sorted(opt.surfaces[1].poly.t.items())}),
               rear_plate=dict(inner_face={f"x^{i} y^{j}": c for (i, j), c in sorted(opt.surfaces[2].poly.t.items())},
                               outer_face={f"x^{i} y^{j}": c for (i, j), c in sorted(opt.surfaces[3].poly.t.items())})),
          open("results/plate_coefficients.json", "w"), indent=1)

INK, MUTED, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
COL = ["#eb6834", "#6250d6", "#2a78d6", "#1baf7a"]; MK = ["s", "D", "o", "^"]
fig, ax = plt.subplots(figsize=(8, 5), facecolor=SURF); ax.set_facecolor(SURF)
for (k, v), c, m in zip(curves.items(), COL, MK):
    ax.plot(ECC, v.mean(0), color=c, lw=2, marker=m, ms=6, mec=SURF, mew=1, label=k)
ax.axhline(0.25, color=MUTED, lw=1, ls=":"); ax.text(0.2, 0.27, "0.25 D: one step on a lens prescription", color=MUTED, fontsize=8)
ax.set_ylim(0, 1.5); ax.set_xlabel("How far the eye looks off-centre (degrees)", color=MUTED, fontsize=9)
ax.set_ylabel("Average blur (dioptres)", color=MUTED, fontsize=9)
ax.set_title("Sharpness when looking off-centre (lower is better)", color=INK, fontsize=11, loc="left")
ax.grid(color="#e4e3df", lw=0.6); ax.tick_params(colors=MUTED, labelsize=8)
for sp in ax.spines.values():
    sp.set_visible(False)
ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK)
fig.tight_layout(); fig.savefig("results/field.png", dpi=150)
print(json.dumps({k: rep[k] for k in ("mean_blur_D", "worst_blur_D", "thickness_mm", "slide_for_M_minus6", "slide_for_cyl_3D")}, indent=1))
