"""Independent check of the ray tracer against Optiland (a third-party open-source
optical design package).  The same lens is built in Optiland; the very same rays
are traced by both codes; exit directions are compared ray by ray.
Usage: python experiments/crosscheck.py results/design_xxx.json"""
import json, os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from optiland.optic import Optic
from optiland.materials import IdealMaterial
from opensight.design import load
from opensight.optics import trace

path = sys.argv[1]
p = load(path)


def coef(poly, n=8):
    c = np.zeros((n, n))
    for (i, j), v in poly.t.items():
        c[i, j] = v
    return c


def build(sx, sy, fx, fy):
    off = p.offsets(sx, sy)
    glass = IdealMaterial(n=p.n)
    o = Optic()
    o.add_surface(index=0, thickness=np.inf)
    z = [s.z0 for s in p.surfaces]
    for k, s in enumerate(p.surfaces):
        dx, dy = off[s.plate][:2]
        th = (z[k + 1] - z[k]) if k < 3 else 27.0
        o.add_surface(index=k + 1, surface_type="polynomial", radius=np.inf, coefficients=coef(s.poly), thickness=th,
                      material=glass if k in (0, 2) else "air", dx=dx, dy=dy)
    o.add_surface(index=5, is_stop=True, thickness=10.0)
    o.add_surface(index=6)
    o.set_aperture(aperture_type="EPD", value=4.0)
    o.set_field_type(field_type="angle")
    o.add_field(y=fy, x=fx)
    o.add_wavelength(value=0.5876, is_primary=True)
    return o, off


worst_dir, worst_pos, rows = 0.0, 0.0, []
rng = np.random.default_rng(0)
cases = [(0, 0, 0, 0), (-5.9, 0, 0, 0), (5.9, 0, 0, 0), (0, 2, 0, 0), (-5.9, 1.5, 15, 10), (4, -2, -20, 5), (2, 1, 8, -18), (-3, 0.5, 20, 20)]
for sx, sy, fx, fy in cases:
    o, off = build(sx, sy, fx, fy)
    px, py = rng.uniform(-0.7, 0.7, 40), rng.uniform(-0.7, 0.7, 40)
    o.trace_generic(Hx=1.0 if fx else 0.0, Hy=1.0 if fy else 0.0, Px=px, Py=py, wavelength=0.5876)
    sg = o.surface_group
    X, Y, Z = np.asarray(sg.x), np.asarray(sg.y), np.asarray(sg.z) + p.surfaces[0].z0   # Optiland puts the first face at z = 0
    L, M, N = np.asarray(sg.L), np.asarray(sg.M), np.asarray(sg.N)
    ok = np.isfinite(X[4]) & np.isfinite(L[4])
    # incoming ray: point on surface 1 and the direction before it (all rays of one field are parallel)
    # surface 1 is a flat face: undo Snell's law there to recover each ray's incoming direction
    d1 = np.stack([L[1], M[1], N[1]], 1)[ok]
    tx, ty = p.n * d1[:, 0], p.n * d1[:, 1]
    d_in_all = np.stack([tx, ty, np.sqrt(1 - tx**2 - ty**2)], 1)
    p1 = np.stack([X[1], Y[1], Z[1]], 1)[ok]
    # recover Optiland's own incoming direction from its first refraction is not needed: use ours and check positions too
    start = p1 - 3.0 * d_in_all
    pe, de = trace(start, d_in_all, p.surfaces, off)
    d_opt = np.stack([L[4], M[4], N[4]], 1)[ok]
    p_opt = np.stack([X[4], Y[4], Z[4]], 1)[ok]
    ed = float(np.abs(de - d_opt).max()); ep = float(np.abs(pe - p_opt).max())
    worst_dir, worst_pos = max(worst_dir, ed), max(worst_pos, ep)
    rows.append(dict(slide=(sx, sy), field_deg=(fx, fy), rays=int(ok.sum()), max_direction_diff=ed, max_position_diff_mm=ep))
    print(rows[-1], flush=True)
json.dump(dict(design=path, tool="optiland", cases=rows, worst_direction_diff=worst_dir, worst_position_diff_mm=worst_pos), open("results/crosscheck.json", "w"), indent=1)
print("worst direction difference:", worst_dir, "(1 arcsecond = 4.8e-6)   worst position difference (mm):", worst_pos)
