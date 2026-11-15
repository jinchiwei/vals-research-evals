# Round 3: results against the preregistration

Written 2026-11-15 by a Claude Code worker for the coordinator (model: Claude Opus 5.5, `claude-opus-5-5`).
The preregistration is [round3-prereg.md](round3-prereg.md) (00:50 EST, before any round-3 run). Every number
below is copied from the workstream documents linked in each row; nothing was recomputed here.

## What was registered and what happened

| ID | Registered | Done | Result | Source |
|---|---|---|---|---|
| R | 2 more full runs per model of `suite/clinical-v1@2`, pooled with run 2 as 3 attempts | 4 runs, 20 attempts, all graded; no infrastructure failure, no relaunch | Gap shown in 3 of 3 attempts on fetal head (both models) and registration (Sonnet); 1 of 3 on Opus registration, Opus spleen, Sonnet spleen and Opus ECG; 0 of 3 on ICU (both) and Sonnet ECG. Agents still ended their turn early (19 of 20 new attempts used under 60 % of the session). | [hosted-agents3.md](hosted-agents3.md) |
| K | Fetal head plus one "keep working while below the bar" paragraph, 3 attempts per model, never pooled with R | `suite/hc18-keepworking-v1@1`, 6 attempts, all graded | All 6 ended their turn below the bar by their own estimate (23–35 of 45 minutes left); gap shown in 6 of 6. Mean reward Opus 0.695 (R 0.651), Sonnet 0.651 (R 0.839); differences are within attempt-to-attempt spread. | [hosted-keepworking1.md](hosted-keepworking1.md) |
| K2 | Addendum (02:15 EST, after R and K results): K plus a "check the clock" paragraph, 3 attempts per model, never pooled | `suite/hc18-clockcheck-v1@1`; oracle reward 0.759 as expected; 6 attempts, all graded | Every agent checked the clock and stated the time correctly; none claimed to be out of time. All 6 still stopped below the bar by their own estimate, with 8–31 minutes left. Mean reward Opus 0.799 (K 0.695, R 0.651), Sonnet 0.542 (one 0 from 2 images over the 10 s limit after a last-minute speed change). Gap shown in 6 of 6. | [hosted-clockcheck1.md](hosted-clockcheck1.md) |
| C | Treatment effect with interval on semi-synthetic data with known truth; oracle check, 1 attempt per model, 2 more if time allowed | `suite/causal-v1@1`; oracle reward 1.0; 3 attempts per model (decided by the clock at 01:29, before any result) | Control: the specialist (47/48 coverage) and all 6 agent attempts (48/48) meet all four gate parts. | [causal_ate.md](causal_ate.md) |
| V | CHASE_DB1 retinal vessels, second human observer as the bar; oracle check, 1 attempt per model | `suite/vessel-v1@1`; oracle reward 0.75 as expected | Scored family (specialist U-Net 6 of 8 images). Opus 5 of 8, Sonnet 4 of 8; no gap shown for either (pass-difference intervals reach 0 with 6 images in S). | [seg_vessel.md](seg_vessel.md) |
| T | PTB-XL report text to diagnostic superclasses, direct-answer contract, control; oracle check, 1 attempt per model | `suite/report-label-v1@1`; oracle reward 0 as expected | Excluded from scoring: no comparator met the gate. Agents reported descriptively: Opus macro F1 0.790 (specialist 0.735; paired difference +0.055, +0.025 to +0.086) but 0.01 short of the 0.80 bar; Sonnet 0.757. | [label_ptbxl_reports.md](label_ptbxl_reports.md) |

Budget rule: stop if round-3 API spend passed $60. Round-3 spend is $17.10 (R $6.60, K2 $5.11, K $2.73,
C $1.26, V $1.01, T $0.39), plus model calls the T agents made from inside the sandbox, which Claude Code does not count
(Opus said "about $0.16", unverified; Sonnet not recorded).

## Deviations from the preregistration, and other changes

1. **T excluded before any agent attempt** (01:35 EST, recorded in the prereg). Neither comparator met the gate
   (specialist macro F1 0.735, worst kappa 0.477; keyword rules 0.757, 0.579). The gate was not changed; the two
   registered agent attempts still ran and are descriptive only.
2. **K2 was added after R and K results were seen.** It is a new task version with its own addendum and is never
   pooled with K or R. The addendum header says 02:15 EST; the K2 oracle run started at 02:11:51 and the worker's
   prespecification (`exp/suite-hosted-clockcheck1/prespec.txt`, about 02:12) says the addendum text was already in
   the file at about 02:07. No K2 agent attempt started before 02:17.
3. **C does not use ACIC data.** The prereg said "ACIC family". ACIC 2016 and 2017 ship the IHDP covariates, whose
   ICPSR terms forbid redistribution; ACIC 2019 states no licence; ACIC 2022 needs a sign-up. C therefore uses an
   ACIC-2016-style data-generating process of our own over PhysioNet 2012 covariates (ODC-By 1.0). The estimand is
   the treatment effect on the treated (SATT), as in ACIC 2016.
4. **C contract.** `run.sh` is called once on all 48 hidden datasets instead of once per dataset, because the
   coverage gate is defined over the set (per-dataset grading would let infinite intervals score 1). The time
   limit is still stated per dataset (20 s × 48 = 960 s).
5. **C comparator.** TMLE (targeted maximum likelihood estimation) was planned as a comparator but not run: no
   offline implementation was available in the project environment.
6. **C instruction names the specialist's method** ("cross-fitted doubly robust (AIPW) specialist estimator"), as
   every family's instruction names its comparator. All six attempts built that method and widened its interval
   by a factor tuned on the development data. This makes C easier than intended.
7. **K paragraph placement.** The prereg fixed the text, not the position. It was appended as the last paragraph,
   after the two sections that state the bar. Data, grader and every other file are byte-identical to
   `suite/clinical-v1@2` (checked by `tests/suite/test_hc18_keepworking.py`).
8. **T agents delegated labelling to model API calls** from Python scripts inside the sandbox (Opus called
   `claude-opus-5-5`, Sonnet called `claude-haiku-5-5`). The network policy allows `api.anthropic.com`, so this
   is within the rules as written, but it was not anticipated and its cost is outside Claude Code's figure.
9. **V family bar.** Fixed in `seg_vessel.md` section 0 before any comparator run: the family is scored only if
   the specialist passes at least 4 of 8 hidden images. It passed 6. A grader bug (PIL 1-bit images crashing
   `skimage` skeletonize) was fixed before export.
10. **K2 launcher slot limit (our bug, recorded before any K2 result).** The prespecification allowed at most 4
    K2 runs active at once; the launcher read the run list with the wrong key, so all six started between 02:17
    and 02:20 EST. They were the only active runs then (6 of the organisation's 10), so C and V were not delayed.
    No run was stopped; every attempt counts.
11. **Run-slot waits.** The organisation's cap of 10 active runs refused several starts (V oracle, C Opus attempt 1);
    each was retried, with no run created by the refused starts and nothing relaunched.

## What did not change

Datasets, hidden cases, graders, time limits, agent (`claude_code_noweb-v1.0.0`, Claude Code 2.1.325), models,
$8 cap and default effort are as in run 2 for R and K. No attempt was rerun for a better number. No UCSF data was
used. No web tool was offered or used in any round-3 trace.
