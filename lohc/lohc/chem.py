"""Molecule handling: lean (aromatic) form -> rich (ring-hydrogenated) form,
hydrogen capacity, validity filters, and 3D structures."""
from __future__ import annotations

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Descriptors
from rdkit.Chem.EnumerateStereoisomers import EnumerateStereoisomers, StereoEnumerationOptions

RDLogger.DisableLog("rdApp.*")
H2_MASS = 2.01588


def canon(smi):
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToSmiles(m) if m is not None else None


def perhydro(smi):
    """Fully hydrogenate every ring double bond. Returns (rich SMILES, n_H2)."""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None, 0
    h0 = sum(a.GetTotalNumHs() for a in m.GetAtoms())
    rw = Chem.RWMol(m)
    Chem.Kekulize(rw, clearAromaticFlags=True)
    for b in rw.GetBonds():
        if b.IsInRing() and b.GetBondType() == Chem.BondType.DOUBLE:
            b.SetBondType(Chem.BondType.SINGLE)
    for a in rw.GetAtoms():
        a.SetNoImplicit(False); a.SetNumExplicitHs(0)
    try:
        Chem.SanitizeMol(rw)
    except Exception:
        return None, 0
    h1 = sum(a.GetTotalNumHs() for a in rw.GetAtoms())
    return Chem.MolToSmiles(rw), (h1 - h0) // 2


def capacity(smi):
    """Gravimetric hydrogen capacity (wt%) of the rich form."""
    rich, n = perhydro(smi)
    if not rich or n == 0:
        return 0.0
    return 100.0 * n * H2_MASS / Descriptors.MolWt(Chem.MolFromSmiles(rich))


_BAD = [Chem.MolFromSmarts(s) for s in ("[#7]-[#7]", "[#8]-[#8]", "[#7]-[#8]", "[#8]-[#6]-[#8]", "[#7;!R]", "[#8;!R]", "[r3,r4]", "[#6;!R]=,#[*]")]


def valid(smi, max_heavy=16):
    """Chemically conservative filter on the lean form: C/H/N/O only, aromatic
    rings, hetero-atoms only inside rings, no weak N-N/O-O/N-O bonds in the
    rich form, no small rings, no exocyclic unsaturation."""
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None or m.GetNumHeavyAtoms() > max_heavy or m.GetNumHeavyAtoms() < 5:
        return False
    if any(a.GetSymbol() not in ("C", "N", "O") or a.GetFormalCharge() != 0 for a in m.GetAtoms()):
        return False
    if not any(a.GetIsAromatic() for a in m.GetAtoms()):
        return False
    if any(a.IsInRing() and not a.GetIsAromatic() for a in m.GetAtoms()):
        return False  # start from fully aromatic ring systems only
    rich, n = perhydro(smi)
    if not rich or n < 2:
        return False
    r = Chem.MolFromSmiles(rich)
    if any(r.HasSubstructMatch(p) for p in _BAD[:4]) or any(m.HasSubstructMatch(p) for p in _BAD[4:]):
        return False
    return True


def embed(smi, n_conf=4, seed=7, max_iso=4):
    """Low-energy 3D structures (MMFF) for a SMILES: a few stereoisomers x conformers.
    Returns a list of (symbols, coords[Angstrom]) sorted by MMFF energy, best first."""
    out = []
    m0 = Chem.MolFromSmiles(smi)
    isos = list(EnumerateStereoisomers(m0, options=StereoEnumerationOptions(maxIsomers=max_iso, rand=seed)))
    for iso in isos:
        mh = Chem.AddHs(iso)
        ids = AllChem.EmbedMultipleConfs(mh, n_conf, randomSeed=seed)
        if not len(ids):
            continue
        res = AllChem.MMFFOptimizeMoleculeConfs(mh, maxIters=500)
        for cid, (_, e) in zip(ids, res):
            out.append((e, [a.GetSymbol() for a in mh.GetAtoms()], mh.GetConformer(cid).GetPositions().copy()))
    out.sort(key=lambda t: t[0])
    return [(s, x) for _, s, x in out]
