# Hosted clock-check variant (K2): fetal head circumference, K plus a "check the time" paragraph

Written 2026-11-15 by a Claude Code worker for the coordinator (model: **Claude Opus 5.5, `claude-opus-5-5`**).
Addendum K2 of `round3-prereg.md`. Machine-readable values: [`hosted-clockcheck1.json`](hosted-clockcheck1.json)
(K2 attempts plus the R and K rows used for comparison). Raw evidence: `exp/suite-hosted-clockcheck1/`
(git-ignored, 272 MB).

K2, K ([`hosted-keepworking1.md`](hosted-keepworking1.md)) and R ([`hosted-agents3.md`](hosted-agents3.md)) are
three different task versions. They are compared here and **never pooled**.

## Summary

- **Every K2 agent checked the clock as told.**
  - All six ran `date` in their first tool call. Each read the clock 4–14 times in total, and the last read was
    0.1–0.3 minutes before the session ended.
  - Every statement about time in their final messages was correct. None claimed to be out of time.
- **Sessions got much longer.**
  - Opus used 60–82 % of the session (K: 33–49 %, R: 18–44 %).
  - Sonnet used 32–76 % (K: 22–44 %, R: 16–72 %).
  - Two agents used the clock to plan: "About 20 minutes are left, so I'll try one cheap variance-reduction step"
    (Opus K2-2).
- **They still all stopped below the bar, now knowingly.** Each final message gives an own estimate of 78–90 % and
  the remaining time, which was 8–31 minutes. Examples:
  - "I stopped with about 18 of the 45 minutes left rather than make untested changes to a working pipeline"
    (Opus K2-3);
  - "About 15 minutes of the 45 are used, but I'm stopping here" (Sonnet K2-2).
- **Opus reward rose and narrowed.** K2 rewards were 0.783, 0.807 and 0.807, mean 0.799. K was 0.695 (0.651–0.747)
  and R was 0.651 (0.422–0.855). With three attempts per arm this is descriptive only.
- **Sonnet: one K2 attempt scored 0 on timing.** Sonnet K2-1 made a last-minute speed change, and 2 of 83 hidden
  images ran past the 10 s limit on the hosted grader (6.8 and 7.5 s locally), so its reward is 0. Its clinically
  acceptable fraction was 0.795.
  - Sonnet K2 rewards: 0.000, 0.843 and 0.783; mean 0.542, or 0.807 for clinically acceptable.
  - Sonnet K was 0.651 and R 0.839.
- **Gap shown in 6 of 6 K2 attempts.** The specialist is within tolerance on 83 of 83 images; agents scored 65–70.
- **API cost of K2: $5.11** (Opus $3.41, Sonnet $1.70). The oracle cost no API. Longer sessions cost more.

## What changed, and only that

The paragraph registered in addendum K2 was added verbatim directly after the K paragraph, at the end of
`instruction.md`:

> **Checking the time.** Run `date` at the start of your session and note the time. Before you end
> your turn, run `date` again and work out how much of the session remains. Do not end your turn
> because you believe time is short without checking.

- **Build.** `scripts/export_hc18_keepworking.py --clock-check --out dist/suite-tasks-k2` uses the same
  `build_spec` and `export_task` as K, then appends both paragraphs. `suite/core/export.py` is unchanged.
- **Diff against K.** `diff -rq -x __pycache__ dist/suite-tasks-k1/measure_hc18 dist/suite-tasks-k2/measure_hc18`
  lists only `instruction.md`, which gains one blank line and the paragraph.
- **Tests.** `tests/suite/test_hc18_keepworking.py` gained 3 tests, and all 7 pass:
  - the paragraph equals the addendum blockquote;
  - it is appended once, after the K paragraph, and only when K is present;
  - every k2 file except `instruction.md` has the same SHA-256 as k1.
- **What the agents saw.** Each attempt's `task_prompt` equals the k2 `instruction.md`.
- **Validation and push.**
  - `validate_exports.py`: problems `[]`.
  - Push → **`suite/hc18-clockcheck-v1@1`**, digest `11aa6e43ada3`, tags `k2` and `latest`.
- **Oracle.** Run `8b8782de-d8d4-4f17-811f-81b80d322122` finished with no errors, reward **0.7590**. All seven keys
  equal the v3 and k1 oracle runs.

## Attempts (`exp/suite-hosted-clockcheck1/prespec.txt`)

| Attempt | Run id | Label |
|---|---|---|
| Opus K2-1 | `42343602-d6f5-449a-bfcc-7339a37f78ba` | hosted-clockcheck1a-opus |
| Opus K2-2 | `6d6a9980-29f1-4343-b812-d97a0b289aca` | hosted-clockcheck1b-opus |
| Opus K2-3 | `8d248879-6e7a-4fed-adf4-b363c4423732` | hosted-clockcheck1c-opus |
| Sonnet K2-1 | `964a63e9-a12f-43eb-8cc5-6aee20834905` | hosted-clockcheck1a-sonnet |
| Sonnet K2-2 | `36830d5f-f8e0-4047-b062-bca7ee5d5cc0` | hosted-clockcheck1b-sonnet |
| Sonnet K2-3 | `e8e49d18-baa8-4579-a9f5-56a24ce7f515` | hosted-clockcheck1c-sonnet |

- **Setup.** The agent, models, provider, caps and secret were the same as K: concurrency 1, one run per attempt.
- **Outcome.** All six finished with verifier exit 0 and no run errors. There was no infrastructure failure and
  nothing was relaunched.
- **Deviation from the slot limit (our bug, recorded before any result).**
  - The launcher read the `run list` JSON with the wrong key, so its "at most 4 active" check always saw 0, and all
    six started between 02:17 and 02:20 EST.
  - At that moment they were the only active runs in the organisation (6 of the 10-run cap), so C and V could still
    start 4 runs.
  - The runs were not stopped (every attempt counts), and the parser is fixed.
- **Collection and regrade** were done as in K, with each pipeline regraded locally against `dist/suite-tasks-k2`.
  All seven keys match the hosted grade in 5 of 6 attempts. For Sonnet K2-1, see below.

## Results: K2 against K and R on fetal head (never pooled)

The bar is at least 90 % of the 83 hidden images within 4.9 %.

**Columns.**
- Session used is the agent process time over 2700 s.
- Clock reads count every tool output that showed the wall-clock time from `date`.
- MAE and median error come from the local regrade.

| Model | Attempt | reward (n/83 acceptable) | MAE / median (mm) | Session used | Clock reads (first; last before end) | Own estimate at stop | Said about time at the end (actual minutes left) | Gap | API cost |
|---|---|---|---|---|---|---|---|---|---|
| Opus | K2-1 | 0.783 (65) | 8.8 / 2.7 | 82 % | 14 (0.1 min; 0.1 min) | CV "about 78%" | "The session ended at 07:55, about 8 minutes before the limit." (8.1) | gap | $0.966 |
| Opus | K2-2 | 0.807 (67) | 7.1 / 3.1 | 63 % | 9 (0.1; 0.2) | CV 85.5 % | "The last time check was 07:47, about 28 minutes into the 45-minute session." (16.7) | gap | $1.288 |
| Opus | K2-3 | 0.807 (67) | 9.4 / 3.0 | 60 % | 9 (0.1; 0.2) | CV "about 82–84%" | "I stopped with about 18 of the 45 minutes left rather than make untested changes to a working pipeline." (17.8) | gap | $1.155 |
| Sonnet | K2-1 | **0.000** (66; 2 images timed out) | 9.7 / 3.3 | 76 % | 8 (0.0; 0.3) | CV 87.5 % (before two untested last edits) | "I stopped at about 35 of the 45 minutes." (10.6) | gap | $0.666 |
| Sonnet | K2-2 | 0.843 (70) | 11.8 / 3.5 | 32 % | 4 (0.0; 0.1) | hold-out "about 88–90%", "isn't a safe pass" | "About 15 minutes of the 45 are used, but I'm stopping here." (30.6) | gap | $0.420 |
| Sonnet | K2-3 | 0.783 (65) | 9.8 / 3.1 | 67 % | 7 (0.0; 0.1) | 2-fold CV "around 80%" | "About 15 minutes of the session were left when I did." (14.9) | gap | $0.614 |

| Model | Arm | Rewards | Mean reward | Mean clin. acceptable | Session used | Stopped below bar (own estimate) | Gap shown | API cost |
|---|---|---|---|---|---|---|---|---|
| Opus | R | 0.422, 0.855, 0.675 | 0.651 | 0.651 | 44, 18, 18 % | 3 of 3 | 3 of 3 | $1.55 |
| Opus | K | 0.687, 0.747, 0.651 | 0.695 | 0.695 | 33, 49, 35 % | 3 of 3 | 3 of 3 | $1.64 |
| Opus | **K2** | 0.783, 0.807, 0.807 | **0.799** | 0.799 | **82, 63, 60 %** | 3 of 3 | 3 of 3 | $3.41 |
| Sonnet | R | 0.771, 0.855, 0.892 | 0.839 | 0.839 | 24, 16, 72 % | 2 of 3 | 3 of 3 | $1.08 |
| Sonnet | K | 0.831, 0.494, 0.627 | 0.651 | 0.651 | 44, 22, 24 % | 3 of 3 | 3 of 3 | $1.09 |
| Sonnet | **K2** | 0.000, 0.843, 0.783 | **0.542** | 0.807 | **76, 32, 67 %** | 3 of 3 (K2-2 "at or just under") | 3 of 3 | $1.70 |

All K2 gap intervals (paired bootstrap of per-image pass, agent minus specialist) lie below 0, from −0.22 (−0.30 to
−0.12) to −0.16 (−0.23 to −0.08). The values are in the JSON.

### Sonnet K2-1: a timing failure, not an accuracy failure
- **What the hosted grader saw.** `case_809204` and `case_a9526f` were killed at 10.01 s (timeout), so `ran`,
  `valid` and `within_time` are each 81/83 = 0.976. A single late image makes the reward 0, and the instruction
  states that rule.
- **Local regrade.** The same pipeline ran these two images in 6.8 and 7.5 s, scored 68/83 and gave a reward of
  0.819.
- **Hosted times overall.** Per-image times were slower on the hosted grader (median 3.4 s, against 2.2 s locally),
  and six images took over 8 s.
- **The agent saw the risk.**
  - In its last 30 seconds it changed the fit to a faster setting and added an untested ×1.07 correction for small
    heads.
  - It timed two cases (4.0 and 5.9 s) and wrote: "The 10 s limit is measured on the grader's machine, so I can't
    promise the margin holds."
- **Verdict.** We count this as the agent's result (gap shown, with the two images as fails), as the prespec says.
  It is not an infrastructure failure: the grader ran and the limit is stated.
- **Our inference.** We infer that the extra session time encouraged a slower, multi-pass pipeline without a
  timeout guard. This is not verified. Opus K2-1 and K2-3, by contrast, added an 8.5 s kill-and-fallback in `run.sh`.

## Trace findings

All six traces were read in full (`exp/suite-hosted-clockcheck1/<model>-k2<a|b|c>/trace-measure-hc18-0001.txt`). The
clock reads were extracted with `exp/suite-hosted-clockcheck1/clock.py`.

**Common to all six:**
- No web tools were offered or used, nothing network-like was found in tool input, and no subagent was used.
- Claude Code 2.1.325 was used throughout.
- Each attempt ended with one `success` result, by the agent's own choice.
- **Clock use.** All six ran `date` in their first tool call, kept reading it during the work, and read it again just
  before ending. They converted it correctly to time used or left.
- **No false time claims.** No agent claimed to be out of time. The R and K pattern ("ran out of session time" at
  8–15 of 45 minutes) did not appear.

### Opus K2-1 (0.783; 36.9 of 45 min)
- A fallback `run.sh` was in place at 6 s.
- **Method.** A two-stage RF segmentation with an ellipse fit gave 55 % CV ("far below the 90% bar"). A ray-based
  skull refinement raised it to 74 %, and two passes reached 78 %.
- **Speed and safety.** It profiled run time and switched to an uncompressed model (load time 0.6 s instead of
  2.1 s). `run.sh` kills Python at 8.5 s and keeps a first estimate.
- **Use of the clock.** "About 12 minutes are left, enough for one more quick test" (at 32.5 min). It ended at
  36.9 min: "does not reach the 90% clinical bar … about 78%".

### Opus K2-2 (0.807; 28.3 min)
- **Method.** A region classifier gave 57 %, ray refinement 70 %, and steepest-descent outer-edge detection 84 %.
  The final version reports the median of three refinement configurations.
- **Use of the clock.** "About 20 minutes are left, so I'll try one cheap variance-reduction step."
- **Checks.** It ran all 152 development cases and a clean `env -i` run with an empty `HOME`.
- **Ending.** "still below the 90% bar: about 85% within tolerance", with 16.7 minutes left.

### Opus K2-3 (0.807; 27.2 min)
- **Method.** Mask plus refinement gave 69 % ("Deploying it now, then improving"), auto-context stage 2 gave 82 %,
  and smoothing σ = 2 gave 84 %.
- **Dropped.** A pixel-size feature, a third stage, a zoomed second pass and multi-start ellipses.
- **Safety.** It added an 8.5 s timeout guard and tested as an unprivileged user from a fresh copy.
- **Ending.** It chose to stop: "I stopped with about 18 of the 45 minutes left rather than make untested changes
  to a working pipeline."

### Sonnet K2-1 (hosted 0.000, 66/83 acceptable; 34.4 min)
- `run.sh` was written at about 10 minutes (from the trace dump).
- **Method.** A ring classifier and ring search, trying four assumed head sizes: 87.5 % in 3-fold CV.
- **Last 30 seconds.** Two untested edits (described above).
- **Ending.** "about 87 %, which is below the 90 % bar. I stopped at about 35 of the 45 minutes."

### Sonnet K2-2 (0.843; 14.4 min)
- Four clock reads, the last 0.1 minutes before the end.
- **Method.** A two-stage gradient-boosted ring classifier at 0.4 mm per pixel, a random-search plus Nelder–Mead
  ellipse, and a ÷0.964 calibration. Its 42-case hold-out gave 88–90 %, tuned on the same 42 cases.
- **Ending.** It stopped with the most time left of any K2 attempt, knowingly: "About 15 minutes of the 45 are
  used, but I'm stopping here. The remaining gap is first-trimester heads, which I didn't find a quick fix for."

### Sonnet K2-3 (0.783; 30.1 min)
- **Method.** A skull-outline classifier at 1.2 mm per pixel and an ellipse search, ×1.028: about 80 % in 2-fold CV.
- **Dropped.** A finer second pass, a filled-head term and resampled training.
- **Ending.** "under the 90% bar, and I stopped there. About 15 minutes of the session were left when I did."

## Interpretation

1. **The time misjudgement in R and K was real, and a clock check removed it.** No K2 agent made a false claim about
   time. Sessions lengthened from about a third to about two-thirds of the limit.
2. **Knowing the time did not make agents use all of it.** With accurate knowledge of 8–31 remaining minutes, all
   six still ended below the bar. The reasons they gave were:
   - no quick fix left (Sonnet K2-2);
   - risk of breaking a working pipeline (Opus K2-3);
   - a plain stop (the rest).
   This looks like a stopping rule of the agents' own, not a misperception.
3. **The extra time bought a little accuracy and some risk.**
   - **Opus.** All three K2 rewards (0.78–0.81) are above every K reward, and above two of the three R rewards.
   - **Sonnet.** Its clinically acceptable fractions (0.78–0.84) are similar to R. One attempt lost everything to two
     late images.
   - **Small samples.** n = 3 per arm, so none of this is a tested difference.

## Limitations

- Three attempts per arm, one task, default effort.
- The "own estimate" and "stopped below bar" columns are our reading of each final message.
- Session time is agent process time; queueing (about 1 minute) is excluded.
- Hosted grader timing is slower and more variable than our local regrade. We report it but do not correct it.
- Modal cost is not reported by Valkyrie. Summed `sandbox_run_duration` for the six K2 attempts is 12,182 s
  (about 3.4 h), plus the oracle run.

## Cost

| Item | Opus | Sonnet | Total |
|---|---|---|---|
| API (Claude Code `total_cost_usd`, list price) | $3.409 (K2-1 $0.966, K2-2 $1.288, K2-3 $1.155) | $1.700 ($0.666, $0.420, $0.614) | **$5.109** |
| Oracle | $0 API | | |

## Files

- Changed: `scripts/export_hc18_keepworking.py` (new `--clock-check` option; the default K export is unchanged),
  and `tests/suite/test_hc18_keepworking.py` (3 new tests).
- New: this file and `hosted-clockcheck1.json`.
- Generated, not in Git: `dist/suite-tasks-k2/`.
- Evidence (git-ignored): `exp/suite-hosted-clockcheck1/` holds the prespec (with the slot deviation), push and
  validation records, `oracle/`, the attempt folders, `results.json`, `clock.py`, `compare.py`, the launcher and the
  collector.
