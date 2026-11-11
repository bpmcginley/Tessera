# Research projects in this repository

Three self-contained research folders live beside the original C# code (which
they do not touch). Each has its own README with results, limits and sources.

| Folder | What it is | Status | Verdict |
|---|---|---|---|
| `opensight/` | Self-adjustable glasses that also correct astigmatism: optical design, 3D models, tolerances | Design verified by ray tracing and cross-checked with a third-party tool; nothing built | **The one worth continuing** |
| `mosaic/` | Risk-aware pooled diagnostic testing | Simulation only | Ties existing methods on the one scenario tied to real data |
| `lohc/` | Evolutionary search for hydrogen-carrier molecules | Computational screening only | Modest gains on paper; novelty unchecked |

## Set up on a laptop

```bash
git clone https://github.com/bpmcginley/Tessera.git
cd Tessera
git checkout claude/revolutionary-scientific-ideation-xgov5c
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements-research.txt
python run_checks.py
```

- Python 3.10 or newer.
- If `tblite` fails to install (likely on Windows), remove that line and
  install the rest. Only computing *new* molecules in `lohc/` needs it; the
  cached results and the `lohc` tests run without it.
- Run each project's scripts from inside its own folder, with that folder on
  `PYTHONPATH` (the READMEs show the exact commands).
- The 3D models are in `opensight/cad/*.step`; any CAD viewer opens them.

## Where to pick up (opensight)

Done: optimised lens shapes; off-centre sharpness; tolerances; fit, tilt and
colour checks; independent ray-trace check; 3D plate models; slim 47 mm cell
with 32 mm round plates.

Open, in priority order:

1. **Patent and prior-art search.** The sliding-plate lens and the
   astigmatism trick are known; freedom to make and sell is unknown. This was
   blocked by network limits in the cloud session and is the first thing to do
   locally.
2. **Self-adjustment of astigmatism.** Unproven. Next step: simulate what a
   wearer sees and design a printed chart and procedure for a small trial.
3. **Mechanism.** Only a block-level layout exists. Needs real mechanical
   design; position must hold to about 0.05–0.1 mm.
4. **Outside review.** An optical engineer re-tracing the design in a
   commercial tool; a mould maker judging the plate shapes.

## Ideas already ruled out

- Child weight estimation from height and arm circumference for emergency
  dosing: already published with 453,990 children (PLoS ONE 2016 and 2018).
- A learned value function for pooled testing (`mosaic/mosaic/learn.py`):
  made results worse each generation; kept only as a record.
