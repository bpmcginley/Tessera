"""Few-round (batched) MOSAIC vs fully sequential MOSAIC vs baselines.
Usage: python experiments/rounds.py <scenario>   (env N, SEED)"""
import json, os, sys
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.policy import Greedy, Staged
from mosaic.program import SCENARIOS, Mosaic, make_assay, population, run_informative_dorfman

N, SEED = int(os.environ.get("N", 40_000)), int(os.environ.get("SEED", 0))


def work(args):
    name, kind, tn, R = args
    sc = SCENARIOS[name]; a = make_assay(sc)
    rng = np.random.default_rng(SEED)
    p, inf = population(rng, N, sc["prev"], sc["auc"]); loads = a.draw_loads(rng, N)
    rng = np.random.default_rng(7 + SEED)
    if kind == "risk-ordered Dorfman":
        r = run_informative_dorfman(rng, a, p, inf, loads, tn); r["mean_rounds"], r["max_depth"] = 2.0, 2
    else:
        fac = (lambda: Greedy(tn, 0.9)) if kind == "sequential" else (lambda: Staged(tn, 0.9, max_rounds=R))
        r = Mosaic(a, policy_factory=fac, q=3, n=10).run(rng, p, inf, loads)
    return dict(kind=kind, tau_neg=tn, max_rounds=R, tests_pp=float(r["tests_pp"]), sens=float(r["sens"]), spec=float(r["spec"]), mean_rounds=float(r["mean_rounds"]))


if __name__ == "__main__":
    name = sys.argv[1]
    tns = [0.03, 0.02, 0.012, 0.007, 0.004]
    tasks = [(name, "sequential", tn, 0) for tn in tns] + [(name, "staged", tn, R) for R in (2, 3, 4) for tn in tns]
    tasks += [(name, "risk-ordered Dorfman", k, 2) for k in (0, 0.005, 0.01, 0.02)]
    with Pool(4) as pool:
        rows = pool.map(work, tasks, chunksize=1)
    json.dump(dict(scenario=name, N=N, seed=SEED, rows=rows), open(f"results/rounds_{name}.json", "w"), indent=1)
    for r in rows:
        print(f"{r['kind']:22s} R<={r['max_rounds']} tau={r['tau_neg']:<6} tests={r['tests_pp']:.3f} sens={r['sens']:.3f} spec={r['spec']:.4f} rounds={r['mean_rounds']:.2f}")
