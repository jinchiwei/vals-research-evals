# ecg_ptbxl: calibrated 5-superclass 12-lead ECG classification

Worker: Claude Opus 5.5 (claude-opus-5-5), 2026-11-14, on teal. Code is in `suite/families/ecg_ptbxl/` and
tests in `tests/suite/test_ecg_ptbxl.py`. Data is in `/home/jkwei/data/vals-suite/ecg_ptbxl/` (see `SOURCE.md` there).
Nothing was committed.

## 1. Data: verified facts

PTB-XL 1.0.3 comes from PhysioNet (DOI 10.13026/kfzx-aw45) under CC BY 4.0. I confirmed the licence on the
landing page ("Anyone can access the files, as long as they conform to the terms of the specified license"),
and the archive's `LICENSE.txt` is the CC BY 4.0 legal code. The archive (1.84 GB) has SHA-256
`2d98687a…29812`, and `sha256sum -c` against PhysioNet's `SHA256SUMS.txt` passed for every file.
`prepare_data.py` measured every figure below and wrote them to `work/data_checks.json`.

| Item | Value |
|---|---|
| Records / patients | 21,799 / 18,869 |
| Superclass mapping | benchmark rule: every SCP code with `diagnostic == 1` maps to its `diagnostic_class`, whatever its likelihood value. The 5 classes are NORM, MI, STTC, CD, HYP (44 diagnostic statements). |
| Records with no superclass | 411. Dropped, as in the benchmark (21,388 remain). |
| Labels per labelled record | 1: 16,244; 2: 4,068; 3: 919; 4: 157 (24 % multi-label) |
| Prevalence (labelled) | NORM 44.5 %, MI 25.6 %, STTC 24.5 %, CD 22.9 %, HYP 12.4 % |
| Folds | 10 `strat_fold`s of 2,173–2,198 records. **No patient appears in more than one fold.** |
| Human validation | `validated_by_human` is true for 100 % of folds 9 and 10, against 64–68 % of folds 1–8 |
| Sex | coded 0/1 (0 = male per dataset documentation): 11,354 / 10,445. No missing values. |
| Age | no NaN. 293 records are coded **300** (the dataset's code for age over 89), and we write them as 90. The other ages run from 2 to 89 years, median 61. |
| Height / weight | missing in 68 % / 57 % of records (not used) |
| Signals (100 Hz) | All 21,799 headers checked: 12 leads, 100 Hz, 1,000 samples (10 s), format 16, gain 1000 adc/mV (1 µV resolution), baseline 0, lead order I, II, III, aVR, aVL, aVF, V1–V6. The raw int16 values match `wfdb.rdrecord` exactly (difference 0.0 mV). No record is clipped at the int16 limits, and 1 record has a flat lead. |

## 2. Split (seed 20261114, fixed before any model was run)

The dataset's own patient-level folds are used, and we only subsample within them. Stratification is
proportional over the 5-label combination × sex, with rare strata pooled. Lists and SHA-256 hashes of the
sorted `ecg_id`s are in `work/splits.json`, and the task-id to `ecg_id` crosswalk in `work/crosswalk.csv`
(never shipped).

| Role | Source | Records (patients) | Notes |
|---|---|---|---|
| Development (agent) | stratified subsample of folds 1–8 | **8,000** (7,398) | 133 MB as int16 µV `.npz`. Random record and patient IDs; `ptbxl_fold` is given so the agent can split by patient. |
| Hidden (grader) | stratified sample of fold 10 | **1,000** (935) | men 515 / women 485; age < 55: 315, 55–69: 337, ≥ 70: 348. MI positives per subgroup: M 138, F 116, < 55: 30, 55–69: 81, ≥ 70: 143. |
| Specialist selection and calibration | all of fold 9 | 2,146 | never given to the agent |
| Specialist training | all of folds 1–8 | 17,084 | |

Hidden-set prevalence is NORM 44.7 %, MI 25.4 %, STTC 24.2 %, CD 23.1 %, HYP 12.0 %.

## 3. Clinical framing and gate (fixed before any comparator result)

**Central target: MI.** In this setting the probabilities order an over-read worklist. MI is the class whose
miss changes management most directly (secondary prevention after an unrecognised infarct, and reperfusion
in the acute case), and it is the class where automated interpretation has historically lagged cardiologists.

| Component | Rule | Source |
|---|---|---|
| MI operating point | sensitivity ≥ **0.70** at the threshold giving specificity **0.90** on hidden MI negatives (ties count as negative calls) | Willems et al., NEJM 1991;325:1767 (CSE study, PMID 1834940, abstract read via PubMed). The programs' median correct classification was 91.3 %, which I read as specificity in controls (a secondary source says so; the full text was not read). Median sensitivity, programs vs cardiologists: anterior MI 77.1 % vs 84.9 %, inferior MI 58.8 % vs 71.7 %. Weighted by the CSE case mix (170 anterior, 273 inferior), that is 0.658 for programs and 0.768 for cardiologists. The bar of 0.70 is just below their midpoint (0.713): better than the median 1991 program, short of cardiologist level. |
| Calibration | mean over the 5 classes of ECE (10 equal-width bins) ≤ **0.05** | **Argued, not cited.** Van Calster et al. (BMC Med 2019; J Clin Epidemiol 2016) and the metrics review require moderate calibration but give no number. 0.05 means an average miscalibration of 5 percentage points, which is small next to the worklist decisions at prevalences of 12–45 %. |
| Subgroup consistency | overall macro AUROC − worst of {M, F, < 55, 55–69, ≥ 70} macro AUROC ≤ **0.05** | **Argued.** The bands were chosen around the dataset's age quartiles (50 / 61 / 72) so that each hidden band has ≥ 300 records. Worst-group reporting follows metrics-review §(e). |

`clinically_acceptable` = (c1 + c1·c2 + c1·c3) / 3. The calibration and subgroup parts count only when the MI
operating point is met. **This conditioning was added after the constant-prevalence self-check scored 2/3**
(a constant is perfectly calibrated and has no subgroup gap). At that point I had also seen the simple
reference's hidden results; the conditioning does not change its score, and no threshold moved.
`gate_all_met` (0/1) is also in `metrics.json`. Under DESIGN.md it is the frontier-gap criterion.

**Time limit:** the whole hidden set runs in one call to `run.sh`, timed on the grader's monotonic clock:
**60 s + 0.5 s per ECG** (560 s for 1,000 ECGs), with a hard kill at 2× that. Argument: ACC/AHA STEMI guidance
expects a 12-lead ECG to be acquired and interpreted within 10 minutes of arrival (O'Gara et al., Circulation
2013;127:e362; cited from memory and not re-read today). A cart prints its automated statement as the
10-second recording ends, and a central ECG system has to keep up with the hospital's stream. 0.5 s is one
twentieth of the acquisition time on 4 CPUs, and the 60 s covers interpreter and model loading. It is a
workflow argument, not a published figure.

**Quality:** clip((macro AUROC − 0.5) / (0.928 − 0.5), 0, 1), where 0.928 is the published xresnet1d101
superdiagnostic result (Strodthoff et al., IEEE JBHI 2021). **vs_specialist:** the same mapping relative to
our specialist's hidden macro AUROC. **valid:** strict CSV parse with exact header, every hidden id exactly
once, and every value finite in [0, 1]. **reward** = clinically_acceptable if ran, valid and within_time are
all met, else 0. Bootstrap 95 % CIs (1,000 resamples, seed 20261114) are reported for macro AUROC, MI
sens@spec90, macro ECE and the subgroup gap. Report-only extras, following metrics-review.md: Brier,
calibration slope and intercept per class, MI net benefit at p_t 0.1–0.4 against treat-all, and the MI
false-negative rate per subgroup at the overall threshold.

## 4. Results on the 1,000 hidden fold-10 records (grader-run, CPU, 4 threads)

| Pipeline | Macro AUROC [95 % CI] | MI sens @ spec 0.90 [CI] | Macro ECE | Brier | Gap (worst group) | Gate | reward | Wall time (per ECG) |
|---|---|---|---|---|---|---|---|---|
| **Specialist** (xresnet1d-style CNN) | **0.921** [0.910, 0.931] | **0.744** [0.661, 0.813] | 0.022 | 0.086 | 0.026 (age ≥ 70) | 3/3 | **1.00** | 3.7–9.4 s (3.7–9.4 ms) |
| Simple reference (features + GBM, dev set only) | 0.916 [0.906, 0.926] | 0.728 [0.642, 0.800] | **0.0503** | 0.094 | 0.032 (age ≥ 70) | 2/3: fails calibration narrowly | 0.67 | 2.3–5.9 s |
| Oracle (hidden labels) | 1.000 | 1.000 | 0.000 | 0 | 0 | 3/3 | 1.00 | 0.04 s |
| Constant prevalence | 0.500 | 0.000 | 0.003 | 0.181 | 0 | MI fails, so 0 | **0.00** | 0.07 s |
| Overconfident (specialist logits × 5) | 0.921 | 0.744 | **0.102** | 0.106 | 0.026 | 2/3 | 0.67 | 0.04 s |
| Invalid (one NaN) | – | – | – | – | – | – | **0.00** (valid 0) | 0.05 s |
| Too slow (specialist outputs after a 620 s sleep) | 0.921 | 0.744 | 0.022 | – | – | 3/3 | **0.00** (within_time 0) | 620.3 s (budget 560 s) |

Per-class AUROC for the specialist: NORM 0.944, MI 0.917, STTC 0.918, CD 0.915, HYP 0.907. Per-class ECE is
0.021–0.025 and calibration slopes are 0.91–1.04. Subgroup macro AUROC: M 0.919, F 0.923, < 55 0.938,
55–69 0.906, ≥ 70 0.895. MI AUROC by group: < 55 0.960 (only 30 positives), 55–69 0.873, ≥ 70 0.885.
The simple reference's calibration slopes are 0.60–0.79 (overconfident), which explains its ECE.
MI net benefit at p_t 0.1 / 0.2 / 0.3 / 0.4 is 0.214 / 0.182 / 0.163 / 0.137 for the specialist (treat-all
0.171 / 0.068 / −0.066 / −0.243) and 0.199 / 0.174 / 0.150 / 0.133 for the simple reference. MI
false-negative rate at the overall 90 %-specificity threshold, specialist: M 0.25, F 0.27, < 55 0.40
(12 of 30), 55–69 0.32, ≥ 70 0.19. Younger patients' MIs are missed more often at a population threshold,
even though their AUROC is highest: lower predicted risk at a fixed threshold. This is descriptive only and
not part of the gate.

The bootstrap ECE interval for the specialist ([0.026, 0.039]) lies above its point estimate (0.022). ECE is
biased upward under resampling with duplicates, so the interval is conservative and the gate uses the point
estimate. The bootstrap is a plain percentile bootstrap.

**Does the specialist clear the gate? Yes, on all three components.** The MI margin is thin: 0.744 against a
bar of 0.70, with a CI lower bound of 0.66. Fold-9 macro AUROC at the selected epoch was 0.929, against the
published 0.928, and 0.921 on our 1,000-record fold-10 sample.

**Reading for the suite.** A 4-minute hand-feature model reaches 99 % of the specialist's discrimination
(vs_specialist 0.99) and the MI bar. What separates them is calibration. The frontier gap this task can show
is therefore mainly "calibrated probabilities that hold across groups", not ranking.

## 5. Comparators: how they were built

- **Specialist:** an xresnet1d-style residual 1D CNN (`specialist/predict.py`; stem 3 convs, 4 stages of 2
  basic blocks with k=5, widths 64–256, concat avg+max pool; 2.38 M parameters). It was trained on all 17,084
  fold 1–8 records at 100 Hz on the full 10 s, with AdamW and one-cycle lr 3e-3, 40 epochs, batch 128, BCE,
  and amplitude-scale plus shift augmentation. The epoch (17) was selected on fold-9 macro AUROC, then
  per-class Platt scaling was fitted on fold-9 logits (raw fold-9 ECE 0.034, 0.014 after in-sample
  calibration). Training took 373 s on the shared RTX 3060; another job was using about 3 GB and 98 %
  utilisation at the start. Fold 10 was never touched in training. The weights, `model.json` (training log),
  hidden predictions and grader metrics are under `work/specialist_pipeline/` and `work/selfcheck/specialist/`.
  CPU inference through the grader (4 threads, including start-up) took 9.4 s for 1,000 ECGs with teal's load
  average around 18, and 3.7 s on a quieter rerun. That is 3.7–9.4 ms per ECG, about 60× under the limit.
- **Simple reference** (`simple_ref/predict.py`, `train_simple.py`): 572 features (per-lead amplitude
  percentiles, derivative statistics, band powers, RR statistics, QRS width, a median-beat template
  downsampled ×2, age, sex), with one `HistGradientBoostingClassifier` per class, fitted on the 8,000
  development records only. Fitting took 4 minutes on teal. It doubles as the Harbor `solution/` (oracle
  agent), since it uses only agent-visible material.

## 6. Grader self-check

`selfcheck.py` runs every pipeline through `grade.py` (strict parser, grader clock, conditional gate). The
results are in the table above and in `work/selfcheck/summary.json`. The grader separates: oracle 1.0;
specialist 1.0; simple 0.67 (calibration); overconfident 0.67 (same AUROC as the specialist, ECE 0.10);
constant 0 (quality 0, MI fails); NaN output invalid, 0; too slow 0 (ran 620.3 s against the 560 s budget: ran 1, valid 1, within_time 0, while quality stays 0.98, so only the time rule zeroes it).
`tests/suite/test_ecg_ptbxl.py` (11 tests, synthetic data, under 10 s) covers: AUROC with ties against the
pairwise definition, sens@spec and the constant-score edge case, ECE and slope, the quality mapping, the
strict parser (header, NaN, range, missing, duplicate, unknown id), end-to-end grading of oracle, constant
and overconfident pipelines, late-but-finished vs hard-killed vs crashed vs missing pipelines, the
conditional gate, proportional stratified sampling, and the features on a synthetic 75 bpm ECG. The grader's
AUROC, ECE and sens@spec match `suite/core/metrics.py` exactly on the specialist's hidden predictions.

## 7. Task image and export

- **CPU PyTorch is included** (`torch==2.5.1+cpu`, wheel 175 MB). On 4 CPU threads a 0.3 M-parameter residual
  CNN trains at about 14 s per epoch over the 8,000 development ECGs, and the 2.4 M specialist-size network at
  about 52 s per epoch. A CNN is therefore feasible inside the agent's 30 minutes. Leaving torch out would
  make any gap partly an artefact of the environment.
- Agent-visible data: **133.5 MB** (`signals.npz` 133 MB + CSVs + README + licence). Image estimate: python
  slim, plus numpy/scipy/pandas/sklearn, plus torch CPU (about 0.7 GB installed), plus data, comes to roughly
  1.1 GB. **Not built:** there is no Docker on teal.
- `build_task.py` reads `family_spec.json` and writes `DATA_ROOT/task/ecg_ptbxl-<hash>/`:
  - `task.toml` (separate verifier, no-network; agent allowlist `api.anthropic.com`; 1,800 s agent and
    verifier; 4 CPUs, 8 GB) and `instruction.md`;
  - `environment/` (Dockerfile and development data);
  - `tests/` (grade.py, the hidden inputs and labels, specialist.json: 16.9 MB, verifier-only);
  - `solution/` (simple pipeline);
  - a per-file manifest tagged by audience.

  The builder asserts that no hidden record id appears in agent-visible files. The pinned Tracker parser
  (`exp/suite-platform-probe/check_taskconfig.py`) reports **no problems**, separate=True and verifier
  no-network. A local dry run of the exported `tests/grade.py` on the exported `solution/` reproduces reward
  0.667. Current export: `task/ecg_ptbxl-0807d15baf/`.
- `suite/core` appeared during this work. Its plug-in contract is per-case: `run.sh` runs once per case and
  rewards are means over cases. This family needs set-level metrics and one batched run, so `grade.py` stays
  family-local and self-contained (numpy only). It writes the same seven reward keys and runs the same
  procedure: fail-closed on `/solution`, `chmod go-rwx /tests`, uid 65534 via `setpriv`, a provisional zero
  reward, and a kill of leftover processes through `/proc`, because slim images lack `pkill`. Porting it needs
  a set-level hook in `core/grading.py`.

## 8. Limitations and unverified items

- The CSE reference standard was clinical, not the ECG, and its cases were selected (controls and
  hypertrophy/MI groups). PTB-XL MI labels are cardiologist ECG reads covering acute and old MI. The 0.70/0.90
  bar is an anchor, not a like-for-like requirement. I read the abstract, not the full text, and the
  "specificity" reading of 91.3 % is unverified.
- The ECE bound, the subgroup gap bound and the time rule are argued, not cited. The ACC/AHA 10-minute
  figure was not re-read today.
- The age < 55 band has only 30 MI positives, so its per-group MI AUROC is descriptive. The gap uses macro
  AUROC over all 5 classes.
- The specialist's MI margin (0.744 vs 0.70) is inside its bootstrap CI. On another fold-10 sample it could
  fail.
- Some fold 1–8 labels come from one reading or the device's automatic report. The hidden labels are 100 %
  human-validated.
- PTB-XL is a famous public dataset. The record ids are re-drawn and the signals are shuffled, but a
  memorised `ecg_id` cannot be recovered from the files. Hidden signals are byte-identical to the public
  PTB-XL 100 Hz records, so an agent with a copy of PTB-XL could look them up by waveform. There is no
  internet in the sandbox.
- Not done: Docker build of the image, a hosted oracle run, and the optional toolbox tier.

## Note added after integration (2026-11-14)

The suite's cohort reward rule (DESIGN.md, amended before any agent run) sets
`clinically_acceptable` to 1 only when every gate part is met. Under that rule the
simple reference and the shipped solution score reward 0.0 (2 of 3 parts; calibration
ECE 0.0503 against the 0.05 bound), not the 0.67 reported above. The measurements are
unchanged; the fraction of parts met is still written to `metrics.json` as `gate_fraction`.
The specialist still meets all three parts (reward 1.0).
