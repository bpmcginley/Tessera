"""The lens: two sliding freeform plates (Alvarez pair) in a rotating round cell.

Slide along the plates' x axis  -> changes sphere (spherical equivalent M).
Slide along the plates' y axis  -> adds a pure cross-cylinder J (no change in M).
Rotate the whole cell           -> sets the cylinder axis.
"""
from __future__ import annotations

import numpy as np

from .optics import Poly, Surface, power, rot

N_PC = 1.586  # polycarbonate at 587 nm


class Pair:
    def __init__(self, A=6.35e-4, tilt=0.0, t0=1.6, gap=0.2, base=0.0, n=N_PC, freeform="outer", extra=None, radius=19.0, bend=0.0, Rb=None, mu=1.0, extra2=None):
        """A: cubic coefficient (mm^-2). tilt: linear term reducing thickness.
        base: built-in power (D) so the slide range is centred where needed.
        freeform='outer' puts the cubic faces outside (flat faces slide on each
        other); 'inner' puts them facing each other.  extra: higher-order terms
        {(i,j): c} added to the cubic profile.  bend: shared curvature (1/mm)
        added to all faces (meniscus form).  Rb: if set, all faces sit on spheres
        centred Rb mm behind the mid-plane and the plates slide along that sphere
        (they rotate about its centre) instead of sliding flat."""
        self.Rb = Rb
        self.A, self.tilt, self.t0, self.gap, self.base, self.n, self.freeform, self.radius = A, tilt, t0, gap, base, n, freeform, radius
        cub = Poly({(3, 0): A / 3, (1, 2): A, (1, 0): tilt})
        if extra:
            cub = cub + Poly(extra)
        self.cub = cub
        # rear plate: the front profile rescaled laterally by mu ("perspective matching"):
        # c2(x, y) = c1(x / mu, y / mu), so the two line up along lines of sight from the eye
        cub2 = Poly({(i, j): c / mu ** (i + j) for (i, j), c in cub.t.items()})
        if extra2:
            cub2 = cub2 + Poly(extra2)
        self.cub2, self.mu = cub2, mu
        qb = -base / (2000.0 * (n - 1))  # r^2 coefficient giving `base` dioptres on one face
        quad = Poly({(2, 0): qb, (0, 2): qb})
        sph = Poly({(2, 0): bend, (0, 2): bend})
        g2 = gap / 2
        cv = (lambda z: 1.0 / (Rb - z)) if Rb else (lambda z: 0.0)
        if freeform == "outer":
            self.surfaces = [Surface(-g2 - t0, cub.scale(-1) + sph, 1.0, n, 0, cv(-g2 - t0)), Surface(-g2, sph, n, 1.0, 0, cv(-g2)),
                             Surface(g2, sph, 1.0, n, 1, cv(g2)), Surface(g2 + t0, cub2.scale(-1) + quad + sph, n, 1.0, 1, cv(g2 + t0))]
        else:
            self.surfaces = [Surface(-g2 - t0, sph, 1.0, n, 0, cv(-g2 - t0)), Surface(-g2, cub + sph, n, 1.0, 0, cv(-g2)),
                             Surface(g2, cub2 + sph, 1.0, n, 1, cv(g2)), Surface(g2 + t0, quad + sph, n, 1.0, 1, cv(g2 + t0))]
        self.z_vertex = g2 + t0

    def offsets(self, sx, sy):
        """Relative slide (sx, sy) split equally between the plates."""
        if self.Rb:
            piv = np.array([0.0, 0.0, self.Rb])
            a, b = sx / 2 / self.Rb, sy / 2 / self.Rb
            return {0: (0.0, 0.0, rot(-a, b), piv), 1: (0.0, 0.0, rot(a, -b), piv)}
        return {0: (sx / 2, sy / 2), 1: (-sx / 2, -sy / 2)}

    def power(self, sx, sy, gaze=(0, 0)):
        return power(self.surfaces, self.offsets(sx, sy), gaze, self.z_vertex)

    def solve(self, M, J):
        """Slides that give spherical equivalent M and cross-cylinder J on axis."""
        k = 2000.0 * self.A * (self.n - 1)  # dioptres per mm, first order
        s = np.array([(M - self.base) / k, J / k])
        for _ in range(6):
            r = self.power(*s)
            e = np.array([r["M"] - M, r["J45"] - J])
            h = 1e-3
            a = self.power(s[0] + h, s[1]); b = self.power(s[0], s[1] + h)
            Jm = np.array([[(a["M"] - r["M"]) / h, (b["M"] - r["M"]) / h], [(a["J45"] - r["J45"]) / h, (b["J45"] - r["J45"]) / h]])
            s = s - np.linalg.solve(Jm, e)
        return s

    def thickness(self, m=61):
        """(min, max) material thickness of each plate over its full extent
        (window radius plus the largest half-slide)."""
        ext = self.radius + 3.2
        g = np.linspace(-ext, ext, m)
        X, Y = np.meshgrid(g, g); ok = (np.abs(X) <= ext) & (X**2 / ext**2 + Y**2 / (self.radius + 1.2) ** 2 <= 1)
        c = self.cub.val(X, Y)[ok]; c2 = self.cub2.val(X, Y)[ok]
        qd = -self.base / (2000.0 * (self.n - 1)) * (X**2 + Y**2)[ok]
        sgn = 1 if self.freeform == "outer" else -1
        t1, t2 = self.t0 + sgn * c, self.t0 - sgn * c2 + qd
        return (float(t1.min()), float(t1.max())), (float(t2.min()), float(t2.max()))


def best_tilt(A, radius):
    """Linear term that minimises the peak sag of the cubic profile over the plate."""
    ext = radius + 3.2
    g = np.linspace(-ext, ext, 81)
    X, Y = np.meshgrid(g, g); ok = X**2 / ext**2 + Y**2 / (radius + 1.2) ** 2 <= 1
    base = (A * (X**3 / 3 + X * Y**2))[ok]; x = X[ok]
    ds = np.linspace(-A * ext**2, 0, 201)
    return float(ds[int(np.argmin([np.abs(base + d * x).max() for d in ds]))])


def conventional(F, front_D=None, n=N_PC, tc=1.5, cyl=0.0):
    """A conventional single-vision lens of power F (parabolic faces) for comparison.
    front_D: front-surface power; None = flat front."""
    c1 = (front_D or 0.0) / (2000.0 * (n - 1))
    c2 = c1 - F / (2000.0 * (n - 1))
    j = cyl / (2000.0 * (n - 1))
    return [Surface(0.0, Poly({(2, 0): c1, (0, 2): c1}), 1.0, n, 0), Surface(tc, Poly({(2, 0): c2, (0, 2): c2, (1, 1): -2 * j}), n, 1.0, 0)], tc


def load(path, t0=None):
    """Rebuild an optimised pair from a results/design_*.json file."""
    import json
    d = json.load(open(path))
    x = np.array(d["x"]) * np.array(d["scale"])
    ex = {tuple(k): v for k, v in zip(d["shared_terms"], x[1:1 + len(d["shared_terms"])])}
    ex2 = {tuple(k): v for k, v in zip(d["rear_terms"], x[1 + len(d["shared_terms"]):])}
    return Pair(A=d["A"], tilt=d["tilt"], t0=t0 or d.get("t0", 2.2), base=-1.5, radius=d["radius"], freeform="inner", gap=d["gap"], mu=1.0 + x[0], extra=ex, extra2=ex2)
