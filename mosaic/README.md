# MOSAIC — risk-aware adaptive pooled testing

**Goal:** find the same number of infected people with far fewer lab tests.

Many diagnostic tests (TB cartridges, HIV viral load, blood-bank screening, STI
PCR, veterinary and food-safety assays) are limited by the cost of each test.
*Pooling* mixes several samples and tests the mix once; if it is negative,
everyone in it is cleared with one test. The classic method (Dorfman, 1943) is
still what most labs use. MOSAIC replaces its fixed recipe with an exact
Bayesian engine that:

1. uses each person's **prior risk** (symptoms, an X-ray AI score, contact status…),
2. models **dilution** (a weak sample can hide in a big pool) and false positives,
3. always picks the next pool that tells it the most, and stops when no one is
   worth another test,
4. can print the result as a **bench card** (a decision tree a technician follows).

> **Status: research prototype, simulation only.** Nothing here has been tested
> on real samples. All populations and assay parameters are synthetic. Do not
> use it for clinical decisions. See "Limits" below.

This folder is self-contained and unrelated to the C# code elsewhere in the repo.

## Headline results (simulation)

Tests used per person to reach a sensitivity target, where the target is a
fraction of what you get by testing **everyone individually**. Every entry is
at least as specific as individual testing. Lower is better. 60,000 simulated
people per scenario, one seed.

| Scenario | Target | Best non-MOSAIC method | MOSAIC | Saving |
|---|---|---|---|---|
| TB-like triage, 10% prevalence, pool ≤ 8 | 100% | 0.98 (triage + individual) | **0.74** | 24% |
| | 97% | 0.83 (triage + individual) | **0.45** | 46% |
| | 90% | 0.37 (risk-ordered Dorfman) | **0.32** | 14% |
| High-load PCR, 2% prevalence, pool ≤ 16 | 97% | 0.39 (Dorfman) | **0.25** | 36% |
| | 94% | 0.23 (risk-ordered Dorfman) | **0.18** | 22% |
| | 90% | 0.22 (risk-ordered Dorfman) | **0.15** | 30% |
| Community screening, 1% prevalence, pool ≤ 16 | 94% | 0.65 (triage + individual) | **0.40** | 39% |
| | 90% | 0.37 (Dorfman) | **0.27** | 27% |
| No risk information, 3% prevalence | 90% | 0.56 (Dorfman, pools of 2) | 0.56 | **none** |

![frontiers](results/frontier.png)

In a noiseless setting the engine uses within 3–5% of the Shannon limit for
prevalence ≥ 5% (Dorfman is 25–50% above it); see `tests/test_core.py`.

### Grounded in published data (TB)

The first TB scenario used an invented dilution curve. Published figures show
it was too pessimistic: in the Start4All phase 1 study (conference slides,
2026, not yet peer reviewed) pooled Xpert Ultra kept 84.9% sensitivity against
88.0% for individual testing, mostly in pools of 4; a 2021 systematic review
reports similar retention for pools of 4 and lower sensitivity above 4.
`experiments/fit_assay.py` fits the load model to those two numbers, and the
`tb_ultra_fit` scenario caps pools at 4. Prevalence (10%) and risk-score quality
(AUC 0.85) are still assumptions. Three seeds, 40,000 people each:

| Target (share of individual-testing sensitivity) | Triage + individual | Dorfman | Risk-ordered Dorfman | MOSAIC |
|---|---|---|---|---|
| 100% | 0.98–1.00 | cannot reach | cannot reach | **0.51–0.57** |
| 98% | 0.83–0.84 | cannot reach | 0.48 | **0.42–0.43** |
| 96% | 0.69–0.70 | 0.56–0.57 | 0.45 | **0.36** |
| 93% | 0.59–0.60 | 0.56–0.57 | 0.37–0.40 | **0.31–0.34** |

So on the fitted assay MOSAIC matches individual testing's sensitivity with
about half the cartridges, and uses 10–20% fewer than risk-ordered Dorfman
where that method can reach the target. The 100% row relies on some repeat
tests (see Limits).

**Correction to read with that table.** The comparison only requires being as
specific as individual testing (about 98%). MOSAIC uses that slack: it
confirms fewer positives. Dorfman is naturally ~99.7% specific. If MOSAIC is
held to the same high specificity (confident-positive threshold 0.9), it only
**ties** risk-ordered Dorfman on this assay (0.405 tests at 84.1% sensitivity
vs 0.406 at 83.9%; 0.474 at 85.7% vs 0.450 at 85.7%). The remaining advantage
at high specificity is reach: sensitivity equal to individual testing at 0.73
tests per person, which Dorfman cannot attain. See `results/rounds_tb_ultra_fit.log`.

### Few-round version and risk-score safeguard (fitted TB assay)

- **Few rounds** (`Staged` in `mosaic/policy.py`): plans each round's pools up
  front so they can run in parallel. With at most 2 rounds it needs 0.45 tests
  per person at 85.2% sensitivity -- the same as risk-ordered Dorfman (0.45 at
  85.7%). So in the few-round regime there is **no gain** over the existing
  method; MOSAIC's edge needs sequential testing.
- **Safeguard**: flattening the reported risk toward the average (slope 0.6)
  before use keeps sensitivity within 84–87% under every miscalibration tested
  (78–90% without it), at the price of ~16% more tests when the score was
  actually fine. With the safeguard on, MOSAIC and risk-ordered Dorfman perform
  the same. See `results/robustness_tb_ultra_fit*.json`.

### What did *not* work (kept on purpose)

- **No risk information + strong dilution: no gain.** When sensitivity is capped
  by dilution, small pools are already near the best possible and MOSAIC only
  ties Dorfman.
- **Full sensitivity at low prevalence is out of reach for every pooling
  method tried** (community ≥ 97%, PCR 100%): low-load samples are lost when
  diluted. That is physics, not algorithm.
- **First self-improvement attempt failed.** `mosaic/learn.py` fits a value
  function to exact trees and re-plans with it (fitted policy iteration). Scored
  exactly, each generation got *worse* (cost 0.97 → 1.18 → 3.0). It is kept only
  as a record (`results/improve_tb_triage_q0.log`); the working loop is below.
- **A wrong risk model is dangerous.** If the risk score is overconfident,
  MOSAIC skips people it should test: PCR sensitivity fell from 0.89 to 0.52
  (risk-ordered Dorfman: 0.92 to 0.70). Risk scores must be calibrated on local
  data, and should be deliberately flattened if in doubt (costs tests, protects
  sensitivity). See `results/robustness_*.json`.
- **Many rounds.** Tests are chosen one at a time; the TB operating point needs
  4–5 sequential tests per cohort on average. The batched variant exists but
  gives up the advantage (see above).

## Recursive improvement (the version that works)

`experiments/evolve.py` optimises one number, total cost per person in units
of one test: **J = tests + 150 × missed infections + 30 × false alarms**.

- Generation 0: one information-greedy policy for everyone.
- Generations 1–4: for each of ~14 risk bands, mutate the best policies
  (stopping thresholds, pool-size cap, dilution penalty), score **every
  candidate exactly** on its full decision tree, keep the best. About 1,000
  policies are scored exactly per scenario; a generation can never be worse.
- Final: exact one-step lookahead on the first three tests of each cohort,
  kept only in bands where it is exactly better.

The optimiser only sees the decoder's model. Each generation is then re-scored
on the truth simulator (200,000 people), which it never saw:

| Scenario | Exact J: gen 0 → gen 4 → +lookahead | Simulator J: gen 0 → gen 4 → +lookahead | Best baseline (simulator) |
|---|---|---|---|
| High-load PCR | 0.446 → 0.429 → 0.428 | 0.443 → 0.440 → 0.442 | 0.476 (risk-ordered Dorfman) |
| TB-like triage | 2.093 → 2.027 → 2.021 | 2.572 → 2.521 → 2.532 | 2.916 (triage + individual) |
| Community 1% | 0.497 → 0.460 → 0.459 | 0.558 → 0.509 → 0.510 | 0.560 (risk-ordered Dorfman) |

Honest reading:

- In exact scoring the loop improves every generation, by 3–8% in total.
- On the simulator the gain is clear only for community screening (−9%), about
  2% for TB, and within noise for PCR (noise on simulator J is roughly ±0.01
  for PCR and community, more for TB).
- The exact lookahead step adds nothing measurable on the simulator.
- The decoder is optimistic for TB (exact 2.03 vs simulated 2.52): its model of
  the assay is not the simulator's.
- After evolution MOSAIC's total cost is 7% (PCR), 13% (TB) and 9% (community)
  below the best tuned baseline. Before evolution it only tied the baseline in
  community screening.

## How it works

- `mosaic/core.py` — exact posterior over all infection states of a cohort
  (≤ 16 people). Two decoders: a simple one (`Cohort`) and a load-aware one
  (`LoadCohort`) that tracks that a low-load person stays hard to detect on
  retest. The load-aware one is what reaches high sensitivity at low prevalence.
- `mosaic/policy.py` — information-greedy policy, Dorfman baseline, and exact
  evaluation of any policy's decision tree (expected tests, misses, false alarms).
- `mosaic/program.py` — synthetic population with a risk score of chosen
  quality (AUC), truth simulator with persistent per-person loads, baselines,
  and the stratified MOSAIC programme.
- `mosaic/card.py` — prints a bench card (example: `results/example_card.txt`).
- `mosaic/policy.py` `Rollout` — exact lookahead used by the improvement loop.
- `mosaic/learn.py` — the failed first self-improvement attempt (record only).

The decoder never sees the true loads; it only sees test outcomes. The
simulator and decoder use different models on purpose, so results include
model mismatch.

## Reproduce

```bash
pip install numpy matplotlib
cd mosaic
python tests/test_core.py                    # correctness checks (~1 min)
N=60000 python experiments/frontier.py       # all scenarios (~20 min, 4 cores)
python experiments/summarize.py && python experiments/plot.py
python experiments/robustness.py tb_triage 0.012 0.6 0 0.02
N=200000 python experiments/evolve.py community   # improvement loop (~30 min)
```

## Limits (read before believing the table)

- Synthetic everything: load distribution, dilution curve, risk-score quality.
  Real gains depend on real values of these.
- One random seed per scenario and no confidence intervals. The community
  scenario has only ~600 infected people, so its sensitivity is ±1–2 points.
- Repeat tests of the same person are simulated as independent given their
  load. Real repeat tests on one specimen are more correlated, so the
  highest-sensitivity MOSAIC points (which rely on retests) are optimistic.
- **The core idea is not new.** A short literature check found Bayesian group
  testing with dilution and individual risk priors (Tatsuoka, Chen and Lu,
  *Biostatistics* 2023, "Bayesian halving"), halving for heterogeneous
  populations (Bilder and Tebbs), and pooling with dilution and heterogeneous
  priors (Saraiva 2023; Aprahamian and El-Amine 2022). The search did not turn
  up pooled Xpert guided by X-ray/risk scores, but it was brief. What is here is
  an open, exact, tested implementation, the load-aware decoder, the exact
  improvement loop, and an honest benchmark -- not a proven breakthrough.
- Baselines were tuned over a grid, not exhaustively.

## Sources

- Systematic review of pooling sputum for Xpert testing, *Emerg Infect Dis* 2021: https://wwwnc.cdc.gov/eid/article/27/3/20-4090_article
- Start4All phase 1 slides (2026): https://aslm.org/wp-content/uploads/2026/04/4.-Tushar-GARG.pdf
- Bayesian group testing with dilution effects: https://www.medrxiv.org/content/10.1101/2021.01.15.21249894.full.pdf

## Next steps that would matter

1. Fit to individual-level pooled-assay data (only two summary numbers are used so far).
2. A batched policy that keeps the sequential advantage (the current one does not).
4. A wet-lab pilot on stored samples with known results.
