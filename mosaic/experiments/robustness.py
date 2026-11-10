"""What if the risk model is wrong?  Distort the reported priors (truth unchanged)
and re-run MOSAIC and risk-ordered Dorfman at fixed settings.
Usage: python experiments/robustness.py <scenario> <tau_neg> <tau_pos> <q> <dorfman_triage>"""
import json, os, sys
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.program import SCENARIOS, Mosaic, make_assay, population, run_informative_dorfman

N = int(os.environ.get("N", 60_000))
SAFE = float(os.environ.get("SAFE", 1.0))  # <1 flattens reported risk toward the average before use
CASES = {"calibrated": (0.0, 1.0), "risk 2x overstated": (0.693, 1.0), "risk 2x understated": (-0.693, 1.0),
         "overconfident (slope 1.5)": (0.0, 1.5), "underconfident (slope 0.6)": (0.0, 0.6)}


def work(args):
    name, case, tn, tp, q, tri = args
    sc = SCENARIOS[name]; a = make_assay(sc)
    rng = np.random.default_rng(0)
    p_true, inf = population(rng, N, sc["prev"], sc["auc"])
    loads = a.draw_loads(rng, N)
    rng = np.random.default_rng(0)
    p_rep, inf2 = population(rng, N, sc["prev"], sc["auc"], miscal=CASES[case])
    assert (inf == inf2).all()
    if SAFE != 1.0:
        l0 = np.log(sc["prev"] / (1 - sc["prev"]))
        p_rep = 1 / (1 + np.exp(-(l0 + SAFE * (np.log(p_rep / (1 - p_rep)) - l0))))
    rng = np.random.default_rng(5)
    m = Mosaic(a, tau_neg=tn, tau_pos=tp, q=q, n=12 if q == 0 else 10).run(rng, p_rep, inf, loads)
    d = run_informative_dorfman(rng, a, p_rep, inf, loads, tri)
    f = lambda r: dict(tests_pp=r["tests_pp"], sens=r["sens"], spec=r["spec"])
    return dict(case=case, mosaic=f(m), informative_dorfman=f(d))


if __name__ == "__main__":
    name, tn, tp, q, tri = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
    with Pool(4) as pool:
        rows = pool.map(work, [(name, c, tn, tp, q, tri) for c in CASES])
    json.dump(dict(scenario=name, N=N, settings=dict(tau_neg=tn, tau_pos=tp, q=q, dorfman_triage=tri), rows=rows), open(f"results/robustness_{name}.json" if SAFE == 1.0 else f"results/robustness_{name}_safe{SAFE}.json", "w"), indent=1)
    for r in rows:
        print(f"{r['case']:28s} MOSAIC tests={r['mosaic']['tests_pp']:.3f} sens={r['mosaic']['sens']:.3f} spec={r['mosaic']['spec']:.4f} | risk-ordered Dorfman tests={r['informative_dorfman']['tests_pp']:.3f} sens={r['informative_dorfman']['sens']:.3f}")
