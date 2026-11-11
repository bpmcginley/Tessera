"""Checks that the ray tracer and the design behave as claimed."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opensight.design import Pair, best_tilt, conventional, load
from opensight.evaluate import blur
from opensight.optics import power

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_thin_lens_formula():
    for F in (-6.0, -2.0, 3.0):
        s, tc = conventional(F)
        assert abs(power(s, {0: (0, 0)}, (0, 0), tc)["M"] - F) < 0.03 * abs(F) + 0.01


def test_toric_lens_reads_back_its_cylinder():
    s, tc = conventional(-2.0, cyl=1.0)
    r = power(s, {0: (0, 0)}, (0, 0), tc)
    assert abs(abs(r["J45"]) - 1.0) < 0.03 and abs(r["J0"]) < 1e-6


def test_knobs_are_independent():
    p = Pair(A=6.35e-4, tilt=best_tilt(6.35e-4, 17.0), t0=2.2, base=-1.5, radius=17.0, freeform="inner", gap=1.0)
    a, b, c = p.power(0, 0), p.power(4, 0), p.power(0, 2)
    assert abs(b["M"] - a["M"]) > 2.5 and abs(b["J45"]) < 0.01 and abs(b["J0"]) < 0.01   # x slide: sphere only
    assert abs(c["J45"]) > 1.3 and abs(c["M"] - a["M"]) < 0.02 and abs(c["J0"]) < 0.01     # y slide: cylinder only


def test_optimised_beats_plain_off_axis_and_stays_sharp():
    opt = load(os.path.join(HERE, "results", "design_A0.000635_gap1_wide.json"))
    plain = Pair(A=opt.A, tilt=opt.tilt, t0=opt.t0, base=-1.5, radius=opt.radius, freeform="inner", gap=opt.gap)
    def b(p, M, J, g):
        return blur(power(p.surfaces, p.offsets(*p.solve(M, J)), g, p.z_vertex), M, 0.0, J)
    for M, J, g in [(-5.0, 0.5, (17.0, 8.0)), (2.5, -1.0, (-12.0, 15.0)), (-3.0, 1.2, (0.0, -19.0))]:
        assert b(opt, M, J, g) < 0.2 and b(opt, M, J, g) < 0.6 * b(plain, M, J, g)


def test_material_is_thick_enough_everywhere():
    opt = load(os.path.join(HERE, "results", "design_A0.000635_gap1_wide.json"))
    (a, _), (c, _) = opt.thickness()
    assert a > 1.0 and c > 1.0


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
