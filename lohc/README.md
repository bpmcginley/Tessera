# LOHC search — evolving hydrogen-carrier molecules with a self-correcting model

**Goal:** find liquid organic hydrogen carriers (LOHCs) that hold a lot of
hydrogen and release it with little heat. An LOHC is an oil-like molecule that
is loaded with hydrogen at a plant, shipped in ordinary tanks, and unloaded
where the hydrogen is needed. The two numbers that matter first are:

- **capacity** — hydrogen as a share of the loaded molecule's weight (wt%);
- **release heat** — energy needed to get the hydrogen back out (kJ per mole
  of H2). Today's carriers need 50–69; lower means lower release temperature
  and less wasted energy.

> **Status: computational screening only. No molecule here has been made or
> tested.** Melting point, stability, reaction speed, catalyst behaviour and
> cost are not computed, and any one of them can rule a candidate out.

This folder is self-contained and unrelated to the other projects in the repo.

## How it works

1. **Building blocks.** Start from 18 known ring molecules. Each step makes
   one atom-level edit: swap a ring carbon for nitrogen, fuse on another ring,
   add or remove a methyl or ethyl group (`lohc/evolve.py`).
2. **Fast score.** A semi-empirical quantum method (GFN2-xTB, ~2 s per
   molecule) estimates the release heat. Alone it is useless: it is off by
   63 kJ/mol on average, with a scatter of 3.6.
3. **Learned correction.** A small regression model learns the gap between the
   fast method and an accurate one (density functional theory, B3LYP-D3 /
   def2-SVP, minutes per molecule).
4. **Loop.** Each generation: mutate the best molecules, score all new ones
   with fast method + correction, send the 8 most promising to the accurate
   method, record how wrong the model was on them, retrain, repeat.

## Results

**The learning loop works.** Error of the corrected fast model on molecules it
had not yet seen, generation by generation: 1.9, 1.2, 1.7, 1.1, 1.1 kJ/mol H2.
In five generations it screened 431 molecules and confirmed 58 with the
accurate method.

**The accurate method tracks experiment.** For six carriers with measured
values the computed (gas-phase) release heat is lower by a steady 3.5 kJ/mol
H2, with 0.9 scatter. I add that 3.5 to give "estimated liquid" values below.
Six points is a thin calibration.

| Known carrier | Computed + 3.5 | Measured |
|---|---|---|
| benzene | 69.6 | 68.7 |
| toluene | 68.3 | 68.3 |
| quinoline | 62.2 | 61.5 |
| 1-methylindole | 55.8 | 55.6 |
| indole | 53.9 | 53.7 |
| N-ethylcarbazole | 48.7 | 50.5 |

**Candidates.** 44 of the 58 confirmed molecules fall in a 40–55 kJ/mol H2
window; 23 of those avoid an N–C–N pattern in the loaded form that is likely
to be unstable. The most interesting, against today's benchmarks:

| Molecule (lean form) | Capacity (wt%) | Release heat, estimated (kJ/mol H2) | Note |
|---|---|---|---|
| toluene (commercial benchmark) | 6.2 | 68 | measured |
| N-ethylcarbazole (research benchmark) | 5.8 | 48.7 (measured 50.5) | measured |
| a triaza-phenanthrene, `c1cnc2c(c1)ncc1ncccc12` | **7.2** | 49.6 | three N–H groups when loaded |
| carbolines (carbazole with one ring C→N), e.g. `c1ccc2c(c1)[nH]c1cnccc12` | 6.7 | 47–48 | carbazole itself: 6.75 / 50.3 |
| pyrrolo-quinolines, e.g. `c1cnc2cc3cc[nH]c3cc2c1` | 6.7 | 49–51 | |
| N-ethyl-carbolines, e.g. `CCn1c2ccccc2c2ncccc21` | 5.8 | **45–47** | like-for-like with N-ethylcarbazole |

Honest reading:

- The gains are **modest**. Like-for-like (N-ethylated, the trick that makes
  carbazole low-melting), swapping one carbon for nitrogen lowers the release
  heat by about 2–3.5 kJ/mol H2 at the same capacity. The differences are only
  two to three times the model's scatter.
- The 7.2 wt% molecule matches toluene's capacity at N-ethylcarbazole's
  release heat **on paper**. It is very likely a solid, has three N–H groups
  that can poison catalysts or break off, and may be hard to make.
- The search drifted toward adding ring nitrogens, which is a known rule of
  thumb in this field. It rediscovered the rule; it did not find a new one.
- **Novelty is unchecked.** "Not in my literature file" is a weak test. Two
  large published screens exist (QM9-LOHC, 10,373 reactions up to 9 heavy
  atoms; an Argonne screen of ZINC15/GDB-17). My molecules have 13–14 heavy
  atoms, outside the first, but I could not check them against the second.
  Carbolines are well-known compounds; whether they have been studied as
  hydrogen carriers I do not know.

## Limits

- Only thermodynamics of full hydrogenation is computed. Not computed:
  melting and boiling points, reaction rates, partial-hydrogenation
  intermediates, side reactions (C–N bond breaking), catalyst poisoning,
  toxicity, synthesis route, cost.
- One geometry per molecule (best of a few conformers and stereoisomers);
  a modest basis set; vibrations from the fast method.
- The 3.5 offset mixes method error with gas-versus-liquid differences.
- `literature.md` was compiled by a search agent from search-result excerpts,
  not from reading the papers; treat its numbers as leads to verify.
- Molecules up to 14 heavy atoms only, C/H/N/O, fully aromatic ring systems.

## Reproduce

```bash
pip install rdkit pyscf pyscf-dispersion tblite ase numpy
cd lohc
python tests/test_lohc.py
PYTHONPATH=. python experiments_search.py 5 8      # ~50 min on 4 cores (instant from cache)
PYTHONPATH=. python experiments_report.py
PYTHONPATH=. python experiments_ethyl.py
```

All computed energies and geometries are cached in `results/cache/`.

## What would make this matter

1. Check the top candidates against the published screens and patents.
2. Predict or look up melting points; discard solids or find low-melting
   alkylated versions.
3. Compute the stepwise hydrogenation path and C–N bond strengths.
4. A chemist buys or makes a few grams of an N-ethyl-carboline and measures
   hydrogen uptake and release next to N-ethylcarbazole.

## Sources

See `literature.md` for the full list with caveats. Key ones:

- Verevkin et al., quinoline thermochemistry: https://doi.org/10.3390/app112411758
- Indole and 1-methylindole thermochemistry: https://www.mdpi.com/2673-9623/3/1/4
- Pez et al. patent (benzene value, nitrogen-heterocycle rule): https://patents.google.com/patent/US7101530B2/en
- LOHC review, J. Matthey Technol. Rev. 2022: https://www.ingentaconnect.com/contentone/matthey/jmtr/2022/00000066/00000003/art00006
