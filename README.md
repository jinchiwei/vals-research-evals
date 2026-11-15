# Clinical deliverables: coding agents against specialist systems on real medical data

<!-- HUMAN-WRITTEN OVERVIEW: Jin writes this paragraph. Do not generate or edit. -->
> _Overview paragraph to be written by Jin._

Submission to the Vals AI hackathon track "Build Your Own Eval" (14 to 15 November 2026), run on
Valkyrie in the organisation `hackathon-neuronetwork-b91c517178`. The exact track text is in
[docs/research/hackathon-prompt.md](docs/research/hackathon-prompt.md).

## How the benchmark works

### What it tests

A frontier coding agent (Claude Code, with no web access) is given real public medical data and
must deliver a clinical artifact: a registration of pre-operative magnetic resonance imaging (MRI)
to intra-operative ultrasound, a computed tomography (CT) organ mask with its volume in millilitres,
a fetal head circumference (HC) in millimetres, a retinal vessel mask, or calibrated probabilities
for electrocardiogram (ECG) classes or intensive care unit (ICU) mortality. A separate verifier runs
the agent's pipeline on hidden cases under a clinical time limit, scores the output with the metric
a clinician or challenge organiser would use, and compares it with a specialist system run on the
same hidden cases. Two further families test a treatment-effect estimate with an interval and the
labelling of free-text ECG reports. The design is in [DESIGN.md](docs/research/suite/DESIGN.md) and
the current plan in [PLAN.md](docs/research/suite/PLAN.md).

### The task contract

- **Agent side.** The agent's workspace holds a README with the clinical task and output format,
  development cases with their references, and nothing from the hidden cases. The task image has a
  fixed Python environment (`/opt/benchmark-venv`) with standard scientific packages and, for some
  families, CPU-only PyTorch with no pretrained weights. The agent's network is limited to the
  model API (`api.anthropic.com`). The agent must leave a self-contained offline pipeline at
  `/workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR`.
- **Verifier side.** A separate verifier sandbox, with no network, runs that pipeline once per hidden
  case (or once on the whole hidden cohort for cohort tasks) as an unprivileged user, under a
  wall-clock limit that the grader measures itself. It grades the outputs against hidden references
  and against the specialist's stored outputs for the same cases.
- **Session limit.** Each task has an agent session limit (30 to 60 minutes). Whatever is in
  `/workspace/output/pipeline/` when the session ends is graded as found. From task version 3
  (dataset `suite/clinical-v1@2`; [instructions-v3.md](docs/research/suite/instructions-v3.md)) the
  instruction states this; earlier versions did not (see [Earlier runs](#earlier-runs)).
- **One exception.** The report-label family uses a direct-answer contract: the agent writes labels
  for the given hidden reports to `/workspace/output/labels.json`, and no agent code runs in the
  verifier ([label_ptbxl_reports.md](docs/research/suite/label_ptbxl_reports.md)).

Every task writes `reward.json` with exactly seven keys, each in [0, 1]
([suite/README.md](suite/README.md)):

| Key | Meaning (per-case tasks: mean over hidden cases) |
|---|---|
| `ran` | the pipeline produced the required files |
| `valid` | the output passed the format, unit and geometry checks |
| `within_time` | the case finished inside the grader's time limit |
| `clinically_acceptable` | valid and meets the clinical threshold; for cohort tasks 1 only if every gate part is met |
| `quality` | the family's primary metric mapped to [0, 1], with 0 for an invalid case |
| `vs_specialist` | `min(1, quality / specialist quality)` |
| `reward` | `clinically_acceptable` if `ran`, `valid` and `within_time` are all 1, otherwise 0 |

Raw values in mm, mL and seconds are written to `metrics.json`. For cohort tasks the fraction of
gate parts met is reported as `gate_fraction` but earns no reward, so a constant predictor cannot
collect partial credit ([DESIGN.md](docs/research/suite/DESIGN.md)).

### Why these metrics

The choices follow the literature review in
[metrics-review.md](docs/research/suite/metrics-review.md); section numbers below refer to it.

- **Registration: target registration error (TRE) on expert landmarks, in mm.** TRE is the accepted
  accuracy measure for registration, and image similarity or whole-organ overlap can rate wrong
  transforms as good (section 1(b), Fitzpatrick and West 2001; Rohlfing 2012).
- **Segmentation: overlap plus volume in physical units.** The Dice similarity coefficient (Dice) is
  the default overlap metric and should be paired with a boundary metric; when the clinical use is a
  volume, report the volume error in mL (section 1(a), Metrics Reloaded; Bland and Altman). Our
  spleen task scores Dice and relative volume error and reports surface distance metrics without a
  threshold.
- **Thin structures: overlap plus connectivity.** For retinal vessels we pair Dice with centreline
  Dice (clDice; Shit et al. 2021), which counts whether thin vessels stay connected, and set the bar
  at a second human observer's agreement on each image ([seg_vessel.md](docs/research/suite/seg_vessel.md)).
- **Measurement: absolute error in physical units against a declared tolerance** (section 3).
- **Probabilities: discrimination is not enough.** The area under the receiver operating
  characteristic curve (AUROC) measures ranking only; calibration and decision-curve net benefit
  decide whether a risk is usable, and most published prediction models never assessed calibration
  (sections 1(c) and 1(d); Van Calster et al.; Vickers and Elkin; Christodoulou et al. 2019).
- **Treatment effects: an interval that covers the truth.** For the causal family the gate follows
  the 2016 Atlantic Causal Inference Conference (ACIC) competition analysis (Dorie et al. 2019):
  coverage of the true effect by the 95 % interval, root mean squared error (RMSE), bias and interval
  length ([causal_ate.md](docs/research/suite/causal_ate.md)).
- **Subgroups.** Averages hide harm, so the cohort tasks require a bound on the worst subgroup
  (section 1(e)).
- **Time is a gate.** An answer that arrives after the clinical window is of no use, so a late case
  fails; challenges such as FLARE and Learn2Reg already score runtime for algorithms (section 1(g)).
- **Small hidden sets.** Agent and specialist are compared on the same cases with a paired bootstrap
  and an interval, and no winner is declared when intervals overlap (section 1(h)).

### Task families

Counts, thresholds and specialist results are from
[task-manifest.json](docs/research/suite/task-manifest.json) and each family's document. "Our
convention" marks a bound we set before any agent result, without a published number behind it.

| Family | Data, licence, cases (development / hidden) | Deliverable | Clinical threshold and source | Time limit | Specialist on the hidden cases | Role |
|---|---|---|---|---|---|---|
| [`reg_resect`](docs/research/suite/reg_resect.md) | RESECT, CC BY 4.0; 4 / 6 patients | each MRI landmark's position in the ultrasound, RAS world mm | per case: mean TRE < 2.0 mm and below the initial error (Gerard et al. 2021, citing Prada et al.; AAPM TG-132 via Latifi et al. 2018) | 120 s per case | MIND-feature rigid registration: 4 of 6 cases pass; mean TRE 3.03 mm (initial 6.18 mm) | scored |
| [`seg_spleen`](docs/research/suite/seg_spleen.md) | Medical Segmentation Decathlon Task09, CC BY-SA 4.0; 8 / 6 CT scans | spleen mask (NIfTI) and volume in mL | per case: Dice ≥ 0.94 and relative volume error ≤ 10 % (Humpire-Mamani et al. 2020 inter-observer; the 10 % uses our normality assumption) | 300 s per case | TotalSegmentator 2.18.0 (not trained on these data): 3 of 6 pass; mean Dice 0.939 | scored |
| [`measure_hc18`](docs/research/suite/measure_hc18.md) | HC18, CC BY 4.0; 152 / 83 ultrasound images | head circumference in mm | per image: error ≤ 4.9 % of reference (Sarris et al. 2012 inter-observer limits, read from the abstract); family bar ≥ 90 % of images (our convention) | 10 s per image (manual measurement time, Han et al. 2024) | U-Net trained on a separate pool: 83 of 83 within tolerance; mean error 2.05 mm | scored |
| [`seg_vessel`](docs/research/suite/seg_vessel.md) | CHASE_DB1, CC BY 4.0; 20 / 8 fundus images (10 / 4 children) | vessel mask (PNG) | per image: Dice and clDice against the first observer both at least the second observer's on that image (Fraz et al. 2012 two-observer reference); family scored only if the specialist passes ≥ 4 of 8 (our convention) | 60 s per image (our convention; 17 × the specialist) | small U-Net trained on the development images: 6 of 8 pass; mean Dice 0.837 | scored (round 3) |
| [`ecg_ptbxl`](docs/research/suite/ecg_ptbxl.md) | PTB-XL 1.0.3, CC BY 4.0; 8,000 / 1,000 ECGs | calibrated probabilities for five diagnostic superclasses | all of: myocardial infarction (MI) sensitivity ≥ 0.70 at specificity 0.90 (Willems et al. 1991); mean expected calibration error (ECE) ≤ 0.05 (our convention); macro AUROC gap to the worst sex or age group ≤ 0.05 (our convention) | 560 s for the cohort, killed at 1,120 s (our convention) | xresnet1d-style CNN: all 3 parts met; macro AUROC 0.921 | scored; behaved as a control |
| [`risk_icu`](docs/research/suite/risk_icu.md) | PhysioNet/CinC Challenge 2012, ODC-By 1.0; 4,000 / 4,000 stays | calibrated in-hospital mortality risk | all of: challenge event-1 score ≥ 0.321 (SAPS-I on the same stays plus 0.05; margin is our convention; Silva et al. 2012); calibration slope 0.8 to 1.2 and calibration-in-the-large within 0.2 logit (our convention); net benefit at threshold 0.20 above treat-all and treat-none (Vickers and Elkin 2006); worst ICU-type or sex AUROC ≥ overall − 0.10 (our convention) | 300 s for the cohort | gradient-boosted trees: all 4 parts met; AUROC 0.873 | scored; control |
| [`causal_ate`](docs/research/suite/causal_ate.md) | our ACIC-2016-style generator over PhysioNet 2012 covariates, ODC-By 1.0; 32 / 48 datasets of 2,000 stays | treatment effect on the treated (SATT) with a 95 % interval, per dataset | all of: coverage ≥ 0.85 (41 of 48); RMSE ≤ 0.10 outcome sd; abs. mean bias ≤ 0.05 sd; mean interval length ≤ 0.50 sd (Dorie et al. 2019) | 960 s for the 48 datasets (20 s each) | cross-fitted doubly robust (AIPW) estimator: all 4 parts met; coverage 47 of 48, RMSE 0.046 sd | control (round 3) |
| [`label_ptbxl_reports`](docs/research/suite/label_ptbxl_reports.md) | PTB-XL 1.0.3 report text, CC BY 4.0; 2,000 / 500 human-validated reports | diagnostic superclasses for each hidden report (direct answer) | both of: Cohen's kappa ≥ 0.60 in each class (Landis and Koch; McHugh 2012); macro F1 ≥ 0.80 (our convention) | 45-minute session | TF-IDF + logistic regression: gate not met (macro F1 0.735, worst kappa 0.477) | excluded: worked example of a label ceiling |
| [`triage_pharyngitis`](docs/research/suite/triage_pharyngitis.md) | PGUPharyngitis (Shojaei et al. 2025), CC BY 4.0; 561 / 180 patients | probability of bacterial sore throat from a throat photo and symptoms | four-part gate (operating point, calibration, net benefit, subgroup sensitivity) | 420 s for the cohort | no comparator passes (best: 2 of 4 parts; AUROC 0.674) | excluded: worked example of label and shortcut problems |

A synthetic toy task (`toy-sphere-volume-0001`) is used only as a platform smoke test and is not
scored. How the datasets were chosen is under [Data and licences](#data-and-licences).

### The gap rule

A frontier gap is claimed only against the specialist on the same hidden cases, never against the
threshold alone ([DESIGN.md](docs/research/suite/DESIGN.md)).

- **Per-case families** (registration, spleen, fetal head, vessel): take the hidden cases the
  specialist passes (S). An invalid or late agent case counts as a fail. Compute the paired
  difference in pass rate (agent minus specialist) on S with a bootstrap 95 % interval (2,000
  resamples, seed 20261114). A gap is shown when the agent fails at least one case in S and the
  interval lies entirely below 0. With S of 3, 4 or 6 cases, the interval excludes 0 only when an
  agent fails most of S, so "no gap shown" on those tasks is underpowered, not evidence of parity.
- **Cohort families** (ECG, ICU, causal): a gap is shown when the specialist meets every gate part
  and the agent misses at least one. If both pass, the task is a control.
- **No comparator passes** (pharyngitis, report labels): the task is excluded from scoring.
- A run that fails because of our own infrastructure or instruction bug is reported as not
  interpretable, not as a gap.
- **Several attempts.** The verdict is computed for each attempt and reported as "gap shown in k of
  n attempts". Attempts are never averaged into one verdict.

Rules fixed before any agent run: the number of attempts per task and model, nothing rerun for a
better number; thresholds set from the literature or stated as our convention before any agent
result; splits and hidden-case hashes recorded per family. Round 3 was preregistered in
[round3-prereg.md](docs/research/suite/round3-prereg.md); every deviation is listed in
[round3-results.md](docs/research/suite/round3-results.md).

## Results

**Status on 2026-11-15.** The headline pools three attempts per task and model on the five original
scored tasks: hosted run 2 (attempt R1) and two repeats (R2, R3) from round 3, all on the same task
version (`suite/clinical-v1@2`, instructions v3), with Claude Code (no web tools), Claude Opus 5.5
and Claude Sonnet 5.5. Retinal vessel segmentation, added in round 3, has one attempt per model.
Controls, the report-label worked example and two instruction tests (K and K2) are reported in
their own subsections and never pooled with the headline. Earlier runs with a different
instruction are summarised under [Earlier runs](#earlier-runs). Full write-ups:
[hosted-agents3.md](docs/research/suite/hosted-agents3.md) (with
[hosted-agents3.json](docs/research/suite/hosted-agents3.json)), and one document per round-3
workstream, linked below.

### Summary

- **Fetal head circumference is the stable gap.** The specialist U-Net is within tolerance on 83 of
  83 hidden images. Opus 5.5 reached 35, 71 and 56 in its three attempts, and Sonnet 5.5 64, 71 and
  74. A gap is shown in 3 of 3 attempts for both models, every interval well clear of 0, and no
  attempt reached the 90 % family bar.
- **Sonnet 5.5 shows a gap on registration in 3 of 3 attempts.** Its pipelines passed 1 of 18 hidden
  cases in total and mostly left the landmarks no better than the uncorrected error; in run 2 it
  shipped an explicit no-op.
- **Registration and spleen depend on the attempt.** Opus 5.5 registration went 0.667, 0.333, 0.000
  and Opus 5.5 spleen 0.500, 0.000, 0.167 (gap shown in 1 of 3 each). One attempt per task would have
  been misleading here.
- **Retinal vessels: near-parity, no gap shown.** Opus 5.5 passes 5 of 8 hidden images and Sonnet 5.5
  4 of 8, against 6 of 8 for the specialist. On the images the specialist passes, every agent miss
  is on thin-vessel connectivity, by less than 0.02 clDice.
- **Controls hold.** ICU risk: every attempt meets every gate part. ECG: Sonnet 5.5 passes 3 of 3;
  Opus 5.5 passes 2 of 3 and misses once on MI sensitivity (0.693 against a 0.70 bar). The new causal
  family is a control: the specialist and all six agent attempts pass.
- **Report labelling: Opus 5.5 beat the specialist but not the bar.** Macro F1 0.790 against 0.735
  (paired difference +0.055, 95 % interval +0.025 to +0.086), 0.01 below the 0.80 bar. No comparator
  passes, so the family is excluded from scoring.
- **Agents stop below the bar with time left, even when they know the time.** No attempt in any
  workstream used its whole session. In R and K, several agents said they had run out of time at 8 to
  15 of 45 minutes without checking the clock, and an instruction to keep working while below the bar
  (K) did not change that. With an added instruction to check the clock (K2), every agent read the
  clock and stated the time correctly, and sessions got longer, but all six still stopped below the
  bar, knowingly, with 8 to 31 minutes left. The belief about time was real; correcting it did not
  remove the early stopping.
- **Clean runs.** No infrastructure failure or relaunch in round 3, no web search or fetch in any
  trace. Hosted API cost over all rounds: about $28 at list price (see [Cost](#cost)).

### Headline: three attempts per task and model against the specialist

Rewards are the hosted grades (R1 = hosted run 2; R2, R3 = round 3). "Gap shown" counts attempts
whose per-attempt verdict under [the gap rule](#the-gap-rule) is a gap. Specialist rewards are on the
same hidden cases.

| Task (hidden cases) | Specialist | Opus 5.5 rewards (R1, R2, R3) | Opus mean | Opus gap shown | Sonnet 5.5 rewards (R1, R2, R3) | Sonnet mean | Sonnet gap shown |
|---|---|---|---|---|---|---|---|
| measure_hc18 (83 images; within 4.9 %) | 1.000 (83/83) | 0.422, 0.855, 0.675 | 0.651 | **3 of 3** | 0.771, 0.855, 0.892 | 0.839 | **3 of 3** |
| reg_resect (6 cases; < 2 mm) | 0.667 (4/6) | 0.667, 0.333, 0.000 | 0.333 | 1 of 3 | 0.000, 0.167, 0.000 | 0.056 | **3 of 3** |
| seg_spleen (6 cases; Dice ≥ 0.94, volume ≤ 10 %) | 0.500 (3/6) | 0.500, 0.000, 0.167 | 0.222 | 1 of 3 | 0.167, 0.000, 0.167 | 0.111 | 1 of 3 |
| seg_vessel (8 images; second observer's Dice and clDice) | 0.750 (6/8) | 0.625 (one attempt) | – | 0 of 1 | 0.500 (one attempt) | – | 0 of 1 |
| ecg_ptbxl (1,000 ECGs; 3 gate parts) | 1 (3/3 parts) | 1, 1, 0 | 0.667 | 1 of 3 | 1, 1, 1 | 1.000 | 0 of 3 |
| risk_icu (4,000 stays; 4 gate parts) | 1 (4/4 parts) | 1, 1, 1 | 1.000 | 0 of 3 | 1, 1, 1 | 1.000 | 0 of 3 |

Sources: [hosted-agents3.md](docs/research/suite/hosted-agents3.md) "Pooled view" and
[seg_vessel.md](docs/research/suite/seg_vessel.md) section 7. Every hidden case in every attempt ran,
was valid and finished inside its time limit, except one Opus registration case in R3 whose
landmarks fell more than 10 mm outside the ultrasound field of view (`valid` 0.833, reward 0). Raw
values in mm, Dice and AUROC come from a local regrade of each saved pipeline with the task's own
grader, because Valkyrie does not keep `metrics.json`. The regrade matches all seven hosted keys in
28 of 30 headline attempts and in both vessel attempts. Of the two exceptions, Opus 5.5 registration
R1 differs only in `quality`, by 0.0002, and Sonnet 5.5 fetal head R3 has a non-deterministic
pipeline (local reward 0.880 against 0.892 hosted); the hosted grade is used.

![Rewards per attempt against the specialist, three attempts per task and model plus vessel](docs/figures/suite/round3_pooled_headline.png)

**Per-attempt gap verdicts** (paired bootstrap of per-case pass on S, agent minus specialist; all
intervals in [hosted-agents3.json](docs/research/suite/hosted-agents3.json)):

| Task (cases in S) | Model | R1 | R2 | R3 |
|---|---|---|---|---|
| measure_hc18 (83) | Opus 5.5 | gap: −0.578 (−0.675 to −0.470) | gap: −0.145 (−0.229 to −0.072) | gap: −0.325 (−0.422 to −0.229) |
| measure_hc18 (83) | Sonnet 5.5 | gap: −0.229 (−0.313 to −0.145) | gap: −0.145 (−0.217 to −0.072) | gap: −0.108 (−0.169 to −0.048) |
| reg_resect (4) | Opus 5.5 | no gap shown (1 failed) | no gap shown (2 failed; −0.50, −1.00 to 0.00) | gap (3 failed; −0.75, −1.00 to −0.25) |
| reg_resect (4) | Sonnet 5.5 | gap (4 of 4 failed; no-op) | gap (3 failed; −0.75, −1.00 to −0.25) | gap (4 of 4 failed) |
| seg_spleen (3) | Opus 5.5 | no gap (0 failed) | gap (3 of 3 failed) | no gap shown (2 failed) |
| seg_spleen (3) | Sonnet 5.5 | no gap shown (2 failed) | gap (3 of 3 failed) | no gap shown (2 failed) |
| seg_vessel (6) | Opus 5.5 | no gap shown (1 failed; −0.17, −0.50 to 0.00) | – | – |
| seg_vessel (6) | Sonnet 5.5 | no gap shown (2 failed; −0.33, −0.67 to 0.00) | – | – |
| ecg_ptbxl | Opus 5.5 | no gap (3/3 parts) | no gap (3/3) | gap (2/3: MI sensitivity 0.693) |
| ecg_ptbxl, risk_icu | Sonnet 5.5; both on ICU | no gap | no gap | no gap |

No verdict is "not interpretable": no infrastructure failure, no grading error, and the v3
instruction stated the session limit, which no attempt reached.

**Fetal head per image.** The best attempt (Sonnet 5.5 R3, 74 of 83) is still nine images short of
the specialist. In run 2, Opus 5.5's errors were spread across the range (median 8.8 mm) and Sonnet
5.5 had five gross under-estimates of 221 to 275 mm on large heads, where its output fell to its own
clamp ([hosted-agents2.md](docs/research/suite/hosted-agents2.md)). Mean absolute error over the
three attempts ranged from 6.6 to 18.0 mm, against 2.05 mm for the specialist.

![Per hidden image, fetal head circumference, hosted run 2 (attempt R1)](docs/figures/suite/hosted2_per_case_measure_hc18.png)

**Registration and spleen per case.** Opus 5.5 R1 matched the specialist on both (registration 4 of 6
under 2 mm, mean TRE 1.61 mm against 3.03 mm; spleen the same 3 of 6). Its R3 registration had one
invalid case and moved another from 7.0 to 12.0 mm. The Opus 5.5 spleen attempts are near misses
(Dice 0.86 to 0.96) that mostly undersize the organ; Sonnet 5.5 R3 scored Dice 0.000 on one hidden
scan (wrong structure). Per-case tables: [hosted-agents3.md](docs/research/suite/hosted-agents3.md).

### Retinal vessels: near-parity with the specialist

One attempt per model ([seg_vessel.md](docs/research/suite/seg_vessel.md); runs `123e97b9-…` Opus,
`8c5fa3ce-…` Sonnet). The bar on each hidden image is the second human observer's own agreement with
the first observer, on Dice and on clDice, with no slack.

| System | Images acceptable | Mean Dice | Mean clDice | Seconds per image (hosted) | Session used |
|---|---|---|---|---|---|
| Second observer (the bar) | 8/8 by construction | 0.783 | 0.843 | – | – |
| Specialist U-Net (trained on a GPU, 375 s) | 6/8 | 0.837 | 0.855 | 1.8–2.1 | – |
| Opus 5.5 (U-Net trained on CPU in about 35 min) | 5/8 | 0.827 | 0.854 | 5.4–5.6 | 63 % |
| Sonnet 5.5 (U-Net, about 22 min of training; final model not validated) | 4/8 | 0.824 | 0.841 | 2.6–2.9 | 60 % |
| Frangi filter (simple comparator) | 0/8 | 0.471 | 0.375 | – | – |

Both agents' mean Dice (0.827 and 0.824) is above the second observer's (0.783), but per image they
also fall below the Dice bar on the two hardest images (hid_4179 for both, hid_1625 for Sonnet
5.5), both of which the specialist also fails. On the six images the specialist passes, every agent
miss is a clDice shortfall below 0.02, meaning thin vessels left disconnected. Opus 5.5 missed
hid_1625 by 0.00002 clDice. This family does not show a gap. Per-image values are in
[seg_vessel_per_image.csv](docs/research/suite/data/seg_vessel_per_image.csv).

![Vessel Dice and clDice per hidden image against the second observer](docs/figures/suite/round3_vessel_per_image.png)

### Controls: ECG, ICU risk and treatment effect

A control is a task where the specialist passes and the agents are expected to pass too; it shows
that the harness is not simply too hard.

- **ICU risk:** all six attempts meet all four gate parts (AUROC 0.865 to 0.874, calibration slope
  1.00 to 1.07; specialist 0.873, 1.04). Opus 5.5 wrote unit repairs specific to the PhysioNet 2012
  data before inspecting any value, in all three attempts: method-level familiarity with a public
  dataset.
- **ECG:** five of six attempts meet all three parts. Opus 5.5's MI sensitivity at 90 % specificity
  was 0.717, 0.713 and 0.693 against the 0.70 bar (specialist 0.744). One miss in three is
  consistent with an agent sitting at the threshold rather than a different capability.
- **Treatment effect (`causal_ate`, new):** 48 hidden semi-synthetic datasets with known true
  effects. The specialist covers the truth in 47 of 48; every agent attempt (3 per model) covers it
  in 48 of 48 with RMSE 0.039 to 0.043 sd, meeting all four gate parts. Two caveats from
  [causal_ate.md](docs/research/suite/causal_ate.md): the instruction names the specialist's method
  (as every family's instruction names its comparator), and all six agents built that method; and
  all six widened their intervals by a factor tuned on the development datasets (Opus 5.5: "I picked
  1.6 by looking at the dev results themselves, so it is tuned on the same data it was checked on").
  Their intervals are 25 to 75 % longer than the specialist's.

![Causal family: coverage, RMSE and interval length per attempt against the gate](docs/figures/suite/round3_causal.png)

### Worked example: report labelling, excluded from scoring

Task `label_ptbxl_reports` asks the agent to read 500 hidden free-text ECG reports (62 % German) and
assign the five diagnostic superclasses ([label_ptbxl_reports.md](docs/research/suite/label_ptbxl_reports.md)).
It was registered as a control and fixed its gate before any result: Cohen's kappa ≥ 0.60 in every
class and macro F1 ≥ 0.80. Neither comparator met it, so it was excluded from scoring before any
agent ran. The cause is label noise: identical report text carries different labels in 6.7 % of
repeated development texts, because a validating cardiologist could change the coded statements
without changing the report.

| Labeller | Macro F1 (95 % CI) | Worst-class kappa | Gate (kappa / F1) | Minus specialist, macro F1 (paired 95 % CI) |
|---|---|---|---|---|
| Specialist: TF-IDF + logistic regression | 0.735 (0.701 to 0.763) | 0.477 (HYP) | no / no | – |
| Keyword rules | 0.757 (0.726 to 0.786) | 0.579 (STTC) | no / no | – |
| Opus 5.5 | 0.790 (0.761 to 0.817) | 0.666 (HYP) | yes / no, by 0.0099 | +0.055 (+0.025 to +0.086) |
| Sonnet 5.5 | 0.757 (0.728 to 0.785) | 0.540 (HYP) | no / no | +0.022 (−0.003 to +0.048) |

HYP is hypertrophy; STTC is ST/T change. Both agents scored reward 0. **Both delegated the reading to
model calls from inside the sandbox.** Opus 5.5 wrote a script that sent batches of ten hidden
reports, with the twelve most similar labelled development reports, to `claude-opus-5-5`; Sonnet 5.5
had `claude-haiku-5-5` tag all 2,500 reports and trained a classifier on the tags. The task allows
the model API host, so this is within the rules as written, but the cost of those calls is not in
Claude Code's figure (Opus 5.5 estimated "about $0.16", unverified; Sonnet 5.5 not recorded). Both
stopped once their own estimate cleared the bar (Opus 5.5 0.878 on 150 development reports, Sonnet
5.5 0.81), with 97 % and 75 % of the session unused.

![Report labelling: macro F1 and worst-class kappa against the comparators](docs/figures/suite/round3_report_label.png)

### Instruction tests on fetal head: keep working (K) and check the clock (K2)

Each test is a new task version that changes only the instruction text; data, hidden cases, grader
and specialist are byte-identical to `suite/clinical-v1@2`. Each has 3 attempts per model and is
compared with the 3 R attempts. They are never pooled.

- **K** ([hosted-keepworking1.md](docs/research/suite/hosted-keepworking1.md), dataset
  `suite/hc18-keepworking-v1@1`) adds: "If your own validation on the development cases is below the
  clinical bar stated above, that is a reason to keep improving the pipeline, not to stop: use the
  remaining session time to try better methods and re-validate".
- **K2** (addendum registered after R and K results; dataset `suite/hc18-clockcheck-v1@1`) adds to K:
  "Run `date` at the start of your session and note the time. Before you end your turn, run `date`
  again and work out how much of the session remains."

| Model | Arm | Rewards (images within tolerance, of 83) | Mean (range) | Session used | Stopped below the bar by own estimate | Gap shown |
|---|---|---|---|---|---|---|
| Opus 5.5 | R | 0.422, 0.855, 0.675 (35, 71, 56) | 0.651 (0.422–0.855) | 44, 18, 18 % | 3 of 3 | 3 of 3 |
| Opus 5.5 | K | 0.687, 0.747, 0.651 (57, 62, 54) | 0.695 (0.651–0.747) | 33, 49, 35 % | 3 of 3 | 3 of 3 |
| Opus 5.5 | K2 | 0.783, 0.807, 0.807 (65, 67, 67) | 0.799 (0.783–0.807) | 82, 63, 60 % | 3 of 3 | 3 of 3 |
| Sonnet 5.5 | R | 0.771, 0.855, 0.892 (64, 71, 74) | 0.839 (0.771–0.892) | 24, 16, 72 % | 2 of 3 | 3 of 3 |
| Sonnet 5.5 | K | 0.831, 0.494, 0.627 (69, 41, 52) | 0.651 (0.494–0.831) | 44, 22, 24 % | 3 of 3 | 3 of 3 |
| Sonnet 5.5 | K2 | 0.000, 0.843, 0.783 (66, 70, 65) | 0.542 (0.000–0.843) | 76, 32, 67 % | 3 of 3 | 3 of 3 |

**K did not change the ending.** All six K agents read the paragraph, said they were below the bar
(own estimates 42 to 80 %), and stopped with 23 to 35 of 45 minutes left; five of six named a next
method and did not try it. Opus 5.5 worked longer (15 to 22 minutes against 8 in R2 and R3), but
reward did not follow time. With three attempts per arm, the spread within an arm is larger than any
difference between arms, so nothing is concluded about reward.

**K2 fixed the time belief but not the stopping**
([hosted-clockcheck1.md](docs/research/suite/hosted-clockcheck1.md)). All six K2 agents ran `date`
in their first tool call, read the clock 4 to 14 times, and read it again within 0.3 minutes of
ending. Every statement about time in their final messages was correct, and none claimed to be out
of time. Sessions got longer (Opus 5.5 60 to 82 %, Sonnet 5.5 32 to 76 %), and two agents used the
clock to plan ("About 20 minutes are left, so I'll try one cheap variance-reduction step", Opus 5.5
K2-2). But all six still ended their turn below the bar by their own estimate (78 to 90 %), with 8 to
31 minutes left, and said so: "I stopped with about 18 of the 45 minutes left rather than make
untested changes to a working pipeline" (Opus 5.5 K2-3); "About 15 minutes of the 45 are used, but
I'm stopping here" (Sonnet 5.5 K2-2). A gap is shown in 6 of 6 K2 attempts (65 to 70 of 83 within
tolerance).

Opus 5.5's K2 rewards were higher and narrower (mean 0.799, against 0.695 for K and 0.651 for R).
Sonnet 5.5's mean was 0.542, pulled down by one attempt that scored 0: in its last 30 seconds it
switched to a faster fit and an untested correction, and 2 of 83 hidden images then ran past the
10-second limit on the hosted grader (6.8 and 7.5 s locally), which by the stated rule makes the
reward 0; 66 of 83 images were within tolerance. With three attempts per arm, these comparisons are
descriptive.

![Fetal head reward against session used, R, K and K2](docs/figures/suite/round3_hc18_elicitation.png)

### Failure modes across the suite

Read from the traces of every round-3 attempt (42 new attempts) and the ten run-2 attempts. Each
quote names the attempt; counts are of observed attempts, not rates.

1. **Stopping below the bar.** In 11 of the 12 new per-case attempts in R, the final message said the
   agent's own development result was below the clinical bar; all 6 K and all 6 K2 attempts did the same. Opus
   5.5 fetal head R1: "about 60% … well below the 90% target, so expect a headline score around 0.6",
   then it ended its turn at 11.6 of 45 minutes (hidden 42 %). Opus 5.5 fetal head R2: "about 88% …
   just under the task's 90% bar … The obvious next step would be a second pass … I didn't have time
   to try it", with 37 minutes left.
2. **"Out of time" with most of the session left, without checking the clock.** Claude Code shows
   no clock, and the instruction gives the limit but not the start time.

   | Attempt | Said | Minutes used / limit |
   |---|---|---|
   | Opus 5.5 fetal head R3 | "I stopped there because of the session limit." | 8.1 / 45 |
   | Opus 5.5 fetal head R2 | "I didn't have time to try it." | 8.0 / 45 |
   | Sonnet 5.5 fetal head K3 | "Fixing it would probably need a stronger boundary model, which I ran out of session time for." | 11.0 / 45 |
   | Opus 5.5 registration R3 | "I didn't try a fully deformable registration in the time available." | 14.0 / 45 |
   | Opus 5.5 registration R2 | "I ran out of session time before closing it." | 14.5 / 45 |
   | Sonnet 5.5 spleen R2 | "I stopped here because of the 60-minute limit." | 35.2 / 60 |

   No fetal head attempt in R2, R3 or K checked the clock, and only one R attempt (Opus 5.5 spleen
   R3) planned against it. In K2, told to check, every agent did and none claimed to be out of time,
   yet all six still stopped below the bar with 8 to 31 minutes left.
3. **Self-estimates above the hidden score.** Agents validated on their own splits, often tuned on
   the same cases. Opus 5.5 fetal head R1: cross-validation about 60 %, hidden 42 %. Opus 5.5 ECG R2:
   MI sensitivity 0.818 on its folds 7 to 8, hidden 0.713. Opus 5.5 registration R3: 3 of 4
   development cases under 2 mm, hidden 1 of 6. Report labels: Opus 5.5 0.878, hidden 0.790; Sonnet
   5.5 0.81, hidden 0.757 ("slightly optimistic, because I tuned the decision thresholds on those same
   CV predictions").
4. **Final changes not re-validated.** All three Sonnet 5.5 causal attempts changed the interval
   factor as their last edit and stopped: "the final version is untested" (attempt 3). Sonnet 5.5
   vessel: "I never ran a full held-out check on the final model … I did not measure clDice or the
   per-image bar." Sonnet 5.5 fetal head K2-1 switched to a faster fit and an untested correction in
   its last 30 seconds; two hidden images then ran past the 10-second limit and the reward was 0.
   Opus 5.5 registration R3 shipped an affine step whose own check did not catch a
   transform that put landmarks outside the image, making one hidden case invalid.
5. **A no-op shipped as the answer.** Sonnet 5.5 registration R1 found its rigid registrations worse
   than no correction on the four development cases and replaced the pipeline with a copy of the
   input landmarks: "Conservative fallback: image-based rigid registration … was consistently WORSE
   than the navigation alignment, so landmarks are passed through." It stopped after 3 minutes: "I
   stopped partway through the 45 minutes." In R3 it ended at 2.1 minutes with a translation-only
   pipeline that left the landmarks essentially uncorrected (0 of 6).
6. **Delegating the task to model calls (report labels).** Both agents had another model read the
   hidden reports through the API from inside the sandbox, as described above. Neither printed a
   hidden report into its own context.

What went right: most attempts wrote a working baseline `run.sh` within minutes ("Write an identity
baseline first", Opus 5.5 registration R2), Opus 5.5 checked units and frames explicitly, and several
agents tested their pipeline as an unprivileged user with an empty `HOME`, as the verifier runs it.

![Session used by every attempt, by workstream](docs/figures/suite/round3_session_use.png)

**Contamination and web use.** No WebFetch or WebSearch was offered or used in any trace, no tool call
reached another host, and no trace recalled hidden labels or published per-case values. The one sign
of prior familiarity is method-level (the ICU unit repairs above).

### Cost

API cost is Claude Code's `total_cost_usd` at list price. Modal sandbox cost is not reported by
Valkyrie and is not included.

| Round | Attempts | API cost |
|---|---|---|
| Hosted smoke test (Sonnet 5.5) | 1 | $0.05 |
| Hosted run 1 (instructions v2) | 10 | about $7.25 ($5.66 exact; $1.59 estimated for killed attempts) |
| Hosted run 2 = R1 | 10 | $3.77 |
| Round 3, R2 and R3 | 20 | $6.60 |
| Round 3, K | 6 | $2.73 |
| Round 3, K2 | 6 | $5.11 |
| Round 3, V (vessel) | 2 | $1.01 |
| Round 3, C (causal) | 6 | $1.26 |
| Round 3, T (report labels) | 2 | $0.39, plus the agents' own model calls from the sandbox (not recorded) |
| **Hosted total** | 63 | **about $28.16** |
| Local pilot 1 (not hosted) | 4 | $1.70 reported; killed attempts have no cost record (upper bound $16.70) |

Round 3 stayed well under its preregistered $60 stop rule.

### Hosted checks of the reference solutions

Before any agent run on a task version, its reference solution (the "oracle") was run on Valkyrie to
check that the hosted image, artifact carry and separate verifier reproduce the locally measured
reward. The oracle is a reference pipeline, not always the specialist: for registration, ICU risk,
vessel and causal it is the specialist; for spleen and fetal head it is a classical method; for ECG
it is a simple model that misses the calibration bound; for report labels it is the specialist,
whose expected reward is 0.

| Dataset | Oracle run | Reward reproduced |
|---|---|---|
| `suite/clinical-v1@2` (five tasks) | `15fc4349-028e-42dc-982f-feccff226b7c` | 5 of 5, all seven keys equal to the v2 oracle run |
| `suite/vessel-v1@1` | `7d02411d-dd46-437a-bcc6-9d72b33a5323` | 0.75 (expected 0.75) |
| `suite/causal-v1@1` | `11115f4f-39bf-4a20-b894-7c1361f9a14b` | 1.0 (expected 1.0) |
| `suite/report-label-v1@1` | `72b3ac93-782a-4fc9-8a42-8e9c064c9168` | 0 (expected 0; the specialist's metrics exactly) |
| `suite/hc18-keepworking-v1@1` | `a73a3bc3-397c-419d-b26a-e993621b4917` | 0.759 (expected 0.759) |
| `suite/hc18-clockcheck-v1@1` | `8b8782de-d8d4-4f17-811f-81b80d322122` | 0.759 (expected 0.759) |

The v2 oracle run (`8ca063d3-…`, [hosted-oracle1.md](docs/research/suite/hosted-oracle1.md)) also
showed that the agent-phase network allowlist is enforced on Modal: pypi.org, files.pythonhosted.org
and example.com were unreachable and api.anthropic.com was reachable.

### Earlier runs

Hosted run 1 (instructions v2, `suite/clinical-v1@1`) and local pilot 1 (instructions v1) did not
state the agent's session limit or that the pipeline is graded as found when the session ends.
Agents planned work that could not fit: the limit killed five of ten run-1 attempts, which the rule
fixed before results classes as not interpretable. That was our bug, fixed by instructions v3. The
interpretable results agree with the headline on fetal head: Sonnet 5.5 showed a gap in run 1 (72 of
83) and both models in pilot 1. Opus 5.5 scored 0.928 on fetal head in both earlier rounds, against
0.422 to 0.855 in the three headline attempts; the instructions, sandbox and effort differed, so this
is not a clean variance estimate. Details: [hosted-agents1.md](docs/research/suite/hosted-agents1.md),
[pilot1-results.md](docs/research/suite/pilot1-results.md); figures `docs/figures/suite/hosted1_*`
and `pilot1_*`.

### Run identifiers

| What | Valkyrie run | Dataset |
|---|---|---|
| R1 = hosted run 2, Opus 5.5 | `1f2e6208-f148-4aaa-b72f-5225bed3b745` | `suite/clinical-v1@2` (instructions v3) |
| R1 = hosted run 2, Sonnet 5.5 | `5110a198-2582-414a-a9fd-81cc15103cdd` | `suite/clinical-v1@2` |
| R2, Opus 5.5 | `7db8faca-9295-4231-9dde-4580dfb8921a` | `suite/clinical-v1@2` |
| R3, Opus 5.5 | `39d574d3-7ee3-444e-b300-fb3c8cd74ae9` | `suite/clinical-v1@2` |
| R2, Sonnet 5.5 | `a3525e04-cb77-4e97-9dc6-ce71a86d3960` | `suite/clinical-v1@2` |
| R3, Sonnet 5.5 | `5378cf20-6ce9-4f13-b007-537c331d8ab5` | `suite/clinical-v1@2` |
| V, Opus 5.5 / Sonnet 5.5 | `123e97b9-acda-4504-96cb-3c46e935a277` / `8c5fa3ce-06cd-42a6-885b-42522e3ae7a2` | `suite/vessel-v1@1` |
| C, Opus 5.5 attempts 1–3 | `bd885935-899e-4031-a574-79f46b1af1b9`, `f0c183b4-f5c1-4da5-991f-a69ddad5c4f8`, `c5bfb9c1-2fd4-4d19-9b50-7f2f3cf2982d` | `suite/causal-v1@1` |
| C, Sonnet 5.5 attempts 1–3 | `c4e354b9-0e2a-4ab4-9434-4ac7317db88d`, `48e2209f-975b-4b84-a350-e1e45d1e2fe6`, `c0d950b0-f2e2-4cf3-b6a1-c939b22295b7` | `suite/causal-v1@1` |
| T, Opus 5.5 / Sonnet 5.5 | `60111604-75d3-4bd2-b928-e814a888244b` / `e1d46b7a-11ef-45ff-9294-670761bd54c0` | `suite/report-label-v1@1` |
| K, Opus 5.5 K1–K3 | `f8a4f7b6-8a1d-4007-b84a-d28c43fa0a23`, `0e58cc29-a54e-4b57-97e3-5f790377a967`, `7a155d74-b565-4a24-b0e0-5dd939c12890` | `suite/hc18-keepworking-v1@1` |
| K, Sonnet 5.5 K1–K3 | `6c5f28d3-72a7-4439-a623-bf050cf30a80`, `6b14667c-73e0-49ae-8a68-aeb2a16c5ee1`, `44c0ffb5-7b48-4852-9629-52acdbeb8d62` | `suite/hc18-keepworking-v1@1` |
| K2, Opus 5.5 (a, b, c) | `42343602-d6f5-449a-bfcc-7339a37f78ba`, `6d6a9980-29f1-4343-b812-d97a0b289aca`, `8d248879-6e7a-4fed-adf4-b363c4423732` | `suite/hc18-clockcheck-v1@1` |
| K2, Sonnet 5.5 (a, b, c) | `964a63e9-a12f-43eb-8cc5-6aee20834905`, `36830d5f-f8e0-4047-b062-bca7ee5d5cc0`, `e8e49d18-baa8-4579-a9f5-56a24ce7f515` | `suite/hc18-clockcheck-v1@1` |
| Hosted run 1, Opus 5.5 / Sonnet 5.5 | `0ae696de-4237-44bf-be49-25b90940772b` / `1a4037a0-e1a9-4670-aee0-ceda221c6264` | `suite/clinical-v1@1` (instructions v2) |
| Oracles | see [the table above](#hosted-checks-of-the-reference-solutions); v2 oracle `8ca063d3-ff52-4bd0-883f-4fc815e6e31a` | |
| Smoke oracle / smoke agent (Sonnet 5.5) | `1ff5a572-99f5-4623-9062-397e992201ca` / `cea5e542-b160-4971-8119-0a9443d82663` | `suite-scratch/toy-smoke@1` |

Raw traces stay outside Git (`exp/` is ignored); the documents above cite the files that hold them.

## How to run

All commands run from the repository root. Install nothing globally: every dependency goes into a
project conda environment or the project's Valkyrie virtual environment
([AGENTS.md](AGENTS.md)).

### Environment and tests

```bash
~/miniconda3/bin/conda env create -f suite/environment.yml        # creates "vals-suite"; pins in suite/requirements.txt
~/miniconda3/envs/vals-suite/bin/python -m pytest tests -q                # 490 passed, 2 skipped on 2026-11-15
```

Each family also has its own environment for data preparation and comparators
(`suite/families/<family>/environment.yml`, environment name `vals-suite-<family>`).

### Data

Download each dataset from its source (table under [Data and licences](#data-and-licences)) and stage
it with the family's own scripts; each family document lists the steps, checksums and split. Data
live under `/home/jkwei/data/vals-suite/<family>/` on the build machine and are not in Git. The
round-3 families:

```bash
# Retinal vessels: extract the 84 files of CHASEDB1.zip (downloaded in a browser) to DATA_ROOT/official/
~/miniconda3/envs/vals-suite-seg_vessel/bin/python -m suite.families.seg_vessel.prepare_data
taskset -c 0-3 ~/miniconda3/envs/vals-suite-seg_vessel/bin/python -m suite.families.seg_vessel.run_comparators \
  --pipeline suite/families/seg_vessel/specialist/pipeline --name unet --group hidden

# Treatment effect: covariates from the PhysioNet 2012 data already staged for risk_icu
P=~/miniconda3/envs/vals-suite-causal_ate/bin/python
$P -m suite.families.causal_ate.datagen.covariates RISK_ICU_EXTRACTED DATA_ROOT
$P -m suite.families.causal_ate.datagen.prepare_data DATA_ROOT
$P -m suite.families.causal_ate.comparators.run_comparators DATA_ROOT hidden

# Report labels: from the PTB-XL 1.0.3 copy staged for ecg_ptbxl (read-only)
~/miniconda3/envs/vals-suite-label_ptbxl_reports/bin/python suite/families/label_ptbxl_reports/prepare_data.py SRC_DIR OUT_DIR
```

### Exporting tasks

Each family has a `build_spec` in `suite/families/<family>/spec.py`, and
`suite.core.export.export_task` writes a Harbor-format task folder, refusing to write if any hidden
input, hidden reference or specialist output would reach the agent side. The pattern (shown for the
toy task in [suite/README.md](suite/README.md)) is:

```bash
~/miniconda3/envs/vals-suite/bin/python -c "from suite.families.toy.spec import build_spec; \
from suite.core.export import export_task; print(export_task(build_spec('/tmp/w'), 'dist/suite-toy'))"
.venv-valkyrie/bin/python scripts/validate_exports.py dist/suite-toy results/<date>-suite-toy-packaging
```

The `build_spec` signatures differ by family (see each `spec.py`; use absolute paths). Exports used
for the hosted datasets:

| Dataset | Export |
|---|---|
| `suite/clinical-v1@2` | `dist/suite-tasks-v3/<family>/<task-id>/` ([instructions-v3.md](docs/research/suite/instructions-v3.md)) |
| `suite/vessel-v1@1` | `export_task(build_spec(...))` from `suite.families.seg_vessel.spec` into `dist/suite-tasks-vessel-v1/` |
| `suite/causal-v1@1` | `export_task(build_spec(DATA_ROOT, WORK_DIR))` from `suite.families.causal_ate.spec` into `dist/suite-tasks-causal-v1/` |
| `suite/report-label-v1@1` | `python -m suite.families.label_ptbxl_reports.spec DATA_ROOT OUT_DIR` (direct-answer contract) |
| `suite/hc18-keepworking-v1@1` | `~/miniconda3/envs/vals-suite/bin/python scripts/export_hc18_keepworking.py --out dist/suite-tasks-k1` |
| `suite/hc18-clockcheck-v1@1` | `~/miniconda3/envs/vals-suite/bin/python scripts/export_hc18_keepworking.py --clock-check --out dist/suite-tasks-k2` |

Exported tasks are not in Git (`dist/` is ignored); the published copies are the Valkyrie datasets.

### Local pilot

Needs Linux with bubblewrap and an existing Claude Code login ([local-pilots.md](docs/research/suite/local-pilots.md)):

```bash
~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py run dist/suite-<family>/<task-id> \
  --run-name <run-name> --model claude-opus-5-5 --effort high --time-limit 2700 --budget 5
~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py summarize exp/suite-pilots/<run-name>
```

### Valkyrie

The CLI is pinned in `requirements-valkyrie.txt` (Python 3.12) and installed in `.venv-valkyrie/`.
Commands as used for this submission (the workstream documents give each exact command):

```bash
V=.venv-valkyrie/bin/valkyrie
$V org use hackathon-neuronetwork-b91c517178

# Publish (one dataset per task version)
$V dataset push suite/clinical-v1 dist/suite-tasks-v3 --tag instr2 --concurrency 2       # -> suite/clinical-v1@2
$V dataset push suite/vessel-v1 dist/suite-tasks-vessel-v1 --tag v1 --concurrency 2      # -> suite/vessel-v1@1
$V dataset push suite/causal-v1 dist/suite-tasks-causal-v1 --tag v1                      # -> suite/causal-v1@1
$V dataset push suite/hc18-keepworking-v1 dist/suite-tasks-k1 --tag k1                   # -> suite/hc18-keepworking-v1@1
$V dataset push suite/hc18-clockcheck-v1 dist/suite-tasks-k2 --tag k2                    # -> suite/hc18-clockcheck-v1@1

# Check the reference solution on Modal before any agent run
$V run start --agent oracle --dataset suite/vessel-v1@v1 --provider modal --concurrency 1 -l <label>

# Install the Claude Code agent without WebFetch and WebSearch (agents/claude_code_noweb)
$V agent push agents/claude_code_noweb

# One attempt = one run per model
$V run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@instr2 \
  --model anthropic/claude-opus-5-5 --provider modal \
  -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 3 -l <label>
```

The no-web agent is the registry `claude_code-v1.0.0` bundle with WebFetch and WebSearch removed,
Claude Code pinned to 2.1.325 and a per-task cap of `--max-budget-usd 8`. We chose Claude Code
because it is one of the harnesses Valkyrie provides, it is the general coding agent people use for
this kind of analysis, and our local pilot runner already used it. We removed the web tools because
the stock bundle reaches them through the allowed model API host
([hosted-smoke.md](docs/research/suite/hosted-smoke.md), finding 2).

### Figures

```bash
~/miniconda3/envs/vals-suite/bin/python scripts/make_suite_figures.py
```

This reads the result JSON files in `docs/research/suite/` (a missing file is skipped), the
aggregate files in `docs/research/suite/data/`, and the specialist numbers and thresholds in
`task-manifest.json`, and writes PNG and SVG files to `docs/figures/suite/`. The `round3_*` figures
show the pooled headline, session use, the K/K2/R comparison, vessel per image, the causal control
and the report-label example. Arms that are not pooled are drawn with different markers, never as
one series.

## Data and licences

| Family | Source | Licence | Attribution |
|---|---|---|---|
| reg_resect | RESECT, NIRD archive, doi:10.11582/2017.00004 | CC BY 4.0 | Xiao Y, Fortin M, Unsgård G, Rivaz H, Reinertsen I. Med Phys 2017;44(7):3875–3882 |
| seg_spleen | Medical Segmentation Decathlon Task09 Spleen (Memorial Sloan Kettering Cancer Center) | CC BY-SA 4.0; derived task data stay CC BY-SA 4.0 | Simpson et al. 2019, arXiv:1902.09063; Antonelli et al. Nat Commun 2022;13:4128 |
| measure_hc18 (and K, K2) | HC18, Zenodo 1327317 | CC BY 4.0 | van den Heuvel TLA, de Bruijn D, de Korte CL, van Ginneken B. PLoS ONE 2018;13(8):e0200412 |
| seg_vessel | CHASE_DB1, Kingston University research repository | CC BY 4.0 | Fraz MM et al. IEEE Trans Biomed Eng 2012;59(9):2538–2548 |
| ecg_ptbxl | PTB-XL 1.0.3, PhysioNet, doi:10.13026/kfzx-aw45 | CC BY 4.0 | Wagner et al. Sci Data 2020;7:154; Goldberger et al. Circulation 2000;101(23) |
| label_ptbxl_reports (excluded) | PTB-XL 1.0.3 report text and statement mapping | CC BY 4.0 | as ecg_ptbxl |
| risk_icu | PhysioNet/CinC Challenge 2012 v1.0.0 | ODC-By 1.0 | Silva I, Moody G, Scott DJ, Celi LA, Mark RG. Computing in Cardiology 2012;39:245–248; Goldberger et al. 2000 |
| causal_ate | Covariates from PhysioNet/CinC Challenge 2012 v1.0.0; treatment and outcomes generated by our own process | ODC-By 1.0 (covariates) | as risk_icu; design after Dorie et al. Stat Sci 2019;34(1):43–68 |
| triage_pharyngitis (excluded) | PGUPharyngitis, figshare doi:10.6084/m9.figshare.28163513.v1 | CC BY 4.0 | Shojaei N. et al. Sci Data 2025;12:1418 |

Each exported task carries its licence and attribution file next to the data, with a list of the
changes we made (for example, opaque case IDs, cleared header text fields, cropping for the spleen
CT). Every task's hidden cases and specialist outputs sit only on the verifier side.

**CHASE_DB1.** The official page states CC BY 4.0, but the file sits behind a Cloudflare "verify you
are human" check, which our worker did not bypass. Jin downloaded `CHASEDB1.zip` in a browser on
2026-11-15 (SHA-256 `bb750b73…6790b6`); a Hugging Face mirror was byte-identical file by file and was
not used to build anything ([seg_vessel.md](docs/research/suite/seg_vessel.md) section 2).

**Why the causal family does not use ACIC data.** ACIC 2016 and 2017 ship the covariates of the
Infant Health and Development Program (IHDP), whose ICPSR terms forbid redistribution without written
agreement; ACIC 2019 states no licence; ACIC 2022 needs a sign-up, which would accept terms on Jin's
behalf. We therefore wrote an ACIC-2016-style generator (seven two-level design knobs, 16 settings)
over real PhysioNet 2012 covariates, whose licence allows redistribution. A side effect: the true
effects are not public, unlike ACIC 2016's ([causal_ate.md](docs/research/suite/causal_ate.md)).

**PTB-XL reports.** Only human-validated, non-auto-generated reports with textual content are used;
hidden reports come from fold 9, which no `ecg_ptbxl` agent sees, and fold 10 (the ECG task's hidden
fold) is never used.

**Why pharyngitis is excluded.** No comparator meets its clinical gate on the hidden patients. The
reference label is a physician panel's vote from a photo and the symptom list, with no culture or
rapid antigen test; the symptoms the agent sees also informed the label; the labels run against the
Centor and McIsaac items (a partial McIsaac score ranks hidden patients inversely, AUROC 0.41); and
the phone model stands in for the city, with bacterial shares of 44 % and 15 %. We keep it as a
worked example of label and shortcut problems. We also removed EXIF metadata from every image
because 216 of 741 released images carried GPS coordinates
([triage_pharyngitis.md](docs/research/suite/triage_pharyngitis.md)).

**How the datasets were chosen.** The survey rated 50 candidate entries, some of them variants of one
source ([dataset-survey.md](docs/research/suite/dataset-survey.md)), in order: a licence that allows
redistribution in a task image on a commercial platform (CC BY, CC BY-SA, ODC-By); a clinical
measure with a published bar; a specialist that can pass that bar on the hidden cases; and a size
that fits a task image. Most datasets from Jin's course material failed on licence: HAM10000 is
CC BY-NC 4.0; APTOS 2019 is under Kaggle competition rules (non-commercial, no redistribution,
according to a secondary source); Open-i is listed as CC BY-NC-ND 4.0 by third-party mirrors; and the
local DRIVE and STARE copies state no licence.

**No UCSF patient data** is on Valkyrie or in this repository. The UCSF lymphoma work stays on the
UCSF servers; Git holds only code, schemas and aggregate results ([AGENTS.md](AGENTS.md)).

## Limitations

- **Few attempts.** Three attempts per task and model for the headline, one for vessel and report
  labels, three per arm for K and K2. Means and ranges are descriptive; three draws cannot estimate
  run-to-run variance well, and the spread already seen (Opus 5.5 fetal head 0.42 to 0.86) is large.
- **Small hidden sets.** Registration and spleen have 6 hidden cases and vessel 8, and the
  specialists pass 4, 3 and 6 of them, so per-attempt intervals there are wide or degenerate. "No
  gap shown" on those tasks is underpowered, not evidence of parity.
- **The specialists are not perfect.** The registration, spleen and vessel specialists fail some
  hidden cases; a gap is judged only on cases they pass.
- **Several bounds are our convention** (marked in the families table). They were fixed before any
  agent result and not tuned afterwards. The vessel bar has no slack: one Opus 5.5 image missed by
  0.00002 clDice.
- **The causal control is easier than intended.** Its instruction names the specialist's method,
  and the agents tuned interval widths on the development datasets.
- **The report-label gate assumed text-determined labels.** The measured label noise puts the
  ceiling below the bar for every labeller tried; a gate set from that ceiling would be a new task
  version.
- **Instruction tests are post hoc.** K was registered before round 3, but K2 was added after R and K
  results were seen. Both are reported as separate task versions and never pooled.
- **Public data.** All datasets are public, so models may have seen them. No trace recalled hidden
  labels or published per-case values, and no run used outside reference values. Opus 5.5 showed
  method-level familiarity with the PhysioNet 2012 data.
- **Local versus hosted.** Pilot 1 ran locally without CPU or memory caps on a shared host; only the
  hosted runs reflect the declared task resources. Valkyrie does not report the CPU and memory
  actually granted.
- **Effort setting.** The hosted agent passes no effort flag, so the Claude Code 2.1.325 default
  applies to every hosted result, which is not "high".
- **Raw values are regraded.** Valkyrie does not keep the grader's `metrics.json`, so values in mm,
  Dice and AUROC come from a local regrade of each saved pipeline (agreement figures above).
- **Cost.** Valkyrie reports no Modal cost. API costs come from Claude Code at list price and miss
  the model calls the report-label agents made from inside the sandbox.
- **Scope.** This is a sandboxed, pre-clinical benchmark. It does not show that any pipeline is safe
  for clinical use.

## Related work

The review in [landscape.md](docs/research/suite/landscape.md) found that agent-produced imaging
deliverables have prior work, so we do not claim to be first at that. ReX-MLE runs machine-learning
engineering scaffolds on medical imaging challenge data and ranks them against human leaderboards;
AutoMedBench scores agent segmentations without a specialist bar; HealthAgentBench runs Claude Code
and Codex on real CT and MRI but grades labels and answers. What this suite adds is the combination:
frontier coding-agent harnesses; artifacts beyond segmentation (a registration in mm, a measurement in
physical units, calibrated risks); clinical time limits as gates; and a specialist run on the same
hidden cases, so that the comparison is per case rather than against a leaderboard. Learn2Reg and FLARE
score TRE, runtime and memory, but for submitted algorithms, not agents.

## Related UCSF PCNSL work

The suite started from a different question: can frontier models predict mutation status in
primary central nervous system lymphoma (PCNSL) from imaging features? On the public UCSF release
(64 patients with genomic records, 439 imaging features), nothing tried gave reliable evidence of
signal above chance for the two main genes, TabPFN included: fixed logistic regression MYD88 AUROC
0.562 (permutation p = 0.27) and CD79B 0.347; TabPFN v2.5 0.420 and 0.386; GPT-5.2 on one fold 0.567
and 0.361, with Opus 5.5 failing the response format. With no comparator that succeeds, a frontier
gap cannot be shown, so the suite moved to tasks where a specialist provably passes. Reports:
[pcnsl/results/](pcnsl/results/) and [docs/research/pcnsl-overview.md](docs/research/pcnsl-overview.md),
the previous README. That work is separate from this submission, and its patient-level data stay on
UCSF servers.
