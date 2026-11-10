"""Mutation operators (atom-level edits on aromatic ring systems) and the
learned correction from fast xTB energies to DFT-quality enthalpies."""
from __future__ import annotations

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from .chem import canon, perhydro, valid

_RXN = {
    "C->N in ring": "[cH:1]>>[n:1]",
    "N->C in ring": "[nX2:1]>>[cH:1]",
    "add methyl": "[cH:1]>>[c:1]C",
    "remove methyl": "[c:1][CH3]>>[cH:1]",
    "N-methylate": "[nH:1]>>[n:1]C",
    "N-ethylate": "[nH:1]>>[n:1]CC",
    "N-dealkylate": "[n:1][CX4;!R]>>[nH:1]",
    "methyl->ethyl": "[a:1][CH3]>>[a:1]CC",
    "fuse benzene": "[cH:1]:[cH:2]>>[c:1]1:[c:2]:c:c:c:c:1",
    "fuse pyridine": "[cH:1]:[cH:2]>>[c:1]1:[c:2]:c:c:c:n:1",
    "fuse pyrrole": "[cH:1]:[cH:2]>>[c:1]1:[c:2]:c:c:[nH]:1",
    "fuse pyrrole b": "[cH:1]:[cH:2]>>[c:1]1:[c:2]:c:[nH]:c:1",
    "fuse imidazole": "[cH:1]:[cH:2]>>[c:1]1:[c:2]:n:c:[nH]:1",
    "fuse furan": "[cH:1]:[cH:2]>>[c:1]1:[c:2]:c:c:o:1",
    "NH->O": "[nH:1]>>[o:1]",
    "O->NH": "[o:1]>>[nH:1]",
}
RXN = {k: AllChem.ReactionFromSmarts(v) for k, v in _RXN.items()}


def mutants(smi, max_heavy=14):
    """All single-edit neighbours of a lean molecule that pass the validity filter."""
    m = Chem.MolFromSmiles(smi)
    out = set()
    for rx in RXN.values():
        try:
            prods = rx.RunReactants((m,))
        except Exception:
            continue
        for (p,) in prods:
            try:
                Chem.SanitizeMol(p)
            except Exception:
                continue
            s = canon(Chem.MolToSmiles(p))
            if s and s != smi and valid(s, max_heavy):
                out.add(s)
    return out


_PAT = {k: Chem.MolFromSmarts(v) for k, v in dict(n_pyridine="[nX2]", n_pyrrole="[nX3]", o_ring="[o]", methyl="[CH3]", fused="[R2]").items()}


def features(smi, xtb_de):
    """Inputs of the learned correction: the xTB energy plus simple counts per H2."""
    m = Chem.MolFromSmiles(smi)
    _, n = perhydro(smi)
    ri = m.GetRingInfo()
    f = [1.0, xtb_de] + [len(m.GetSubstructMatches(p)) / n for p in _PAT.values()]
    f += [sum(len(r) == 5 for r in ri.AtomRings()) / n, sum(len(r) == 6 for r in ri.AtomRings()) / n]
    return np.array(f)


class Corrector:
    """Ridge regression: (xTB energy, structure counts) -> DFT-level enthalpy per H2."""

    def __init__(self, lam=1.0):
        self.lam, self.w = lam, None

    def fit(self, X, y):
        X = np.asarray(X); y = np.asarray(y)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        self.mu[0], self.sd[0] = 0.0, 1.0
        Z = (X - self.mu) / self.sd
        R = self.lam * np.eye(Z.shape[1]); R[0, 0] = 0
        self.w = np.linalg.solve(Z.T @ Z + R, Z.T @ y)
        return self

    def predict(self, X):
        return ((np.asarray(X) - self.mu) / self.sd) @ self.w
