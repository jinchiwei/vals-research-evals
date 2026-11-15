# Hosted agent runs 2 (headline): Claude Code (no web) on the five scored tasks, instructions v3

Written 2026-11-15 by a Claude Code worker acting as experiment operator (model: **Claude Opus 5.5,
`claude-opus-5-5`**). Authorised by the project lead through the coordinator. Two runs fixed before launch
(one attempt per task and model), nothing rerun, nothing relaunched. Raw evidence: `exp/suite-hosted-agents2/`
(git-ignored by `.gitignore` line 33, `exp/`). Machine-readable numbers, run ids and per-case values:
[`hosted-agents2.json`](hosted-agents2.json). Batch 1 (`hosted-agents1.*`, task version 1, session limit
not stated) is a separate set and is not pooled with this one.

## Summary

- **Ten attempts, ten graded results, no infrastructure failure.** No relaunch was needed. No attempt hit
  its session limit or the $8 budget cap. Every attempt ended on its own: 9 of 10 used less than half
  their session.
- **Controls hold.** Both models pass every gate part on ECG and ICU risk, as the specialist does
  (no gap).
- **Gaps shown on fetal head circumference for both models.** The specialist is within tolerance on
  83/83 images; Opus 35/83, Sonnet 64/83.
- **Gap shown on registration for Sonnet only.** It shipped a pipeline that copies the landmarks
  unchanged, after 3 minutes, by its own choice.
- **Opus matches the specialist on registration and spleen.** Registration: 4/6 under 2 mm with mean
  TRE 1.61 mm (specialist 4/6, 3.03 mm). Spleen: the same 3/6 cases pass, mean Dice 0.940 vs 0.939.
- **Total API cost: $3.77** (Opus $2.75, Sonnet $1.02). Modal cost is not shown by Valkyrie.

## Prespecified design (fixed 02:06Z, before launch; `exp/suite-hosted-agents2/prespec.txt`)

| Item | Value |
|---|---|
| Dataset | `suite/clinical-v1@2` (tag `instr2`, digest `f7d7cd08f525`): reg-resect-build-0001, seg-spleen-build-0001, measure-hc18-0001, ecg-ptbxl-superdiag-0001, risk-icu-mortality-0001. Oracle on this version: run `15fc4349-…` reproduced every expected reward. |
| Agent | `claude_code_noweb-v1.0.0` as installed by the batch-1 worker. Downloaded at 02:05Z: `contract.yaml`, `setup.sh`, `collect_outputs.py` and `README.md` are byte-identical to `agents/claude_code_noweb/`. It passes `--disallowedTools "WebFetch WebSearch"` and `--max-budget-usd 8` per task, and `setup.sh` pins Claude Code **2.1.325** (confirmed in every trace). |
| Models | `anthropic/claude-opus-5-5`, `anthropic/claude-sonnet-5-5` (only these appear in the API responses) |
| Effort | **Not "high".** The contract's only parameter is `model`, `run_cmd` passes only `{model}` and the bundle passes no `--effort`, so the agent cannot accept an effort setting. The Claude Code 2.1.325 default applied; the traces do not record which level that is. |
| Attempts | one per task and model, 10 in 2 runs, launched together, concurrency 3 each |
| Timeouts | the tasks' own (agent 1800–3600 s, now stated in the instruction) |
| Relaunch rule | once, single task, only for a clear infrastructure failure (not needed) |
| Gap rule | DESIGN.md, operationalised before launch: see "Gap verdicts" |

Commands (from the repo root; secret named, never printed):

```
.venv-valkyrie/bin/valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@instr2 \
  --provider modal --model anthropic/claude-opus-5-5 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 3 -l hosted-agents2-opus
.venv-valkyrie/bin/valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@instr2 \
  --provider modal --model anthropic/claude-sonnet-5-5 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 3 -l hosted-agents2-sonnet
```

| Run | Run id | Started (UTC) | Finished | Status | final_score | Run errors |
|---|---|---|---|---|---|---|
| Opus | `1f2e6208-f148-4aaa-b72f-5225bed3b745` | 02:05:21 | 02:56:29 | FINISHED 5/5 | 71.77 | none recorded |
| Sonnet | `5110a198-2582-414a-a9fd-81cc15103cdd` | 02:05:24 | 02:34:39 | FINISHED 5/5 | 58.76 | none recorded |

### Collection

Every task was fetched with `run task --format json`, `run logs --task-id … --format jsonl` and
`run outputs --task-ids`. The run-level records come from `run fetch`, `run results`, `run errors`,
`run tasks` and `run artifacts`. All of it is in `exp/suite-hosted-agents2/{opus,sonnet}/`, and a scan for
`sk-ant` found nothing.

**Raw values come from a local regrade**, because Valkyrie does not carry the grader's `metrics.json`.
- **How.** Each carried `/workspace/output/pipeline` was regraded locally with the task's own
  `tests/grade.py` from `dist/suite-tasks-v3/`. The pilot runner's grading path was used: the pipeline
  ran in the no-network bubblewrap sandbox, with the runtime env bound at `/opt/benchmark-venv`.
- **Validation.** Regrading the hc18 oracle solution this way gave 0.759, as expected.
- **Agreement with the hosted grades.**
  - All seven reward keys match the hosted grades exactly in 9 of 10 attempts.
  - The exception is Opus reg_resect. `reward`, `clinically_acceptable` and every per-case pass match,
    but `quality` differs by 0.0002, because c57eed's TRE was 1.357 mm hosted and 1.361 mm locally. The
    agent's deformable step is not bit-for-bit deterministic under different CPU load.
- **Where the hosted grade decides.** Pass/fail and quality per case come from the hosted verifier lines
  (all present, including all 83 hc18 lines; the hosted summary line for hc18 was cut by the platform).
  Cohort raw metrics (AUROC, ECE and so on) come from the regrade.
- **Regrade environments.** Exact image pins for reg, hc18 and ICU. Approximate for ECG (torch 2.5.1
  without the `+cpu` build tag) and spleen (pandas 3.1.1 instead of 2.2.3; torch without `+cpu`).
- **Specialist values** are the stored specialist outputs graded by the same vendored grader. They
  reproduce the hosted `vs_specialist` denominators (for example, spleen 0.4095 / 0.9387 = 0.4362 for the
  oracle).

## Results

Rewards are hosted. Headline raw values are from the local regrade, in units. Specialist values are on the
same hidden cases. Wall is the agent process time (`metrics_total.json`). Cost is Claude Code's
`total_cost_usd` (list price).

| Task | Model | reward | ran / valid / in time | quality | vs_spec | Headline (agent) | Specialist | Turns | Wall | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| reg_resect (6 cases; < 2 mm) | Opus | **0.667** | 1/1/1 | 0.463 | 1.000 | 4/6 < 2 mm; mean TRE 1.61 mm (median 1.31) | 4/6; 3.03 mm (median 1.91) | 19 | 1089 s (of 2700) | $0.553 |
| | Sonnet | **0.000** | 1/1/1 | 0.070 | 0.213 | 0/6; mean TRE 6.18 mm = no correction | same | 7 | 186 s | $0.142 |
| seg_spleen (6 cases; Dice ≥ 0.94, abs. vol. err. ≤ 10 %) | Opus | **0.500** | 1/1/1 | 0.940 | 1.000 | 3/6; mean Dice 0.940; mean abs. vol. err. 4.1 %; HD95 4.2 mm | 3/6; 0.939; 4.3 %; 3.9 mm | 22 | 1869 s (of 3600) | $0.910 |
| | Sonnet | **0.167** | 1/1/1 | 0.621 | 0.661 | 1/6; mean Dice 0.621 (median 0.840); abs. vol. err. 34 %; HD95 34.9 mm | same | 20 | 978 s | $0.332 |
| measure_hc18 (83 images; within 4.9 %) | Opus | **0.422** | 1/1/1 | 0.293 | 0.409 | 35/83; MAE 16.2 mm (median 8.8) | 83/83; MAE 2.05 mm (median 1.51) | 19 | 1181 s (of 2700) | $0.567 |
| | Sonnet | **0.771** | 1/1/1 | 0.502 | 0.700 | 64/83; MAE 18.0 mm (median 3.3) | same | 30 | 645 s | $0.356 |
| ecg_ptbxl (cohort; 3 gate parts) | Opus | **1.000** | 1/1/1 | 0.953 | 0.970 | all 3 parts; macro AUROC 0.908; MI sens @90 % spec 0.717 (≥ 0.70); ECE 0.030 (≤ 0.05); subgroup gap 0.029 (≤ 0.05) | all 3; 0.921; 0.744; 0.022; 0.026 | 12 | 473 s (of 1800) | $0.382 |
| | Sonnet | **1.000** | 1/1/1 | 0.967 | 0.984 | all 3; 0.914; 0.760; 0.025; 0.023 | same | 10 | 588 s | $0.121 |
| risk_icu (cohort; 4 gate parts) | Opus | **1.000** | 1/1/1 | 0.747 | 1.000 | all 4; AUROC 0.874; event-1 0.538; cal. slope 1.04, CITL −0.08; NB@0.2 0.070; worst subgroup AUROC 0.833 | all 4; 0.873; 0.533; 1.04, −0.00; 0.070; 0.826 | 10 | 186 s (of 2700) | $0.334 |
| | Sonnet | **1.000** | 1/1/1 | 0.730 | 0.980 | all 4; 0.865; 0.519; 1.07, −0.02; 0.066; 0.822 | same | 3 | 98 s | $0.070 |

**Hosted pipeline time.** Every case was within its limit.

| Task | Opus | Sonnet | Limit |
|---|---|---|---|
| reg_resect | median 24.8 s, max 90.1 s | 0.1 s | 120 s per case |
| seg_spleen | median 10.6 s | 6.7 s | 300 s per case |
| measure_hc18 | median 1.6 s | 2.2 s | 10 s per case |
| ecg_ptbxl | 12.7 s | 5.6 s | 560 s for the cohort |
| risk_icu | 16.2 s | 34.4 s | 300 s for the cohort |

**Tokens** (`modelUsage`, both models): output 3.7k–18.5k per attempt, cache reads 61k–917k, thinking
tokens 253–5,445, and zero web search or web fetch requests. Per-attempt values are in the JSON.

### Per-case detail (per-case families)

reg_resect, mean TRE in mm (hosted values; the regrade agrees within 0.004 mm):

| Case | Uncorrected | Specialist | Opus | Sonnet |
|---|---|---|---|---|
| c18b03 | 6.39 | 1.98 ✓ | 1.26 ✓ | 6.39 |
| c57eed | 3.39 | 1.38 ✓ | 1.36 ✓ | 3.39 |
| c65c1b | 5.68 | 8.38 | 2.69 | 5.68 |
| cb06b4 | 4.55 | 1.83 ✓ | **2.01** (fail by 0.01 mm) | 4.55 |
| cdd96a | 10.06 | 3.26 | 1.23 ✓ | 10.06 |
| ce4785 | 7.01 | 1.37 ✓ | 1.12 ✓ | 7.01 |

seg_spleen, Dice / signed volume error:

| Case | Specialist | Opus | Sonnet |
|---|---|---|---|
| hid_1200 | 0.959 / −2.8 % ✓ | 0.965 / −1.4 % ✓ | 0.960 / −1.8 % ✓ |
| hid_1392 | 0.936 / +3.7 % | 0.910 / +5.0 % | 0.907 / +9.0 % |
| hid_2997 | 0.955 / −4.6 % ✓ | 0.951 / +1.5 % ✓ | **0.9395** / +4.0 % (Dice short by 0.0005) |
| hid_4506 | 0.962 / −1.0 % ✓ | 0.961 / −2.5 % ✓ | 0.773 / +50 % |
| hid_6971 | 0.892 / −8.6 % | 0.933 / +2.6 % | **0.000** / −50 % (wrong structure) |
| hid_8298 | 0.927 / +5.3 % | 0.921 / +11.8 % | 0.144 / −90 % |

measure_hc18, within tolerance by HC tertile (small / mid / large, n = 29 / 27 / 27):

| | Small | Mid | Large |
|---|---|---|---|
| Specialist | 29 | 27 | 27 |
| Opus | 11 | 19 | 5 |
| Sonnet | 17 | 26 | 21 |

- **Opus.** 9 errors above 40 mm (largest +127 mm), and a broad error spread (median 8.8 mm), so its
  failures are mostly boundary error rather than wrong-structure detections.
- **Sonnet.** A median error of 3.3 mm, but 5 gross under-estimates of 221–275 mm on large heads,
  where its output fell to near the 41 mm clamp. Per-case values for all 83 images are in the JSON;
  hidden reference values are not reproduced.

## Trace findings, per attempt

All ten traces were read in full: `exp/…/{model}/trace-<task>.txt` (readable dump) and `trace-<task>.json`
(summary).

**Common to all ten attempts:**
- **Tools and network.**
  - The `init` event offers no WebFetch or WebSearch, and `server_tool_use` shows 0 web search and
    0 web fetch requests.
  - No tool input contains curl, wget, pip, git, ssh, http(s) URLs or socket code.
  - No subagent (Task or Agent) was used.
- **Python.** Every agent used `/opt/benchmark-venv/bin/python3` or bare `python3`, and bare `python3`
  resolved to the venv. This confirms the hosted-oracle1 PATH fix from inside an agent.
- **Endings.** Every session ended with a `success` result well before its limit; none was killed.

### reg_resect · Opus (0.667; ended voluntarily at 18 of 45 min)

- **run.sh first.** "Put identity baseline first." Within 7 s of starting, `run.sh` copied the input
  landmarks and then ran `reg.py` under `timeout 105`, falling back to identity.
- **Method.** FLAIR → US: nibabel affines, so world RAS mm throughout; 1 mm resampling inside the
  sweep mask; MIND features; rigid translation grid search plus Powell; then one pass of regularised
  MIND block matching. Landmarks were moved by the inverse rigid transform and a fixed-point inversion
  of the field.
- **Dev cases.**
  - It used all four with references, ran its full `run.sh` on them through its own `runall.sh` after
    each change, and tuned 10+ settings in-sample on those four cases.
  - Final dev TRE was 1.29, 1.09, 2.14 and 1.35 mm. It reported c4fe8a as staying above target.
  - It also tested robustness by shifting one US header by 8.4 mm ("still reached 1.29 mm") and timed
    a lone run at 19 s.
- **Hidden.**
  - 4/6, with a better mean TRE than the specialist (1.61 vs 3.03 mm).
  - It missed cb06b4 by 0.01 mm (2.01 mm; specialist 1.83). Case cb06b4 also took 90 s of the
    120 s limit.
  - It passed cdd96a, which the specialist fails.
- **Other.** No sign of recognising RESECT beyond the README.

### reg_resect · Sonnet (0.000; ended voluntarily at 3 of 45 min)

- **Early run.sh.** The second tool call wrote `run.sh` with a SimpleITK rigid MI registration. Frames
  were handled explicitly ("(-p[0], -p[1], p[2])" LPS↔RAS).
- **Experiments.** Three scripts on the four dev cases: MI and NCC on T1, FLAIR and gradient images;
  then a ±8 mm translation grid with MI, NCC and simplified LC2. Nearly all gave 2.5–15 mm against
  2.6–4.6 mm uncorrected.
- **Shipped a no-op.** It replaced the pipeline with a copy of the MRI landmarks: "Conservative
  fallback: image-based rigid registration … was consistently WORSE than the navigation alignment, so
  landmarks are passed through."
- **Ending.** It stopped after 7 turns: "I didn't try deformable registration … I stopped partway
  through the 45 minutes."
- **Possible frame bug (agent side, our inference, not verified).** Its grid search maps world shifts
  to array shifts with a sign taken from the diagonal of the direction matrix. Errors far larger than
  no correction are consistent with a sign or axis error in that mapping.
- **Not our bug.** The instruction states the frames and the session limit, and the attempt was not
  cut short.

### seg_spleen · Opus (0.500; ended voluntarily at 31 of 60 min)

- **Method.** A 2.5D U-Net trained from scratch on CPU: 1 mm in-plane, neighbouring slices at about
  ±4 and ±10 mm, HU window −250…350, intensity augmentation for contrast timing, largest-component
  clean-up, volume = voxel count × voxel volume.
- **Spacing and orientation.** Checked via `aff2axcodes` and the affines; the output was mapped back to
  the input grid.
- **run.sh early.** `run.sh` existed 2 minutes in and was smoke-tested on an early checkpoint (Dice 0.00
  at that point).
- **Checkpoints.**
  - It shipped a held-out checkpoint at 13 minutes: "Held-out case already at Dice 0.959 … Shipping this
    checkpoint now as a safe model".
  - It then fine-tuned on all eight cases and ran the final `run.sh` on all eight with `timeout 300` and a
    fresh `HOME`. It stated that the 8-case figures "are optimistic".
- **Hidden.** Exactly the specialist's three cases pass. It was better than the specialist on hid_6971
  (0.933 vs 0.892) but failed hid_8298 on volume (+11.8 %).

### seg_spleen · Sonnet (0.167; ended voluntarily at 16 of 60 min)

- **Method.** Two-stage ExtraTrees: a 3 mm localiser, then 1.5 mm refinement, with spacing-aware
  resampling.
- **Validation.** Leave-one-out on the eight dev cases: mean Dice about 0.92, 4/8 passing. It named
  "poor stage-1 localisation" as the failure mode.
- **Delivery.** `run.sh` appeared only at 11 minutes. It ran the final pipeline on all eight cases
  under `env -i` with an empty `HOME`.
- **Ending.** It stopped with 44 minutes left, expecting "roughly 4–5 of the 6 hidden scans to pass".
- **Hidden.**
  - 1/6. Two cases were mislocalised (hid_6971 Dice 0.000; hid_8298 0.144), and hid_4506 had a 50 %
    volume over-estimate.
  - hid_2997 missed the Dice bar by 0.0005.

### measure_hc18 · Opus (0.422; first answer at 11.6 min, process ended at 19.7 of 45 min)

- **Baseline first.** "Write a baseline run.sh now (constant pixel perimeter), then improve." Within
  5 s it had a working `run.sh` with a fallback of `pixel_size_mm × 1349`.
- **Units.** It checked pixel and mm consistency on the references before modelling.
- **Method.** An ExtraTrees two-stage pixel classifier on 4× downsampled features, mask clean-up and an
  ellipse fit (Ramanujan perimeter × pixel size), plus a 0.98 correction factor from validation.
- **Validation.** 4-fold CV gave "about 60% … well below the 90% target, so expect a headline score
  around 0.6". It ran `run.sh` on six dev cases (about 1.6 s each).
- **Ending.**
  - The first result event came at 11.6 minutes.
  - A background comparison job (`pp.py`) was still running. Claude Code stopped it at its 10-minute
    background limit, and that woke the session for one more turn ("Nothing changes in the pipeline").
  - So there are two result events: 18 + 1 turns, cumulative cost $0.567.
- **Hidden.** 42 %, worse than its own CV, with large errors in the large-head tertile (5/27).

### measure_hc18 · Sonnet (0.771; ended voluntarily at 10.7 of 45 min)

- **Method.** A gradient-boosted pixel classifier for the skull ring, then a RANSAC-style ellipse search
  and Nelder–Mead refinement, with pixel size used for mm.
- **Images.** It looked at visualisations of its own outputs with `Read` (three PNGs).
- **Tuning.** It found a systematic inward bias and added 1 mm to both semi-axes, tuned on the same CV
  ("took the cross-validated rate from 67% to 83%").
- **Ending.** `run.sh` existed at 30 s. It ran on three dev cases (about 1.3 s each) and stopped,
  stating "it probably won't reach the 90% bar".
- **Hidden.** 77 % (64/83), consistent with its CV. It was weakest on small heads (17/29), and the
  5 gross failures on large heads all fell near the output clamp.

### ecg_ptbxl · Opus (1.000; ended voluntarily at 8 of 30 min)

- **Method.** Two seeds of a 1D ResNet on 12 leads plus age and sex, trained on folds 1–7. Per-class
  Platt calibration fitted on fold 8, "fitted and scored on separate parts" of fold 8.
- **Checks.**
  - It computed all three gate parts on fold 8: MI sensitivity 0.81, ECE 0.023, subgroup gap 0.020.
  - It ran `run.sh` on a fold-8 copy without labels (2.4 s) and checked the output format.
- **Hidden.** Passed all three parts, but MI sensitivity was 0.717 against the 0.70 bar (its fold-8
  estimate was 0.81).

### ecg_ptbxl · Sonnet (1.000; ended voluntarily at 10 of 30 min)

- **Method.** A small 1D CNN with age and sex, trained 35 epochs on folds 1–7, with Platt calibration on
  fold 8.
- **Early pipeline.** `run.sh` existed in the second tool call, and a 1-epoch model made it work within
  the first minute.
- **Live overwrites.** During training, `train.py` overwrote `net.pt` and `cal.pkl` in the live pipeline
  folder. This was harmless here, but a kill mid-write could have broken it.
- **Checks.** It did not compute the gate parts ("I can't tell yet whether it passes the three-part
  gate"). It ran `run.sh` on all 8,000 dev ECGs with labels stripped (about 10 s).
- **Hidden.** Passed all three parts, with margins wider than Opus's.

### risk_icu · Opus (1.000; ended voluntarily at 3 of 45 min)

- **Data handling.** Per-stay summary features, with explicit unit repairs: FiO2 given as a percentage,
  pH ×100, Temp in °F, SaO2 as a fraction.
- **Prior familiarity (method level).** These specific repairs were written in the first code, before
  any value was inspected. The instruction only says "some values are … entered in the wrong units". We
  read this as prior familiarity with PhysioNet 2012's known quirks, not memorised labels.
- **Model.** Three gradient-boosting models blended with a logistic regression, then Platt
  recalibration on 5-fold out-of-fold predictions.
- **Checks.** It computed all four gate parts out of fold, ran `run.sh` on all 4,000 dev stays (16 s),
  and tested records that are nearly empty or hold only a RecordID.
- **Hidden.** Passed all four parts, matching the specialist (AUROC 0.874 vs 0.873).

### risk_icu · Sonnet (1.000; ended voluntarily at 1.6 of 45 min)

- **One shot.** A single tool call wrote the features, five gradient-boosting models with logistic
  recalibration on out-of-fold predictions, and `run.sh`. A second call ran it on the dev set (33 s).
- **Stated gaps.** It said it did not compute the calibration slope or intercept, and did not test as an
  unprivileged user.
- **Hidden.** Passed all four parts.

### Contamination and other hosts

- **Datasets.** Every instruction names its dataset. No trace recalls hidden labels or published
  per-case values, and every prediction comes from a method fitted on the development data.
- **Prior knowledge.** The only sign of familiarity with the data itself is Opus's ICU unit repairs
  (above).
- **Network.** No attempt to reach another host was found.

## Gap verdicts (DESIGN.md rule as operationalised in the prespecification)

- **Per-case families.** S is the set of hidden cases the specialist passes. The measures are paired
  bootstrap differences, agent minus specialist, on S: `suite.core.metrics.paired_bootstrap_difference`
  with `np.mean`, 2000 resamples, seed 20261114, 95 % percentile interval. An invalid or late case would
  count as a fail.
  - **Gap shown:** the agent fails at least one case in S and the pass-difference interval lies entirely
    below 0.
  - **No gap shown:** an interval that includes 0.
- **Cohort families.** The specialist meets every gate part; gap shown if the agent misses any part.

| Attempt | S | Agent passes in S | Pass diff (95 % CI) | Quality diff (95 % CI) | Raw diff on S (95 % CI) | Verdict |
|---|---|---|---|---|---|---|
| reg · Opus | 4 | 3 | −0.25 (−0.75 to 0.00) | +0.050 (−0.015 to +0.123) | TRE −0.20 mm (−0.55 to +0.08) | **no gap shown** (1 of 4 failed, by 0.01 mm; interval includes 0; n = 4) |
| reg · Sonnet | 4 | 0 | −1.00 (degenerate) | −0.355 (−0.434 to −0.306) | TRE +3.69 mm (+2.36 to +5.02) | **gap shown**: an agent-chosen no-op pipeline, not a delivery failure and not our bug |
| spleen · Opus | 3 | 3 | 0.00 | 0.000 (−0.005 to +0.007) | Dice 0.000 (−0.005 to +0.007) | **no gap** |
| spleen · Sonnet | 3 | 1 | −0.67 (−1.00 to 0.00) | −0.068 (−0.189 to +0.001) | Dice −0.068 (−0.189 to +0.001) | **no gap shown** (2 of 3 failed; with n = 3 the interval reaches 0, so underpowered rather than reassuring) |
| hc18 · Opus | 83 | 35 | −0.578 (−0.675 to −0.470) | −0.424 (−0.504 to −0.344) | abs. err. +14.1 mm (+9.8 to +18.7) | **gap shown** |
| hc18 · Sonnet | 83 | 64 | −0.229 (−0.313 to −0.145) | −0.215 (−0.285 to −0.142) | abs. err. +15.9 mm (+5.4 to +29.0) | **gap shown** |
| ecg · Opus | – | – | – | – | gate 3/3 vs 3/3 | **no gap** (control) |
| ecg · Sonnet | – | – | – | – | gate 3/3 vs 3/3 | **no gap** (control) |
| icu · Opus | – | – | – | – | gate 4/4 vs 4/4 | **no gap** (control) |
| icu · Sonnet | – | – | – | – | gate 4/4 vs 4/4 | **no gap** (control) |

None of the verdicts is "not interpretable".
- There was no infrastructure failure and no grading error.
- No trace points to our instructions or grader as the cause of a result.
- The instruction stated the session limit, and no attempt reached it.

The hc18 gaps are the only ones with intervals well clear of 0. On reg_resect and seg_spleen the hidden
sets (6 cases, S of 4 or 3) are too small for the rule to show a gap short of a total failure.

## Incidents

- **No infrastructure incidents.** No relaunch and no run errors ("No current error messages
  recorded"). Images were cached, with builds of 1–17 s.
- **Opus spleen started 18 minutes late.** It was queued behind the other Opus tasks at concurrency 3:
  task start 02:05, agent start 02:23. The queue wait is not counted in the agent's session.
- **Opus hc18 second result event**, as described above. One extra turn ($0.13); the pipeline did not
  change.
- **Claude Code blocked `sleep N` waits** in four attempts (Opus hc18 and spleen, Sonnet ECG and spleen).
  Each agent switched to `until` loops. This is harness behaviour, not ours.
- **Missing tools in the image.** `ps`, `pgrep`, `free`, `bc` and `/usr/bin/time` are absent in
  `python:3.12-slim`. This cost a few tool calls and had no effect on results.

## Our bugs and limitations (named as ours)

1. **Effort was not "high".** Our no-web bundle has no effort parameter and passes no `--effort`, so the
   prespecified "effort high if accepted" fell back to the Claude Code 2.1.325 default. The traces do not
   record the level. For reference, the Claude API's own default for Opus 5.5 is `medium`; what Claude
   Code uses is not verified here. Results should be read as "default effort".
2. **The grader's `metrics.json` is not kept by Valkyrie, and the hc18 stdout summary is cut at about
   16 kB** (known since hosted-oracle1). Raw values here come from local regrades. They are labelled as
   such and checked against the hosted reward keys.
3. **Regrade environments for spleen and ECG are not the exact image pins.** Rewards still matched
   exactly.
4. **The specialist's runtime was measured on the export host.** So `runtime_ratio_vs_specialist` is
   not a like-for-like comparison and is not used here.
5. **No result here points to an instruction or grader bug.**
   - The v3 session section did what it was for: none was killed at the limit, and 8 of 10 attempts had a
     working `run.sh` within 3 minutes. Opus ECG's `run.sh` was written at 2 minutes but first worked at
     about 8 minutes, once the calibration file existed; Sonnet spleen's first appeared at 11 minutes.
   - **Open question, not established as our bug:** agents ended voluntarily with 48–96 % of the session
     unused, several while knowing they were below the bar (Opus hc18 "about 60%"; Sonnet hc18 "probably
     won't reach the 90% bar"; Sonnet reg "I stopped partway").
   - Nothing in the instruction tells them to stop. `claude -p` simply ends when the model ends its turn.
     Whether a "use the time you have" sentence would change this is untested; adding one would be a new
     task version.

## Other limitations

- **One attempt** per task and model, so there is no run-to-run variance. Opus's 0.42 and Sonnet's 0.77
  on hc18 are single draws, and both are lower than the local pilot-1 hc18 results (Opus 0.928, Sonnet
  0.819, v1 instructions, local sandbox).
- **Small hidden sets for reg_resect and seg_spleen** (6 cases each), so intervals are wide or
  degenerate.
- **Public datasets.** Contamination at the method level is possible (see Opus ICU). No label
  memorisation was seen.
- **Agent development folds.** In-sample tuning on 4 or 8 development cases (reg, spleen) and random-ID
  CV folds (hc18) made several agents' own estimates optimistic. Opus hc18: CV 60 %, hidden 42 %. Opus ECG
  MI sensitivity: fold 8 0.81, hidden 0.717.

## Cost

| Item | Opus | Sonnet | Total |
|---|---|---|---|
| API (Claude Code `total_cost_usd`, list basis) | $2.746 | $1.021 | **$3.766** |
| Per attempt | reg $0.553, spleen $0.910, hc18 $0.567, ECG $0.382, ICU $0.334 | reg $0.142, spleen $0.332, hc18 $0.356, ECG $0.121, ICU $0.070 | |
| Modal | not reported by Valkyrie (no cost field in `run fetch`, `run results` or `run task`) | | |

Sandbox time (`sandbox_run_duration`) summed to about 2.5 h (9,039 s) across the ten tasks (largest: Opus spleen
1,996 s). Image builds were cached. Actual Modal spend needs the Modal dashboard.
