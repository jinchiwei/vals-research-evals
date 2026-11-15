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
a fetal head circumference (HC) in millimetres, or calibrated probabilities for electrocardiogram
(ECG) classes or intensive care unit (ICU) mortality. A separate verifier runs the agent's pipeline
on hidden cases under a clinical time limit, scores the output with the metric a clinician or
challenge organiser would use, and compares it with a specialist system run on the same hidden
cases. The design is in [DESIGN.md](docs/research/suite/DESIGN.md) and the current plan in
[PLAN.md](docs/research/suite/PLAN.md).

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
  (dataset `suite/clinical-v1@2`; [instructions-v3.md](docs/research/suite/instructions-v3.md)) the instruction states this; earlier
  versions did not (see Results).

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
- **Measurement: absolute error in physical units against a declared tolerance** (section 3).
- **Probabilities: discrimination is not enough.** The area under the receiver operating
  characteristic curve (AUROC) measures ranking only; calibration and decision-curve net benefit
  decide whether a risk is usable, and most published prediction models never assessed calibration
  (sections 1(c) and 1(d); Van Calster et al.; Vickers and Elkin; Christodoulou et al. 2019).
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
| [`ecg_ptbxl`](docs/research/suite/ecg_ptbxl.md) | PTB-XL 1.0.3, CC BY 4.0; 8,000 / 1,000 ECGs | calibrated probabilities for five diagnostic superclasses | all of: myocardial infarction (MI) sensitivity ≥ 0.70 at specificity 0.90 (Willems et al. 1991); mean expected calibration error (ECE) ≤ 0.05 (our convention); macro AUROC gap to the worst sex or age group ≤ 0.05 (our convention) | 560 s for the cohort, killed at 1,120 s (our convention) | xresnet1d-style CNN: all 3 parts met; macro AUROC 0.921 | scored |
| [`risk_icu`](docs/research/suite/risk_icu.md) | PhysioNet/CinC Challenge 2012, ODC-By 1.0; 4,000 / 4,000 stays | calibrated in-hospital mortality risk | all of: challenge event-1 score ≥ 0.321 (SAPS-I on the same stays plus 0.05; margin is our convention; Silva et al. 2012); calibration slope 0.8 to 1.2 and calibration-in-the-large within 0.2 logit (our convention); net benefit at threshold 0.20 above treat-all and treat-none (Vickers and Elkin 2006); worst ICU-type or sex AUROC ≥ overall − 0.10 (our convention) | 300 s for the cohort | gradient-boosted trees: all 4 parts met; AUROC 0.873 | scored; [PLAN.md](docs/research/suite/PLAN.md) expects a control |
| [`triage_pharyngitis`](docs/research/suite/triage_pharyngitis.md) | PGUPharyngitis (Shojaei et al. 2025), CC BY 4.0; 561 / 180 patients | probability of bacterial sore throat from a throat photo and symptoms | four-part gate (operating point, calibration, net benefit, subgroup sensitivity) | 420 s for the cohort | no comparator passes (best: 2 of 4 parts; AUROC 0.674) | excluded: worked example of label and shortcut problems |

A synthetic toy task (`toy-sphere-volume-0001`) is used only as a platform smoke test and is not
scored.

### The gap rule

A frontier gap is claimed only against the specialist on the same hidden cases, never against the
threshold alone ([DESIGN.md](docs/research/suite/DESIGN.md)).

- **Per-case families** (registration, segmentation, measurement): take the hidden cases the
  specialist passes. An invalid or late agent case counts as a fail. Compute the paired difference
  in pass rate (agent minus specialist) with a bootstrap 95 % interval (2,000 resamples, seed
  20261114). A gap is shown when the agent fails at least one of these cases and the interval lies
  entirely below 0.
- **Cohort families** (ECG, ICU): a gap is shown when the specialist meets every gate part and the
  agent misses at least one. If both pass, the task is a control.
- **No comparator passes** (pharyngitis): the task is excluded from scoring.
- A run that fails because of our own infrastructure or instruction bug is reported as not
  interpretable, not as a gap.

Rules fixed before any agent run: one attempt per task and model, nothing rerun for a better
number; thresholds set from the literature or stated as our convention before any agent result;
splits and hidden-case hashes recorded per family ([PLAN.md](docs/research/suite/PLAN.md)).

## Results

**Status on 2026-11-15.** The headline is hosted run 2: Claude Code (no web tools) with Claude Opus 5.5
and Claude Sonnet 5.5 on the five scored tasks, task instructions v3, Valkyrie dataset
`suite/clinical-v1@2`. Every number has one attempt per task and model, and the hidden sets for
registration and spleen have only 6 cases. Earlier runs used instructions that did not state the
session limit; they are summarised separately under [Earlier runs](#earlier-runs) and never pooled
with hosted run 2. Full write-up, trace notes and per-case values:
[hosted-agents2.md](docs/research/suite/hosted-agents2.md) and
[hosted-agents2.json](docs/research/suite/hosted-agents2.json).

### Summary

- **Both models fall short of the specialist on a measurement in physical units.** On fetal head
  circumference the specialist U-Net is within tolerance on 83 of 83 hidden images; Opus 5.5 on 35
  and Sonnet 5.5 on 64. Both paired intervals lie well below 0, and neither agent reaches the 90 %
  family bar.
- **Opus 5.5 matches the specialist on registration and spleen.** Registration: 4 of 6 cases under
  2 mm and mean TRE 1.61 mm, against the specialist's 4 of 6 and 3.03 mm. Spleen: the same 3 of 6
  cases pass, with mean Dice 0.940 against 0.939, from a small U-Net it trained on CPU. With 3 or 4
  specialist-passed cases these "no gap" results are underpowered, not proof of parity.
- **Sonnet 5.5 shipped a no-op on registration.** After 3 minutes it replaced its pipeline with one
  that copies the landmarks unchanged (mean TRE 6.18 mm, the uncorrected error), so it fails all four
  cases the specialist passes.
- **Controls hold.** On ECG classes and ICU mortality risk both models meet every gate part, as the
  specialists do.
- **Agents stop early.** All ten attempts ended by themselves with 48 to 96 % of their session
  unused, several while stating they were below the clinical bar. None was killed at the limit.
- **Clean runs.** No infrastructure failure or relaunch, no web search or fetch in any trace, no
  recalled labels. Total API cost 3.77 USD.

### Hosted run 2: agent against specialist (headline)

Runs `1f2e6208-f148-4aaa-b72f-5225bed3b745` (Opus 5.5, Valkyrie `final_score` 71.77) and
`5110a198-2582-414a-a9fd-81cc15103cdd` (Sonnet 5.5, 58.76), agent `claude_code_noweb-v1.0.0`
(Claude Code 2.1.325, WebFetch and WebSearch disallowed, 8 USD cap per task, the Claude Code default
effort). Reward keys are the hosted grades. Raw values in units come from a local regrade of each
run's saved pipeline with the task's own grader, because Valkyrie does not keep `metrics.json`; the
regrade matches all seven hosted keys in 9 of 10 attempts, and in the tenth (Opus registration) only
`quality` differs, by 0.0002. Specialist values are on the same hidden cases. Session is the
minute the agent ended its turn, out of its limit (Opus 5.5 fetal head: first answer at 11.6
minutes; a background job woke it for one more turn that changed nothing, and the process ended at
19.7 minutes).

| Task | Model | reward | ran / valid / within_time | quality | vs_specialist | Agent (raw, in units) | Specialist (same cases) | Session | API cost |
|---|---|---|---|---|---|---|---|---|---|
| reg_resect (6 cases; < 2 mm) | Opus 5.5 | **0.667** | 1 / 1 / 1 | 0.463 | 1.000 | 4/6 under 2 mm; mean TRE 1.61 mm (median 1.31) | 4/6; 3.03 mm (median 1.91) | 18 of 45 min | $0.553 |
| | Sonnet 5.5 | **0.000** | 1 / 1 / 1 | 0.070 | 0.213 | 0/6; mean TRE 6.18 mm, the uncorrected error | as above | 3 of 45 min | $0.142 |
| seg_spleen (6 cases; Dice ≥ 0.94 and volume error ≤ 10 %) | Opus 5.5 | **0.500** | 1 / 1 / 1 | 0.940 | 1.000 | 3/6; mean Dice 0.940; mean abs. volume error 4.1 % | 3/6; 0.939; 4.3 % | 31 of 60 min | $0.910 |
| | Sonnet 5.5 | **0.167** | 1 / 1 / 1 | 0.621 | 0.661 | 1/6; mean Dice 0.621 (median 0.840); volume error 34 % | as above | 16 of 60 min | $0.332 |
| measure_hc18 (83 images; within 4.9 %) | Opus 5.5 | **0.422** | 1 / 1 / 1 | 0.293 | 0.409 | 35/83; mean error 16.2 mm (median 8.8) | 83/83; 2.05 mm (median 1.51) | 11.6 of 45 min | $0.567 |
| | Sonnet 5.5 | **0.771** | 1 / 1 / 1 | 0.502 | 0.700 | 64/83; mean error 18.0 mm (median 3.3) | as above | 10.7 of 45 min | $0.356 |
| ecg_ptbxl (1,000 ECGs; 3 gate parts) | Opus 5.5 | **1.000** | 1 / 1 / 1 | 0.953 | 0.970 | 3/3 parts; macro AUROC 0.908; MI sensitivity 0.717; ECE 0.030; subgroup gap 0.029 | 3/3; 0.921; 0.744; 0.022; 0.026 | 8 of 30 min | $0.382 |
| | Sonnet 5.5 | **1.000** | 1 / 1 / 1 | 0.967 | 0.984 | 3/3; 0.914; 0.760; 0.025; 0.023 | as above | 10 of 30 min | $0.121 |
| risk_icu (4,000 stays; 4 gate parts) | Opus 5.5 | **1.000** | 1 / 1 / 1 | 0.747 | 1.000 | 4/4 parts; AUROC 0.874; calibration slope 1.04 | 4/4; 0.873; 1.04 | 3 of 45 min | $0.334 |
| | Sonnet 5.5 | **1.000** | 1 / 1 / 1 | 0.730 | 0.980 | 4/4; 0.865; 1.07 | as above | 1.6 of 45 min | $0.070 |

Every hidden case finished inside its time limit (slowest: Opus registration, 90.1 s of 120 s on one
case), so all rewards lost here are clinical, not delivery failures.

![Agent vs specialist on each task's headline clinical metric, hosted run 2](docs/figures/suite/hosted2_headline.png)

![Reward keys per task and model, hosted run 2](docs/figures/suite/hosted2_reward_keys.png)

### Gap verdicts

The rule is fixed in [DESIGN.md](docs/research/suite/DESIGN.md) and was operationalised before
launch: on the hidden cases the specialist passes (S), paired difference agent minus specialist,
2,000 bootstrap resamples, seed 20261114, 95 % percentile interval.

| Task · model | Cases in S | Agent passes in S | Pass-rate difference (95 % CI) | Raw difference on S (95 % CI) | Verdict |
|---|---|---|---|---|---|
| reg_resect · Opus 5.5 | 4 | 3 | −0.25 (−0.75 to 0.00) | TRE −0.20 mm (−0.55 to +0.08) | no gap shown; the one miss was 2.01 mm against the 2.0 mm bar; n = 4 |
| reg_resect · Sonnet 5.5 | 4 | 0 | −1.00 (degenerate) | TRE +3.69 mm (+2.36 to +5.02) | **gap shown**: an agent-chosen no-op pipeline |
| seg_spleen · Opus 5.5 | 3 | 3 | 0.00 | Dice 0.000 (−0.005 to +0.007) | no gap |
| seg_spleen · Sonnet 5.5 | 3 | 1 | −0.67 (−1.00 to 0.00) | Dice −0.068 (−0.189 to +0.001) | no gap shown; underpowered at n = 3, not reassuring |
| measure_hc18 · Opus 5.5 | 83 | 35 | −0.578 (−0.675 to −0.470) | abs. error +14.1 mm (+9.8 to +18.7) | **gap shown** |
| measure_hc18 · Sonnet 5.5 | 83 | 64 | −0.229 (−0.313 to −0.145) | abs. error +15.9 mm (+5.4 to +29.0) | **gap shown** |
| ecg_ptbxl · both | – | – | – | gate 3/3 vs 3/3 | no gap (control) |
| risk_icu · both | – | – | – | gate 4/4 vs 4/4 | no gap (control) |

No verdict is "not interpretable": no infrastructure failure, no grading error, and the v3
instruction stated the session limit, which no attempt reached. The fetal head gaps are the only
ones with intervals well clear of 0; on registration and spleen, 6 hidden cases cannot show a gap
short of a total failure.

![Per hidden image, fetal head circumference, hosted run 2](docs/figures/suite/hosted2_per_case_measure_hc18.png)

![Per hidden case, registration, hosted run 2](docs/figures/suite/hosted2_per_case_reg_resect.png)

![Per hidden case, spleen, hosted run 2](docs/figures/suite/hosted2_per_case_seg_spleen.png)

Per case: Opus 5.5 passes registration case cdd96a, which the specialist fails, and misses cb06b4 by
0.01 mm. On fetal head, Opus 5.5's errors are spread across the range (median 8.8 mm, 9 errors above
40 mm) and are worst on large heads (5 of 27 within tolerance); Sonnet 5.5 has a median error of
3.3 mm but 5 gross under-estimates of 221 to 275 mm on large heads, where its output fell to its own
clamp.

### What frontier agents get wrong

From the hosted run 2 traces, all ten read in full
([hosted-agents2.md](docs/research/suite/hosted-agents2.md), "Trace findings, per attempt"). Each
item is one observed run, not a rate.

1. **Stopping while knowing the result is below the bar.** Opus 5.5 on fetal head circumference had
   a working baseline `run.sh` within 5 seconds, built a pixel classifier with an ellipse fit, and
   estimated by 4-fold cross-validation "about 60% … well below the 90% target, so expect a headline
   score around 0.6". It then ended its turn at 11.6 of 45 minutes. The hidden result was 42 % (35 of
   83), against 100 % for the specialist.
2. **Shipping a no-op.** Sonnet 5.5 on registration tried SimpleITK rigid registration with mutual
   information, normalised cross-correlation and a translation grid on the four development cases,
   found them worse than no correction, and replaced the pipeline with a copy of the input
   landmarks: "Conservative fallback: image-based rigid registration … was consistently WORSE than
   the navigation alignment, so landmarks are passed through." It stopped after 7 turns and 3
   minutes: "I didn't try deformable registration … I stopped partway through the 45 minutes." Its
   grid search may contain a sign or axis error in the world-to-array mapping (our inference from the
   trace, not verified), which would explain errors larger than no correction.
3. **Mislocalising the organ.** Sonnet 5.5 on spleen (two-stage ExtraTrees) expected "roughly 4–5 of
   the 6 hidden scans to pass" and stopped with 44 minutes left. One hidden case scored Dice 0.000
   (wrong structure), another 0.144, and a third over-estimated the volume by 50 %.
4. **Optimistic self-validation.** In-sample tuning and random-ID folds made the agents' own
   estimates too high: Opus 5.5 fetal head, cross-validation about 60 %, hidden 42 %; Opus 5.5 ECG,
   myocardial infarction sensitivity 0.81 on its fold 8, hidden 0.717 against the 0.70 bar.

What went right, also from the traces: 8 of 10 attempts had a working `run.sh` within 3 minutes;
Opus 5.5 checked units and frames explicitly (world RAS mm via the affines for registration, pixel
size against the references for fetal head); and Opus 5.5 on spleen shipped a held-out checkpoint at
13 minutes "as a safe model" before fine-tuning further.

**Early stopping is the cross-cutting finding.** Every attempt ended its own turn with 48 to 96 % of
its session unused (Opus 5.5 spleen used 31 of 60 minutes; Sonnet 5.5 ICU 1.6 of 45). Three stated
that they were below the bar or had stopped early: Opus 5.5 fetal head ("about 60%"), Sonnet 5.5
fetal head ("it probably won't reach the 90% bar") and Sonnet 5.5 registration ("I stopped partway").
Nothing in the instruction tells the agent to stop; `claude -p` ends when the model ends its turn.
Whether an instruction to use the remaining time would change this is untested, and adding one would
be a new task version.

**Contamination and web use.** No WebFetch or WebSearch was offered or used, no tool call reached for
another host, and no trace recalled hidden labels or published per-case values. The one sign of prior
familiarity with the data is method-level: Opus 5.5 on ICU risk wrote unit repairs specific to the
PhysioNet 2012 data (FiO2 as a percentage, pH × 100, temperature in °F) before inspecting any value.

### Cost

| Item | Opus 5.5 | Sonnet 5.5 | Total |
|---|---|---|---|
| API, Claude Code `total_cost_usd` (list price) | $2.75 | $1.02 | **$3.77** |
| Modal sandboxes | not reported by Valkyrie | | about 2.5 h sandbox time across 10 tasks |

### Hosted checks of the reference solutions

Before any agent run, each task's shipped reference solution (the "oracle") was run on Valkyrie to
check that the hosted image, artifact carry and separate verifier reproduce the locally measured
reward. The oracle is a reference pipeline, not the specialist: for registration and ICU risk it
is the specialist; for spleen and fetal head it is a classical method; for ECG it is a simple model
that misses the calibration bound.

Run `15fc4349-028e-42dc-982f-feccff226b7c` on `suite/clinical-v1@2`, from
[instructions-v3.md](docs/research/suite/instructions-v3.md):

| Task | reward | ran | valid | within_time | clinically_acceptable | quality | vs_specialist | expected reward | match |
|---|---|---|---|---|---|---|---|---|---|
| reg-resect-build-0001 | 0.6667 | 1 | 1 | 1 | 0.6667 | 0.3313 | 1.0 | 0.6667 | yes |
| seg-spleen-build-0001 | 0.0 | 1 | 1 | 1 | 0.0 | 0.4095 | 0.4362 | 0.0 | yes |
| measure-hc18-0001 | 0.7590 | 1 | 1 | 1 | 0.7590 | 0.4369 | 0.6092 | 0.759 | yes |
| ecg-ptbxl-superdiag-0001 | 0.0 | 1 | 1 | 1 | 0.0 | 0.9730 | 0.9903 | 0.0 | yes |
| risk-icu-mortality-0001 | 1.0 | 1 | 1 | 1 | 1.0 | 0.7451 | 0.9999 | 1.0 | yes |

All five rewards equal the expected values, and all seven keys equal the earlier oracle run
`8ca063d3-ff52-4bd0-883f-4fc815e6e31a` on version 2 ([hosted-oracle1.md](docs/research/suite/hosted-oracle1.md)).
That run also showed that the agent-phase network allowlist is enforced on Modal: pypi.org,
files.pythonhosted.org and example.com were unreachable and api.anthropic.com was reachable. DNS
for public names still resolved. Earlier, a synthetic smoke task gave reward 1.0 for both the oracle
and a Claude Sonnet 5.5 agent ([hosted-smoke.md](docs/research/suite/hosted-smoke.md)).

### Earlier runs

Both earlier rounds used instructions that did not state the agent's session limit or that the
pipeline is graded as found when the session ends. Agents planned work that could not fit and were
killed mid-task. That was our bug; instructions v3 fixed it, and none of the hosted run 2 attempts
reached its limit. These rounds are reported for completeness and are not pooled with hosted run 2.

**Hosted run 1** (instructions v2, `suite/clinical-v1@1`; runs `0ae696de-4237-44bf-be49-25b90940772b`
Opus 5.5 and `1a4037a0-e1a9-4670-aee0-ceda221c6264` Sonnet 5.5;
[hosted-agents1.md](docs/research/suite/hosted-agents1.md)). The session limit killed five of ten
attempts (registration and spleen for both models, fetal head for Opus 5.5), which the rule fixed
before results classes as not interpretable. Registration and spleen had no interpretable attempt.
ECG and ICU were controls for both models, as in run 2. The one interpretable gap was Sonnet 5.5 on
fetal head: 72 of 83 within tolerance against 83 of 83, pass-rate difference −0.133 (−0.205 to
−0.060). Opus 5.5's killed fetal head attempt scored 0.928 (77 of 83). API cost about 5.20 USD (Opus 5.5)
and 2.05 USD (Sonnet 5.5). Figures: `docs/figures/suite/hosted1_*.png`.

**Local pilot 1** (instructions v1, local bubblewrap sandbox with only the model API reachable, effort
high, 45-minute session; [pilot1-results.md](docs/research/suite/pilot1-results.md)). Fetal head:
Opus 5.5 0.928 and Sonnet 5.5 0.819, both with gaps shown against the specialist (−0.072, −0.133 to
−0.024; −0.181, −0.265 to −0.108). Registration: both 0, a delivery failure at the deadline (Opus 5.5
wrote `run.sh` 2.5 minutes before the end, never ran it, and `python3 -I` broke its import; Sonnet 5.5
left the pipeline folder empty), not a measured accuracy gap. The local host had no CPU or memory caps
and was shared. Figures: `docs/figures/suite/pilot1_*.png`.

Run to run, fetal head moved a lot for the same model: Opus 5.5 scored 0.928 in pilot 1 and hosted
run 1 but 0.422 in hosted run 2; Sonnet 5.5 0.819, 0.867 and 0.771. The instructions, sandbox and
effort setting differed between rounds, so this is not a clean variance estimate, but it is a reason
to read every single-attempt number in this README as one draw.

### Run identifiers

| What | Valkyrie run | Dataset |
|---|---|---|
| Agents, hosted run 2 (headline), Opus 5.5 | `1f2e6208-f148-4aaa-b72f-5225bed3b745` | `suite/clinical-v1@2` (instructions v3) |
| Agents, hosted run 2 (headline), Sonnet 5.5 | `5110a198-2582-414a-a9fd-81cc15103cdd` | `suite/clinical-v1@2` (instructions v3) |
| Oracle, instructions v3 | `15fc4349-028e-42dc-982f-feccff226b7c` | `suite/clinical-v1@2` |
| Agents, hosted run 1, Opus 5.5 | `0ae696de-4237-44bf-be49-25b90940772b` | `suite/clinical-v1@1` (instructions v2) |
| Agents, hosted run 1, Sonnet 5.5 | `1a4037a0-e1a9-4670-aee0-ceda221c6264` | `suite/clinical-v1@1` (instructions v2) |
| Oracle, instructions v2 | `8ca063d3-ff52-4bd0-883f-4fc815e6e31a` | `suite/clinical-v1@1` |
| Smoke oracle | `1ff5a572-99f5-4623-9062-397e992201ca` | `suite-scratch/toy-smoke@1` |
| Smoke agent (Sonnet 5.5) | `cea5e542-b160-4971-8119-0a9443d82663` | `suite-scratch/toy-smoke@1` |

Raw traces stay outside Git (`exp/` is ignored); the summaries above cite the files that hold them.

## How to run

All commands run from the repository root. Install nothing globally: every dependency goes into a
project conda environment or the project's Valkyrie virtual environment
([AGENTS.md](AGENTS.md)).

### Environment and tests

```bash
~/miniconda3/bin/conda env create -f suite/environment.yml        # creates "vals-suite"; pins in suite/requirements.txt
~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite -q    # 214 passed, 1 skipped on 2026-11-14
```

Each family also has its own environment for data preparation and comparators
(`suite/families/<family>/environment.yml`, environment name `vals-suite-<family>`).

### Data

Download each dataset from its source (table under "Data and licences") and stage it with the family's
own scripts; each family document lists the steps, checksums and split. Data live under
`/home/jkwei/data/vals-suite/<family>/` on the build machine and are not in Git.

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

The `build_spec` signatures differ by family (see each `spec.py`). The version 3 export of the five
scored tasks went to `dist/suite-tasks-v3/<family>/<task-id>/`
([instructions-v3.md](docs/research/suite/instructions-v3.md)). Exported tasks are not in Git
(`dist/` is ignored); the published copy is the Valkyrie dataset `suite/clinical-v1@2`.

### Local pilot

Needs Linux with bubblewrap and an existing Claude Code login ([local-pilots.md](docs/research/suite/local-pilots.md)):

```bash
~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py run dist/suite-<family>/<task-id> \
  --run-name <run-name> --model claude-opus-5-5 --effort high --time-limit 2700 --budget 5
~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py summarize exp/suite-pilots/<run-name>
```

### Valkyrie

The CLI is pinned in `requirements-valkyrie.txt` (Python 3.12) and installed in `.venv-valkyrie/`.
Commands as used for this submission ([hosted-oracle1.md](docs/research/suite/hosted-oracle1.md),
[instructions-v3.md](docs/research/suite/instructions-v3.md), `exp/suite-hosted-agents1/prespec.txt`):

```bash
V=.venv-valkyrie/bin/valkyrie
$V org use hackathon-neuronetwork-b91c517178

# Publish the five scored tasks (version 3 became suite/clinical-v1@2, tag instr2)
$V dataset push suite/clinical-v1 dist/suite-tasks-v3 --tag instr2 --concurrency 2

# Check the reference solutions on Modal
$V run start --agent oracle --dataset suite/clinical-v1@2 --provider modal --concurrency 2 -l hosted-oracle-instr2

# Install the Claude Code agent without WebFetch and WebSearch (agents/claude_code_noweb)
$V agent push agents/claude_code_noweb

# One attempt per task and model
$V run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@2 \
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

This reads `docs/research/suite/pilot1-results.json`, `hosted-agents1.json` and `hosted-agents2.json`
when present (a missing file is skipped), takes specialist numbers and thresholds from
`task-manifest.json`, and writes PNG and SVG files to `docs/figures/suite/`, one set per source.
Sources are never pooled in one panel.

## Data and licences

| Family | Source | Licence | Attribution |
|---|---|---|---|
| reg_resect | RESECT, NIRD archive, doi:10.11582/2017.00004 | CC BY 4.0 | Xiao Y, Fortin M, Unsgård G, Rivaz H, Reinertsen I. Med Phys 2017;44(7):3875–3882 |
| seg_spleen | Medical Segmentation Decathlon Task09 Spleen (Memorial Sloan Kettering Cancer Center) | CC BY-SA 4.0; derived task data stay CC BY-SA 4.0 | Simpson et al. 2019, arXiv:1902.09063; Antonelli et al. Nat Commun 2022;13:4128 |
| measure_hc18 | HC18, Zenodo 1327317 | CC BY 4.0 | van den Heuvel TLA, de Bruijn D, de Korte CL, van Ginneken B. PLoS ONE 2018;13(8):e0200412 |
| ecg_ptbxl | PTB-XL 1.0.3, PhysioNet, doi:10.13026/kfzx-aw45 | CC BY 4.0 | Wagner et al. Sci Data 2020;7:154; Goldberger et al. Circulation 2000;101(23) |
| risk_icu | PhysioNet/CinC Challenge 2012 v1.0.0 | ODC-By 1.0 | Silva I, Moody G, Scott DJ, Celi LA, Mark RG. Computing in Cardiology 2012;39:245–248; Goldberger et al. 2000 |
| triage_pharyngitis (excluded) | PGUPharyngitis, figshare doi:10.6084/m9.figshare.28163513.v1 | CC BY 4.0 | Shojaei N. et al. Sci Data 2025;12:1418 |

Each exported task carries its licence and attribution file next to the data, with a list of the
changes we made (for example, opaque case IDs, cleared header text fields, cropping for the spleen
CT). Every task's hidden cases and specialist outputs sit only on the verifier side.

**Why pharyngitis is excluded.** No comparator meets its clinical gate on the hidden patients. The
reference label is a physician panel's vote from a photo and the symptom list, with no culture or
rapid antigen test; the symptoms the agent sees also informed the label; the labels run against the
Centor and McIsaac items (a partial McIsaac score ranks hidden patients inversely, AUROC 0.41); and
the phone model stands in for the city, with bacterial shares of 44 % and 15 %. We keep it as a
worked example of label and shortcut problems. We also removed EXIF metadata from every image
because 216 of 741 released images carried GPS coordinates
([triage_pharyngitis.md](docs/research/suite/triage_pharyngitis.md)).

**No UCSF patient data** is on Valkyrie or in this repository. The UCSF lymphoma work stays on the
UCSF servers; Git holds only code, schemas and aggregate results ([AGENTS.md](AGENTS.md)).

## Limitations

- **One attempt per task and model**, so there is no estimate of run-to-run variation. Fetal head
  scores for the same model moved between rounds (Opus 5.5: 0.928, 0.928, 0.422), though each round
  also changed the instructions or sandbox.
- **Small hidden sets.** Registration and spleen have 6 hidden cases each, and the specialist passes
  only 4 and 3 of them, so per-case intervals there are wide or degenerate. "No gap" on those tasks is
  underpowered, not evidence of parity.
- **The specialists are not perfect.** The registration and spleen specialists fail some hidden cases;
  a gap is judged only on cases they pass.
- **Several bounds are our convention** (marked in the families table). They were fixed before any
  agent result and not tuned afterwards.
- **Public data.** All datasets are public, so models may have seen them. No trace recalled hidden
  labels or published per-case values, and no run used outside reference values. One trace showed
  method-level familiarity: Opus 5.5 on ICU risk wrote dataset-specific unit repairs before looking at
  any value.
- **Local versus hosted.** Pilot 1 ran locally without CPU or memory caps on a shared host; only the
  hosted runs reflect the declared task resources. Valkyrie does not report the CPU and memory
  actually granted.
- **Effort setting.** The local pilot set effort high; the hosted agent passes no effort flag, so the
  Claude Code 2.1.325 default applies to every hosted result, which is not "high".
- **Task versions.** Version 1 and 2 instructions did not state the session limit; version 3 does.
  Results from different versions are reported separately.
- **Raw values are regraded.** Valkyrie does not keep the grader's `metrics.json`, so values in mm,
  mL and AUROC come from a local regrade of each saved pipeline; it matches the hosted reward keys in
  9 of 10 attempts and differs by 0.0002 in `quality` only in the tenth.
- **Cost.** Valkyrie reports no Modal cost; API costs come from the agent traces at list prices.
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

Earlier work in this repository on primary central nervous system lymphoma (PCNSL) imaging and
genetics, synthetic research-repair tasks and their pilots is described in
[docs/research/pcnsl-overview.md](docs/research/pcnsl-overview.md), the previous README. That work is
separate from this submission, and its patient-level data stay on UCSF servers.
