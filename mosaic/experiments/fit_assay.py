"""Fit the load model to published pooled Xpert Ultra figures.

Targets (Start4All phase 1, conference slides 2026, not peer reviewed):
  individual Xpert Ultra sensitivity vs culture 88.0%; pooled (87% pools of 4) 84.9%.
We hold the detection curve fixed (lod 2.2, slope 0.3) and fit the mean and
spread of log10 load so that P(detect alone) and P(detect in a pool of 4) match."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.core import Assay

best = None
for sigma in np.arange(1.0, 6.01, 0.25):
    for mu in np.arange(3.0, 10.01, 0.1):
        a = Assay.from_load(mu, sigma, 2.2, 0.3, 1.0, 4, n_mc=40_000)
        err = (a.T[1, 1] - 0.880) ** 2 + (a.T[4, 1] - 0.849) ** 2
        if best is None or err < best[0]:
            best = (err, mu, sigma, a.T[1, 1], a.T[4, 1])
print("fit: mu=%.1f sigma=%.2f  -> individual %.3f, pool-of-4 %.3f" % best[1:])
