"""Evolutionary search for hydrogen carriers with a self-correcting model.

Loop per generation:
  1. mutate the current best molecules (single atom-level edits)
  2. score every new molecule with fast xTB + the learned correction
  3. send the most promising new ones to DFT
  4. record how wrong the model was on them (before it saw them), then retrain
Usage: python experiments_search.py [generations] [dft_per_generation]"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
from multiprocessing import Pool
import numpy as np
from lohc.chem import canon, capacity, perhydro, valid
from lohc.energy import reaction, xtb
from lohc.evolve import Corrector, features, mutants

TARGET, WIDTH = 45.0, 7.0   # desired dehydrogenation enthalpy (kJ/mol H2) and tolerance
MAXH = 14
SEEDS = ["c1ccccc1", "Cc1ccccc1", "c1ccc2ccccc2c1", "c1ccncc1", "c1cc[nH]c1", "Cn1cccc1", "c1ccc2[nH]ccc2c1", "Cn1ccc2ccccc21",
         "Cc1cc2ccccc2[nH]1", "c1ccc2ncccc2c1", "c1cnccn1", "c1ccc2c(c1)[nH]c1ccccc12", "CCn1c2ccccc2c2ccccc21", "c1c[nH]cn1",
         "c1ccoc1", "c1ccc2occc2c1", "c1ccc2nc3ccccc3nc2c1", "c1cnc2cccnc2c1"]


def score(dh, wt):
    """Higher is better: hydrogen capacity, discounted when the enthalpy leaves the target window."""
    return wt * np.exp(-(((dh - TARGET) / WIDTH) ** 2))


def w_xtb(s):
    try:
        return s, reaction(s, "xtb")
    except Exception:
        return s, None


def w_dft(s):
    try:
        e = reaction(s, "dft")
        de, hc = reaction(s, "xtb", thermo=True)
        return s, (None if e is None else e + hc)
    except Exception:
        return s, None


if __name__ == "__main__":
    G = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    seeds = [canon(s) for s in SEEDS]
    assert all(valid(s, 16) for s in seeds), [s for s in seeds if not valid(s, 16)]
    X, D, log = {}, {}, dict(target=TARGET, width=WIDTH, generations=[])
    out = "results/search.json"
    with Pool(4) as pool:
        t0 = time.time()
        X.update({s: v for s, v in pool.map(w_xtb, seeds, chunksize=1) if v is not None})
        D.update({s: v for s, v in pool.map(w_dft, seeds, chunksize=1) if v is not None})
        print(f"gen 0: {len(D)} seed molecules computed with DFT ({time.time()-t0:.0f}s)", flush=True)
        model = Corrector().fit([features(s, X[s]) for s in D], [D[s] for s in D])
        elite = sorted(D, key=lambda s: -score(D[s], capacity(s)))[:10]
        log["generations"].append(dict(gen=0, n_dft=len(D), best=[(s, round(D[s], 1), round(capacity(s), 2)) for s in elite[:5]]))
        for g in range(1, G + 1):
            t0 = time.time()
            cand = set()
            for s in elite:
                cand |= mutants(s, MAXH)
            new = [s for s in cand if s not in X]
            X.update({s: v for s, v in pool.map(w_xtb, new, chunksize=4) if v is not None})
            pool_s = [s for s in X if s not in D]
            pred = dict(zip(pool_s, model.predict([features(s, X[s]) for s in pool_s])))
            pick = sorted(pool_s, key=lambda s: -score(pred[s], capacity(s)))[:K]
            res = {s: v for s, v in pool.map(w_dft, pick, chunksize=1) if v is not None}
            err = [pred[s] - res[s] for s in res]            # model error BEFORE seeing these molecules
            D.update(res)
            model = Corrector().fit([features(s, X[s]) for s in D], [D[s] for s in D])
            elite = sorted(D, key=lambda s: -score(D[s], capacity(s)))[:10]
            row = dict(gen=g, screened_xtb=len(X), n_dft=len(D), prospective_mae=float(np.mean(np.abs(err))) if err else None,
                       prospective_bias=float(np.mean(err)) if err else None,
                       picked=[(s, round(pred[s], 1), round(res[s], 1), round(capacity(s), 2)) for s in res],
                       best=[(s, round(D[s], 1), round(capacity(s), 2), round(float(score(D[s], capacity(s))), 2)) for s in elite[:8]])
            log["generations"].append(row)
            log["dft"] = {s: D[s] for s in D}; log["xtb"] = {s: X[s] for s in X}
            json.dump(log, open(out, "w"), indent=1)
            print(f"gen {g}: screened {len(X)} by xTB, {len(D)} by DFT; model error on new picks {row['prospective_mae']:.1f} kJ/mol; "
                  f"best {elite[0]} dH={D[elite[0]]:.1f} wt%={capacity(elite[0]):.2f}  ({time.time()-t0:.0f}s)", flush=True)
