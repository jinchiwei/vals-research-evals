# Instructions v3: session limit stated, two wording fixes (five scored tasks)

Written 2026-11-14 by a Claude Code worker (model: Claude Opus 5.5, `claude-opus-5-5`) for the
coordinator. No agent was run. No Git commit was made.

## Status of this version

**This is a new prespecified task version, created after pilot 1 because of our own instruction bug.**
Pilot 1 (`pilot1-results.md`) found that the agent-facing instruction never stated the agent's session
limit, nor that `/workspace/output/pipeline` is graded as found when the session ends (pilot 1, "Our
bugs" 1). The v3 export fixes that and two wording bugs (pilot 1, bugs 4 and 5). Nothing that is scored
changed: thresholds, splits, graders, comparator outputs and time limits are byte-identical to v2.

**Pilot 1 and the hosted run in progress on v2 are kept as recorded.** They were run on the v1/v2
instruction text and stay valid results for that text. They are not rerun, relabelled or replaced. Runs
on v3 are a separate set and are not pooled with v1/v2 runs without saying so.

## What changed and why

| # | Bug (pilot 1) | Fix | Files |
|---|---|---|---|
| 1 | Instruction omits the session limit and the "graded as found" rule; three of four pilot runs hit the limit, both reg_resect zeros were delivery failures at the deadline | The exporter puts a section **"Session limit and what is graded (read first)"** directly under the title of every `instruction.md` (both per-case and cohort). It states: the session limit in minutes and seconds, read from the same `FamilySpec.agent_timeout_sec` that the exporter writes to `task.toml` `[agent] timeout_sec`; that whatever is in `/workspace/output/pipeline/` when the session ends is graded exactly as found and that a missing or broken `run.sh` scores 0; a plain recommendation to put a working `run.sh` in place early and improve it afterwards; and the grader's pipeline time limit (per hidden case, or for the whole hidden set with the hard kill where there is one). No method hints. | `suite/core/export.py` (`session_minutes`, `pipeline_time_limit_text`, `session_section`, used by `instruction` and `_instruction_cohort`) |
| 2 | reg_resect: data README said `dev_predictions/`, `instruction.md` said `visible_predictions/` | README now says `/workspace/output/visible_predictions/`, the name the exporter uses for every task. seg_spleen had the same mismatch in its data README and was fixed the same way. Neither folder is scored. | `suite/families/reg_resect/README_agent.md`, `suite/families/seg_spleen/task/README.md` |
| 3 | measure_hc18: README said an invalid image "counts as a miss", then that the headline is 0 unless every image is valid | Validity bullet now matches the grader: one invalid image makes the headline reward 0, not one miss; in the reported quality that image scores 0. The grader was read, not changed: `suite.core.reward.scalar_reward` returns 0 unless `ran`, `valid` and `within_time` are all 1, and `measure_hc18.grader.grade_case` returns `quality 0.0` for an invalid image. | `suite/families/measure_hc18/task/README.md` |
| 4 | `summarize` labels quality as `agent_headline_raw` | Not edited (`suite/pilot/` and `scripts/` are out of scope). Interpretation below. | none |

### Bug 4: how to read `suite/pilot/pilot.py::summarize` output

- `agent_headline_raw` is **not** a raw value in mm, mL or seconds. It is the mean of the family's
  per-case `quality` score (0 to 1, higher better) over the hidden cases whose output was **valid**.
  Invalid cases are left out, so it can be higher than `reward.json` `quality`, which averages over every
  hidden case with 0 for an invalid one. It is `None` when no case was valid.
- `specialist_headline` is the specialist's `quality` averaged over **all** hidden cases. The two columns
  are only comparable when the agent had every case valid.
- The note line "headline = `<primary_metric>`" names the family's primary metric (e.g. reg_resect's
  mean TRE), but the number in the column is the 0-to-1 quality mapping of it, not the metric itself.
- Raw values are in `metrics.json`: per case under `cases[*].metrics` (e.g. TRE in mm for reg_resect,
  `abs_err_mm` for measure_hc18) and aggregated under `summary`. Pilot 1's tables already report raw
  values from there; only the `summary.md` column header is misleading.

## Instruction diff v2 → v3 (measure-hc18-0001)

Shows bugs 1 and 3. Every other task gets the same session section with its own numbers (below).

```diff
--- dist/suite-tasks-v2/measure_hc18/measure-hc18-0001/instruction.md
+++ dist/suite-tasks-v3/measure_hc18/measure-hc18-0001/instruction.md
@@ -1,5 +1,16 @@
 # Fetal head circumference in mm from 2D ultrasound (HC18)
 
+## Session limit and what is graded (read first)
+
+- **Your session lasts at most 45 minutes** (2700 seconds) of wall-clock
+  time. When the limit is reached the session is stopped, whether or not you have finished.
+- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
+  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
+  or does not work at that moment, the score is 0.
+- We recommend putting a working `run.sh` in place early and improving it afterwards.
+- Separately, the grader limits your pipeline to **10 seconds of wall-clock time per hidden case**
+  (details under "What you must leave behind" below).
+
 # Fetal head circumference from 2D ultrasound
 
 ## Why this matters
@@ -66,7 +77,8 @@
 - **Quality**: the mean over images of `max(0, 1 - |error mm| / 7.26)`. This is 0.5 at the
   inter-observer mean absolute difference on this dataset (3.6 mm) and 0 at twice that.
 - **Validity**: every image needs exactly one finite `hc_mm` between 40 and 400 mm. A missing row,
-  NaN, or a value in pixels or centimetres makes that image invalid, and it then counts as a miss.
+  NaN, or a value in pixels or centimetres makes that image invalid. A single invalid image makes the
+  headline reward 0 (see below), not just one miss; in the reported quality it scores 0.
 - **Time**: each image must finish within the limit.
 
 The headline reward is the fraction of hidden images that are clinically acceptable. It is zero
```

(The second H1 is the family README's own title; it was already there in v2.)

reg_resect data README (`environment/data/README.md`), bug 2:

```diff
-- Put any predictions you make on development cases in `/workspace/output/dev_predictions/` if you
+- Put any predictions you make on development cases in `/workspace/output/visible_predictions/` if you
```

Session-section numbers per task (from each task's own `task.toml` and `tests/task_config.json`):

| Task | Session (task.toml `[agent] timeout_sec`) | Pipeline limit stated |
|---|---|---|
| reg-resect-build-0001 | 45 min (2700 s) | 120 s per hidden case |
| seg-spleen-build-0001 | 60 min (3600 s) | 300 s per hidden case |
| measure-hc18-0001 | 45 min (2700 s) | 10 s per hidden case |
| ecg-ptbxl-superdiag-0001 | 30 min (1800 s) | 560 s for the whole hidden set; killed at 1120 s |
| risk-icu-mortality-0001 | 45 min (2700 s) | 300 s for the whole hidden set |

## Export

Driver (scratchpad, 20 lines): each family's own `build_spec` with work folders in the session
scratchpad, then `export_task(spec, <repo>/dist/suite-tasks-v3/<family>)`; `export_task` resolves every
path to absolute. reg_resect was given the v1 export's stored `tests/specialist/`, as for v2, so the
specialist was not rerun. Staged data under `/home/jkwei/data/vals-suite/` was only read.
`dist/suite-tasks/` and `dist/suite-tasks-v2/` were not touched.

`diff -rq -x __pycache__` of v2 against v3:

| Family | Files that differ |
|---|---|
| reg_resect, seg_spleen, measure_hc18 | `instruction.md`, `environment/data/README.md`, `solution/solve.sh` |
| ecg_ptbxl, risk_icu | `instruction.md`, `solution/solve.sh` |

`solve.sh` differs only because v2 carried the hosted-oracle1 operator egress probe, appended by hand
(`hosted-oracle1.md`); v3 has the exporter's plain `solve.sh`. Every data, hidden, reference,
specialist, grader, vendored-library, Dockerfile and solution-pipeline file is byte-identical to v2, and
so is every `task.toml`.

## Validation

| Check | reg_resect | seg_spleen | measure_hc18 | ecg_ptbxl | risk_icu |
|---|---|---|---|---|---|
| `check_no_leak` | pass | pass | pass | pass | pass |
| `check_taskconfig.py` (problems; separate verifier; agent allowlist; verifier no-network) | [] / yes / api.anthropic.com / yes | same | same | same | same |
| `validate_exports.py` (CLI 2026.11.12.2, SDK 0.34.0): problems | [] | [] | [] | [] | [] |
| Local `tests/grade.py` on `solution/pipeline` (family env, `--sandbox-root none`): reward | 0.6667 | 0.0 | 0.7590 | 0.0 | 1.0 |
| `oracle_expected_reward` | 0.6667 | 0.0 | 0.759 | 0.0 | 1.0 |
| Match | yes | yes | yes | yes | yes |
| Local grading wall time | 66 s | 116 s | 27 s | 10 s | 62 s |

All seven reward keys equal the v2 local grading (`hosted-oracle1.md`) for every task.
`validate_exports.py` printed "Validated and packed 5 tasks; no uploads performed." (the packed archives
were deleted afterwards).

Tests: new `tests/suite/test_export_session_limit.py` (16 tests): the section is the first H2 under
the title and precedes the task text, in both grading modes and for four timeouts; the stated minutes
and seconds equal `task.toml` `[agent] timeout_sec`; the "graded as found" and "run.sh early"
sentences; the pipeline limit (and hard kill); no method words; a real toy export; and every task in
`dist/suite-tasks-v3/` (the five scored families, each checked against its own `task.toml` and
`task_config.json`). `test_export_python_path.py`'s stub spec gained `agent_timeout_sec`.
`~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite -q`: **214 passed, 1 skipped** (the
existing openpyxl skip).

## Valkyrie dataset and oracle run

The CLI has no separate "tag only" upload: `dataset push` always publishes a new version of the named
dataset, and `--tag` adds a tag to it. So v3 is **version 2 of the same dataset**, tagged `instr2`.

```
$ .venv-valkyrie/bin/valkyrie dataset push suite/clinical-v1 dist/suite-tasks-v3 --tag instr2 --concurrency 2
✓ Uploaded seg-spleen-build-0001 (259,474,669 bytes)
✓ Uploaded reg-resect-build-0001 (509,426,359 bytes)
✓ Uploaded measure-hc18-0001 (30,157,480 bytes)
✓ Uploaded ecg-ptbxl-superdiag-0001 (155,147,376 bytes)
✓ Uploaded risk-icu-mortality-0001 (17,529,596 bytes)
✓ Published suite/clinical-v1@2: 5 task(s), 5 uploaded. Tags: instr2, latest.

$ .venv-valkyrie/bin/valkyrie dataset versions suite/clinical-v1
Version  Digest        Tasks  Tags            Published
2        f7d7cd08f525  5      instr2, latest  2026-11-14 20:24:24 EST
1        c755684595ed  5      oracle1         2026-11-14 19:32:37 EST
```

| Item | Value |
|---|---|
| Created | `suite/clinical-v1@2`, digest `f7d7cd08f525`, 5 tasks, tags `instr2` and `latest` |
| Unchanged | `suite/clinical-v1@1` (digest `c755684595ed`, tag `oracle1`): the v2 tasks, still addressable as `@1` or `@oracle1` |
| **Side effect** | The push moved **`latest` from version 1 to version 2** (the CLI does this on every push). The run already in progress was started on a resolved version and is not affected, but any new run that names `suite/clinical-v1` without `@1`/`@oracle1` now gets v3. I did not move `latest` back (only the push and one oracle run were authorised); `valkyrie dataset tag` can do it if wanted. |

Oracle run (one run, no agent, no model):

```
$ .venv-valkyrie/bin/valkyrie run start --agent oracle --dataset suite/clinical-v1@instr2 --provider modal --concurrency 2 -l hosted-oracle-instr2
│ Run ID:           15fc4349-028e-42dc-982f-feccff226b7c
│ Dataset version:  suite/clinical-v1@2
│ Spend:            development · default · new_benchmark_generation
```

Run `15fc4349-028e-42dc-982f-feccff226b7c`, label `hosted-oracle-instr2`, on Modal: status FINISHED,
01:24:38Z to 01:33:33Z (8.9 min), `n_errors` 0, `run errors` "No current error messages recorded",
`final_score` 48.51 (the same as oracle1). Every task FINISHED with verifier exit 0 and no failure
category. Fetched with `run results --path`, `run tasks --format json` and `run errors` into the
session scratchpad; no secret strings in them (`sk-ant` count 0).

| Task | reward | ran | valid | within_time | clin_acc | quality | vs_specialist | `oracle_expected_reward` | Match |
|---|---|---|---|---|---|---|---|---|---|
| reg-resect-build-0001 | 0.6667 | 1 | 1 | 1 | 0.6667 | 0.3313 | 1.0 | 0.6667 | yes |
| seg-spleen-build-0001 | 0.0 | 1 | 1 | 1 | 0.0 | 0.4095 | 0.4362 | 0.0 | yes |
| measure-hc18-0001 | 0.7590 | 1 | 1 | 1 | 0.7590 | 0.4369 | 0.6092 | 0.759 | yes |
| ecg-ptbxl-superdiag-0001 | 0.0 | 1 | 1 | 1 | 0.0 | 0.9730 | 0.9903 | 0.0 | yes |
| risk-icu-mortality-0001 | 1.0 | 1 | 1 | 1 | 1.0 | 0.7451 | 0.9999 | 1.0 | yes |

**All five rewards equal `oracle_expected_reward`**, and all seven keys equal the oracle1 run on v2
(`hosted-oracle1.md`), as expected for a change that touches only agent-facing text.

To run agents on v3, name the version explicitly: `--dataset suite/clinical-v1@instr2`.

## Not verified / open

- **Hosted behaviour at the agent timeout.** The new text says the pipeline is graded as found when the
  session ends. That is what the local pilot runner does and what `task.toml` asks for (artifact
  `/workspace/output`, separate verifier). Whether Valkyrie runs the verifier after an agent *timeout*
  has not been observed on the hosted platform; no hosted agent has timed out yet. The first hosted v3
  run that hits the limit should confirm it.
- **Other stale README wording, not changed (out of the three bugs):** reg_resect's data README still
  says "`python3` on PATH" and "at most 512 MB"; seg_spleen's says "under 500 MB". The instruction's
  own rules (absolute interpreter path; 512 MiB compressed) are the stricter, correct statement.
- `suite/families/seg_spleen/family.json` still lists `dev_predictions` in an artifact exclude list. The
  exporter does not use it (`task.toml` artifacts come from `export.py`), so it has no effect.
