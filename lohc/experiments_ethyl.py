"""Like-for-like check: N-ethyl versions of the best scaffolds vs N-ethylcarbazole
(N-ethylation is how carbazole is made low-melting in practice)."""
import json, os
os.environ.setdefault("OMP_NUM_THREADS", "1")
from multiprocessing import Pool
from lohc.chem import canon, capacity, perhydro
from lohc.energy import reaction

MOLS = {"N-ethylcarbazole (benchmark)": "CCn1c2ccccc2c2ccccc21", "9-ethyl-beta-carboline": "CCn1c2ccccc2c2ccncc21",
        "5-ethyl-gamma-carboline": "CCn1c2ccccc2c2cnccc21", "5-ethyl-delta-carboline": "CCn1c2ccccc2c2ncccc21"}


def w(item):
    n, s = item
    e = reaction(s, "dft"); _, hc = reaction(s, "xtb", thermo=True)
    return dict(name=n, lean=canon(s), rich=perhydro(s)[0], wt_pct=round(capacity(s), 2), dH_gas_computed=round(e + hc, 1))


if __name__ == "__main__":
    off = json.load(open("results/report.json"))["validation"]["offset_added"]
    with Pool(4) as p:
        rows = p.map(w, MOLS.items())
    for r in rows:
        r["dH_liquid_estimate"] = round(r["dH_gas_computed"] + off, 1)
        print(r)
    json.dump(rows, open("results/ethyl.json", "w"), indent=1)
