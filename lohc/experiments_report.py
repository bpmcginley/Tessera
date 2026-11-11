"""Summarise the search: validation against experiment, learning curve,
ranked candidates with practical flags, and a novelty check against literature.md."""
import json, re
import numpy as np
from rdkit import Chem
from lohc.chem import canon, capacity, perhydro

d = json.load(open("results/search.json"))
D, X = d["dft"], d["xtb"]
ANCH = {"c1ccccc1": ("benzene", 68.7), "Cc1ccccc1": ("toluene", 68.3), "CCn1c2ccccc2c2ccccc21": ("N-ethylcarbazole", 50.5),
        "c1ccc2ncccc2c1": ("quinoline", 61.5), "Cn1ccc2ccccc21": ("1-methylindole", 55.6), "c1ccc2[nH]ccc2c1": ("indole", 53.7)}
rows = [(n, D[canon(s)], e) for s, (n, e) in ANCH.items() if canon(s) in D]
off = float(np.mean([e - c for _, c, e in rows]))
sd = float(np.std([e - c - off for _, c, e in rows]))
lit = set()
for tok in re.findall(r"`([^`]+)`", open("literature.md").read()):
    c = canon(tok)
    if c:
        lit.add(c)
AMINAL = Chem.MolFromSmarts("[#7]-[#6]-[#7]")
NH = Chem.MolFromSmarts("[#7;H1,H2]")


def info(s):
    rich, n = perhydro(s)
    r = Chem.MolFromSmiles(rich)
    return dict(lean=s, rich=rich, n_H2=n, wt_pct=round(capacity(s), 2), dH_gas_computed=round(D[s], 1), dH_liquid_estimate=round(D[s] + off, 1),
                heavy_atoms=Chem.MolFromSmiles(s).GetNumHeavyAtoms(), aminal_in_rich_form=r.HasSubstructMatch(AMINAL),
                NH_groups_in_rich_form=len(r.GetSubstructMatches(NH)), in_literature_file=s in lit)


allc = [info(s) for s in D]
win = [c for c in allc if 40 <= c["dH_liquid_estimate"] <= 55]
win.sort(key=lambda c: -c["wt_pct"])
safe = [c for c in win if not c["aminal_in_rich_form"]]
raw = np.array([X[s] - D[s] for s in D])
gens = [dict(gen=g["gen"], n_dft=g["n_dft"], screened=g.get("screened_xtb"), model_error_on_new=g.get("prospective_mae")) for g in d["generations"]]
rep = dict(validation=dict(rows=[dict(name=n, computed_gas=round(c, 1), literature=e) for n, c, e in rows], offset_added=round(off, 1), scatter_after_offset=round(sd, 1)),
           fast_method_raw_error=dict(mean=round(float(raw.mean()), 1), scatter=round(float(raw.std()), 1)), generations=gens,
           n_dft=len(D), n_screened=len(X), n_in_window=len(win), n_in_window_no_aminal=len(safe), top_in_window=win[:12], top_no_aminal=safe[:12])
json.dump(rep, open("results/report.json", "w"), indent=1)
print("validation offset", rep["validation"]["offset_added"], "scatter", rep["validation"]["scatter_after_offset"], "| raw xTB error", rep["fast_method_raw_error"])
for g in gens:
    print(g)
print(f"{len(D)} DFT, {len(X)} screened; in 40-55 window: {len(win)}; without aminal: {len(safe)}")
for title, lst in (("TOP (any)", win[:8]), ("TOP (no aminal)", safe[:10])):
    print(title)
    for c in lst:
        print(f"  {c['lean']:32s} wt%={c['wt_pct']:.2f} dH_liq~{c['dH_liquid_estimate']:.1f} nH2={c['n_H2']} heavy={c['heavy_atoms']} NH={c['NH_groups_in_rich_form']} known={c['in_literature_file']}")
