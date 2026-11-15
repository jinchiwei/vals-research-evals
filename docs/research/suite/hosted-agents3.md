# Hosted agent runs 3 (repeats R): three attempts per task and model on the headline suite

Written 2026-11-15 by a Claude Code worker for the coordinator (model: **Claude Opus 5.5, `claude-opus-5-5`**).
Workstream R of `round3-prereg.md`. Machine-readable values: [`hosted-agents3.json`](hosted-agents3.json).
Raw evidence: `exp/suite-hosted-agents3/` (git-ignored by `.gitignore` line 33, `exp/`; about 175 MB with the
carried pipelines). Attempt R1 of each task and model is run 2 ([`hosted-agents2.md`](hosted-agents2.md)). R2 and
R3 are the two new runs per model. All three are the same task version, `suite/clinical-v1@2`, and are pooled as
the prereg says. The keep-working variant (K) is a different task version and is reported separately in
[`hosted-keepworking1.md`](hosted-keepworking1.md).

## Summary

- **Twenty new attempts, twenty graded results, no infrastructure failure.** Nothing was relaunched. No attempt hit
  its session limit or the $8 budget cap. Every attempt ended on its own.
- **One attempt does not predict the next.** Opus registration went 0.667 → 0.333 → 0.000 and Opus spleen
  0.500 → 0.000 → 0.167. Opus fetal head ranged 0.42–0.86, and Opus ECG failed a gate part once (0.000) after two
  passes.
- **Gap shown in 3 of 3 attempts:**
  - fetal head, both models (the specialist is within tolerance on 83 of 83 images; agents 35–74);
  - registration, Sonnet.
- **Gap shown in 1 of 3 attempts:** Opus registration, Opus spleen, Opus ECG (MI sensitivity 0.693 against a 0.70
  bar) and Sonnet spleen.
- **ICU risk and Sonnet ECG pass every gate part in all three attempts** (controls hold).
- **Agents still stop early.** 19 of 20 new attempts used under 60 % of the session (the exception used 72 %).
  Several said they were out of time when they were not. One example: "I stopped there because of the session
  limit" at 8 of 45 minutes. No web tool was offered or used.
- **API cost of the 20 new attempts: $6.60** (Opus $4.45, Sonnet $2.15). Modal cost is not shown by Valkyrie.

## Design (fixed before launch: `exp/suite-hosted-agents3/prespec.txt`)

Everything is as in run 2: dataset `suite/clinical-v1@instr2` (version 2, digest `f7d7cd08f525`), agent
`claude_code_noweb-v1.0.0` (Claude Code 2.1.325 in every trace, `--disallowedTools "WebFetch WebSearch"`,
`--max-budget-usd 8`), the tasks' own session limits, Modal, and Claude Code's default effort. The four runs were
launched together at 05:57Z:

```
.venv-valkyrie/bin/valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@instr2 \
  --provider modal --model anthropic/claude-<opus|sonnet>-5-5 -s ANTHROPIC_API_KEY anthropic-api-key \
  --concurrency 3 -l hosted-agents3<a|b>-<opus|sonnet>
```

| Attempt | Model | Run id | Label | Status | final_score | Run errors |
|---|---|---|---|---|---|---|
| R2 | Opus | `7db8faca-9295-4231-9dde-4580dfb8921a` | hosted-agents3a-opus | finished 5/5 | 63.78 | none recorded |
| R3 | Opus | `39d574d3-7ee3-444e-b300-fb3c8cd74ae9` | hosted-agents3b-opus | finished 5/5 | 36.83 | none recorded |
| R2 | Sonnet | `a3525e04-cb77-4e97-9dc6-ce71a86d3960` | hosted-agents3a-sonnet | finished 5/5 | 60.44 | none recorded |
| R3 | Sonnet | `5378cf20-6ce9-4f13-b007-537c331d8ab5` | hosted-agents3b-sonnet | finished 5/5 | 61.16 | none recorded |

R1 is run 2: Opus `1f2e6208-…`, Sonnet `5110a198-…`. Its values here are rebuilt from the `hosted-agents2`
evidence with the same builder, and they reproduce `hosted-agents2.json` exactly (rewards, verdicts, raw values).

**Collection and regrade** were done exactly as in `hosted-agents2.md`.
- Per task: `run task`, `run logs --format jsonl`, `run outputs`. Per run: `run fetch` and `run errors` (in
  `runlevel/`).
- Each carried `/workspace/output/pipeline` was regraded with the task's own `tests/grade.py` from
  `dist/suite-tasks-v3/`, on the pilot runner's bubblewrap no-network path, with the same runtime envs as run 2.
- **Agreement with the hosted grade.** All seven reward keys match in 19 of 20 attempts. The exception is Sonnet R3
  fetal head:
  - its pipeline is not deterministic (no fixed seed in its ellipse search), so 38 of 83 per-image qualities differ
    slightly;
  - one image (`case_f3690e`, 4.52 mm error against a 4.28 mm tolerance) flips to a fail locally;
  - the local reward is 0.880 against 0.892 hosted.
- **Which source decides.** The hosted grade decides. Pass/fail and quality per case come from the hosted verifier
  lines (all present). Raw errors in mm, Dice and cohort metrics come from the regrade.
- **Secrets.** A scan for `sk-ant` over all evidence found nothing.

## Per-attempt results (30 attempts: R1 = run 2, R2 and R3 new)

- **Rewards** are the hosted grades.
- **Headline** is the raw value from the local regrade.
- **Agent time** is the agent process time (`metrics_total.json`); **session used** is that time over the task's
  limit (reg, hc18, icu 2700 s; spleen 3600 s; ecg 1800 s).
- **Cost** is Claude Code's `total_cost_usd` (list price).
- **Gap** is the DESIGN.md rule as set out in the run-2 prespec: "gap" means gap shown; "no gap shown" means the
  agent failed some specialist-passed cases but the interval includes 0.

| Task | Model | Att. | reward | ran | valid | within_time | clin_acc | quality | vs_spec | Headline (raw) | Agent time | Session used | API cost | Gap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reg | Opus | R1 | 0.667 | 1 | 1 | 1 | 0.667 | 0.463 | 1.000 | 4/6 < 2 mm; mean TRE 1.61 mm | 1089 s | 40 % | $0.55 | no gap shown |
| reg | Opus | R2 | 0.333 | 1 | 1 | 1 | 0.333 | 0.355 | 1.000 | 2/6; 2.15 mm | 871 s | 32 % | $0.52 | no gap shown |
| reg | Opus | R3 | **0.000** | 1 | **0.833** | 1 | 0.167 | 0.133 | 0.400 | 1/6; 6.36 mm (5 valid cases); 1 case invalid | 839 s | 31 % | $0.42 | gap |
| reg | Sonnet | R1 | 0.000 | 1 | 1 | 1 | 0.000 | 0.070 | 0.213 | 0/6; 6.18 mm (no-op) | 186 s | 7 % | $0.14 | gap |
| reg | Sonnet | R2 | 0.167 | 1 | 1 | 1 | 0.167 | 0.140 | 0.424 | 1/6; 7.54 mm | 504 s | 19 % | $0.24 | gap |
| reg | Sonnet | R3 | 0.000 | 1 | 1 | 1 | 0.000 | 0.067 | 0.202 | 0/6; 6.58 mm | 126 s | 5 % | $0.08 | gap |
| spleen | Opus | R1 | 0.500 | 1 | 1 | 1 | 0.500 | 0.940 | 1.000 | 3/6; Dice 0.940; abs. vol. err. 4.1 % | 1869 s | 52 % | $0.91 | no gap |
| spleen | Opus | R2 | 0.000 | 1 | 1 | 1 | 0.000 | 0.905 | 0.964 | 0/6; 0.905; 11.7 % | 1510 s | 42 % | $0.53 | gap |
| spleen | Opus | R3 | 0.167 | 1 | 1 | 1 | 0.167 | 0.912 | 0.972 | 1/6; 0.912; 7.4 % | 2109 s | 59 % | $0.86 | no gap shown |
| spleen | Sonnet | R1 | 0.167 | 1 | 1 | 1 | 0.167 | 0.621 | 0.661 | 1/6; 0.621; 34.2 % | 978 s | 27 % | $0.33 | no gap shown |
| spleen | Sonnet | R2 | 0.000 | 1 | 1 | 1 | 0.000 | 0.857 | 0.913 | 0/6; 0.857; 18.1 % | 2112 s | 59 % | $0.30 | gap |
| spleen | Sonnet | R3 | 0.167 | 1 | 1 | 1 | 0.167 | 0.720 | 0.767 | 1/6; 0.720; 15.1 % | 1654 s | 46 % | $0.43 | no gap shown |
| hc18 | Opus | R1 | 0.422 | 1 | 1 | 1 | 0.422 | 0.293 | 0.409 | 35/83; MAE 16.2 mm (median 8.8) | 1181 s | 44 % | $0.57 | gap |
| hc18 | Opus | R2 | 0.855 | 1 | 1 | 1 | 0.855 | 0.561 | 0.782 | 71/83; 6.6 mm (2.1) | 481 s | 18 % | $0.52 | gap |
| hc18 | Opus | R3 | 0.675 | 1 | 1 | 1 | 0.675 | 0.385 | 0.536 | 56/83; 10.3 mm (4.5) | 485 s | 18 % | $0.46 | gap |
| hc18 | Sonnet | R1 | 0.771 | 1 | 1 | 1 | 0.771 | 0.502 | 0.700 | 64/83; 18.0 mm (3.3) | 645 s | 24 % | $0.36 | gap |
| hc18 | Sonnet | R2 | 0.855 | 1 | 1 | 1 | 0.855 | 0.521 | 0.726 | 71/83; 13.0 mm (3.1) | 431 s | 16 % | $0.29 | gap |
| hc18 | Sonnet | R3 | 0.892 | 1 | 1 | 1 | 0.892 | 0.550 | 0.767 | 74/83; 8.2 mm (3.0) | 1953 s | 72 % | $0.44 | gap |
| ecg | Opus | R1 | 1.000 | 1 | 1 | 1 | 1.000 | 0.953 | 0.970 | 3/3 parts; AUROC 0.908; MI sens 0.717; ECE 0.030; subgroup gap 0.029 | 473 s | 26 % | $0.38 | no gap |
| ecg | Opus | R2 | 1.000 | 1 | 1 | 1 | 1.000 | 0.960 | 0.977 | 3/3; 0.911; 0.713; 0.031; 0.033 | 771 s | 43 % | $0.38 | no gap |
| ecg | Opus | R3 | **0.000** | 1 | 1 | 1 | 0.000 | 0.956 | 0.973 | **2/3**; 0.909; **0.693**; 0.034; 0.033 | 436 s | 24 % | $0.24 | gap |
| ecg | Sonnet | R1 | 1.000 | 1 | 1 | 1 | 1.000 | 0.967 | 0.984 | 3/3; 0.914; 0.760; 0.025; 0.023 | 588 s | 33 % | $0.12 | no gap |
| ecg | Sonnet | R2 | 1.000 | 1 | 1 | 1 | 1.000 | 0.912 | 0.928 | 3/3; 0.890; 0.709; 0.032; 0.032 | 686 s | 38 % | $0.16 | no gap |
| ecg | Sonnet | R3 | 1.000 | 1 | 1 | 1 | 1.000 | 0.946 | 0.963 | 3/3; 0.905; 0.717; 0.027; 0.027 | 455 s | 25 % | $0.09 | no gap |
| icu | Opus | R1 | 1.000 | 1 | 1 | 1 | 1.000 | 0.747 | 1.000 | 4/4 parts; AUROC 0.874; cal. slope 1.04; NB@0.2 0.070 | 186 s | 7 % | $0.33 | no gap |
| icu | Opus | R2 | 1.000 | 1 | 1 | 1 | 1.000 | 0.732 | 0.982 | 4/4; 0.866; 1.00; 0.071 | 134 s | 5 % | $0.21 | no gap |
| icu | Opus | R3 | 1.000 | 1 | 1 | 1 | 1.000 | 0.743 | 0.997 | 4/4; 0.871; 1.06; 0.071 | 253 s | 9 % | $0.32 | no gap |
| icu | Sonnet | R1 | 1.000 | 1 | 1 | 1 | 1.000 | 0.730 | 0.980 | 4/4; 0.865; 1.07; 0.066 | 98 s | 4 % | $0.07 | no gap |
| icu | Sonnet | R2 | 1.000 | 1 | 1 | 1 | 1.000 | 0.730 | 0.979 | 4/4; 0.865; 1.06; 0.067 | 75 s | 3 % | $0.06 | no gap |
| icu | Sonnet | R3 | 1.000 | 1 | 1 | 1 | 1.000 | 0.736 | 0.988 | 4/4; 0.868; 1.06; 0.067 | 87 s | 3 % | $0.07 | no gap |

Specialist values on the same hidden cases are unchanged from run 2:
- reg 4/6, mean TRE 3.03 mm;
- spleen 3/6, Dice 0.939;
- hc18 83/83, MAE 2.05 mm;
- ECG all 3 parts (MI sensitivity 0.744);
- ICU all 4 parts.

## Pooled view: three attempts per task and model

| Task | Model | Rewards (R1, R2, R3) | Mean | Range | Gap shown in | Session used (R1, R2, R3) | API cost (3 attempts) |
|---|---|---|---|---|---|---|---|
| reg_resect | Opus | 0.667, 0.333, 0.000 | 0.333 | 0.000–0.667 | **1 of 3** | 40, 32, 31 % | $1.49 |
| reg_resect | Sonnet | 0.000, 0.167, 0.000 | 0.056 | 0.000–0.167 | **3 of 3** | 7, 19, 5 % | $0.46 |
| seg_spleen | Opus | 0.500, 0.000, 0.167 | 0.222 | 0.000–0.500 | **1 of 3** | 52, 42, 59 % | $2.30 |
| seg_spleen | Sonnet | 0.167, 0.000, 0.167 | 0.111 | 0.000–0.167 | **1 of 3** | 27, 59, 46 % | $1.06 |
| measure_hc18 | Opus | 0.422, 0.855, 0.675 | 0.651 | 0.422–0.855 | **3 of 3** | 44, 18, 18 % | $1.55 |
| measure_hc18 | Sonnet | 0.771, 0.855, 0.892 | 0.839 | 0.771–0.892 | **3 of 3** | 24, 16, 72 % | $1.08 |
| ecg_ptbxl | Opus | 1.000, 1.000, 0.000 | 0.667 | 0.000–1.000 | **1 of 3** | 26, 43, 24 % | $1.00 |
| ecg_ptbxl | Sonnet | 1.000, 1.000, 1.000 | 1.000 | 1.000 | 0 of 3 | 33, 38, 25 % | $0.37 |
| risk_icu | Opus | 1.000, 1.000, 1.000 | 1.000 | 1.000 | 0 of 3 | 7, 5, 9 % | $0.87 |
| risk_icu | Sonnet | 1.000, 1.000, 1.000 | 1.000 | 1.000 | 0 of 3 | 4, 3, 3 % | $0.20 |

**Per-attempt gap verdicts** (95 % paired bootstrap of per-case pass, agent minus specialist, on the specialist-passed
set S; the full intervals are in the JSON):

| Task | Model | R1 | R2 | R3 |
|---|---|---|---|---|
| reg (S = 4) | Opus | no gap shown (1 of 4 failed) | no gap shown (2 failed; −0.50, −1.00 to 0.00) | gap shown (3 failed; −0.75, −1.00 to −0.25) |
| reg | Sonnet | gap (4 of 4) | gap (3 of 4; −0.75, −1.00 to −0.25) | gap (4 of 4) |
| spleen (S = 3) | Opus | no gap (0 failed) | gap (3 of 3) | no gap shown (2 of 3 failed; −0.67, −1.00 to 0.00) |
| spleen | Sonnet | no gap shown (2 of 3) | gap (3 of 3) | no gap shown (2 of 3) |
| hc18 (S = 83) | Opus | gap (−0.578, −0.675 to −0.470) | gap (−0.145, −0.229 to −0.072) | gap (−0.325, −0.422 to −0.229) |
| hc18 | Sonnet | gap (−0.229, −0.313 to −0.145) | gap (−0.145, −0.217 to −0.072) | gap (−0.108, −0.169 to −0.048) |
| ecg | Opus | no gap (3/3 parts) | no gap (3/3) | gap (misses MI operating point) |
| ecg | Sonnet | no gap | no gap | no gap |
| icu | both | no gap | no gap | no gap |

**Reading.**
- **Fetal head is the stable result.** A gap is shown in every attempt of both models, with every interval clear of
  0. The best attempt (Sonnet R3, 74/83) is still nine images short of the specialist.
- **Registration and spleen depend on the draw.**
  - With S of 4 and 3 cases, the rule shows a gap only when an agent fails most of S.
  - Opus moved from matching the specialist (R1) to a validity failure (R3), and Sonnet registration is a gap every
    time.
  - Reporting one attempt per task, as run 2 did, would have been misleading for these two.
- **The Opus ECG control is close to the bar.** MI sensitivity at 90 % specificity was 0.717, 0.713 and 0.693
  against a 0.70 bar (specialist 0.744). Sonnet's was 0.760, 0.709 and 0.717. A single miss in three attempts is
  consistent with an agent sitting at the threshold, not with a different capability.

### Per-case detail, new attempts (local regrade; ✓ = clinically acceptable on the hosted grade)

reg_resect, mean TRE in mm (uncorrected: c18b03 6.39, c57eed 3.39, c65c1b 5.68, cb06b4 4.55, cdd96a 10.06,
ce4785 7.01; the specialist passes c18b03, c57eed, cb06b4, ce4785):

| Case | Opus R2 | Opus R3 | Sonnet R2 | Sonnet R3 |
|---|---|---|---|---|
| c18b03 | 2.35 | 1.91 ✓ | 10.45 | 6.39 |
| c57eed | 1.29 ✓ | **invalid** (5 of 15 points > 10 mm outside the US field of view) | 1.63 ✓ | 3.39 |
| c65c1b | 2.89 | 5.68 | 12.43 | 6.39 |
| cb06b4 | 1.57 ✓ | 2.13 | 6.43 | 4.55 |
| cdd96a | 2.23 | 10.06 | 12.19 | 11.78 |
| ce4785 | 2.57 | 12.02 | 2.11 | 7.01 |

seg_spleen, Dice / signed volume error (pass needs Dice ≥ 0.94 and |vol. err.| ≤ 10 %; the specialist passes
hid_1200, hid_2997, hid_4506):

| Case | Opus R2 | Opus R3 | Sonnet R2 | Sonnet R3 |
|---|---|---|---|---|
| hid_1200 | 0.924 / −8.3 % | 0.912 / −13.8 % | 0.888 / −16.8 % | 0.939 / +1.5 % |
| hid_1392 | 0.879 / +8.9 % | 0.862 / +8.6 % | 0.890 / +6.1 % | 0.904 / −8.7 % |
| hid_2997 | 0.919 / −11.8 % | 0.961 / −2.5 % ✓ | 0.847 / −24.0 % | 0.874 / −14.6 % |
| hid_4506 | 0.939 / −4.2 % | 0.914 / −11.0 % | 0.861 / −15.5 % | 0.946 / −1.0 % ✓ |
| hid_6971 | 0.884 / −13.2 % | 0.893 / −7.4 % | 0.742 / −28.5 % | 0.654 / +7.8 % |
| hid_8298 | 0.882 / +23.9 % | 0.930 / −1.2 % | 0.913 / +17.6 % | 0.000 / +56.9 % |

The Opus spleen attempts are near misses (Dice 0.86–0.96) that mostly undersize the organ, as Opus R2 predicted
("the model tended to undersize the organ").

## Trace findings, per new attempt

All 20 new traces were read (`exp/suite-hosted-agents3/<model>-3<a|b>/trace-<task>.txt`, plus the summaries in
`trace-<task>.json`).

**Common to all 20:**
- **No web or network use.** The `init` event offers no WebFetch or WebSearch, and there were 0 web search or fetch
  requests. No tool input reached for the network, and no subagent was used.
- **Python.** Every attempt used the image's venv Python.
- **Ending.** Every attempt ended with a `success` result, by its own choice, well before its limit.
- **Harness friction, as in run 2.**
  - `sleep N` waits were blocked by Claude Code in 12 of 20 attempts.
  - `Monitor` calls were denied in one attempt (Sonnet hc18 R3).
  - `ps`, `pkill`, `free`, `bc` and `/usr/bin/time` are absent from the image.
  - Several agents lost minutes waiting on background jobs they could not inspect.
- **Late agent starts.** At concurrency 3, spleen and ICU were queued behind the other tasks, so their agents started
  5–15 minutes after the run (the other tasks within 1 minute). Queue time is not part of the agent's session.

### Registration
- **Opus R2 (0.333; 14.5 of 45 min).**
  - "Write an identity baseline first." `run.sh` was in place at 4 s.
  - Method: FLAIR rigid registration, a four-way ensemble (three MIND settings plus LC2) with a per-landmark median,
    a ±12 mm search and a 95 s cap per member. Dev: 2 of 4 under 2 mm.
  - Ending: "I ran out of session time before closing it." 30 minutes were left.
  - Hidden: 2/6, and every case improved on no correction (2.2–2.9 mm misses).
- **Opus R3 (0.000; 14.0 of 45 min).**
  - `run.sh` wrote the identity first and then ran `reg.py` under `timeout 105`.
  - Method: MIND rigid plus a small affine refinement, FLAIR only. A result is rejected if it implies more than 15 %
    volume change. Dev: 3 of 4 under 2 mm (tuned on the same 4).
  - Ending: "I didn't try a fully deformable registration in the time available" (31 minutes left).
  - **Hidden: c57eed invalid.** Five landmarks were more than 10 mm outside the ultrasound field of view, so `valid`
    is 0.833 and the reward is 0, although c18b03 passed. The agent's volume-change check did not catch a bad affine.
    ce4785 went from 7.0 to 12.0 mm.
- **Sonnet R2 (0.167; 8.4 of 45 min).**
  - It tried rigid MI, translation MI and intensity regression, and kept a gradient-magnitude translation search.
    On dev it made one case much worse (2.83 → 10.94 mm).
  - "I did not add a fallback that returns the unshifted landmarks when the match score is low."
  - Hidden: 4 of 6 worse than no correction.
- **Sonnet R3 (0.000; 2.1 of 45 min, 8 turns).**
  - Rigid MI, gradient correlation and translation MI were all unreliable. It shipped translation MI, kept only if
    the mean shift is under 4 mm.
  - "The pipeline probably won't meet the 2 mm threshold on most hidden cases … I did not try deformable
    registration, FLAIR, or MIND-style features."
  - Hidden: 0/6, essentially no correction.

### Spleen
- **Opus R2 (0.000; 25.2 of 60 min).**
  - An empty-mask fallback `run.sh` was in place within a minute.
  - Method: a 2.5D U-Net from scratch at 1.5 mm with augmentation. A hold-out model and a full model were trained
    in parallel and ensembled at threshold 0.4.
  - Hold-out: one of two dev cases passed (0.951; 0.921 failed). It tested under a clean env and an empty `HOME`,
    and warned "expect some hidden scans to land near or below the 0.94 Dice line".
  - Hidden: 0/6, all Dice 0.88–0.94.
- **Opus R3 (0.167; 35.1 of 60 min).**
  - A 2D U-Net at 1.25 mm, with the mid-training checkpoint shipped as a fallback. Fine-tuning on all eight cases was
    done while "current model remains in the pipeline as fallback". Hold-out Dice was 0.937.
  - **The only attempt that planned against the clock.** "Training is running (21 min …)", followed by a wait
    written as `until [ "$(date +%M)" -ge 21 ]`.
  - Hidden: 1/6, other cases near misses.
- **Sonnet R2 (0.000; 35.2 of 60 min).**
  - A 3D U-Net at 3 mm. On a 6/2 hold-out, Dice was 0.923 and 0.924, both below the bar.
  - It then trained a final model on all eight for about 23 minutes and spent that time in wait loops.
  - "I stopped here because of the 60-minute limit." This was said at 35 of 60 minutes. It printed `date` many times
    but had no start time to compare with.
  - Hidden: 0/6.
- **Sonnet R3 (0.167; first answer at 27.5 of 60 min).**
  - A classical threshold segmenter, then a small 3D U-Net at 4 mm. `run.sh` was in place only at 6 minutes.
  - Two-case hold-out: Dice 0.874 and 0.910. It warned "Expect some hidden cases to fail."
  - Hidden: 1/6. hid_8298 got Dice 0.000 (wrong structure).

### Fetal head
- **Opus R2 (0.855; 8.0 of 45 min).**
  - A pixel-size baseline `run.sh` was in place at 7 s.
  - Method: a gradient-boosted edge classifier and a RANSAC ellipse gave 80 % CV ("Shipping it now, then
    improving."). An aspect limit and a ×1.012 factor raised it to 88 % CV. It tested as `nobody` with an empty
    `HOME`.
  - Ending: "about 88% … just under the task's 90% bar … The obvious next step would be a second pass that crops
    around the first ellipse … I didn't have time to try it." 37 minutes were left.
- **Opus R3 (0.675; 8.1 of 45 min).**
  - "Baseline first … put in place immediately."
  - Method: a three-stage gradient-boosted inside-head cascade and an ellipse fit: 58.6 % 5-fold CV.
  - Ending: "it probably won't reach the 90% target … I stopped there because of the session limit." This was said at
    8 of 45 minutes.
- **Sonnet R2 (0.855; 7.2 of 45 min).**
  - `run.sh` and an ExtraTrees skull-ring classifier came in the second tool call.
  - It tuned a size-preference weight by hand on a 52-case hold-out (38 % → 79 %), retrained on all 152 cases, and
    timed one case.
  - Ending: "The error rate is still above the 90% bar, so don't expect it to meet that." It gave no reason for
    stopping.
- **Sonnet R3 (0.892; 32.5 of 45 min, the longest fetal-head session in R).**
  - Four classical attempts scored 10–41 % CV. It then built a gradient-boosted skull-outline classifier.
  - **Degraded window.** For 21 minutes the live `hc.py` loaded a `model.pkl` that did not exist yet. Its
    `try/except` fell back to `1300 × pixel size`, so the pipeline stayed valid but crude.
  - About 13 minutes went on waiting for slow training.
  - Ending: it added a ×1.035 factor chosen on the same 52 hold-out images ("about 90%"). "I did not retrain on all
    152 cases because training was slow and I was running short on time." 12 minutes were left.

### ECG (control)
- **Opus R2 (1.000; 12.8 of 30 min).** Four seeds, trained on folds 1–6 and calibrated and checked on folds 7–8. The
  fold 7–8 check gave MI sensitivity 0.818, which was 0.713 hidden.
- **Opus R3 (0.000; 7.3 of 30 min).**
  - A one-epoch model made `run.sh` work at about 1 minute ("Make a working run.sh now with the 1-epoch model as a
    fallback.").
  - Three seeds, calibrated on fold 8. Fold-8 MI sensitivity was 0.774, and it named MI as "the least room … the
    7-point margin is not a guarantee".
  - Hidden: MI sensitivity 0.693, failing the 0.70 gate.
- **Sonnet R2 (1.000; three result events, 11.5 of 30 min).**
  - It ended its turn twice while training ran in the background ("Waiting for training to finish.") and was woken
    each time by Claude Code's background-task notice. It also accidentally started a duplicate training run and
    killed one.
  - `run.sh` existed throughout. It did not check subgroups.
- **Sonnet R3 (1.000; 7.6 of 30 min).** Two seeds and Platt calibration. It did not measure the subgroup part. The
  training script wrote weights into the live pipeline folder.

### ICU (control)
- **Opus R2 (1.000; 2.2 min) and R3 (1.000; 4.2 min).**
  - Both wrote unit repairs in their first code (FiO2 as a percentage, pH ×10/×100, °F; R3 also height in inches).
    This is the same method-level familiarity with PhysioNet 2012 noted in run 2.
  - Both used a boosted-tree ensemble with logistic recalibration on out-of-fold predictions. Both checked all four
    gate parts; R3 also used three 70/30 splits.
- **Sonnet R2 (1.000; 1.2 min, 3 turns) and R3 (1.000; 1.5 min, 4 turns).** One-shot boosted trees and recalibration.
  Neither computed every gate part (R2 skipped AUROC by sex; R3 skipped calibration slope and net benefit).

### Session use, endings and time

- **Session used.** Under 60 % in 19 of 20 new attempts. The exception is Sonnet hc18 R3 (72 %); next are Opus spleen
  R3 and Sonnet spleen R2 (59 % each).
- **Below the bar.** In 11 of the 12 new per-case attempts (registration, spleen, fetal head), the agent's final
  message said its own development results were below the clinical bar overall or on some cases. The exception is
  Sonnet hc18 R3, which estimated about 90 %. In the cohort tasks, every agent reported its checked gate parts as
  met.
- **Elapsed time.** At least five agents described running out of time when most of the session was left:

| Attempt | Said | Minutes used / limit |
|---|---|---|
| Opus hc18 R3 | "I stopped there because of the session limit." | 8.1 / 45 |
| Opus hc18 R2 | "I didn't have time to try it." | 8.0 / 45 |
| Opus reg R2 | "I ran out of session time before closing it." | 14.5 / 45 |
| Opus reg R3 | "I didn't try a fully deformable registration in the time available." | 14.0 / 45 |
| Sonnet spleen R2 | "I stopped here because of the 60-minute limit." | 35.2 / 60 |

- **No clock.** Claude Code shows no clock, and the instruction gives the limit but not the start time. Only one new
  attempt (Opus spleen R3) planned against the clock.
- **Inference (not verified).** We read this as agents misjudging elapsed time, not as a hard limit. The K variant
  tests a related idea, an explicit instruction not to stop while below the bar. It did not change the endings (see
  `hosted-keepworking1.md`).

## Incidents

- **No infrastructure incidents** and no relaunches. `run errors` reports "No current error messages recorded" for
  all four runs. Image builds took 0.7–12 s (cached).
- **Our collector bug, fixed before any analysis.** Our first collection script looked for the carried pipeline at
  `artifacts/workspace/output/pipeline`, but Valkyrie unpacks it to `artifacts/workspace/output/output/pipeline`, as
  in run 2. The first regrades were skipped and were then run once each. One regrade was interrupted by our own
  monitor's timeout, deleted and rerun. Hosted results were not affected.
- **Non-deterministic agent pipeline** (Sonnet hc18 R3), described above. The hosted grade is used.
- **Three attempts had more than one result event**, each when a background job woke the session after the agent
  ended its turn: Sonnet ECG R2 (three), and Sonnet spleen R3 and Opus hc18 R1 (two each). Costs are cumulative, and
  the last value is used.

## Limitations

- **Three attempts per cell.** The means and ranges are descriptive.
  - Registration and spleen have 6 hidden cases (S = 4 and 3), so their per-attempt verdicts are coarse.
  - For fetal head, with S = 83, every attempt's interval is clear of 0.
- **Effort** is Claude Code's default; the bundle passes no `--effort` (`hosted-agents2.md`, "Our bugs" 1).
- **Regrade environments** are as in run 2: exact pins for reg, hc18 and ICU; approximate for ECG and spleen. All
  rewards matched except the non-deterministic case above.
- **Specialist runtime** was measured on the export host and is not used.
- **Development-set estimates.** Agents' own estimates were often tuned on their own validation cases. Opus ECG R2:
  fold 7–8 MI 0.818, hidden 0.713. Opus registration R3: dev 3/4, hidden 1/6.

## Cost

| Item | Opus | Sonnet | Total |
|---|---|---|---|
| API, 10 new attempts per model (Claude Code `total_cost_usd`, list price) | $4.451 | $2.150 | **$6.602** |
| API, run 2 (already reported) | $2.746 | $1.021 | $3.766 |
| Modal | not reported by Valkyrie (`run fetch`, `run results` and `run task` have no cost field) | | |

Summed `sandbox_run_duration` over the 20 new tasks is 19,762 s (about 5.5 h). The Modal dashboard is needed for the
actual Modal cost.
