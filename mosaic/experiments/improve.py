"""Recursive improvement loop, scored exactly.

gen 0 = best information-greedy policy (thresholds tuned to the cost);
gen k+1 = one-step lookahead on the value function fitted to gen k's exact trees.
Usage: python experiments/improve.py <scenario> [c_fn c_fp]
"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.core import Cohort, LoadCohort
from mosaic.learn import KNOTS, ValueGreedy, fit_g
from mosaic.policy import Greedy, Tree
from mosaic.program import SCENARIOS, make_assay

STRATA = [0.003, 0.01, 0.03, 0.08, 0.2]
NCO, Q = int(os.environ.get("NCO", 10)), int(os.environ.get("Q", 0))
PRUNE = 1e-5


def work(args):
    name, p, kind, par, c_fn, c_fp = args
    a = make_assay(SCENARIOS[name])
    pol = Greedy(*par) if kind == "greedy" else ValueGreedy(c_fn, c_fp, par)
    t = Tree(LoadCohort([p] * NCO, a, q=Q) if Q else Cohort([p] * NCO, a), pol, max_depth=30)
    j, samples = t.values(c_fn, c_fp, prune=PRUNE)
    ev = t.evaluate(prune=PRUNE)
    return j / NCO, samples, ev["tests_pp"], ev["sens"], ev["spec"]


if __name__ == "__main__":
    name = sys.argv[1]
    c_fn, c_fp = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (100.0, 30.0)
    log = dict(scenario=name, c_fn=c_fn, c_fp=c_fp, strata=STRATA, gens=[])
    with Pool(4) as pool:
        best = None
        for tn in (0.003, 0.01, 0.02, 0.05):
            for tp in (0.5, 0.8, 0.95):
                res = pool.map(work, [(name, p, "greedy", (tn, tp), c_fn, c_fp) for p in STRATA])
                J = [r[0] for r in res]
                print(f"greedy tau=({tn},{tp}) J/person per stratum {np.round(J,4)} mean {np.mean(J):.4f}", flush=True)
                if best is None or np.mean(J) < np.mean(best[0]):
                    best = (J, res, (tn, tp))
        J, res, par = best
        for gen in range(5):
            row = dict(gen=gen, J=J, mean_J=float(np.mean(J)), tests_pp=[r[2] for r in res], sens=[r[3] for r in res], spec=[r[4] for r in res])
            if gen == 0:
                row["greedy_thresholds"] = par
            log["gens"].append(row)
            print(f"GEN {gen}: mean J/person {np.mean(J):.4f}  per stratum {np.round(J,4)}  tests {np.round(row['tests_pp'],3)} sens {np.round(row['sens'],3)}", flush=True)
            if gen == 4:
                break
            g = fit_g([s for r in res for s in r[1]], c_fn, c_fp)
            log["gens"][-1]["g_next"] = g.tolist()
            t0 = time.time()
            res = pool.map(work, [(name, p, "value", g, c_fn, c_fp) for p in STRATA])
            J = [r[0] for r in res]
    log["knots"] = KNOTS.tolist()
    json.dump(log, open(f"results/improve_{name}_q{Q}.json", "w"), indent=1)
