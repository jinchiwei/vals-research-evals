# Hosted agent runs 1: Claude Code (no web) on the five scored tasks, Opus 5.5 and Sonnet 5.5

Written 2026-11-14/15 by a Claude Code worker acting as experiment operator (model: Claude Opus 5.5,
`claude-opus-5-5`). Authorised by the project lead through the coordinator. One prespecified attempt per task
and model. Nothing was rerun or relaunched. Evidence is in `exp/suite-hosted-agents1/`, which is git-ignored
(`.gitignore` has `exp/`). The machine-readable numbers are in `hosted-agents1.json`.

## Summary

| | Opus 5.5 | Sonnet 5.5 | Specialist (same hidden cases) |
|---|---|---|---|
| Mean reward over 5 tasks (Valkyrie `final_score`) | 0.586 (58.55) | 0.573 (57.35) | — |
| Tasks with reward > 0 | 3 (hc18 0.928, ecg 1, icu 1) | 3 (hc18 0.867, ecg 1, icu 1) | — |
| Attempts killed by the session limit | 3 (reg, spleen, hc18) | 2 (reg, spleen) | — |
| Attempts that ended by themselves | 2 (ecg, icu) | 3 (hc18, ecg, icu) | — |
| API cost (list price, from traces) | about $5.20 | about $2.05 | — |

**Our main bug.** The session limit killed five of the eight attempts on the four tasks whose instruction does
not state it: reg (both models), spleen (both) and hc18 (Opus).
- No agent mentioned a session limit.
- Several planned work that could not fit:
  - Opus spleen estimated its training run at "about 2 hours" in a 60-minute session.
  - Sonnet spleen was waiting for its final training to write the model file.
  - Both reg agents were still comparing similarity measures.
- The fix is one sentence in each instruction: state the session limit, and say that whatever is in
  `/workspace/output/pipeline/` at the kill is what gets graded.

Under the rule fixed before any result, these five attempts are "not interpretable" as capability evidence,
whatever they scored. The reg and spleen comparisons have **no interpretable attempt in this round**.

**Interpretable results.**
- ECG and ICU are controls. Both models met every gate part, as did the specialists.
- On HC18, Sonnet finished by itself and missed the task's 90 % bar: 72 of 83 images within tolerance,
  against the specialist's 83 of 83. That is the only interpretable per-case gap in this round.

## Design (as prespecified, `exp/suite-hosted-agents1/prespec.txt`)

| Item | Value |
|---|---|
| Dataset | `suite/clinical-v1@1` (tag `oracle1`, digest `c755684595ed`): reg_resect, seg_spleen, measure_hc18, ecg_ptbxl, risk_icu |
| Agent | `claude_code_noweb-v1.0.0` (stock registry Claude Code, WebFetch and WebSearch disallowed) |
| Models | `anthropic/claude-opus-5-5`, `anthropic/claude-sonnet-5-5`; one attempt per task each, 10 attempts in 2 runs |
| Concurrency | `--concurrency 3` per run, with both runs launched together, so at most 6 tasks ran at once. I read "up to 3" as the per-run flag. Two runs at 3 each would not have fitted the time budget in sequence. |
| Timeouts | The tasks' own: agent 1800 s (ecg), 2700 s (reg, hc18, icu), 3600 s (spleen) |
| Effort | The agent has no effort setting and the bundle passes no `--effort`, so Claude Code 2.1.325's default applied. It is not reported in the trace. For reference, the API default is `medium` for Opus 5.5 and `high` for Sonnet 5.5; the CLI may set its own. **Effort was not set to high.** |
| Relaunch rule | Only for a clear infrastructure failure, once. **None was needed; no relaunch was made.** |

### Analysis rules added before results (timestamped in `prespec.txt`)

- **00:55:37Z, before any task result** (coordinator note):
  - Only ecg_ptbxl tells the agent its own session limit ("about 30 minutes", timeout 1800 s).
  - reg, hc18, icu (2700 s) and spleen (3600 s) do not, and no instruction says that the pipeline left at the kill
    is what gets graded.
  - An attempt on those four tasks that ends by session timeout is classified **our bug / not interpretable**.
  - A timeout on ecg would count as the agent's own result.
- **Gap-rule operationalisation, fixed while only "ecg evaluating" was known:**
  - Per-case families: on the hidden cases the specialist passes, compute the paired difference agent − specialist
    in per-case clinical acceptability (0/1). Use `suite.core.metrics.paired_bootstrap_difference(np.mean)`
    with 2000 resamples, seed 20261114 and a 95 % percentile interval.
  - "Gap shown" if the upper bound is below 0.
  - Cohort families: DESIGN.md as written.

## Agent install (step 1)

Two changes to `agents/claude_code_noweb/`, and nothing else
(`exp/suite-hosted-agents1/agent-noweb/cap-pin.diff`):

- **`collect_outputs.py`:** passes `--max-budget-usd 8`, a per-task spending cap. The flag is listed in the
  Claude Code 2.1.325 `--help` and was validated in `pcnsl_claude`.
- **`setup.sh`:** `curl -fsSL https://claude.ai/install.sh | bash -s 2.1.325`. The installer takes a version
  argument, so this is a one-line pin. Every hosted setup log shows `Version: 2.1.325`, and every trace's init
  reports `claude_code_version 2.1.325`.

**Validation.**
- **SDK** (`.venv-valkyrie`, valkyrie-sdk 0.34.0; `agent-noweb/sdk-validation.txt`): `AgentContract.from_directory`
  passes. `validate_kwargs` accepts both models. The bundle has the same 9 files, and argv ends with
  `--max-budget-usd 8`.
- **Offline CLI check** (`agent-noweb/offline-cli-check.txt`): local 2.1.325, dummy key, base URL
  `http://127.0.0.1:9`. The CLI accepts the argv and emits init with 26 tools, none of them WebFetch or WebSearch.

**Install.** `.venv-valkyrie/bin/valkyrie agent push agents/claude_code_noweb` reported
`✓ Agent 'claude_code_noweb-v1.0.0' pushed successfully!` at 00:50:22Z.
- `agent download` gives a copy identical to the local folder (`diff -r`).
- No other agent was installed. The stock `claude_code-v1.0.0` was not used.

**The cap was never reached.** The most expensive attempt, Opus on hc18, cost about $1.70.

## Commands

```
.venv-valkyrie/bin/valkyrie agent push agents/claude_code_noweb
.venv-valkyrie/bin/valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@1 --provider modal \
    --model anthropic/claude-opus-5-5 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 3 -l hosted-agents1-opus
      # Run ID 0ae696de-4237-44bf-be49-25b90940772b, started 19:51:13 EST
.venv-valkyrie/bin/valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@1 --provider modal \
    --model anthropic/claude-sonnet-5-5 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 3 -l hosted-agents1-sonnet
      # Run ID 1a4037a0-e1a9-4670-aee0-ceda221c6264, started 19:51:17 EST
```

**Collection** (per run, `exp/suite-hosted-agents1/<opus|sonnet>/`): `run fetch`, `run tasks`, `run task` per
task, `run logs` (text and jsonl, run-wide and per task), `run errors`, `run status`, `run artifacts`,
`run results` and `run outputs`. The outputs hold the full Claude Code trajectory, summary and carried pipeline
for each attempt. A scan of every fetched file for `sk-ant-` found nothing.

**Specialist values.** I graded each task's stored specialist outputs on the hidden cases with that task's own
vendored grader (`grading._grade_specialist`; `analysis/specialist_hidden.json`). No agent code ran locally.
- These reproduce the family documents and the oracle run: reg 4/6 (mean TRE 3.03 mm), spleen 3/6
  (mean Dice 0.939), hc18 83/83, ecg 3/3 gate parts, icu 4/4.
- As a check, the reg oracle's per-case TRE recovered from hosted stdout equals the specialist's local TRE to
  4 decimal places of quality.

## Results

Hidden cases per task: reg 6, spleen 6, hc18 83 images, ecg 1 cohort of 1,000 ECGs, icu 1 cohort of 4,000
stays. Reward keys are listed as ran / valid / within_time.

| Task | Model | reward | ran / valid / on time | Agent headline (units) | Specialist, same hidden cases | Ended | Agent time | Turns | API $ |
|---|---|---|---|---|---|---|---|---|---|
| reg | Opus | 0.0 | 0 / 0 / 0 | No pipeline left (`run.sh missing`); 0 of 6 cases under 2 mm | 4 of 6 under 2 mm; mean TRE 3.03 mm (median 1.91) | **killed at 2700 s** | 2700 s | — (31 API calls) | ≈1.61 (≥1.05 exact) |
| reg | Sonnet | 0.0 | 1 / 0.83 / 1 | 0 of 6 under 2 mm. Mean TRE 7.55 mm over 5 valid cases (2.50 to 13.91); 1 invalid (a landmark >10 mm outside the ultrasound). Worse than the uncorrected error on 3 cases | as above | **killed at 2700 s** | 2700 s | — (22 API calls) | ≈0.54 (≥0.34 exact) |
| spleen | Opus | 0.0 | 1 / 1 / 1 | 0 of 6; Dice 0.000 on every case: valid but empty masks, because the pipeline had no model weights | 3 of 6 (Dice ≥ 0.94 and volume within 10 %); mean Dice 0.939 | **killed at 3600 s** | 3600 s | 19 | 0.77 |
| spleen | Sonnet | 0.0 | 0 / 0 / 0 | 0 of 6; no output (exit 1, no weights) | as above | **killed at 3600 s** | 3600 s | — (24 API calls) | ≈0.70 (≥0.52 exact) |
| hc18 | Opus | 0.928 | 1 / 1 / 1 | 77 of 83 (92.8 %) within 4.9 %, above the task's 90 % bar. Median |error| 1.70 mm, mean 5.41 mm (80 recoverable) | 83 of 83 (100 %); median 1.51 mm, mean 2.05 mm | **killed at 2700 s** (pipeline already in place) | 2700 s | — (34 API calls) | ≈1.70 (≥1.05 exact) |
| hc18 | Sonnet | 0.867 | 1 / 1 / 1 | 72 of 83 (86.7 %), below the 90 % bar. Median 2.27 mm, mean 6.30 mm (79 recoverable) | as above | finished by itself | 1088 s | 31 | 0.55 |
| ecg | Opus | 1.0 | 1 / 1 / 1 | Gate 3 of 3; macro AUROC 0.911; cohort run 3.3 s | Gate 3 of 3; macro AUROC 0.921 | finished | 989 s | 13 | 0.48 |
| ecg | Sonnet | 1.0 | 1 / 1 / 1 | Gate 3 of 3; macro AUROC 0.911; 3.0 s | as above | finished | 1111 s | 14 | 0.18 |
| icu | Opus | 1.0 | 1 / 1 / 1 | Gate 4 of 4; AUROC 0.874; 14.8 s | Gate 4 of 4; AUROC 0.873 | finished | 535 s | 24 | 0.64 |
| icu | Sonnet | 1.0 | 1 / 1 / 1 | Gate 4 of 4; AUROC 0.865; 13.9 s | as above | finished | 60 s | 5 | 0.09 |

**Agent time** is the platform's `agent_run_duration`.

**Turns** are `num_turns` summed over a trace's result events. A killed trace has no result event, so the number
of distinct API calls is shown instead.

**Every hidden-case pipeline run was far inside the per-case limits**, which no agent violated:
- reg 2 to 5 s against 120 s;
- spleen 3 to 12 s against 300 s;
- hc18 2.6 to 4.5 s against 10 s;
- ecg 3 s against 560 s;
- icu 14 s against 300 s.

**Where the numbers come from.**
- **Rewards:** the hosted `reward.json`.
- **Per-case values:** the hosted verifier stdout. `metrics.json` is not carried by the platform; see
  `hosted-oracle1.md`.
- **Raw units are exact inversions of the per-case quality** (registration error TRE = target registration error):
  - reg mean TRE (mm) = −2 ln(quality), or the mm value in the failure text.
  - spleen Dice = quality.
  - hc18 |error| (mm) = 7.26 (1 − quality) where quality > 0, or the signed mm value in the failure text.
    Within-tolerance cases with |error| ≥ 7.26 mm cannot be recovered, so the hc18 mean |error| is over
    recoverable cases only and **is biased low**.
  - ecg macro AUROC = 0.5 + 0.428 × quality.
  - icu AUROC = (quality + 1)/2.
- **All 83 hc18 case lines fit** inside the platform's ~16 kB stdout cut in both runs. Only the summary was cut.

### Gap verdicts

**How to read the intervals.** Each is a paired difference, agent − specialist, on the hidden cases the specialist
passes, with a 95 % bootstrap interval (2000 resamples, seed 20261114). A per-case gap is "shown" when the
acceptability interval lies wholly below 0. Raw differences in mm or Dice are secondary.

| Task | Opus 5.5 | Sonnet 5.5 |
|---|---|---|
| reg (specialist passes 4) | **Not interpretable: our bug.** Killed at the unstated 2700 s limit with no pipeline. Numeric: 0 of 4; acceptability −1.00 [−1, −1] | **Not interpretable: our bug.** Killed. The graded pipeline was the first draft, which its own development check showed made alignment worse. Numeric: 0 of 4, −1.00 [−1, −1]; mean TRE +7.18 mm [+3.60, +10.75] |
| spleen (specialist passes 3) | **Not interpretable: our bug.** Killed with no trained weights, so the masks were empty. Numeric: 0 of 3, −1.00; Dice −0.959 [−0.962, −0.955] | **Not interpretable: our bug.** Killed while final training was writing the weights. Numeric: 0 of 3, −1.00 |
| hc18 (specialist passes 83) | **Not interpretable** under the prespecified timeout rule. Killed at 2700 s; the grader scored an intermediate pipeline, and a better second pass (cross-validated 96.1 %) was never wired in. Numeric: acceptability −0.072 [−0.133, −0.024]; quality −0.076 [−0.126, −0.020]; |error| +3.48 mm [+1.10, +6.34] (n = 80). The attempt cleared the task's own 90 % bar | **Gap shown.** Acceptability −0.133 [−0.205, −0.060]; quality −0.131 [−0.190, −0.067]; |error| +4.36 mm [+1.72, +7.69] (n = 79). Finished by itself and said beforehand that it "probably won't meet the 90% bar" (cross-validated 85 %, hidden 86.7 %). Caveat: it stopped with 27 minutes unused that it did not know it had |
| ecg | **No gap (control).** Agent and specialist both meet all 3 gate parts (MI operating point, calibration, subgroup gap) | **No gap (control)**, same |
| icu | **No gap (control).** Both meet all 4 parts (event-1 against SAPS-I, calibration, net benefit, worst subgroup) | **No gap (control)**, same |

**Across the two models:**
- Both met every cohort gate.
- Opus came closer on hc18 (92.8 % against 86.7 %), but its attempt is not interpretable under the timeout rule.
- Neither produced an interpretable registration or segmentation result.
- One interpretable per-case gap remains: Sonnet on hc18, with n = 1 attempt.

## Per-attempt trace findings

Every trace was read in full (condensed transcripts in `exp/suite-hosted-agents1/<run>/digest/`).

**Checks common to all ten attempts.**
- **No web tools.** WebFetch and WebSearch were not offered, `server_tool_use` was 0/0 wherever reported,
  and there were no web tool calls.
- **No other hosts.** No command tried to reach another host: no curl, wget, pip install, git, HTTP URL or
  socket use. One false positive was ruled out: `torch.load`'s warning text contains a GitHub URL.
- **No recognition of the public dataset or use of memorised values.** The one suspicious line, Opus ECG's
  "the reference result is 0.928", is quoted from the task's own instruction and README ("a published
  deep-learning result on this data").
- **Every agent used the benchmark venv and handled units and frames.** Sonnet's bare `python` resolved to the
  venv, which is the first in-agent confirmation of the PATH fix from `hosted-oracle1.md`.
- **No agent mentioned a session time limit.** The only time limits they discussed were the per-case or
  cohort pipeline limits.
- **Harness behaviour, not our bug:** several agents lost turns to Claude Code blocking `sleep N; cmd` and to
  the 10-minute background-task limit.

The table covers each attempt's approach, how it used the development cases, how its run ended, and whether
it left a runnable pipeline early. The paragraphs after it add short quotes as evidence.

| Attempt | Approach and use of the development cases | Units, frames, spacing | Ran its own pipeline? | Time awareness and ending | Our bug? |
|---|---|---|---|---|---|
| reg Opus | Rigid registration. It went from mutual information to LC2 to MIND-SSC, then tried smoothing the ultrasound first. It scored candidate similarity measures by starting the optimizer at the reference landmark transform of the 4 development cases. That is legitimate use of development references, but it is diagnosis, not a pipeline | RAS↔LPS written out ("tx maps fixed(US, LPS)->moving(MRI, LPS)… (RAS)"); header zooms and axcodes inspected | **No.** It never created `/workspace/output/pipeline/` | No session-limit mention; the only limit it named was 2 minutes per case. Killed 90 s into a parameter sweep. Best development result was 1.65 mm mean starting from the reference transform, which is not a deployable pipeline | Yes: the session limit was not stated |
| reg Sonnet | Its first pipeline, a few minutes in, was a SimpleITK Mattes mutual-information rigid registration. Its own development check: "c0c472 init 2.83 final 8.89 … c6eae9 init 4.57 final 10.01". It then explored LC2 and NGF metrics, scored from the reference transform, in `/workspace`, and never replaced or removed the bad pipeline | `def lps(p): return [-p[0],-p[1],p[2]]`; correct use of the inverse transform | Yes, the first draft only; its own check showed it made alignment worse | No session-limit mention. Killed while waiting on a background sweep. The graded pipeline was the known-bad draft | Yes: the session limit was not stated |
| spleen Opus | 2.5D U-Net (5 neighbouring slices, resampled to 1×1×2.5 mm), cross-validated with 2 development cases held out. Held-out Dice reached 0.960 and 0.932 at 2000 iterations. `infer.py` averages every model in `pipeline/models/`, of which there were none | Volume = voxel count × det(affine) ÷ 1000 mL; resampling from header zooms | Not end to end on a case with a model | "Training runs at about 1.7 s per iteration, so the 4000-iteration run will take about 2 hours", in a 60-minute session it was never told about. Last message: "Waiting for the cross-validation run to finish its remaining 2000 iterations, about 55 minutes." Idle until killed | Yes. Also a pipeline design that outputs an empty mask when there is no model, rather than failing |
| spleen Sonnet | 3D CNN. It trained a model with 2 development cases held out (raw Dice 0.83; 0.898 with post-processing on dev_3211), then started 40-epoch full training writing `full.pt` into the pipeline. It spent its last turns waiting for that file | HU windowing, header zooms, mL from voxel volume | No (no weights existed yet) | "Training (30 min) is running in the background"; no session-limit mention. Killed before `full.pt` was written | Yes: the session limit was not stated |
| hc18 Opus | Pixel classifiers with gradient-boosted trees on multi-scale features, then a second stage with context features and an ellipse fit. Cross-validated on the 152 development images: "Stage 2 brings cross-validated accuracy to **95.4%** within tolerance (MAE 3.1 mm)". It then built a scale-normalised second pass (96.1 % cross-validated) | `perim(...) * SCALE * px`, using pixel size from `case.json` | **Yes, early.** It wrote run.sh at about 13 minutes (20:05) and timed it at 2.8 s per image | No session-limit mention. Killed while evaluating candidate rules. The grader scored the 20:05 stage-2 pipeline with a later `ellfit.py` edit; `canon.py` was never wired in | Yes: the session limit was not stated. Its result (92.8 %) is above the bar anyway |
| hc18 Sonnet | Two-stage gradient-boosted pixel classifiers for head interior and skull outline, a learned ellipse scorer, random search and refinement, with 4-fold cross-validation on the development images | It first scaled the perimeter by pixel size, then resampled every image to 0.6 mm per pixel | Yes: 2 s per image on 2 development cases | Ended by itself at 1088 s, saying "it probably won't meet the 90% bar". Its cross-validated 85 % matched the hidden 86.7 % | No. The unstated limit could only have mattered through an early stop |
| ecg Opus | Ensemble of four 1D-ResNets. Each was trained with one source fold held out and Platt-calibrated per class on that fold; it checked all three gate parts on the pooled held-out folds (4,028 ECGs) | "values in microvolts (divide by 1000 for mV)" applied (`/1000.0`) | Yes. It ran with `env -i`, an empty HOME and a minimal PATH: 3.0 s for 1,000 ECGs | Knew its limit from the instruction. Finished at 989 s of 1800 s | No |
| ecg Sonnet | Two small 1D CNNs trained on folds 1 to 7; Platt calibration fitted on held-out fold 8 (1,023 ECGs), with the recalibration scored by 5-fold cross-validation | µV ÷ 1000 and per-lead median removal | Yes: 4.1 s for 1,000 ECGs | Finished at 1111 s. "I haven't checked the subgroup gate." The hidden set passed it anyway | No |
| icu Opus | Gradient boosting on 381 features. Cross-validation showed calibration failing (slope 0.79), so it added Platt recalibration on out-of-fold scores, checked with nested cross-validation, plus a final 5 % slope shrink that it said was not re-validated | Range cleaning; −1 treated as missing | Yes, as the unprivileged user `nobody`: 19 s for 4,000 stays. It also tested empty, garbled and descriptor-only files | Finished at 535 s | No |
| icu Sonnet | Gradient boosting with summary features per variable and logistic recalibration on 5-fold out-of-fold predictions; every gate part cross-validated except calibration-in-the-large after recalibration, which it said it did not re-measure | Range cleaning; −1 treated as missing | Yes: 9 s for 4,000 stays | Finished at 60 s | No |

**Instruction, image and grader checks.**
- **No image or grader bug was found.**
  - The grader handled every failure mode it met (missing run.sh, exit 1, a point outside the field of view,
    empty masks) with the specified zeros and reasons.
  - The image's venv was reachable by absolute path and by bare `python`/`python3`.
- **Our bugs, named:**
  1. **No session time limit in four instructions.** The reg, spleen, hc18 and icu instructions do not state the
     agent's session limit, and no instruction says that the pipeline left at the kill is graded. This decided
     5 of the 10 attempts.
  2. **The HC18 instruction has its title twice.** Cosmetic.
  3. **Hosted verifier output is incomplete.** Raw `metrics.json` is not carried by the platform, and the hc18
     summary line is cut, so units such as spleen volume error must be inverted from quality or are lost.

**Not our bugs, but worth knowing:**
- Claude Code's own harness blocked `sleep N; cmd` and moved long foreground commands to the background after
  10 minutes. Several agents lost turns to this.
- When the model ends a turn while background jobs are pending, the CLI keeps running and idles until the job
  finishes or the session is killed. Opus spleen idled from its last message until the kill.

## Infrastructure incidents

None.
- All 10 task attempts reached the verifier.
- Image builds were cached from the oracle run (0.8 to 17 s).
- Verifier mode was `separate` with exit 0 throughout.
- No `failure_category` or `error_message` was set.

The platform reported `agent_caused_exit_reason: TIMEOUT` for five attempts. Each was the platform's own
session-limit kill ("has reached the designated generation allowance … The process has been terminated and
evaluation will proceed"), not a sandbox loss.

## Costs

| Attempt | Cost source | Input + cache (exact) | Output | Total |
|---|---|---|---|---|
| reg Opus | killed, estimated | $1.051 | ≈$0.56 (est.) | ≈$1.61 |
| spleen Opus | result event | — | — | $0.767 |
| hc18 Opus | killed, estimated | $1.052 | ≈$0.65 (est.) | ≈$1.70 |
| ecg Opus | result event | — | 8,107 tokens | $0.481 |
| icu Opus | result event | — | 16,308 tokens | $0.637 |
| **Opus total** | | | | **≈$5.20** ($3.99 exact + $1.21 estimated) |
| reg Sonnet | killed, estimated | $0.344 | ≈$0.19 (est.) | ≈$0.54 |
| spleen Sonnet | killed, estimated | $0.517 | ≈$0.18 (est.) | ≈$0.70 |
| hc18 Sonnet | result events (2) | — | 29,911 tokens | $0.545 |
| ecg Sonnet | result event | — | 6,363 tokens | $0.177 |
| icu Sonnet | result event | — | 4,501 tokens | $0.088 |
| **Sonnet total** | | | | **≈$2.05** ($1.67 exact + $0.38 estimated) |
| **All 10 attempts** | | | | **≈$7.25** ($5.66 exact + $1.59 estimated) |

No attempt approached the $8 per-task cap.

**How the API cost was computed.**
- **Completed attempts:** `total_cost_usd` from the last result event of each trace. This is Claude Code's
  list-price calculation and is cumulative across result events. The Sonnet HC18 trace has two result events,
  because a background task woke the session; its turns are summed.
- **Killed attempts:** these have no result event. Input and cache tokens are exact from the per-message usage
  in the trace. Output tokens are not recorded there, because stream events carry the usage from the start of
  each response. Output is therefore estimated from the same model's completed attempts (output / (cache read +
  write) = 0.0208 for Opus, 0.0233 for Sonnet).
- **Prices:** list prices from the claude-api reference (cached 2026-11-03). Opus 5.5 $4 / $20, cache read
  $0.20, cache write $5. Sonnet 5.5 $2 / $10, $0.10, $2.50. Checked: these prices reproduce Opus ECG's
  `total_cost_usd` to 4 decimals.
- **Modal cost is not shown by Valkyrie.** No cost field exists in `run fetch`, `run results`, `run task` or
  `run status`. Sandbox time is in the JSON (`agent_run_seconds`, `evaluation_seconds`); the Modal dashboard is
  needed for dollars.

## Limitations

- **One attempt per task and model.** These results are not variance estimates. A second attempt could differ
  in either direction.
- **Small hidden sets.**
  - reg (6 cases, of which 4 the specialist passes) and spleen (6 cases, 3 passed by the specialist) give
    bootstrap intervals that are crude, and degenerate when every pair differs.
  - Only hc18 (83 cases) supports a per-case interval with real width.
  - Cohort families are one draw of 1,000 (ecg) and 4,000 (icu) records.
- **Public data, so a contamination risk.** RESECT, MSD Task09, HC18, PTB-XL and PhysioNet 2012 are all
  public and well known. No trace shows recognition or memorised values. That is not proof of absence, because
  thinking is not visible in these traces (display omitted).
- **No turn cap.** Claude Code 2.1.325 has no `--max-turns`. Spending was bounded by the $8 cap (never reached)
  and the session limit.
- **Effort was not set.** The CLI default applied, which may be below the "high" the coordinator asked for.
  The agent contract has no effort parameter, and the brief allowed only the cap and pin edits.
- **Our instruction bug confounds 5 of the 10 attempts**, and with them the reg and spleen comparisons
  entirely. The hosted instructions should state the session limit and the grading-at-kill rule before any
  rerun. Any rerun would be a new prespecified experiment, not a retry of this one.
- **Raw values come from verifier stdout, not `metrics.json`.** They are exact inversions, but spleen volume
  error, NSD and HD95, and the cohort calibration numbers are not available from the hosted record.
