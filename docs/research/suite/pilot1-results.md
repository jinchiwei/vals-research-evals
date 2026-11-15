# Pilot 1: first frontier-agent runs on measure_hc18 and reg_resect (local)

Operator: a Claude Code subagent running **Claude Opus 5.5 (`claude-opus-5-5`)**, 2026-11-14, on teal.
Runner: `scripts/run_suite_pilot.py` (see `local-pilots.md`). This is a **local bubblewrap pilot, not a
hosted Valkyrie run**. Raw outputs: `exp/suite-pilots/20261114-pilot1/` (git-ignored). Machine-readable
numbers: `pilot1-results.json` next to this file.

## Prespecified design (fixed before any model call)

| Item | Value |
|---|---|
| Tasks (build tier) | `measure-hc18-0001` (fetal HC in mm, 83 hidden images); `reg-resect-build-0001` (MRI to intra-operative US, 6 hidden cases) |
| Task folders | `/home/jkwei/data/vals-suite/measure_hc18/dist/measure-hc18-0001`; `/home/jkwei/data/vals-suite/reg_resect/dist/reg-resect-build-0001` |
| Agents | Claude Code 2.1.325 (`--safe-mode`, OAuth login, egress proxy to `api.anthropic.com` only) with `claude-opus-5-5` and `claude-sonnet-5-5`, effort high |
| Attempts | one per task and model, four runs in total, nothing rerun |
| Limits | agent time 2700 s, `--max-budget-usd 5` |
| Concurrency | at most two agents at once: slot 1 ran hc18/Opus then reg/Opus, slot 2 ran reg/Sonnet then hc18/Sonnet |
| Run name | `20261114-pilot1` |

**The measure_hc18 export.** The task its worker exported was in the coordinator's session scratchpad
(`.../scratchpad/dist-hc18/measure-hc18-0001`, written 18:04, after the last edit to the family code). I
copied it unchanged to the documented location. `diff -r` shows no difference. It was not re-exported.
`tests/specialist/` holds 83 case folders and `runtime.json`.

**Gap rule** (fixed at 18:25, before any agent result was read, in the scratchpad `gap.py`):
- **Comparison set.** S is the set of hidden cases the specialist passes.
- **Per case on S.** An invalid or late agent case counts as a fail with quality 0.
- **Statistics.** Paired bootstrap of agent minus specialist with `suite.core.metrics.paired_bootstrap_difference`: np.mean, 2000 resamples, seed 20261114, 95 % percentile interval. Three quantities: (a) the pass indicator, (b) quality, (c) raw error in mm on cases where the agent output was valid.
- **Verdicts.**
  - *Gap shown*: the agent fails at least one case in S and the interval for (a) lies entirely below 0.
  - *No gap*: the agent passes every case in S.
  - *Not interpretable*: anything else, or a grading infrastructure error.

## Pre-run checks

**1. Grading reproduces the documented numbers.** The shipped `solution/pipeline` was regraded through the
runner's own grading path: `suite.pilot.pilot.grade`, which uses the shim, the no-network pipeline sandbox
and the task's `tests/grade.py`. There was no model call. Outputs are in `exp/.../precheck/<task>/solution/`.

| Task | Pipeline | reward | quality | raw | Documented | Match |
|---|---|---|---|---|---|---|
| measure_hc18 | `solution/` (classical) | 0.759 | 0.437 | MAE 13.74 mm | 0.76, 0.437, 13.74 mm | yes |
| measure_hc18 | stored specialist (U-Net) | 1.00 within | 0.717 | MAE 2.05 mm | 1.00, 0.717, 2.05 mm | yes |
| reg_resect | `solution/` (= specialist, MIND rigid) | 0.667 | 0.331 | mTRE 3.03 mm (1.98/1.38/8.38/1.83/3.26/1.37) | 0.667, 0.331, 3.03 ± 2.71 mm | yes |

For reg_resect, the specialist result stored in `tests/specialist/` gives the same per-case TREs.

**2. Agent workspace.** I built the sandbox with the runner's own `sandbox.agent_command` and ran a listing
shell in place of the CLI. Listings are in `exp/.../precheck/<task>/workspace_probe.json`.

- **measure_hc18.** `/workspace` contains:
  - `instruction.md`;
  - an empty `output/`;
  - `data/README.md` and `data/LICENSE-DATA.md`;
  - `data/dev/references.csv`;
  - 152 `data/dev/case_*/` folders, each with `{image.png, case.json, annotation.png}` (459 files in all).
- **reg_resect.** `/workspace` contains:
  - `instruction.md`;
  - an empty `output/`;
  - `data/README.md` and `data/LICENSE-DATA.md`;
  - 4 `data/dev/<case>/` folders, each with `input/{mri_t1,mri_flair,us}.nii.gz`, `input/landmarks_mri.csv` and `reference/landmarks_us.csv` (22 files in all).
- **Both.** `/home/agent` holds only `.claude/` and `.claude.json`. `/opt` holds `agent/claude` and
  `benchmark-venv`. `python3` resolves to `/opt/benchmark-venv`. `/workspace/data` is read-only.
- **Hidden material is absent.** `/tests`, `/solution`, the task's host `tests/` and `solution/`, `/home/jkwei`,
  `/home/jkwei/data`, `/mnt/c` and the repository are all absent.
- **No leaks found.** No hidden case ID appears on the agent side. No file is byte-identical between `tests/`
  or `solution/` and the agent data. The dev `reference/` files and `references.csv` are allowed dev labels.
- **README.** It states the task, output format, per-case time limit and scoring. **It does not state the
  agent's own session limit (2700 s)**, or that `/workspace/output` is graded as it stands when the session
  is killed. I did not catch this before launch. See "Our bugs".

The runtime envs `vals-suite-rt-measure_hc18` and `vals-suite-rt-reg_resect` were created by the runner's
own `runtime.ensure_env` from each task's Dockerfile pins. The login token had 474 minutes left at launch.

## Results

Run on 2026-11-14 from 18:17 to 19:50 EST. `summarize` output: `exp/.../summary.md`.

| Task | Model (API) | reward | ran | valid | within_time | clin. acc. | quality | vs_spec | Headline raw (mm) | Specialist | Agent wall | Turns | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| measure_hc18 | claude-opus-5-5 | **0.928** | 1 | 1 | 1 | 0.928 | 0.626 | 0.872 | MAE 10.08 (median 2.05) | 1.00; MAE 2.05; q 0.717 | 1813 s, completed | 41 | $1.70 |
| measure_hc18 | claude-sonnet-5-5 | **0.819** | 1 | 1 | 1 | 0.819 | 0.424 | 0.591 | MAE 8.57 (median 4.08) | same | 2701 s, **timeout** | 59* | not reported |
| reg_resect | claude-opus-5-5 | **0** | 0 | 0 | 0 | 0 | 0 | 0 | none (no output) | 0.667; mTRE 3.03; q 0.331 | 2701 s, **timeout** | 39* | not reported |
| reg_resect | claude-sonnet-5-5 | **0** | 0 | 0 | 0 | 0 | 0 | 0 | none (no pipeline) | same | 2702 s, **timeout** | 44* | not reported |

\* Counted from the trace's API messages. A run killed at the time limit gets no CLI `result` event, so
`run.json` has no turns and no cost for it. Each such run was capped at 5 USD. **Reported cost totals
1.70 USD; the upper bound is 16.70 USD.**

Other facts common to the runs:
- The API reported only the requested model in every run.
- Egress went to `api.anthropic.com:443` only (1 to 3 connections), with nothing denied.
- No credentials were found in the kept files (0 redactions).
- There was no grading infrastructure error.
- Hidden-case pipeline time for measure_hc18 was a median 2.6 s (max 3.2 s) for Opus and 1.6 s (max 3.5 s)
  for Sonnet, against a 10 s limit.

**Family bar.** measure_hc18 asks for at least 90 % of images within tolerance. Opus clears it (92.8 %).
Sonnet does not (81.9 %). The shipped classical solution gets 75.9 % and the specialist 100 %.

measure_hc18, within tolerance by HC tertile (small / mid / large, n = 29 / 27 / 27):

| | Small | Mid | Large |
|---|---|---|---|
| Opus | 27 | 27 | 23 |
| Sonnet | 19 | 26 | 23 |
| Specialist | 29 | 27 | 27 |

## Trace analysis

### measure_hc18 · claude-opus-5-5 (reward 0.928, completed in 30 min)

**Approach.**
- **Units first.** Before building anything, the agent checked units and spacing against the references:
  "The ellipse from annotation.png matches hc_mm within 0.02 mm, so it serves as ground truth" (Ramanujan
  perimeter × `pixel_size_mm`).
- **Model.** It built a scikit-learn gradient-boosting pixel classifier for the skull ring, then generated
  ellipse candidates by polar search. A learned ranker picks candidates, and a learned boundary refinement
  works in elliptic-polar strips.
- **Plausibility.** A filter rejects candidates on perimeter and extension beyond the image. The output is
  clamped to 45 to 380 mm, inside the 40 to 400 mm validity range.

**Validation.**
- Every stage used 4- or 5-fold cross-validation on the 152 dev cases. Its reported progression of the
  within-tolerance rate: "74 % → 70 % → 91.4 % → 94.1 % → 95.4 %".
- It labelled the in-sample 99.3 % "optimistic".
- The folds are random over case IDs. Dev images from the same examination (152 images, 121 prefixes) can
  fall on both sides of a fold, so the CV is slightly optimistic. The agent could not know this, because
  IDs are opaque. Hidden result: 92.8 %.

**Time.**
- It profiled the pipeline (about 3 to 4 s per image).
- One dev run took 116 s. Its reading: "look like transient machine stalls". That run fell in the
  host-memory-pressure window (see Incidents).
- In response it added a fallback write of 175 mm and "a watchdog that ... hard-exits at 8 s". It tested
  the watchdog with an injected hang ("fires at 8.06 s").
- It also tested the pipeline from a read-only copy with an empty `HOME`.
- It finished at 30 min with budget to spare, so time and budget were not binding.

**Where it went wrong.** Six of the 83 hidden images were gross mis-detections of the wrong structure,
not boundary error:
- four large heads: errors −233, −170, +65 and +60 mm;
- two small heads: +66 and +45 mm.

Its own summary named this failure mode: "locks onto the wrong structure". The median error (2.05 mm)
equals the specialist's mean.

**Sandbox or instructions at fault?** The stall it saw came from our shared host. It did not change the
graded result: the maximum hidden-case time was 3.2 s.

### measure_hc18 · claude-sonnet-5-5 (reward 0.819, killed at 45 min)

**Approach.**
- A learned edge map plus ellipse fit, with images resampled to 0.4 mm per pixel using `pixel_size_mm`, so
  spacing was handled.
- Then RANSAC ellipse candidates and a learned candidate scorer. Its oracle check: "the right ellipse is in
  the RANSAC candidate pool for about 91 % of dev images".

**Validation.** 5-fold KFold on dev. It wrote: "I've built a working pipeline in /workspace/output/pipeline/
that takes about 2 s per image and puts roughly 88 % of dev cases within 4.9 %". It ran `run.sh` end to end
on three dev cases with a fresh `HOME` and timed them (1.8 to 2.2 s). Hidden result: 81.9 %.

**What happened next.**
- The pipeline was shipped about 17 minutes in.
- The agent spent the remaining 28 minutes on an augmentation retrain that never finished. It also edited
  the shipped `feat.py` in place during this time. The change was backward compatible, and the graded
  pipeline ran valid.
- Time was lost to its own process management: "My pkill killed my own shell, so the job never launched;
  the real stall was pgrep -f matching its own command line".
- It never mentioned the session limit. The kill arrived while it was waiting on a job.

**Errors.** Fifteen hidden misses. The small-head tertile was worst (19/29): several were 5 to 10 mm
boundary errors on small heads, plus gross errors of 75 to 102 mm.

**Sandbox or instructions at fault?** Partly. The README never states the 45-minute session limit. Here it
cost nothing, because a working pipeline was already in place.

### reg_resect · claude-opus-5-5 (reward 0, killed at 45 min)

**Approach.**
- It used a dev-only "best rigid fit to the landmarks" as an upper bound: "about 1.0–1.4 mm". It says this
  fit was "for diagnosis only" and did not use it in the pipeline.
- It built an LC2 rigid registration in numpy/scipy, working in nibabel affines, so RAS throughout. Voxel
  sizes came from the affines.
- It compared LC2 with MIND-SSC. One diagnosis: "LC2 reaches the same optimum from both starting points,
  so the optimizer is fine and the bias comes from the metric itself".

**Dev results.** "Best so far: 0.7 mm resolution, 7-voxel patches ... Mean TRE is 1.70, but c6eae9 is
still at 2.21 mm". This was tuned in-sample on 4 cases; the specialist's dev mean is 1.85.

**Where it went wrong.**
- It spent the session sweeping settings. It wrote `run.sh` for the first time about 2.5 minutes before the
  kill and never executed it.
- That `run.sh` ends `exec python3 -I "$HERE/main.py"`. `-I` removes the script directory from `sys.path`,
  so every hidden case failed in 0.2 s with `ModuleNotFoundError: No module named 'reg'`.
- `main.py` still held the early configuration from about minute 5, not the tuned one.
- No statement about the session limit appears in the trace.

**Sandbox or instructions at fault?** The `-I` crash is the agent's own bug. The unstated session limit is
ours, and it plausibly changed behaviour: the agent kept sweeping with no visible sense of a deadline.

### reg_resect · claude-sonnet-5-5 (reward 0, killed at 45 min; empty pipeline folder)

**Approach.**
- It started with SimpleITK Mattes MI, handling the frame explicitly ("T maps fixed(US) points -> moving(MRI)
  points (LPS). We need MRI->US: inverse", negating x and y).
- Then LC2, then MIND-SSC with an exhaustive integer translation search: "MIND-SSC with an exhaustive integer
  search beats MI and LC2 on dev, bringing landmark error down to about 1.3–3.0 mm".
- Then a regional deformable step, swept over parameters.

**Where it went wrong.**
- It created `/workspace/output/pipeline/` in its first minutes and never put a file in it.
- It ran 3 or 4 parallel experiment processes of 2 to 11 GB each. The host OOM killer killed three python3
  processes during its run (see Incidents). The agent then lowered resolution and stride.
- It killed its own shell twice: "Again `pkill -f` killed my own shell".
- It used sleep-based waits that the CLI blocked.
- No mention of the session limit.

**Sandbox or instructions at fault?** Partly, again:
- The README omits the session limit.
- The local host had less RAM than the task declares (15 GB shared versus 16 GB). However, the largest
  killed process alone was 11.2 GB beside two others of 2.8 and 4.2 GB, so a 16 GB container would likely
  also have killed it.
- The run did not die. It ran to the time limit, so it is a result and was not relaunched.

### Contamination

No trace shows recognition of HC18 or RESECT beyond the dataset names in the README. Opus's "look like
low-grade gliomas" follows from FLAIR images and the README's surgery context. No run used outside
reference values: every prediction came from methods fitted on the dev cases, and the hidden-case errors
look like those of a real method (gross mis-detections), not lookups. The network was restricted to the
model API.

## Gap verdicts (DESIGN.md per-case rule)

Paired differences are agent minus specialist, with bootstrap 95 % CIs over the cases in S.

| Run | S | Agent passes in S | Pass-rate difference | Quality difference | Raw error difference (mm) | Verdict |
|---|---|---|---|---|---|---|
| hc18 · Opus | 83 | 77 | −0.072 (−0.133 to −0.024) | −0.092 (−0.148 to −0.030) | +8.0 (+2.0 to +15.5) | **gap shown** |
| hc18 · Sonnet | 83 | 68 | −0.181 (−0.265 to −0.108) | −0.293 (−0.370 to −0.210) | +6.5 (+3.2 to +10.4) | **gap shown** |
| reg · Opus | 4 | 0 | −1.0 (degenerate) | −0.444 (−0.502 to −0.386) | none (no output) | **gap shown**: a delivery failure, not a measured accuracy gap |
| reg · Sonnet | 4 | 0 | −1.0 (degenerate) | −0.444 (−0.502 to −0.386) | none (no pipeline) | **gap shown**: a delivery failure |

Notes on the verdicts:
- **hc18 · Opus.** The gap is real, but the agent clears the family's own clinical bar (92.8 % ≥ 90 %).
  "Gap versus specialist" and "fails clinically" are different claims here.
- **reg_resect.** The verdict follows from the prespecified rule, but it measures only that no runnable
  pipeline existed when the session was killed. It says nothing about how accurate the agents' methods
  were. Their dev numbers were comparable to the specialist's: Opus 1.70 mm tuned in-sample, Sonnet 1.3 to
  3.0 mm, specialist 1.85 mm. Because the README never stated the session limit, these two results should
  not be quoted as evidence of a registration capability gap.

measure_hc18: every hidden case where the agent or the specialist failed. Absolute error is in mm. The
other 66 cases pass for all three systems. The full 83-case table is in the JSON. Hidden reference values
are not reproduced.

| Case | Tertile | Specialist error | Opus error | Opus pass | Sonnet error | Sonnet pass |
|---|---|---|---|---|---|---|
| case_1fb964 | large | 5.6 | 232.8 | no | 3.5 | yes |
| case_305e43 | large | 5.2 | 14.8 | yes | 20.8 | no |
| case_3dbea3 | mid | 7.4 | 6.7 | yes | 9.5 | no |
| case_53c8ee | small | 3.6 | 0.2 | yes | 102.3 | no |
| case_56d788 | small | 1.2 | 2.5 | yes | 6.7 | no |
| case_56f59c | small | 1.3 | 0.3 | yes | 5.9 | no |
| case_5ff515 | small | 2.5 | 0.8 | yes | 10.2 | no |
| case_78c9fe | small | 0.5 | 4.2 | yes | 10.4 | no |
| case_809204 | large | 3.9 | 65.0 | no | 19.1 | no |
| case_8342d7 | large | 2.1 | 3.6 | yes | 31.2 | no |
| case_89f045 | small | 1.7 | 65.6 | no | 88.7 | no |
| case_9536d9 | small | 1.5 | 45.4 | no | 74.4 | no |
| case_c5de36 | small | 2.3 | 1.6 | yes | 5.1 | no |
| case_ca7ae6 | small | 1.5 | 1.0 | yes | 5.9 | no |
| case_ed3d08 | large | 5.8 | 169.7 | no | 51.3 | no |
| case_f3690e | small | 0.1 | 0.9 | yes | 9.6 | no |
| case_fb3c42 | large | 5.8 | 59.9 | no | 4.3 | yes |

The specialist passes all 17 of these.
- **Opus** is more accurate than the specialist on 33 of 83 images. The median paired difference is
  +0.54 mm.
- **Sonnet** is more accurate on 17 of 83, with a median paired difference of +2.34 mm.
- **Both agents miss** four images: case_809204, case_89f045, case_9536d9 and case_ed3d08.

reg_resect, per case in mm:

| Case | Initial | Specialist | Specialist pass | Opus | Sonnet |
|---|---|---|---|---|---|
| c18b03 | 6.39 | 1.98 | yes | no output | no output |
| c57eed | 3.39 | 1.38 | yes | no output | no output |
| c65c1b | 5.68 | 8.38 | no | no output | no output |
| cb06b4 | 4.55 | 1.83 | yes | no output | no output |
| cdd96a | 10.06 | 3.26 | no | no output | no output |
| ce4785 | 7.01 | 1.37 | yes | no output | no output |

## Infrastructure incidents

No run died for an infrastructure reason, and nothing was relaunched.
- **Host OOM kills.** The kernel OOM killer (dmesg) killed three python3 processes at 18:44:22, 18:44:46 and
  18:47:15 EST, with anon RSS of 4.6, 5.3 and 11.2 GB. By size and timing they were the reg_resect Sonnet
  agent's own parallel experiment workers. They were the only python3 processes over 2 GB on the host, and
  they vanished at the kills. The agent's background task was recorded as killed, and the agent carried on.
- **Stall in the other run.** In the same window, the measure_hc18 Opus agent saw a 116 s development-case
  run that took 2.7 s when rerun.
- **Root cause.** The local sandbox has no CPU or RAM caps. The host's 16 cores and 15 GB were shared by
  both agents and other workers' sessions. The tasks declare 4 CPUs and 8 GB (hc18) or 16 GB (reg).

## Our bugs and ambiguities (results kept as measured)

1. **The session limit is not in the instructions.** Neither `instruction.md` nor the data README tells the
   agent it has 2700 s, or that `/workspace/output` is graded as it stands when the session is killed.
   - Three of four runs hit the limit, and both reg_resect zeros are delivery failures at the deadline.
   - This is an instruction gap in `suite/core/export.py`'s generated text, not a model failure.
   - It should be fixed before pilot 2. I did not edit it.
2. **`summarize` labels quality as the raw metric.** The `agent_headline_raw` column is mean quality (0 to
   1), not a value in mm, yet the note for reg_resect says "headline = mean_tre_mm".
3. **Timed-out runs lose cost and turns.** A run killed at the limit has no cost or turn count in
   `run.json`, because the CLI never emits its result event.
4. **Diagnostics folder named two ways.** For reg_resect, the data README says `dev_predictions/` and
   `instruction.md` says `visible_predictions/`. Neither is scored.
5. **Contradictory validity wording.** The measure_hc18 README says an invalid image "counts as a miss", then
   says the headline is 0 unless every image is valid. The grader does the latter.
6. **Session folder moved by hand.** The measure_hc18 export lived only in a session scratchpad. I moved it
   to the documented data folder unchanged.

## Limits

- **One attempt** per task and model. There is no estimate of run-to-run variance, and Opus's 0.928 against
  Sonnet's 0.819 is a single draw each.
- **Small hidden sets.**
  - measure_hc18 has 83 images.
  - reg_resect has 6 cases, 4 of them passed by the specialist, so its intervals are degenerate.
- **Local bubblewrap sandbox, not the hosted one.** There are no CPU or RAM caps, the host is shared, and
  the toolset in `/usr` is larger than in the hosted image. The pipeline runs under the invoking uid.
- **Public data.** HC18 and RESECT are public datasets, so contamination is possible. No sign of it was
  seen in the traces.
- **Stored specialist.** The measure_hc18 specialist outputs are stored results, not rerun. Grading against
  them reproduced the documented values exactly.
