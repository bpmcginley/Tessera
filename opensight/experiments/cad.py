"""3D models: the two lens plates (exact freeform faces, spline-fitted) and a
block-level layout of the adjusting cell.  Writes STEP files into cad/.
Usage: python experiments/cad.py results/design_xxx.json"""
import json, os, sys
import numpy as np
import cadquery as cq
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import load

RP = float(sys.argv[2]) if len(sys.argv) > 2 else 16.0     # plate (disc) radius, mm
p = load(sys.argv[1], t0=1.9)
AX = AY = RP                                               # round plates (see experiments/slim.py)
G = np.linspace(-AX - 2, AX + 2, 45)


def face(srf):
    pts = [[cq.Vector(float(x), float(y), float(srf.z0 + srf.val(np.array(x), np.array(y)))) for y in G] for x in G]
    return cq.Face.makeSplineApprox(pts, tol=1e-4, minDeg=3, maxDeg=8)


def prism(srf, dz):
    return cq.Solid.extrudeLinear(face(srf), cq.Vector(0, 0, dz))


outline = cq.Workplane("XY").workplane(offset=-15).ellipse(AX, AY).extrude(30).val()
s = p.surfaces
front = prism(s[1], -12).intersect(outline).intersect(cq.Workplane("XY").workplane(offset=s[0].z0).rect(80, 80).extrude(20).val())
rear = prism(s[2], 12).intersect(prism(s[3], -12)).intersect(outline)
out = {}
for name, body in (("front_plate", front), ("rear_plate", rear)):
    cq.exporters.export(cq.Workplane(obj=body), f"cad/{name}.step")
    bb = body.BoundingBox()
    out[name] = dict(volume_mm3=round(body.Volume(), 1), mass_g=round(body.Volume() / 1000 * 1.2, 2), size_mm=[round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)], valid=bool(body.isValid()))

# ---- block-level cell layout (not an engineered mechanism) ----------------
zf, zr = s[0].z0, s[3].z0 + 1.5
# carriers are thin rims that follow the plate outline, so the cell can be as small as possible
car = lambda z0, z1: (cq.Workplane("XY").workplane(offset=z0).ellipse(AX + 1.5, AY + 1.5).extrude(z1 - z0)
                      .cut(cq.Workplane("XY").workplane(offset=z0 - 1).ellipse(AX - 0.8, AY - 0.8).extrude(z1 - z0 + 2)))
carrier_f = car(zf, -p.gap / 2)
carrier_r = car(p.gap / 2, zr)
TRAVEL = 3.1                                   # each plate moves +/- this much in x
R_in = AX + 1.5 + TRAVEL + 0.3                 # smallest circle the sliding carriers fit in
R_out = R_in + 1.5
cell = (cq.Workplane("XY").workplane(offset=zf - 1.5).circle(R_out).circle(R_in).extrude(zr - zf + 3.0)
        .union(cq.Workplane("XY").workplane(offset=zf - 1.5).circle(R_in).circle(RP - 1.0).extrude(1.0)))
ys = AY + 3.2                                  # screws sit in the free space above and below the plates
half = float(np.sqrt(R_in**2 - ys**2)) - 0.5
screw_x = cq.Workplane("YZ").workplane(offset=-half).center(ys, 0).circle(0.8).extrude(2 * half)
screw_y = cq.Workplane("YZ").workplane(offset=-half).center(-ys, 0).circle(0.7).extrude(2 * half)
lock = cq.Workplane("XY").workplane(offset=zr + 1.5).circle(R_out + 1.5).circle(R_in).extrude(1.2)
asm = cq.Assembly(name="opensight_cell")
for n, o, c in (("front_plate", cq.Workplane(obj=front), "lightblue"), ("rear_plate", cq.Workplane(obj=rear), "lightblue"), ("front_carrier", carrier_f, "gray"),
                ("rear_carrier", carrier_r, "gray"), ("rotating_cell", cell, "white"), ("sphere_screw", screw_x, "orange"), ("cylinder_screw", screw_y, "orange"), ("lock_ring", lock, "black")):
    asm.add(o, name=n, color=cq.Color(c))
asm.save("cad/cell_layout.step")
out["cell_layout"] = dict(plate_diameter_mm=2 * RP, cell_outer_diameter_mm=round(2 * (R_out + 1.5), 1), depth_mm=round(zr - zf + 4.2, 1), note="block-level layout for discussion; not an engineered mechanism")
json.dump(out, open("cad/summary.json", "w"), indent=1)
print(json.dumps(out, indent=1))
