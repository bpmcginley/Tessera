"""Energies at three levels:
  xTB  (GFN2-xTB, seconds)   - geometry optimisation and vibrations
  DFT  (B3LYP-D3BJ/def2-SVP, density fitting, minutes) - electronic energy on the xTB geometry
Everything is cached on disk so no molecule is computed twice."""
from __future__ import annotations

import json, os, hashlib
import numpy as np

HARTREE_KJ = 2625.4996
EV_KJ = 96.4853
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "cache")
os.makedirs(CACHE, exist_ok=True)


def _key(level, smi):
    return os.path.join(CACHE, level + "_" + hashlib.md5(smi.encode()).hexdigest() + ".json")


def _load(level, smi):
    f = _key(level, smi)
    return json.load(open(f)) if os.path.exists(f) else None


def _save(level, smi, d):
    json.dump(d, open(_key(level, smi), "w"))
    return d


def _atoms(sym, xyz):
    from ase import Atoms
    from tblite.ase import TBLite
    a = Atoms(sym, positions=xyz)
    a.calc = TBLite(method="GFN2-xTB", verbosity=0)
    return a


def xtb(smi, thermo=False):
    """Optimise the best MMFF structures with GFN2-xTB; return dict with energy
    (kJ/mol), geometry, and (if thermo) the enthalpy correction H(298)-E_elec."""
    hit = _load("xtb", smi)
    if hit and (not thermo or "hcorr" in hit):
        return hit
    from ase.optimize import LBFGS
    from .chem import embed
    if hit:
        best = (hit["e"], hit["sym"], np.array(hit["xyz"]))
    else:
        best = None
        for sym, xyz in embed(smi)[:3]:
            a = _atoms(sym, xyz)
            try:
                LBFGS(a, logfile=None).run(fmax=0.05, steps=400)
                e = a.get_potential_energy() * EV_KJ
            except Exception:
                continue
            if best is None or e < best[0]:
                best = (e, sym, a.get_positions().copy())
        if best is None:
            return None
    d = dict(smi=smi, e=float(best[0]), sym=list(best[1]), xyz=np.asarray(best[2]).tolist())
    if thermo:
        import shutil, tempfile
        from ase.thermochemistry import IdealGasThermo
        from ase.vibrations import Vibrations
        a = _atoms(d["sym"], np.array(d["xyz"]))
        LBFGS(a, logfile=None).run(fmax=0.01, steps=300)
        tmp = tempfile.mkdtemp()
        try:
            vib = Vibrations(a, name=os.path.join(tmp, "v")); vib.run()
            en = np.real(vib.get_energies())
            lin = len(a) == 2
            en = np.sort(en)[5 if lin else 6:]
            en = np.maximum(en, 1e-4)
            th = IdealGasThermo(vib_energies=en, potentialenergy=0.0, atoms=a, geometry="linear" if lin else "nonlinear", symmetrynumber=1, spin=0)
            d["hcorr"] = float(th.get_enthalpy(298.15, verbose=False) * EV_KJ)
            d["e"] = float(a.get_potential_energy() * EV_KJ); d["xyz"] = a.get_positions().tolist()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _save("xtb", smi, d)


def dft(smi, basis="def2-svp"):
    """B3LYP-D3BJ single point on the xTB geometry (kJ/mol)."""
    level = "dft_" + basis.replace("-", "")
    hit = _load(level, smi)
    if hit:
        return hit
    g = xtb(smi)
    if g is None:
        return None
    from pyscf import gto, dft as pdft
    mol = gto.M(atom=[(s, tuple(x)) for s, x in zip(g["sym"], g["xyz"])], basis=basis, verbose=0)
    mf = pdft.RKS(mol).density_fit()
    mf.xc = "b3lyp"; mf.disp = "d3bj"; mf.grids.level = 3
    e = mf.kernel()
    if not mf.converged:
        return None
    return _save(level, smi, dict(smi=smi, e=float(e * HARTREE_KJ)))


def reaction(smi_lean, level="xtb", thermo=False, basis="def2-svp"):
    """Dehydrogenation energy per H2 (kJ/mol): rich -> lean + n H2.  Positive = heat needed."""
    from .chem import perhydro
    rich, n = perhydro(smi_lean)
    f = (lambda s: xtb(s, thermo)) if level == "xtb" else (lambda s: dft(s, basis))
    a, b, h = f(smi_lean), f(rich), f("[H][H]")
    if not (a and b and h):
        return None
    de = (a["e"] + n * h["e"] - b["e"]) / n
    if thermo and level == "xtb":
        return de, (a["hcorr"] + n * h["hcorr"] - b["hcorr"]) / n
    return de
