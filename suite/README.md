# Healthcare suite core: how a family plugs in

`suite/core/` is shared by every task family. A family supplies data, a per-case grader and a
spec; the core supplies metrics, geometry checks, the timed pipeline runner, the reward
contract, the verifier procedure and the Harbor exporter. The toy family (`suite/families/toy/`)
is the worked example and the zero-risk smoke task.

| Module | What it gives you |
|---|---|
| `metrics.py` | Segmentation (Dice, NSD@τ mm, HD/HD95 mm, volume error mL, lesion detection/F1/lesion-wise Dice, `segmentation_headline`), registration (TRE stats, initial vs final, Jacobian folding), classification/risk (AUROC, AP, Brier, ECE, calibration slope/intercept/CITL, sens@spec, spec@sens, net benefit and curve, subgroup worst-gap), measurement (abs/% error with tolerance, Bland-Altman), statistics (bootstrap CI, paired bootstrap difference). Every docstring states the definition and edge cases. |
| `geometry.py` | `load_reference_grid`, `load_mask_on_grid` (safe read with no symlinks and a size cap, unit conversion, grid diagnosis), `read_regular_file`. |
| `runner.py` | `run_pipeline`: `bash run.sh IN OUT`, hard wall-clock limit, process-group kill, uid 65534 when root, minimal env, capped log, grader-measured time. |
| `reward.py` | `REWARD_KEYS`, `scalar_reward` (**the one place the headline rule lives**), `build_reward`, `write_reward`. |
| `grading.py` | The verifier procedure every exported `tests/grade.py` runs. |
| `export.py` | `FamilySpec`, `export_task`, `check_no_leak`, `task_manifest`. |

## Agent-side contract (written into every instruction.md)

The agent leaves `/workspace/output/pipeline/run.sh`. The grader runs `run.sh INPUT_DIR OUTPUT_DIR` once
per hidden case, offline, as an unprivileged user, under the per-case limit `time_limit_seconds`.

## Reward contract

`reward.json` = exactly `reward, ran, valid, within_time, clinically_acceptable, quality, vs_specialist`,
each a finite number in [0,1]. The first six are means over hidden cases:

- `ran`: the required files exist.
- `within_time`: ran and was not killed on timeout.
- `valid`: ran and `grade_case` says valid.
- `clinically_acceptable`: valid and meets the family threshold.
- `quality`: the family's primary metric, with 0 for an invalid case.

`vs_specialist = min(1, quality / specialist quality)`. The default scalar is
`reward = clinically_acceptable` if `ran == valid == within_time == 1`, else 0. Change it in
`reward.scalar_reward`. Raw mm, mL and seconds go to `metrics.json`. That file holds per-case
metrics, the failure reason, the run record and the specialist results.

## What a family provides

1. **`suite/families/<name>/grader.py`**, imported in the verifier from `tests/lib`. It may import
   only `suite.core.*`, numpy, scipy, nibabel, SimpleITK, scikit-image, scikit-learn and sibling modules
   of its own package. It must define:
   ```python
   REQUIRED_OUTPUTS = ('mask.nii.gz', 'measurements.json')   # files run.sh must write
   CLINICAL_THRESHOLD = 'Dice >= 0.90 and ...'               # one line, shown in metrics.json
   PRIMARY_METRIC = 'mean of Dice and NSD at 1 mm'
   def grade_case(output_dir, input_dir, reference_dir) -> dict:
       # {'valid': bool, 'acceptable': bool, 'quality': float in [0,1],
       #  'reason': str|None (why invalid / not acceptable), 'metrics': {...raw values...}}
   ```
   Read agent files only through `geometry.load_mask_on_grid` / `geometry.read_regular_file`. The
   grader runs as root, so a symlink planted by the pipeline must not be followed. An exception
   in `grade_case` is recorded as an invalid case, so the grader does not crash.
2. **A spec builder** that returns `export.FamilySpec`:
   - `public_dir` becomes `environment/data/`. It holds a README, the development cases with
     references, and the format documentation.
   - `hidden_cases` maps each case to a folder with `input/` and `reference/`.
   - `oracle_pipeline_dir` must be built from agent-visible material only.
   - Give either `specialist_pipeline_dir`, which the exporter runs on the hidden inputs and
     times, or `specialist_results_dir` with precomputed results (`<case>/...` plus `runtime.json`
     `{"wall_seconds": {case: s}}`).
   - Also set `time_limit_seconds`, cpus, memory and GPU, `allowed_hosts` and `packages`.
3. **Pipelines for tests**: at least an oracle. The toy family also has slow, wrong-geometry and
   wrong-units pipelines.
4. **Image packages**: `FamilySpec.packages` is this family's own pin list (default
   `DEFAULT_PACKAGES`, the imaging stack). Families without imaging declare theirs in
   `suite/families/<name>/image_requirements.txt` (`# extra-index-url: URL` for CPU torch) and pass
   `export.family_packages(name)`; every list must include numpy and scipy (the verifier's own
   needs). The Dockerfile installs them into `/opt/benchmark-venv` in one pip line and its build
   check imports exactly those modules.
5. **Bookkeeping**: `tier`, `expected_solution_reward` (what a hosted oracle run of `solution/` must
   score; written to `task.toml` as `oracle_expected_reward`) and `scored` (False for worked examples).

### Cohort families (one run on the whole hidden set)

Families whose metrics are defined over the cohort (ECG, ICU risk, pharyngitis) set
`FamilySpec(grading='cohort', cohort_size=N, hard_kill_seconds=optional)` with exactly one hidden
folder (`cohort/input`, `cohort/reference`) and define in the grader module:

```python
GRADING = 'cohort'
def grade_cohort(output_dir, input_dir, reference_dir) -> dict:
    # {'valid': bool, 'quality': float in [0,1], 'reason': str|None,
    #  'gate': {part: bool, ...}  (every part of the clinical gate), 'metrics': {...raw cohort metrics...}}
```

The core runs the pipeline once under the cohort limit and applies the cohort rule:
`clinically_acceptable = 1` only if the output is valid and **every** gate part is met, else 0.
`metrics.json` gets `gate` (each part) and `gate_fraction` for the agent and the specialist. The
seven reward keys are the same as for per-case tasks. A run finishing after `time_limit_seconds`
but before `hard_kill_seconds` is graded but not `within_time`. The instruction text says the
pipeline runs once on the whole hidden set.

Then:

Paths are resolved to absolute before anything runs (the specialist pipeline runs with cwd = a fresh
home, so a relative path once left `tests/specialist/` empty). The export fails with `ExportError` if
any hidden case lacks the family's `REQUIRED_OUTPUTS` under `tests/specialist/<case>/` or a runtime.

```bash
~/miniconda3/envs/vals-suite/bin/python -c "from suite.families.toy.spec import build_spec; \
from suite.core.export import export_task; print(export_task(build_spec('/tmp/w'), 'dist/suite-toy'))"
.venv-valkyrie/bin/python -I exp/suite-platform-probe/check_taskconfig.py dist/suite-toy
.venv-valkyrie/bin/python scripts/validate_exports.py dist/suite-toy results/<date>-suite-toy-packaging
```

The export fails with `ExportLeakError` if any hidden reference, hidden input or specialist
output appears in `environment/`, `instruction.md` or `solution/`. It checks the bytes, the
gunzipped content and the SHA-256 hex digest.

Local dry run of the verifier without Docker; paths are remapped and the shared-sandbox check is off:

```bash
python -I -B dist/suite-toy/<task>/tests/grade.py --tests dist/suite-toy/<task>/tests \
  --pipeline PIPELINE_DIR --logs /tmp/logs --work /tmp/eval --sandbox-root none \
  --pipeline-path ~/miniconda3/envs/vals-suite/bin:/usr/bin:/bin
```

## Environment and tests

```bash
~/miniconda3/bin/conda env create -f suite/environment.yml      # env "vals-suite", pip pins in requirements.txt
~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite -q     # whole suite, one env (pandas included)
```

The integrated exports, their validation and the suite manifest are described in
`docs/research/suite/integration.md` and `docs/research/suite/task-manifest.json`.

When the exporter runs a specialist pipeline, set `SUITE_PIPELINE_PATH` to a `PATH` whose
`python3` has the image's packages (locally, the vals-suite env bin).

## Interpretations and limits

- **Timed-out cases.** A case killed on timeout is scored `within_time = 0`. Its outputs are still
  graded for `ran`, `valid` and `quality` (a correct but slow pipeline is visible as such), and the
  gate still makes the reward 0.
- **No warm-up.** There is no warm-up run, so the first case pays import costs. Limits should be
  generous: 3-5× the specialist.
- **Specialist runtime.** It is measured at export time on the export host, not on the verifier
  machine. Treat `runtime_ratio_vs_specialist_median` in `metrics.json` as indicative only.
- **Not tested locally.** Some things need a root, hosted verifier: the privilege drop to uid 65534,
  `chmod go-rwx /tests`, killing processes by uid, and network isolation. Local tests run as a
  normal user. `RLIMIT_AS` memory caps are optional (`memory_limit_bytes`).
- **Surface distances.** They use voxel-centre border voxels and voxel counts, not surfel areas. HD95
  follows the MONAI convention: the maximum of the two directed 95th percentiles.
