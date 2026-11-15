# Suite integration: one core grader, one export path, validated tasks

Written 2026-11-14 by the integration worker (model: Claude Opus 5.5, `claude-opus-5-5`). Everything
below was measured on teal (WSL2) without Docker and without a hosted run. Machine-readable results:
`docs/research/suite/task-manifest.json` (tracked copy of `dist/suite-tasks/MANIFEST.json`).

## Outcome

Seven tasks (six families, build tier, plus the toy smoke task) are exported with
`suite.core.export.export_task` to `dist/suite-tasks/<family>/<task-id>/`. Every exported
`tests/grade.py` is the shared core grader (`suite.core.grading.main`), every `reward.json` has the
same seven keys, and the local pilot runner (`suite/pilot`) accepts every task (`load_task`, unmodified).

Validation per task (leak check = `suite.core.export.check_no_leak`; task config =
`exp/suite-platform-probe/check_taskconfig.py` with the pinned Tracker `TaskConfig`: no problems,
separate verifier, verifier no-network, agent allowlist `api.anthropic.com`, artifact `/workspace/output`;
packing = `scripts/validate_exports.py` with `.venv-valkyrie` (SDK 0.34.0, `hosted_run: false`)). Rewards
come from each task's own `tests/grade.py` run locally on (a) `solution/pipeline` and (b) a replay of the
stored specialist outputs in `tests/specialist/` through the same grader. "Expected" is the number
in `task.toml` (`oracle_expected_reward`); "documented" is the family document's number. Hidden counts
for cohort tasks are records in the single cohort run.

| Task | Grading | Dev / hidden | Leak | Task config | Packing | Solution reward: measured (expected; documented) | Specialist reward: measured (documented) | Specialist headline | environment / tests MB | Scored |
|---|---|---|---|---|---|---|---|---|---|---|
| `reg-resect-build-0001` | per_case | 4 / 6 | pass | pass | pass | **0.667** (0.667; 0.667) | **0.667** (0.667) | mean of per-case mean TRE (mm) 3.034 | 211 / 298 | yes |
| `seg-spleen-build-0001` | per_case | 8 / 6 | pass | pass | pass | **0.000** (0.000; 0.000) | **0.500** (0.500) | mean Dice 0.939 | 161 / 99 | yes |
| `measure-hc18-0001` | per_case | 152 / 83 | pass | pass | pass | **0.759** (0.759; 0.760) | **1.000** (1.000) | mean absolute HC error (mm) 2.055 | 19 / 11 | yes |
| `ecg-ptbxl-superdiag-0001` | cohort | 8000 / 1000 | pass | pass | pass | **0.000** (0.000; 0.670) | **1.000** (1.000) | macro AUROC 0.921 | 133 / 17 | yes |
| `risk-icu-mortality-0001` | cohort | 4000 / 4000 | pass | pass | pass | **1.000** (1.000; 1.000) | **1.000** (1.000) | AUROC 0.873 | 28 / 28 | yes |
| `triage-pharyngitis-0001` | cohort | 561 / 180 | pass | pass | pass | **0.000** (0.000; 0.000) | **0.000** (0.000) | AUROC 0.674 | 246 / 49 | no |
| `toy-sphere-volume-0001` | per_case | 2 / 3 | pass | pass | pass | **1.000** (1.000; 1.000) | **1.000** (–) | mean quality (Dice-based) 0.982 | 0 / 0 | no |

Notes on the runs:
- reg_resect solution per-case mean TRE 1.98, 1.38, 8.38, 1.83, 3.26, 1.37 mm (4 of 6 under 2 mm), as documented.
- seg_spleen: classical mean Dice 0.409, 0/6 acceptable; TotalSegmentator Dice 0.959, 0.936, 0.955,
  0.962, 0.892, 0.927, 3/6 acceptable.
- measure_hc18: classical 63/83 within tolerance, quality 0.437; U-Net MAE 2.05 mm, quality 0.717.
- ecg_ptbxl: simple reference macro AUROC 0.916, MI sens 0.728, macro ECE 0.0503 (fails calibration),
  gap 0.032, gate_fraction 2/3; specialist 0.921 / 0.744 / 0.0225 / 0.026, 3/3. Identical to the document.
- risk_icu: GBM AUROC 0.8726, 4/4 for solution and specialist. The solution took 141 s of the 300 s
  limit here (documented 14.6–22.8 s); load average was 11–18 from parallel validation jobs. Within the
  limit, but the margin on a loaded host is smaller than the document suggests.
- triage_pharyngitis: comparator (d) AUROC 0.674 (quality 0.347), gate 2/4 (fails operating point and
  subgroup) for both solution and specialist. The shipped solution reads the ResNet-50 weights from
  `/workspace/data/models/` (present in the image); on teal that path does not exist, so the unmodified
  solution exits 1 locally. The number above is from a copy whose `model.json` points at the exported
  `environment/data/models/` file; the hosted run should not need this.
- toy: solution 1.0; the smoothed-threshold specialist is 3/3 acceptable (quality 0.982).
- Every task is accepted by `suite.pilot.pilot.load_task` (task config schema, grader, tier).


## Core changes (`suite/core/`)

1. **Export paths (`export.py`).** `export_task` now resolves the output directory and every path in
   the spec (`public_dir`, hidden case folders, oracle, specialist pipeline/results) to absolute before
   anything runs. Cause of the bug: `run_specialist` runs the specialist pipeline with cwd = a fresh
   home, so a relative `tests/specialist/<case>` path was written inside that home and the exported
   folder stayed empty. New `check_specialist_outputs` raises `ExportError` (no partial folder left)
   unless every hidden case has the family's `REQUIRED_OUTPUTS` (non-empty) under
   `tests/specialist/<case>/` and a runtime in `runtime.json`. Tests:
   `test_relative_export_paths_fill_specialist`, `test_export_fails_loudly_without_specialist_outputs`.
2. **Cohort grading hook (`grading.py`).** `task_config.json` carries `grading: per_case | cohort`.
   A cohort task has exactly one hidden folder; the core stages it, runs the pipeline once under the
   cohort limit (optional `hard_kill_seconds`: finishing after the limit but before the kill is
   `ran` and graded, but not `within_time`), and calls the family's
   `grade_cohort(output_dir, input_dir, reference_dir) -> {valid, quality, reason, gate: {part: bool}, metrics}`.
   Reward rule (DESIGN.md): `clinically_acceptable = 1.0` only if the output is valid and every gate
   part is met, else 0.0; `metrics.json` gets `gate` (each part) and `gate_fraction` at top level, in
   `summary`, and for the specialist. A valid result without gate parts is an infrastructure error.
   The same rule grades the stored specialist output. Per-case grading is unchanged (same code
   path; `within_time` rule unchanged when there is no separate hard kill). The specialist block now
   also reports `valid` and `reward_if_on_time` (the scalar rule applied to the stored outputs).
   Tests: four `test_cohort_*` tests in `tests/suite/test_integration.py` (all parts → 1; 2 of 3
   parts → 0 with `gate_fraction` 2/3; invalid; late-before-kill; config errors).
3. **Cohort instruction text.** For cohort tasks `instruction.md` says the pipeline runs once on the
   whole hidden set, states the limit for the whole set (and the hard kill), and says the score is 1
   only if every gate part is met, with no partial credit.
4. **Per-family image requirements.** `FamilySpec.packages` is the family's own pin list;
   `family_packages(family)` reads `suite/families/<family>/image_requirements.txt`
   (`# extra-index-url: URL` for CPU torch, new field `pip_extra_index_url`). The Dockerfile installs
   them into `/opt/benchmark-venv` in one pip line (the pilot runner reads that line; the index is a
   single `--extra-index-url=URL` token so the pin list stays clean) and its build check imports
   exactly the declared modules, instead of always importing nibabel, SimpleITK and scikit-image.
   Every list must include numpy and scipy (what the vendored verifier needs). risk_icu, ecg_ptbxl and
   triage_pharyngitis images no longer carry nibabel, SimpleITK or scikit-image;
   `test_cohort_graders_import_without_imaging_libraries` imports their graders with those modules
   blocked.
5. **Bookkeeping fields.** `FamilySpec.tier`, `expected_solution_reward` and `scored` are written to
   `task.toml [metadata]` (`tier`, `grading`, `scored`, `oracle_expected_reward`), so a hosted oracle
   run of `solution/` can be checked against a stated number.

## Family changes

| Family | Changes |
|---|---|
| reg_resect | `spec.py`: `tier`, `expected_solution_reward = 4/6` (solution ships the specialist). No other change. |
| seg_spleen | New `spec.py` (build tier) from `family.json`: dev cases + `volumes.csv` (label voxels × voxel volume, 2 decimals) + licence + attribution; hidden `input/image.nii.gz`, `reference/label.nii.gz`; specialist = stored TotalSegmentator outputs `specialist/ts_gpu_full_hidden` (the run in `summary_hidden.json`) with their measured wall times; solution = classical pipeline; pins from `family.json` (incl. CPU torch 2.15.0 from the extra index); expected solution reward 0.0. Toolbox tier not built (below). Uses the existing `grade_case` adapter in `grader.py`. |
| measure_hc18 | `spec.py`: `tier`, `expected_solution_reward = 63/83` (classical comparator). |
| ecg_ptbxl | New `grader.py` (core plug-in, `GRADING = 'cohort'`, `grade_cohort` wrapping the unchanged parser, metrics and gate in `grade.py`; refuses a symlinked `predictions.csv`) and `spec.py` (task `ecg-ptbxl-superdiag-0001`, hidden folder `cohort`, stored specialist predictions from `work/selfcheck/specialist`, time limit 560 s with hard kill 1,120 s as in `TIME_RULE`). `image_requirements.txt` now declares CPU torch (it was an extra in `family_spec.json`). `README.md` scoring paragraph updated to the cohort rule (all three parts). `build_task.py` marked superseded. |
| risk_icu | `grader.py`: `GRADING = 'cohort'`, `grade_cohort` (gate parts = the four components; symlinked output refused); `grade_case` kept as a per-case view for the family tests. `spec.py`: `grading='cohort'`, pins from new `image_requirements.txt` (numpy, scipy, pandas, scikit-learn), expected 1.0. |
| triage_pharyngitis | `grader.py`: `GRADING = 'cohort'`, `grade_cohort` (gate parts = the four components). `spec.py`: `grading='cohort'`, pins from its `image_requirements.txt` (the torch index moved out of the pin list), expected 0.0, `scored = False`. |
| toy | `spec.py`: expected 1.0, `scored = False` (smoke task). |

No clinical threshold, split, time limit or stored comparator output was changed.

## Reported numbers that changed

One, and it is a rule change rather than a measurement change: **ecg_ptbxl's shipped solution
(simple reference) moves from reward 0.67 to 0.0.** Its metrics are identical (gate 2 of 3, failing
calibration at ECE 0.0503 against 0.05). `ecg_ptbxl.md` reported 0.67 under the family's earlier rule
(`clinically_acceptable` = conditional fraction of gate parts). DESIGN.md's amended cohort rule, which
this integration was asked to implement, gives 1 only when all parts are met. The fraction is still
reported (`gate_fraction` 2/3, and the family's conditional `gate_fraction_met`). The agent README for
the task was updated to state the all-parts rule. I did not adjust anything to keep 0.67; the
coordinator should decide whether `ecg_ptbxl.md` gets a note (I did not edit other documents).
The specialist (1.0) and every other family's documented rewards are reproduced exactly. risk_icu's
"reward (family)" column in `risk_icu.md` (0.25, 0.75 for the constant and overconfident self-checks) was
already superseded by its "reward (exported, core)" column, which matches the cohort rule.

## Tests

`~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite -q` collects and runs in the single
core env after adding `pandas==2.2.3` to `suite/requirements.txt` (installed into `vals-suite`). No
assertion was weakened; the only skip besides the manifest test's guard is the existing openpyxl skip
in `test_triage_pharyngitis.py`. New file `tests/suite/test_integration.py`: relative export
paths, loud failure on missing specialist outputs, relative grading paths, the cohort hook (all parts,
partial, invalid, late-before-kill, config errors), per-family Dockerfile pins, cohort graders importing
without imaging libraries, the ECG cohort plug-in (incl. a planted symlink), and the manifest fields (12 tests).

A second relative-path bug was found while validating: `grading.main` with a relative `--work` made
`bash run.sh` unreachable from the pipeline's cwd. `grade_task` now makes its paths absolute (test
`test_relative_grading_paths`). The exports were made before this fix, so the seven vendored
`tests/lib/suite/core/grading.py` files were refreshed by copying the fixed file (the only difference;
hosted defaults are absolute, so no validated number depends on it). The SDK packing ran before the
refresh; leak check and task config are unaffected by it.

Result on 2026-11-14 after all changes: **191 passed, 1 skipped** (openpyxl) in 69 s.

## Not verified here (needs Docker or a hosted run)

- **No image was built.** The per-family Dockerfiles (pins, the extra torch index, the import check)
  were checked by text and by the platform parsers only. In particular `torch==2.15.0+cpu`
  (seg_spleen, from `family.json`) and `torch==2.5.1+cpu` (ecg_ptbxl, triage) were not installed from
  the index here.
- **Grading ran as a normal user** with `--sandbox-root none`: the privilege drop to uid 65534,
  `chmod go-rwx /tests`, killing by uid, network isolation and the fail-closed `/solution` check were
  not exercised for these tasks (they are covered for the toy task only by the unit tests).
- **Timing is teal's, not Modal's.** Specialist runtimes are the families' stored measurements;
  seg_spleen's are GPU wall times (its CPU 4-thread full-model median was 32 s per case, well under
  the 300 s limit).
- **No hosted oracle run.** The expected numbers in `task.toml` (`oracle_expected_reward`) and the
  manifest are what a hosted oracle run should reproduce.
- **Local pilot runtime for torch tasks.** `suite/pilot` builds its runtime env from the Dockerfile
  pins without the extra index, so `torch==…+cpu` pins (ecg_ptbxl, seg_spleen, triage) will not
  install there; the pilot code was not changed (out of scope).
- **seg_spleen toolbox tier** was not built: it needs TotalSegmentator and its weights in the image
  and a writable copy of `totalseg_home` (TotalSegmentator writes `config.json` into it), neither of
  which can be checked without Docker.
