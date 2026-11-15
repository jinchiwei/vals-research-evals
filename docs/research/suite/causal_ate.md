# causal_ate: treatment effect on the treated with a valid 95% interval

Round 3, workstream C (`round3-prereg.md`). Built 2026-11-15 by a Claude Code worker (model: Claude Opus 5.5,
`claude-opus-5-5`) for the coordinator "neo". No Git commit was made.

Everything above the line "Results (after the gate was fixed)" was written before any comparator or agent
was run on the hidden datasets.

## 1. Data and licence check (00:55-01:05 EST)

| Candidate | Access | Licence / terms | Usable in a hosted image? |
|---|---|---|---|
| ACIC 2016 (`aciccomp2016` R package, 77 settings over IHDP covariates) | GitHub `vdorie/aciccomp/2016`, no login | Package DESCRIPTION: `License: GPL (>= 2)` (code). The bundled covariates are the IHDP study data, distributed by ICPSR (study 9795) under ICPSR terms of use, which forbid redistribution without ICPSR's written agreement (ICPSR standard terms, e.g. icpsr.umich.edu/web/ICPSR/studies/171/terms). The GPL label of the package does not license the upstream data. | **No** (redistribution of the IHDP covariates is not clearly permitted). Also needs R, which is not on teal. |
| ACIC 2017 (`aciccomp2017`, same IHDP covariates) | GitHub `vdorie/aciccomp/2017` | `License: GPL (>= 2)`; same IHDP upstream | **No**, same reason |
| ACIC 2019 (McGill) | Challenge site, "no registration required" (mcgill.ca/epi-biostat-occh/news-events/atlantic-causal-inference-conference-2019/data-challenge) | **No licence or terms stated** on the page | **No** (no stated permission to redistribute) |
| ACIC 2022 (Mathematica, longitudinal Medicare-like) | Sign-up through the challenge e-mail list; `acic2022.mathematica.org` did not resolve on 2026-11-15 | Terms not found | **No** (sign-up = terms acceptance on Jin's behalf; licence unknown) |
| IHDP "as commonly distributed" (Hill 2011 / CFRNet CSVs) | various mirrors | none stated; upstream ICPSR 9795 | **No** |

**Choice: the brief's fallback.** An ACIC-2016-style data-generating process (DGP) of our own over real
covariates with a clean licence already on disk: PhysioNet/CinC Challenge 2012 v1.0.0 (ODC-By 1.0; downloaded
without login 2026-11-14, see `/home/jkwei/data/vals-suite/risk_icu/SOURCE.md`). A side benefit: the true
effects of ACIC 2016 are public and may be memorised by the models; ours are not.

Sources: Dorie V, Hill J, Shalit U, Scott M, Cervone D. Automated versus do-it-yourself methods for causal
inference: lessons learned from a data analysis competition. *Statistical Science* 2019;34(1):43-68
(arXiv:1707.02641; read in full for this design). Chernozhukov V et al. Double/debiased machine learning for
treatment and structural parameters. *Econometrics Journal* 2018;21:C1-C68 (ATT score, section 5.1).

## 2. Design (fixed 01:05-01:15 EST, before any hidden run)

### Covariates

24 covariates per stay from PhysioNet 2012 (`suite/families/causal_ate/datagen/covariates.py`): age, sex,
weight, mechanical ventilation, ICU type, and first/min/max of routine vitals and labs (HR, non-invasive MAP,
temperature, GCS, BUN, creatinine, glucose, HCO3, HCT, K, Na, platelets, WBC, Mg, total urine), cleaned with
the risk_icu rules and median-imputed within each pool. Height was dropped (48% missing). Development pool:
set A (4,000 stays). Hidden pool: set B (4,000 stays); no stay is in both. Challenge outcomes are not used.

### DGP (`suite/families/causal_ate/datagen/dgp.py`, seed 20261114; never exported)

Following Dorie et al. 2019 section 4.3 and appendix A.1, seven two-level knobs:

| Knob | Levels |
|---|---|
| Assignment nonlinearity | linear; or 2/3 nonlinear terms (squares, cubes, two-way interactions, steps) |
| Response nonlinearity | linear; or the same nonlinear terms plus an exponentiated linear term |
| Share treated | 0.35 or 0.65 (intercept solved per dataset) |
| Overlap | full; or limited: a corner (two covariates above their 80th percentile) forced to propensity 0, corner indicator added to the response surface (as in ACIC 2016) |
| Alignment | 25% or 75% of the 8 assignment terms also enter the response surface |
| Heterogeneity | none; or tau(x) = tau0 + 0.5 sd-units x combination of response and new terms |
| Confounding strength | sd of the true assignment logit 0.8 or 1.6 |

Propensities are capped at 0.95, so every treated unit has comparable controls (ACIC 2016 enforced overlap
for the treated). 16 settings = a 2^(7-3) resolution-IV fractional factorial (generators E=ABC, F=BCD,
G=ACD), each knob at each level in 8 settings. Y = location + scale x (mu0(X) + Z tau(X) + eps), eps ~ N(0,1),
mu0 standardised; tau0 ~ U(0.2, 0.8) with a random sign (80% positive); location ~ U(-50, 150) and scale
log-uniform on [0.5, 40], so outcome units are arbitrary. n = 2,000 stays sampled per dataset.

- **Estimand: SATT** = mean over the treated units of E[Y(1)-Y(0) | X] (the conditional SATT of ACIC 2016).
  Chosen over the ATE because limited-overlap settings leave controls without treated counterparts, which
  makes the ATE unidentified in that region; ACIC 2016 chose SATT for the same reason.
- **Development:** 32 datasets (16 settings x 2) on set A, given to the agent with true SATT.
- **Hidden:** 48 datasets (16 settings x 3) on set B, random order and random ids, verifier only.
- Settings labels, seeds and the DGP stay in `/home/jkwei/data/vals-suite/causal_ate/private/` and
  `datagen/`; the exporter vendors only the family's top-level `*.py` (grader, gate, spec) into `tests/lib`.

### Contract

Cohort grading through the shared core (`grading='cohort'`, no core change). `run.sh INPUT_DIR OUTPUT_DIR`
is called **once**; `INPUT_DIR/<dataset_id>/data.csv` holds every hidden dataset (columns `z`, `y`, 24
covariates). Output `OUTPUT_DIR/estimates.json`:
`{"estimand": "SATT", "datasets": {id: {"estimate", "ci_lower", "ci_upper"}}}`.
**Deviation from the brief ("input is one dataset"):** one call covers all datasets, because the gate is
defined over the set of datasets and the core's per-case mode would turn coverage into a per-dataset
fraction (a method with infinite intervals would score 1). Running per dataset would need a new core
mode; the cohort mode needs none. The time limit is still stated per dataset (20 s x 48 = 960 s, 4 CPUs).

### Gate (`suite/families/causal_ate/gate.py`)

All errors in units of each dataset's observed outcome sd (as ACIC 2016). All four parts must hold:

| Part | Bar | Source |
|---|---|---|
| Coverage of the true SATT by the 95% interval | >= 0.85 (41/48) | Dorie et al. 2019 sec. 6.2/Fig. 3: plain BART ~82% ("disappointing"); BART+TMLE nearly nominal; BART with propensity score a little over 90%; SL+TMLE with BART ~92%. A truly 95% method falls below 41/48 with probability ~0.003. |
| RMSE | <= 0.10 sd | Dorie et al. sec. 6.2: most methods at or below ~0.05 sd at n = 4,802; x sqrt(4802/2000) = 0.077 at n = 2,000; 0.10 allows for our covariates and DGP |
| abs(mean bias) | <= 0.05 sd | Dorie et al. sec. 6.2. Weak here by design (random confounding directions); kept because ACIC reports it |
| Mean interval length | <= 0.50 sd | Dorie et al. single out CBPS (0.78 sd) as wide; our median abs(SATT) is ~0.3 sd |

`quality = clip(1 - RMSE/0.5, 0, 1)`. Gap rule: DESIGN.md cohort rule (specialist meets every part and the
agent misses at least one = gap; both pass = control; no comparator passes = excluded from scoring).

### Comparators (`suite/families/causal_ate/comparators/pipelines/dr_att/estimate.py`)

- **Specialist: cross-fitted doubly robust (AIPW) ATT estimator.** 5-fold cross-fitting; control outcome
  regression and propensity each the average of a gradient-boosted model (scikit-learn
  HistGradientBoosting) and a linear model (ridge / logistic); propensity clipped to [0.01, 0.99];
  influence-function standard error (Chernozhukov et al. 2018, ATT score). This is the method family of
  Jin's ARIA causal work.
- **Regression adjustment:** OLS of y on z and covariates, HC1 robust SE (a classical comparator).
- **Naive difference in means**, Welch SE: expected to fail.
- **TMLE: not run.** No TMLE implementation is available offline in the project environment (no `zepid`,
  no R `tmle`); writing one was out of time scope. Recorded as not available.

### Specialist choice on development data only (01:08-01:15)

Five nuisance-model variants of the doubly robust estimator were compared on the 32 development datasets
(scratch script, not kept): GBM only (coverage 0.906, RMSE 0.120, length 0.434), larger GBM (0.906, 0.121,
0.444), GBM + linear average (0.875, 0.069, 0.225), the same with Hajek-normalised weights (0.875, 0.069,
0.250), NNLS-stacked GBM + linear (0.875, 0.071, 0.241) and stacked with additive splines (0.844, 0.071,
0.244). The GBM + linear average was kept (best RMSE, shortest intervals, fastest). Development results of
the timed comparators (suite runner, 4 threads; `results/dev/summary.json`):

| Comparator | Coverage | RMSE (sd) | Bias (sd) | Mean length (sd) | Gate | Wall (32 datasets) |
|---|---|---|---|---|---|---|
| Doubly robust ATT (specialist) | 0.875 (28/32) | 0.069 | -0.018 | 0.225 | all 4 | 60 s |
| OLS regression adjustment | 0.688 | 0.082 | -0.032 | 0.152 | fails coverage | 1 s |
| Naive difference in means | 0.313 | 0.180 | -0.021 | 0.181 | fails coverage, RMSE | 1 s |

Time limit: the specialist needs about 1.9 s per dataset on 4 threads, so 20 s per dataset (960 s for the
48) is about 10x the specialist.

---

## Results (after the gate was fixed)

### Comparators on the 48 hidden datasets (run 01:15-01:17 EST; `results/hidden/summary.json`)

| Comparator | Coverage | RMSE (sd) | Bias (sd) | Max abs. error (sd) | Mean length (sd) | Gate | quality | Wall |
|---|---|---|---|---|---|---|---|---|
| **Doubly robust ATT (specialist)** | **0.979 (47/48)** | **0.046** | -0.006 | 0.103 | 0.215 | **all 4 met** | 0.908 | 84 s |
| OLS regression adjustment | 0.750 (36/48) | 0.076 | -0.032 | 0.209 | 0.148 | fails coverage | 0.848 | 1 s |
| Naive difference in means | 0.417 (20/48) | 0.183 | -0.030 | 0.494 | 0.180 | fails coverage, RMSE | 0.633 | 1 s |
| TMLE | not run (no offline implementation in the env) | | | | | | | |

The specialist passes, so the family is **scored** (DESIGN.md cohort rule). The naive comparator fails as
intended; regression adjustment gets point estimates close enough but its model-based intervals are too
narrow under nonlinearity and heterogeneity, the failure mode ACIC 2016 reported for many methods.
The bias part is met by every comparator (confounding directions are random), as noted in the design.

### Export and oracle

- Export `dist/suite-tasks-causal-v1/causal-satt-0001` (shared exporter, absolute paths; leak check passed;
  `tests/lib` holds only `gate.py`, `grader.py`, `spec.py` of the family, no `datagen/`; the environment holds
  the 32 dev datasets, their truth, README and licence; no hidden data, truth or DGP code).
  `check_taskconfig.py`: no problems. `validate_exports.py` (SDK 0.34.0): no problems.
- Local verifier on `solution/` (vals-suite-causal_ate env = image pins): reward 1.0, all four parts, pipeline
  88 s of the 960 s limit.
- Pushed: `suite/causal-v1@1`, tags `latest`, `v1`, 5,866,768 bytes.
- **Hosted oracle:** run `11115f4f-39bf-4a20-b894-7c1361f9a14b` (label `causal-oracle1`, Modal), FINISHED with
  no error: reward 1.0 = `oracle_expected_reward`; ran/valid/within_time/clinically_acceptable 1.0, quality
  0.9081 (identical to the local grade), all four gate parts met. Pipeline 156 s hosted (88 s on teal) of
  the 960 s limit; build 24 s, evaluation 195 s.
- Full test suite (`vals-suite` env): 275 passed, 1 skipped (includes the 12 new `test_causal_ate.py` tests).
- Known property of the instruction (suite convention, as in the other families): the last line names the
  comparator ("cross-fitted doubly robust (AIPW) specialist estimator"), which hints at the method family.

### Agent attempts (prespecified in `exp/causal_ate/prespec.txt` before launch)

`claude_code_noweb-v1.0.0`, provider Modal, `-s ANTHROPIC_API_KEY anthropic-api-key`, default effort, $8 cap per
attempt, dataset `suite/causal-v1@1`. Attempt 1 per model launched 01:28 EST. At 01:29, by the clock, attempts
2 and 3 were decided; they were launched 01:40-01:42 when the attempt-1 runs freed run slots and before any
attempt-1 result was read. The first Opus launch was refused by the org cap of 10 active runs (no run was
created) and was retried 9 s later; no relaunches were needed.

| Model | Attempt | Run id | reward | Coverage | RMSE (sd) | Bias (sd) | Mean length (sd) | Gate | Pipeline s (hosted) | Session s (of 2700) | Turns | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Opus 5.5 | 1 | `bd885935-899e-4031-a574-79f46b1af1b9` | **1.0** | 48/48 | 0.039 | -0.001 | 0.375 | all 4 | 162 | 455 | 10 | $0.294 |
| Opus 5.5 | 2 | `f0c183b4-f5c1-4da5-991f-a69ddad5c4f8` | **1.0** | 48/48 | 0.040 | -0.010 | 0.335 | all 4 | 205 | 139 | 7 | $0.237 |
| Opus 5.5 | 3 | `c5bfb9c1-2fd4-4d19-9b50-7f2f3cf2982d` | **1.0** | 48/48 | 0.041 | -0.003 | 0.346 | all 4 | 254 | 709 | 20 | $0.519 |
| Sonnet 5.5 | 1 | `c4e354b9-0e2a-4ab4-9434-4ac7317db88d` | **1.0** | 48/48 | 0.039 | -0.009 | 0.292 | all 4 | 375 | 219 | 8 | $0.083 |
| Sonnet 5.5 | 2 | `48e2209f-975b-4b84-a350-e1e45d1e2fe6` | **1.0** | 48/48 | 0.041 | -0.010 | 0.262 | all 4 | 294 | 172 | 7 | $0.081 |
| Sonnet 5.5 | 3 | `c0d950b0-f2e2-4cf3-b6a1-c939b22295b7` | **1.0** | 48/48 | 0.043 | -0.011 | 0.272 | all 4 | 112 | 117 | 4 | $0.044 |
| Specialist | - | stored outputs | (1.0) | 47/48 | 0.046 | -0.006 | 0.215 | all 4 | 156 (oracle run) | - | - | - |

Rewards and pass/fail are hosted. Every attempt's other six reward keys are 1.0 except quality (0.913-0.923)
and vs_specialist is 1.0 (agent RMSE below the specialist's). Coverage, RMSE, bias and length come from the
local regrade (task's own `tests/grade.py`, pipeline in the pilot's no-network bubblewrap sandbox, runtime env
`vals-suite-causal_ate` = the image pins). The regrade matches every hosted reward key exactly in 5 of 6
attempts; Opus attempt 3 differs in quality by 0.0003 (0.9177 local vs 0.9173 hosted) because its pipeline
switches to a cheaper fit after an elapsed-time guard, which trips differently on a slower machine. Validation
of the regrade path: the oracle's carried pipeline regrades to 1.0, quality 0.9081, as hosted. API cost for the
six attempts: **$1.26** (Opus $1.05, Sonnet $0.21; Claude Code `total_cost_usd`); a scan of every fetched file
for `sk-ant` found nothing. All traces: Claude Code 2.1.325, no web tools offered, only the named model.

**Gap verdict (DESIGN.md cohort rule): no gap. Both the specialist and every agent attempt meet all four
parts, so `causal_ate` is a control family**, like ECG in run 2: the frontier models deliver a valid
interval estimator for this ACIC-style problem within minutes and for cents.

### What the agents did (traces in `exp/causal_ate/<attempt>/trace.txt`)

All six built the same method family as the specialist (the instruction names it): a cross-fitted AIPW
estimator of the ATT with blended gradient-boosting and linear nuisance models and an influence-function SE.
All six found that the plain IF interval under-covers on the development data (84-88%) and then **widened
it by a factor picked on the development data**: Opus x1.6, x1.9 and x1.3 plus an additive 0.06-sd floor;
Sonnet x1.7, x1.5 and x1.6. This is why their intervals are 25-75% longer than the specialist's (0.26-0.38 vs
0.215 sd) and cover 48/48 instead of 47/48; their point estimates are slightly better (RMSE 0.039-0.043 vs
0.046). They were candid about the tuning, e.g. Opus attempt 1: "I picked 1.6 by looking at the dev results
themselves, so it is tuned on the same data it was checked on"; Opus attempt 2: "the 1.9 multiplier was tuned
on the dev datasets".

Failure modes that did not cost reward here but would in a tighter task:
- **Sonnet never validated its final pipeline (3 of 3).** Each changed the inflation factor as the last edit and
  ended the session without re-running: "I haven't re-run it since the last change, which widened the
  intervals" (attempt 1); "Neither the new coverage nor the new length was measured" (attempt 2); "the final
  version is untested" (attempt 3). Sonnet used 117-219 s of the 2,700 s session. Opus measured its final interval rule on the full
  development set in all three attempts (139-709 s used); in attempt 1 it then added a time guard and a
  fallback and tested those on 2 datasets only, as it said.
- **Early stopping with most of the session unused**: the longest attempt used 26% of the session.
- Four of six attempts tried a blocked `sleep N; cat` wait once and recovered (Sonnet attempt 1 also called
  `Monitor` without loading its schema).

### Observation on the split

The hidden datasets were easier than the development datasets for every method (specialist coverage 0.875
dev vs 0.979 hidden, RMSE 0.069 vs 0.046; agent RMSE about 0.065 dev vs 0.040 hidden). The splits use different
patient pools (set A vs set B) and independent DGP draws per dataset; with 32 and 48 datasets this difference is
within what draw-to-draw variation of the nonlinear terms can produce, but it was not investigated further.

### Files

- Family: `suite/families/causal_ate/` (`README.md`, `gate.py`, `grader.py`, `spec.py`, `environment.yml`,
  `requirements.txt`, `image_requirements.txt`, `datagen/{covariates,dgp,prepare_data}.py`,
  `comparators/{run_comparators.py,pipelines/dr_att/{run.sh,estimate.py}}`).
- Tests: `tests/suite/test_causal_ate.py` (12 tests). No change to `suite/core/`.
- Export: `dist/suite-tasks-causal-v1/causal-satt-0001`. Data: `/home/jkwei/data/vals-suite/causal_ate/`
  (`SOURCE.md`, licence copies, pools, splits, `private/`, `results/`). Hosted evidence: `exp/causal_ate/`.
- Rebuild: `covariates.py` -> `prepare_data.py` -> `run_comparators.py DATA_ROOT dev|hidden` -> `export_task(build_spec(...))`
  with absolute paths (`scripts/export_suite_tasks.py` was not edited; it does not list this family).
