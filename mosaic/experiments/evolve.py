"""Recursive improvement that cannot go backwards.

Objective (lower is better), in units of one test:
    J = tests + c_fn * missed infections + c_fp * false alarms      (per person)

gen 0   one global information-greedy policy (best thresholds on a grid)
gen 1+  evolutionary search *per risk band*: mutate the best policies, score every
        candidate EXACTLY on its full decision tree, keep the best (monotone)
final   exact one-step lookahead (rollout) on top of each band's best policy,
        kept only where it is exactly better
Then every generation is re-scored on the truth simulator (which the optimiser
never saw) next to the tuned baselines.

Usage: python experiments/evolve.py <scenario> [c_fn c_fp]
"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mosaic.core import LoadCohort
from mosaic.policy import Greedy, Rollout, Tree
from mosaic.program import (DEFAULT_EDGES, SCENARIOS, Mosaic, make_assay, population, run_dorfman,
                            run_individual, run_informative_dorfman)

N = int(os.environ.get("N", 60_000))
NCO, Q, MAXS, PRUNE, DEPTH = 8, 3, 6000, 1e-4, 30
GENS, POP = int(os.environ.get("GENS", 4)), int(os.environ.get("POP", 16))
_W = {}


def world(name):
    if name not in _W:
        sc = SCENARIOS[name]; a = make_assay(sc); a.classes(Q)
        rng = np.random.default_rng(0)
        p, inf = population(rng, N, sc["prev"], sc["auc"])
        _W[name] = (sc, a, p, inf, a.draw_loads(rng, N))
    return _W[name]


def cohort(a, pbar):
    n = NCO
    while True:
        try:
            return LoadCohort([pbar] * n, a, q=Q, max_states=MAXS)
        except MemoryError:
            n -= 1


def policy(th, c_fn, c_fp, rollout=False):
    g = Greedy(th[0], th[1], max_pool=int(th[2]), size_penalty=th[3], call_thr=c_fp / (c_fn + c_fp))
    return Rollout(g, c_fn, c_fp, max_depth=DEPTH) if rollout else g


def exact(args):
    name, pbar, th, c_fn, c_fp, rollout = args
    a = world(name)[1]
    c = cohort(a, pbar)
    t = Tree(c, policy(th, c_fn, c_fp, rollout), max_depth=DEPTH)
    return t.j_from((), c_fn, c_fp, PRUNE) / c.n


def truth(args):
    name, label, spec, c_fn, c_fp = args
    sc, a, p, inf, loads = world(name)
    rng = np.random.default_rng(11)
    t0 = time.time()
    if spec[0] == "mosaic":
        m = Mosaic(a, q=Q, n=NCO, max_states=MAXS)
        m.max_depth = DEPTH
        m.policies = {int(s): (lambda th=th, ro=ro: policy(th, c_fn, c_fp, ro)) for s, (th, ro) in spec[1].items()}
        r = m.run(rng, p, inf, loads)
    elif spec[0] == "individual":
        r = run_individual(rng, a, p, inf, loads, spec[1])
    elif spec[0] == "dorfman":
        r = run_dorfman(rng, a, p, inf, loads, spec[1])
    else:
        r = run_informative_dorfman(rng, a, p, inf, loads, spec[1])
    n_inf = int(inf.sum())
    J = (r["tests"] + c_fn * (n_inf - r["tp"]) + c_fp * r["fp"]) / N
    return dict(label=label, J=float(J), tests_pp=float(r["tests_pp"]), sens=float(r["sens"]), spec=float(r["spec"]), secs=round(time.time() - t0))


def mutate(rng, th, m):
    tn, tp, mp, sp = th
    tn = float(np.clip(tn * np.exp(rng.normal(0, 0.5)), 1e-4, 1.0))
    tp = float(np.clip(tp + rng.normal(0, 0.1), 0.2, 0.99))
    mp = int(np.clip(mp + rng.integers(-2, 3), 1, m))
    sp = float(rng.choice([1e-6, 0.003, 0.01, 0.03])) if rng.random() < 0.3 else sp
    return (tn, tp, mp, sp)


if __name__ == "__main__":
    name = sys.argv[1]
    c_fn, c_fp = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (150.0, 30.0)
    sc, a, p, inf, loads = world(name)
    m = sc["max_pool"]
    b = np.searchsorted(DEFAULT_EDGES, p, side="right") - 1
    strata = [int(s) for s in np.unique(b)]
    pbar = {s: float(p[b == s].mean()) for s in strata}
    wt = {s: float((b == s).mean()) for s in strata}
    rng = np.random.default_rng(3)
    log = dict(scenario=name, c_fn=c_fn, c_fp=c_fp, N=N, strata={s: dict(p=pbar[s], share=wt[s]) for s in strata}, generations=[])
    out = f"results/evolve_{name}.json"
    with Pool(4) as pool:
        # ---- gen 0: one global policy from a grid
        grid = [(tn, tp, m, 1e-6) for tn in (0.001, 0.003, 0.01, 0.03) for tp in (0.5, 0.8)] + [(1.0, 0.8, m, 1e-6)]
        res = pool.map(exact, [(name, pbar[s], th, c_fn, c_fp, False) for th in grid for s in strata], chunksize=1)
        R = np.array(res).reshape(len(grid), len(strata))
        tot = R @ np.array([wt[s] for s in strata])
        g0 = grid[int(np.argmin(tot))]
        best = {s: (g0, float(R[int(np.argmin(tot)), i])) for i, s in enumerate(strata)}
        seen = {s: {th: float(R[k, i]) for k, th in enumerate(grid)} for i, s in enumerate(strata)}
        Jm = lambda bs: float(sum(wt[s] * bs[s][1] for s in strata))
        specs = [("gen 0 (one global policy)", ("mosaic", {s: (best[s][0], False) for s in strata}))]
        log["generations"].append(dict(gen=0, J_model=Jm(best), policy={s: best[s][0] for s in strata}, evaluated=len(res)))
        print(f"gen 0: exact J = {Jm(best):.4f}   global thresholds {g0}", flush=True)
        # ---- gens 1..: per-band evolutionary search, exact scoring, keep-best
        n_eval = len(res)
        for gen in range(1, GENS + 1):
            tasks = []
            for s in strata:
                top = sorted(seen[s], key=seen[s].get)[:4]
                cands = set()
                while len(cands) < POP:
                    th = mutate(rng, top[rng.integers(len(top))], m)
                    if th not in seen[s]:
                        cands.add(th)
                tasks += [(s, th) for th in cands]
            res = pool.map(exact, [(name, pbar[s], th, c_fn, c_fp, False) for s, th in tasks], chunksize=1)
            n_eval += len(res)
            for (s, th), j in zip(tasks, res):
                seen[s][th] = j
                if j < best[s][1]:
                    best[s] = (th, j)
            specs.append((f"gen {gen} (evolved per risk band)", ("mosaic", {s: (best[s][0], False) for s in strata})))
            log["generations"].append(dict(gen=gen, J_model=Jm(best), policy={s: best[s][0] for s in strata}, evaluated=n_eval))
            print(f"gen {gen}: exact J = {Jm(best):.4f}   ({n_eval} policies scored exactly so far)", flush=True)
            json.dump(log, open(out, "w"), indent=1)
        # ---- exact rollout on top
        res = pool.map(exact, [(name, pbar[s], best[s][0], c_fn, c_fp, True) for s in strata], chunksize=1)
        ro = {s: (best[s][0], bool(j < best[s][1] - 1e-9)) for s, j in zip(strata, res)}
        bestR = {s: (best[s][0], min(j, best[s][1])) for s, j in zip(strata, res)}
        specs.append(("final (+ exact lookahead)", ("mosaic", ro)))
        log["generations"].append(dict(gen="rollout", J_model=Jm(bestR), rollout_used={s: ro[s][1] for s in strata}))
        print(f"rollout: exact J = {Jm(bestR):.4f}   improved bands: {sum(v[1] for v in ro.values())}/{len(strata)}", flush=True)
        json.dump(log, open(out, "w"), indent=1)
        # ---- truth simulator: generations + tuned baselines
        tri = [0, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08]
        specs = [specs[0], specs[len(specs) // 2], specs[-2], specs[-1]]
        specs += [(f"individual, triage {k}", ("individual", k)) for k in tri]
        specs += [(f"Dorfman, pools of {k}", ("dorfman", k)) for k in range(2, m + 1)]
        specs += [(f"risk-ordered Dorfman, triage {k}", ("informative", k)) for k in tri]
        rows = pool.map(truth, [(name, lab, sp, c_fn, c_fp) for lab, sp in specs], chunksize=1)
    log["truth"] = rows
    json.dump(log, open(out, "w"), indent=1)
    print("\nTruth simulator (never seen by the optimiser):")
    for r in rows[:4]:
        print(f"  {r['label']:34s} J={r['J']:.4f} tests={r['tests_pp']:.3f} sens={r['sens']:.3f} spec={r['spec']:.4f}")
    for fam in ("individual", "Dorfman", "risk-ordered"):
        bb = min((r for r in rows[4:] if r["label"].startswith(fam)), key=lambda r: r["J"])
        print(f"  best {bb['label']:29s} J={bb['J']:.4f} tests={bb['tests_pp']:.3f} sens={bb['sens']:.3f} spec={bb['spec']:.4f}")
