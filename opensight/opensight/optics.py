"""Exact geometric ray tracing through freeform plates, and spectacle-style
power evaluation along any direction of gaze.

Units: millimetres; optical power in dioptres (1/m).  +z points from the world
towards the eye.  A surface is z = z0 + poly(x - ox, y - oy), where (ox, oy) is
the lateral slide of the plate that carries it.
"""
from __future__ import annotations

import numpy as np


class Poly:
    """Bivariate polynomial sum c[i,j] x^i y^j."""

    def __init__(self, terms=None):
        self.t = dict(terms or {})

    def __add__(self, o):
        t = dict(self.t)
        for k, v in o.t.items():
            t[k] = t.get(k, 0.0) + v
        return Poly(t)

    def scale(self, s):
        return Poly({k: v * s for k, v in self.t.items()})

    def val(self, x, y):
        z = np.zeros_like(x, dtype=float)
        for (i, j), c in self.t.items():
            z = z + c * x**i * y**j
        return z

    def grad(self, x, y):
        gx = np.zeros_like(x, dtype=float); gy = np.zeros_like(x, dtype=float)
        for (i, j), c in self.t.items():
            if i:
                gx = gx + c * i * x ** (i - 1) * y**j
            if j:
                gy = gy + c * j * x**i * y ** (j - 1)
        return gx, gy


class Surface:
    """z = z0 + sphere(curv) + poly.  curv = 1/R of an exact spherical base
    (positive = centre of curvature on the eye side)."""

    def __init__(self, z0, poly, n_before, n_after, plate=0, curv=0.0):
        self.z0, self.poly, self.n1, self.n2, self.plate, self.curv = z0, poly, n_before, n_after, plate, curv

    def val(self, x, y):
        z = self.poly.val(x, y)
        if self.curv:
            r2 = x * x + y * y
            z = z + self.curv * r2 / (1 + np.sqrt(np.maximum(1 - self.curv**2 * r2, 1e-9)))
        return z

    def grad(self, x, y):
        gx, gy = self.poly.grad(x, y)
        if self.curv:
            k = self.curv / np.sqrt(np.maximum(1 - self.curv**2 * (x * x + y * y), 1e-9))
            gx, gy = gx + k * x, gy + k * y
        return gx, gy


def rot(ax, ay):
    """Rotation matrix: angle ax about the y axis, then ay about the x axis (radians)."""
    cx, sx, cy, sy = np.cos(ax), np.sin(ax), np.cos(ay), np.sin(ay)
    Ry = np.array([[cx, 0, sx], [0, 1, 0], [-sx, 0, cx]])
    Rx = np.array([[1, 0, 0], [0, cy, -sy], [0, sy, cy]])
    return Rx @ Ry


def trace(p, d, surfaces, offsets, reverse=False):
    """Trace rays (p[N,3], d[N,3] unit) through surfaces in order.
    offsets[plate] = (ox, oy) for a flat slide, or (ox, oy, R, pivot) to also
    rotate the plate by matrix R about a pivot point (sliding along a curve).
    reverse=True goes eye -> world."""
    p = np.array(p, dtype=float); d = np.array(d, dtype=float)
    seq = surfaces[::-1] if reverse else surfaces
    for s in seq:
        ox, oy = offsets[s.plate][:2]
        Rm = offsets[s.plate][2] if len(offsets[s.plate]) > 2 else None
        if Rm is not None:
            piv = offsets[s.plate][3]
            p = (p - piv) @ Rm + piv; d = d @ Rm
        n1, n2 = (s.n2, s.n1) if reverse else (s.n1, s.n2)
        t = (s.z0 - p[:, 2]) / d[:, 2]
        for _ in range(8):  # Newton on the ray parameter
            x = p[:, 0] + t * d[:, 0] - ox; y = p[:, 1] + t * d[:, 1] - oy
            f = p[:, 2] + t * d[:, 2] - s.z0 - s.val(x, y)
            gx, gy = s.grad(x, y)
            t = t - f / (d[:, 2] - gx * d[:, 0] - gy * d[:, 1])
        p = p + t[:, None] * d
        gx, gy = s.grad(p[:, 0] - ox, p[:, 1] - oy)
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        cosi = np.sum(nrm * d, 1)
        nrm = np.where(cosi[:, None] < 0, -nrm, nrm); cosi = np.abs(cosi)
        mu = n1 / n2
        k = 1 - mu**2 * (1 - cosi**2)
        d = mu * d + (np.sqrt(np.maximum(k, 0)) - mu * cosi)[:, None] * nrm
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        if Rm is not None:
            p = (p - piv) @ Rm.T + piv; d = d @ Rm.T
    return p, d


def _pupil(radius, rings=3):
    pts = [(0.0, 0.0)]
    for r in range(1, rings + 1):
        for k in range(6 * r):
            a = 2 * np.pi * k / (6 * r)
            pts.append((radius * r / rings * np.cos(a), radius * r / rings * np.sin(a)))
    return np.array(pts)


PUP = _pupil(2.0)  # 4 mm pupil


def power(surfaces, offsets, gaze=(0.0, 0.0), z_vertex=0.0, d_rot=27.0, n_wave=None, decenter=(0.0, 0.0), tilt_deg=(0.0, 0.0)):
    """Power the eye receives along a direction of gaze (degrees, about the eye's
    centre of rotation d_rot mm behind the back vertex).

    Returns dict(M, J0, J45 in dioptres, hoa = residual ray-angle RMS in arcmin,
    prism in prism dioptres).  decenter: sideways/vertical offset (mm) of the eye
    from the lens centre.  tilt_deg: (pantoscopic, wrap) tilt of the lens on the
    face, modelled by rotating the eye about the lens vertex.  Method: reverse-trace the chief ray from the
    rotation centre, send a 4 mm bundle of parallel rays back along it, and fit
    the emerging wavefront's vergence matrix on the vertex sphere."""
    ax, ay = np.radians(gaze)
    g = np.array([np.sin(ax) * np.cos(ay), np.sin(ay), np.cos(ax) * np.cos(ay)])
    Rt = rot(np.radians(tilt_deg[1]), np.radians(tilt_deg[0]))
    g = Rt @ g
    C = np.array([decenter[0], decenter[1], z_vertex]) + Rt @ np.array([0.0, 0.0, d_rot])
    pc, dc = trace(C[None], -g[None], surfaces, offsets, reverse=True)
    u = -dc[0]
    e1 = np.cross([0, 1, 0], u); e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1)
    start = pc[0] - 5.0 * u + PUP[:, :1] * e1 + PUP[:, 1:] * e2
    p, d = trace(start, np.repeat(u[None], len(PUP), 0), surfaces, offsets)
    f1 = np.cross([0, 1, 0], g); f1 /= np.linalg.norm(f1); f2 = np.cross(g, f1)
    V0 = C - d_rot * g
    t = ((V0 - p) @ g) / (d @ g)
    q = p + t[:, None] * d - V0
    X = np.stack([np.ones(len(q)), q @ f1, q @ f2], 1)
    tau = np.stack([d @ f1, d @ f2], 1) / (d @ g)[:, None]
    coef, *_ = np.linalg.lstsq(X, tau, rcond=None)
    V = -1000.0 * coef[1:].T  # dioptres; diverging = negative
    res = tau - X @ coef
    return dict(M=(V[0, 0] + V[1, 1]) / 2, J0=(V[0, 0] - V[1, 1]) / 2, J45=(V[0, 1] + V[1, 0]) / 2,
                hoa=float(np.sqrt((res**2).sum(1).mean())) * 3437.75,
                prism=float(100 * np.linalg.norm(np.cross(u, g))))
