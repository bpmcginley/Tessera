"""Image-quality maps: how far the delivered power is from the prescription
as the eye looks around (the standard way spectacle lenses are judged)."""
from __future__ import annotations

import numpy as np

from .optics import power

GAZES = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for r in (10.0, 20.0, 30.0) for a in np.arange(8) * np.pi / 4]
RX = [(M, J) for M in (-6.0, -4.0, -2.0, 0.0, 2.0, 3.0) for J in (0.0, 0.75, 1.5)]


def blur(r, M, J0, J45):
    """Dioptric blur: length of the power-error vector (D)."""
    return float(np.sqrt((r["M"] - M) ** 2 + (r["J0"] - J0) ** 2 + (r["J45"] - J45) ** 2))


def field(pair, M, J, gazes=GAZES):
    """Blur at each gaze for the pair set to prescription (M, J)."""
    sx, sy = pair.solve(M, J)
    off = pair.offsets(sx, sy)
    out = []
    for g in gazes:
        r = power(pair.surfaces, off, g, pair.z_vertex)
        out.append((blur(r, M, 0.0, J), r["hoa"]))
    return np.array(out), (sx, sy)


def score(pair, rx=RX, gazes=GAZES):
    """Mean and worst blur by gaze eccentricity over the prescription grid."""
    B = np.array([field(pair, M, J, gazes)[0][:, 0] for M, J in rx])
    ecc = np.array([np.hypot(*g) for g in gazes])
    return {int(e): (float(B[:, ecc == e].mean()), float(B[:, ecc == e].max())) for e in np.unique(ecc.round())}, B
