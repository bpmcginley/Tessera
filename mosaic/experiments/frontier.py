"""Cost-vs-sensitivity frontiers for every strategy on every scenario.

Usage: python experiments/frontier.py [scenario ...]  (env N=population size)
Writes results/frontier_<scenario>.json
"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.program import (SCENARIOS, Mosaic, make_assay, population, run_dorfman,
                            run_individual, run_informative_dorfman)

N = int(os.environ.get("N", 100_000))
SEED = int(os.environ.get("SEED", 0))


def world(name, seed=None):
    seed = SEED if seed is None else seed
    sc = SCENARIOS[name]
    a = make_assay(sc)
    rng = np.random.default_rng(seed)
    p, inf = population(rng, N, sc["prev"], sc["auc"])
    return sc, a, p, inf, a.draw_loads(rng, N)


def task(args):
    name, method, knob = args
    sc, a, p, inf, loads = world(name)
    rng = np.random.default_rng(abs(hash((method, str(knob), SEED))) % 2**32)
    t0 = time.time()
    if method == "individual":
        r = run_individual(rng, a, p, inf, loads, knob)
    elif method == "dorfman":
        r = run_dorfman(rng, a, p, inf, loads, knob)
    elif method == "informative_dorfman":
        r = run_informative_dorfman(rng, a, p, inf, loads, knob)
    elif method == "mosaic":
        r = Mosaic(a, tau_neg=knob[0], tau_pos=knob[1], q=knob[2], n=12 if knob[2] == 0 else 10).run(rng, p, inf, loads)
    out = {k: (float(v) if not isinstance(v, int) else v) for k, v in r.items()}
    out.update(method=method, knob=knob, secs=round(time.time() - t0, 1))
    return out


def tasks(name):
    tri = [0, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08]
    t = [(name, "individual", k) for k in tri]
    t += [(name, "dorfman", s) for s in range(2, SCENARIOS[name]["max_pool"] + 1)]
    t += [(name, "informative_dorfman", k) for k in tri]
    t += [(name, "mosaic", (tn, tp, q)) for q in (0, 3) for tn in [0.05, 0.03, 0.02, 0.012, 0.007, 0.004, 0.002, 0.001, 0.0005] for tp in [0.6, 0.9]]
    return t


if __name__ == "__main__":
    names = sys.argv[1:] or list(SCENARIOS)
    with Pool(4) as pool:
        for name in names:
            t0 = time.time()
            rows = pool.map(task, sorted(tasks(name), key=lambda t: -(t[1] == "mosaic") * (1 + t[2][2] if t[1] == "mosaic" else 0)), chunksize=1)
            sc = SCENARIOS[name]
            json.dump(dict(scenario=name, seed=SEED, params=sc, N=N, rows=rows), open(f"results/frontier_{name}.json" if SEED == 0 else f"results/frontier_{name}_seed{SEED}.json", "w"), indent=1)
            print(name, f"{time.time()-t0:.0f}s", flush=True)
