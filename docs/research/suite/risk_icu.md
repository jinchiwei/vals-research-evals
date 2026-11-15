# risk_icu: calibrated 48-hour ICU in-hospital mortality risk

Worker: Claude Opus 5.5 (claude-opus-5-5), 2026-11-14, on teal, CPU only (GPU not used).
Family code: `suite/families/risk_icu/`. Tests: `tests/suite/test_risk_icu.py` (41 pass, synthetic patients).
Data and every patient-level output: `/home/jkwei/data/vals-suite/risk_icu/` (see `SOURCE.md` there).
Environment: `vals-suite-risk_icu` (python 3.12.16, numpy 2.1.3, scipy 1.14.1, pandas 2.2.3, scikit-learn 1.5.2).
This conda build rejected `--override-channels -c conda-forge` on `env create`. The env was then
created from the yml (channel conda-forge) without the flag. Python comes from conda-forge.

## 1. Data: verified facts

- Source: PhysioNet/CinC Challenge 2012 v1.0.0, physionet.org/content/challenge-2012/1.0.0. Downloaded
  2026-11-14 without a login.
- **Licence: ODC-By 1.0**, confirmed on the project page ("Anyone can access the files, as long as
  they conform to the terms of the specified license. License: Open Data Commons Attribution License v1.0").
- PhysioNet publishes no SHA256SUMS for this project. Our own checksums are in `SOURCE.md`.
- **Outcomes are public for A, B and C.** Each `Outcomes-*.txt` has 4,000 rows and the IDs match the
  4,000 record files of that set exactly.
- Record format: `Time,Parameter,Value`. Time is `HH:MM` from 00:00 to 48:00; the latest
  observation in every set is at 48:00. The six descriptors appear at 00:00, and `-1` means missing.
  There are 36 time-series variables plus MechVent; Weight recurs as a time series. All 12,000 files
  have the correct header.
- Outcome columns: RecordID, SAPS-I, SOFA, Length_of_stay, Survival, In-hospital_death. SAPS-I and
  SOFA are -1 for some stays (missing). For Survival, -1 means no recorded death.

| | set A (development) | set B (hidden) | set C (reserve) |
|---|---|---|---|
| stays / deaths | 4000 / 554 | 4000 / 568 | 4000 / 585 |
| in-hospital mortality | **13.85%** | **14.20%** | 14.63% |
| SAPS-I missing / SOFA missing | 190 / 144 | 162 / 137 | 166 / 122 |
| ICU type 1 CCU / 2 CSRU / 3 MICU / 4 SICU | 577/874/1481/1068 | 590/782/1436/1192 | 602/874/1376/1148 |
| mortality CCU/CSRU/MICU/SICU | 14.0/4.9/18.6/14.5% | 12.2/4.4/19.9/14.8% | 11.8/5.3/21.2/15.4% |
| Gender missing (-1) | 3 | 5 | 4 |
| Height missing / Weight missing at 00:00 | 47% / 8% | 48% / 9% | 48% / 8% |

Quirks found (set A, full counts in `audit.json`):
- The -1 missing code also appears inside time series: 24 negative Temp values in A, and 57 negative
  DiasABP and 167 negative NIDiasABP values in C only.
- Zeros that are dropouts: SysABP 685, NISysABP 174, Weight 184, Temp 39, HR 11.
- pH entered ×100: 9 values above 14.
- Temp below 20 °C: 129 values.
- Variable presence: Cholesterol 8%, TroponinI 5%, TroponinT 22%, RespRate 28%, Lactate 55%.
  About 1.6% of stays lack even HR and GCS.

## 2. Split (fixed before any model was fitted)

`suite/families/risk_icu/prepare_data.py`, seed 20261114. Manifest: `split/split.json`.
- **Development** = all of set A, verbatim. IDs sha256 `8326d776…`; record-folder hash `dd43d8c5…`.
- **Hidden** = all 4,000 stays of set B. Each RecordID is re-drawn to a random number in
  300000–999999 (seeded sample). Only the RecordID line changes. Original-ID list sha256 `843e1009…`;
  hidden-ID list `a3b1439e…`; outcomes `cbee1e01…`. The ID map is `split/hidden_id_map.csv`, grader-side only.
- **Reserve** = set C, untouched (ID list `af11ebaa…`).
- Why all of B: it gives 568 deaths overall and at least 34 in the smallest subgroup (CSRU).
  The hidden set lives only in `tests/`, so its size does not affect the agent image.

## 3. Gate (`gate.py`, fixed after SAPS-I was scored on hidden, before the GBM or any agent)

| # | Component | Bar | Source |
|---|---|---|---|
| 1 | Challenge event-1 = min(Se, PPV) | ≥ **0.321** = SAPS-I on the same hidden stays (0.2711) + 0.05 | event-1 definition and SAPS-I baseline 0.3125 (Silva et al., CinC 2012;39:245–248, text read from cinc.org/archives/2012/pdf/0245.pdf; `score.c` v1.4). The +0.05 margin is our convention. |
| 2 | Calibration slope; calibration-in-the-large (slope fixed at 1) | slope in [0.8, 1.2]; \|CITL\| ≤ 0.2 logit | Van Calster et al. 2016/2019 (weak calibration), metrics-review §(d). The tolerances are our convention. |
| 3 | Net benefit at p_t = 0.20 | > treat-all and > treat-none | Vickers & Elkin 2006; Vickers et al. 2016/2019. p_t = 0.2 means a flag triggers a senior review or goals-of-care talk, and we accept 4 unnecessary reviews per future death. |
| 4 | Worst subgroup AUROC (ICU type 1–4, sex) | ≥ overall AUROC − 0.10 (subgroups need ≥ 10 deaths and ≥ 10 survivors) | TRIPOD+AI subgroup reporting (Collins et al., BMJ 2024). The 0.10 gap is our convention. |

How event 1 turns a risk into a call: the grader flags the `K = round(Σ risk)` highest-risk stays,
which is the model's own expected death count, and ties are flagged together. The agent therefore
cannot tune a threshold, and event 1 also rewards calibration-in-the-large. Challenge entrants
submitted their own binary call, so our event-1 values are close to theirs but not identical.

Decisions use point estimates. Bootstrap (1,000 patient resamples) 95% intervals and
per-component pass rates are reported alongside.
- quality = clip(2·AUROC − 1, 0, 1).
- vs_specialist = quality / specialist quality.
- Time limit: **300 s wall for the whole hidden cohort on 4 CPUs** (75 ms per stay). The reason is
  in `gate.py`: refreshing every bed must not delay a ward round. The specialist needs 15–23 s.
- Validity: header `RecordID,risk`, exactly one finite risk in [0,1] per input file, with no
  duplicates or extra rows.

**Core integration note.** The coordinator asked for `clinically_acceptable` = the fraction of
components met. suite/core casts each case's `acceptable` to bool, and risk_icu exports as a single
"cohort" case. In the exported task, `clinically_acceptable` and `reward` are therefore 1 only when
all four components pass; the fraction goes into `metrics.json` as `gate_fraction`.
The family-local `grade.py` (self-check and tests) computes the fraction as specified. If the core
accepted a float `acceptable`, the exported task would carry the fraction too.

## 4. Comparators on the 4,000 hidden stays (stored under `results/`)

| | AUROC [95% CI] | event-1 (Se/PPV) | slope | CITL | NB@0.2 (treat-all −0.0725) | worst subgroup AUROC | Brier | event-2 H | gate | runtime |
|---|---|---|---|---|---|---|---|---|---|---|
| SAPS-I recalibrated on A | 0.667 [0.645, 0.688] | 0.271 [0.235, 0.299] | 1.15 [0.99, 1.31] | +0.03 | 0.0136 | CSRU 0.633 | 0.116 | 72.4 | 3/4 (fails event 1 by construction) | n/a* |
| GBM, specialist and oracle | **0.873 [0.857, 0.887]** | **0.533** (0.535/0.533) [0.489, 0.560] | 1.04 [0.91, 1.16] | −0.002 [−0.11, 0.10] | 0.0703 [0.059, 0.081] | MICU 0.826 [0.789, 0.845]† | 0.087 | 44.0 | **4/4** | 22.8 s (family runner), 14.6 s (core runner) |
| TabPFN | unavailable | | | | | | | | | |

\* SAPS-I values come from the challenge outcomes file, and the risk is
`1/(1+exp(−(−3.564 + 0.1088·SAPS-I)))` fitted on set A. Stays with missing SAPS-I get 0.132, the
set-A mortality of SAPS-missing stays. No SAPS calculator was timed.
† The interval is for the worst-subgroup statistic.

GBM details:
- HistGradientBoosting on 329 48-hour summary features: first, last, min, max, mean, sd, count,
  mean of the last 24 h and slope per variable, plus urine totals, descriptors and MechVent, with the
  cleaning rules in `comparators/features.py`.
- Settings chosen by 5-fold CV on A (lr 0.03, 8 leaves), then isotonic `CalibratedClassifierCV(cv=5)`.
- Nested-CV AUROC on A: 0.861. The fit takes 47 s.

Subgroups on hidden (AUROC [95% CI], calibration slope, O/E):
- GBM: CCU 0.846 [0.80, 0.89]; CSRU 0.875 [0.80, 0.94], slope 0.72, O/E 0.75; MICU 0.826
  [0.80, 0.85]; SICU 0.899 [0.88, 0.92], slope 1.36; female 0.865 [0.84, 0.89]; male 0.879 [0.86, 0.90].
- SAPS-I: CCU 0.711, CSRU 0.633 (O/E 0.26: it badly over-predicts after cardiac surgery), MICU
  0.674 (O/E 1.47), SICU 0.745, female 0.661, male 0.669.

Published context (Silva et al. 2012, final scores on set C):
- SAPS-I baseline: event 1 0.3125, event 2 68.58. Ours on B: 0.271 / 72.4, a different set with our K rule.
- Best entries: 0.5353 / 17.88. The GBM's event 1 (0.533) matches the winners. Its
  Hosmer-Lemeshow event 2 (44.0) is worse than the event-2 winners: event 2 punishes decile
  miscalibration that the slope/CITL gate tolerates. We report event 2 but do not gate on it.
- The project's `top-ten-event1.txt` (updated 27/8/2012) lists 0.531 as the leading event-1 score.
  Which set that file refers to is not verified.

**TabPFN**: `~/.cache/tabpfn/` holds only an empty `.tabpfn-v3.5-20260909.safetensors.lock` and no
weights. No other local checkpoint was found. The default weights need a Prior Labs login and
licence acceptance, so TabPFN is marked unavailable and nothing was substituted under its name.

## 5. Grader self-check on hidden (family grader, `selfcheck.py`; results in `results/selfcheck/`)

| pipeline | ran | valid | in time | gate (fraction) | quality | reward (family) | reward (exported, core) |
|---|---|---|---|---|---|---|---|
| oracle (GBM) | 1 | 1 | 1 (22.8 s) | 4/4 | 0.745 | 1.0 | 1.0 |
| constant 0.1385 | 1 | 1 | 1 | 1/4 (only the subgroup component, trivially: 0.5 ≥ 0.5 − 0.1) | 0 | 0.25 | 0 |
| overconfident (logit × 3) | 1 | 1 | 1 | 3/4: AUROC 0.872, but slope 0.37 and CITL +1.86 fail | 0.745 | 0.75 | 0 (core dry run: "gate failed: calibration") |
| invalid (one NaN) | 1 | 0 | 1 | – | 0 | 0 | 0 |
| too slow (sleep 400) | 0 | 0 | 0 (killed at 300.1 s) | – | 0 | 0 | 0 |

- The exported task was built with `suite.core.export.export_task` into the scratchpad and passed
  `check_no_leak`.
- A dry run of its `tests/` with `suite.core.grading.grade_task` gave oracle reward 1.0 and
  overconfident 0.0. That run was not as root and had no sandbox.

## 6. Export spec and image

- `spec.py::build_spec(DATA_ROOT, WORK)` returns a `FamilySpec`:
  - task `risk-icu-mortality-0001`, grader module `suite.families.risk_icu.grader`;
  - one hidden case `cohort` (input = 4,000 hidden record files; reference = `outcomes.csv`);
  - precomputed specialist outputs and runtime;
  - the GBM pipeline as oracle (fitted on set A only);
  - 4 CPUs, 8 GB, 300 s, packages = core defaults + pandas 2.2.3.
- Agent-visible data: `dev/input/` (set A, 35 MB), `dev/reference/Outcomes-a.txt`, `README.md`,
  `LICENSE-DATA.md`. `tests/` is 35 MB and `solution/` is 3.6 MB.
- The image was **not built**: there is no Docker on teal. Estimated uncompressed size is about
  0.65–0.75 GB:
  - python:3.12-slim, about 125 MB;
  - numpy, scipy, pandas and scikit-learn measured at 349 MB installed;
  - nibabel, SimpleITK and scikit-image, which the core Dockerfile insists on, unmeasured;
  - 35 MB of data.

## 7. Limitations and unverified items

- Expected difficulty: low to moderate, so this is likely a **control**. A careful frontier agent
  that builds summary features, uses HistGradientBoosting or logistic regression, and calibrates on
  A should pass. Failure modes the gate catches: overconfident or uncalibrated boosting (component 2),
  ignoring the CSRU and MICU subgroups, a pipeline that depends on files outside `pipeline/`, and
  NaN outputs for sparse stays.
- Contamination: the challenge is famous and the outcome files are public. Re-drawn hidden IDs
  prevent lookup by RecordID. The record contents of set B are unchanged, so a model that memorised
  set-B rows could in principle match them; we judge this implausible.
- Event 1 here uses the K = Σ risk rule, not an entrant-chosen threshold, so it is not directly
  comparable with the leaderboard.
- The gate tolerances (+0.05, 0.8–1.2, 0.2 logit, 0.10 AUROC gap) are conventions fixed by us, not
  literature thresholds.
- The constant pipeline earns the subgroup component trivially. This is left as fixed and does
  not matter for the exported all-four reward.
- Unverified:
  - which set the `top-ten-event*.txt` files score;
  - the hosted image size and the build;
  - verifier timing on Modal (runtime measured on teal only);
  - the published top scores on set B specifically;
  - per-variable units, taken from the challenge page and not re-checked against MIMIC-II.
