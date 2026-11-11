# Prompt for the next session

Paste everything below the line into a new Claude Code session started in this
repository on your laptop.

---

You are continuing a research project in this repository. Read `RESEARCH.md`
first, then `opensight/README.md`. Do not modify the original C# code
(`src/`, `tests/`, `bench/`, `Tessera.slnx`, root `README.md`).

## Background

A previous cloud session built three research folders. Only one is worth
continuing: `opensight/`, an optical design for self-adjustable glasses that
correct astigmatism as well as near/far-sightedness. Two moulded plastic
plates per eye slide against each other; one slide direction sets sphere, the
other sets the amount of astigmatism, and rotating the round cell sets its
direction. The optics are verified by ray tracing and cross-checked against a
third-party tool (Optiland). Nothing has been built. `mosaic/` and `lohc/` are
finished records; leave them alone unless asked.

## How to work (the loop that was used)

1. Pick a real, documented need.
2. **Check prior art and patents before building anything.** One idea was
   dropped last time because it had already been published at 160 times the
   scale.
3. Simulate only what can be simulated reliably, and say what cannot.
4. Compare against the best existing alternative, not a weak one.
5. Report failures and limits as plainly as successes. Never overstate.
6. Keep each project self-contained in its own folder with a README, tests,
   and results files. Commit as you go.

## Set up

```bash
python -m venv .venv   # then activate it
pip install -r requirements-research.txt   # on Windows, drop tblite if it fails
python run_checks.py   # all 15 checks should pass
```

## Tasks, in priority order

### 1. Patent and prior-art search for the glasses (do this first)

The cloud session could not reach paper or patent sites; this machine can.

- Search Google Patents / Espacenet for: Alvarez lens spectacles, adjustable
  focus eyeglasses with astigmatism or cylinder correction, sliding lens
  pairs with a second slide direction and rotation. Known starting point:
  US7325922.
- Search the literature for optimised Alvarez-type spectacle lenses
  (authors to check: Barbero, Rubinstein, Zapata) and for anything resembling
  "perspective matching" of the rear plate or higher-order terms that act
  only when the plates are slid.
- Read the 2018 Tübingen study on self-refraction of sphero-cylindrical
  errors with Alvarez lenses (PMC5947140) in full.
- Write `opensight/PRIOR_ART.md`: what is already patented or published,
  whether each patent is likely still in force (filing dates), what in this
  design appears new, and what does not. Cite a URL for every claim. Say
  clearly that this is not legal advice.
- If the core design turns out to be fully anticipated or blocked, say so
  and stop before doing tasks 2–3.

### 2. Can a wearer set astigmatism unaided?

This is the largest unproven assumption.

- Simulate what a person sees through the lens: compute the blur for a given
  refractive error and lens setting, render a printed target (letters, a
  clock-dial or fan chart, a line grid) through that blur.
- Design a step-by-step procedure using the three independent adjustments
  (sphere first, then astigmatism amount and direction), and a printable
  chart to go with it.
- Model a wearer as a noisy observer and estimate how close they get, across
  a range of prescriptions, compared with sphere-only adjustment.
- State plainly that this is a model of human vision and needs a real trial.
  Deliver the printable chart, the written procedure, and the predicted
  accuracy.

### 3. Mechanism design

Only a block-level layout exists (`opensight/cad/cell_layout.step`,
`opensight/experiments/cad.py`). Requirements from the optics:

- hold plate position to about 0.05–0.1 mm; plate rotation about the optical
  axis under 0.3°;
- travel ±3.1 mm per plate for sphere, about ±1 mm for cylinder;
- 32 mm round plates, cell about 47 mm across, lens tilt on the face under
  about 5°;
- a lock, and printed scales (`opensight/results/setting_table.csv`).

Produce a real mechanical design in CadQuery: opposed-thread screws,
carriers, guides, rotating cell with axis scale, lock, and a frame that sets
eye spacing. Check clearances and redo the tolerance stack-up
(`opensight/experiments/mechanism.py`) with the actual geometry.

### 4. If time remains

Look for one new public-benefit project using the same loop. Data sites that
were blocked in the cloud (CDC, Zenodo, Hugging Face, OpenML) are reachable
here.

## What "done" looks like

- `opensight/PRIOR_ART.md` exists with sources and a clear verdict.
- Tasks 2 and 3 each have code, results files, tests, and a README section
  with limits.
- `python run_checks.py` passes.
- A short final summary: what was established, what failed, what is still
  unknown, and what a human expert or lab must do next.
