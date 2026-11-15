# Round 3: preregistration

Written 2026-11-15 00:50 EST by the coordinator, before any round-3 run. Demos are Sunday 2 PM.
Nothing below may change after a result is seen; anything that does change is recorded at the
bottom with the reason and the time.

## Why round 3

Hosted run 2 (`suite/clinical-v1@2`) gave one attempt per task and model. Judges will ask three
things it cannot answer: how much one attempt varies, whether the early stopping is a capability
limit or an instruction effect, and whether the suite covers more than imaging and cohort risk.

## Workstreams

| ID | What | Dataset | Attempts, fixed now |
|---|---|---|---|
| R | Repeats of the headline suite, unchanged | `suite/clinical-v1@2` (tag `instr2`) | 2 more full runs per model (Opus 5.5, Sonnet 5.5), giving 3 attempts per task and model with run 2 |
| K | "Keep working" variant of fetal head | new version, `measure_hc18` only | 3 attempts per model |
| C | Causal inference: treatment effect with interval on semi-synthetic data with known truth (ACIC family) | new dataset | hosted oracle check, then 1 attempt per model; 2 more per model if time allows (decided by clock, not by results) |
| V | Retinal vessel segmentation, CHASE_DB1, second human observer as reference bar | new dataset | hosted oracle check, then 1 attempt per model |
| T | Report-label control: PTB-XL free-text ECG reports to diagnostic superclasses (human-validated records only) | new dataset | hosted oracle check, then 1 attempt per model |

All agent runs use `claude_code_noweb-v1.0.0`, models `anthropic/claude-opus-5-5` and
`anthropic/claude-sonnet-5-5`, provider Modal, the same $8 per-attempt budget cap and Claude Code's
default effort, as in run 2.

## Rules

- Every attempt counts. Nothing is rerun for a better number. An infrastructure failure (no agent
  turn recorded, sandbox never started) may be relaunched once and is reported as such.
- Run 2 and round-3 repeats (R) are pooled as attempts 1–3 of the same task version. K is a
  different task version and is never pooled with R; it is compared with the 3 R attempts on fetal
  head.
- K changes only the instruction: one added paragraph telling the agent that its own validation
  below the clinical bar is a reason to keep improving within the session. Data, hidden cases,
  grader, limits and specialist are identical to `measure_hc18` in `suite/clinical-v1@2`. The
  added paragraph, fixed now:

  > **Using your session time.** Your session ends when you end your turn, and the pipeline is
  > then graded as found. If your own validation on the development cases is below the clinical bar
  > stated above, that is a reason to keep improving the pipeline, not to stop: use the remaining
  > session time to try better methods and re-validate, and keep the best working pipeline in place
  > at all times.
- New families (C, V, T): thresholds, time limits, splits and comparators are fixed and written in
  the family document before any agent attempt, with sources. The gap rule is DESIGN.md's. If no
  comparator passes, the family is excluded from scoring (as pharyngitis was).
- T is a control by design: frontier models label radiology-style reports near human agreement
  (Jin's ARIA report benchmark, 27 models, best kappa 0.72). It uses a direct-answer contract
  (agent writes labels for given reports; labels hidden) rather than the pipeline contract, and is
  reported separately for that reason.
- No UCSF data anywhere in round 3.
- Budget: stop and report if round-3 API spend passes $60 (run 2 cost $3.77).

## Addendum K2, registered 02:15 EST after R and K results (a new, separately reported version)

R and K showed agents ending their turn below the bar while saying they had run out of time at
8–15 of 45 minutes; no fetal head attempt checked the clock. K2 tests whether a clock check changes
this. It is `measure_hc18` exactly as in K, with this paragraph added after the K paragraph:

> **Checking the time.** Run `date` at the start of your session and note the time. Before you end
> your turn, run `date` again and work out how much of the session remains. Do not end your turn
> because you believe time is short without checking.

Fixed now: 3 attempts per model, same agent, models, provider and caps. Compared with K and R on
fetal head; never pooled with either. Run only if org run slots allow without delaying C and V.

## Changes after registration

- 01:35 EST, before any T agent attempt: neither T comparator met the gate on the hidden reports
  (TF-IDF + logistic regression macro F1 0.735, worst kappa 0.477; keyword rules macro F1 0.757,
  worst kappa 0.579), so T is excluded from scoring as registered. The cause is label noise: identical
  report text carries different labels in 6.7% of repeated development texts. The two registered T
  agent attempts still run, reported descriptively and outside the scored suite. No gate change; a
  ceiling-based gate would be a new task version after the demo.
