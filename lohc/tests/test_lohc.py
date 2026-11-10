"""Quick checks (no quantum chemistry needed except the cached one)."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lohc.chem import capacity, perhydro, valid
from lohc.evolve import Corrector, mutants

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_hydrogenation_counts_and_capacity():
    assert perhydro("c1ccccc1") == ("C1CCCCC1", 3)
    assert perhydro("CCn1c2ccccc2c2ccccc21")[1] == 6
    assert abs(capacity("c1ccccc1") - 7.19) < 0.01 and abs(capacity("CCn1c2ccccc2c2ccccc21") - 5.83) < 0.02


def test_filter_rejects_weak_bonds_and_accepts_known_carriers():
    assert valid("c1ccc2ncccc2c1") and valid("c1ccc2[nH]ccc2c1")
    assert not valid("c1ccnnc1")          # N-N bond in the hydrogen-rich form
    assert not valid("Nc1ccccc1")         # nitrogen outside a ring
    assert not valid("C1CCCCC1")          # nothing left to hydrogenate


def test_mutations_stay_valid():
    ms = mutants("c1ccc2[nH]ccc2c1")
    assert len(ms) > 10 and all(valid(m) for m in ms)


def test_corrector_recovers_a_linear_rule():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(40), rng.normal(100, 10, 40), rng.random(40)])
    y = 0.6 * X[:, 1] - 20 + 5 * X[:, 2]
    assert np.abs(Corrector(lam=1e-6).fit(X, y).predict(X) - y).max() < 1e-3


def test_computed_enthalpies_track_experiment():
    rep = json.load(open(os.path.join(HERE, "results", "report.json")))["validation"]
    assert len(rep["rows"]) >= 6 and rep["scatter_after_offset"] < 2.0


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
