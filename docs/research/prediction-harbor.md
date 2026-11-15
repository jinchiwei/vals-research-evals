# Harbor prediction task: held-out mutation probabilities

`pcnsl/prediction_export.py` packages **one gene × one prespecified fold** as a
Harbor/Valkyrie task. An agent gets labeled training rows and unlabeled test rows,
may use Python/scikit-learn (and TabPFN only if a prepared image provides it), and must
write probabilities. A trusted verifier scores the probabilities against held-out labels.
The task measures prediction. It does not test code repair, and there is no checklist.

Status: packaging and local tests only. **Nothing has been uploaded, built as a Docker
image or run on Valkyrie.** Organization `hackathon-neuronetwork-b91c517178` access
has not been verified. All tests use synthetic fixtures.

## Workflow (root, on the data host)

```bash
# 1. Split: folds come from prediction_eval.make_folds (seed 20261114), so this
#    is the same split that every comparator arm uses. Writes public/gold/crosswalk;
#    refuses to overwrite.
python3 -m pcnsl.prediction_export fold --dataset DATASET.json --gene MYD88 --fold 0 \
  --private-dir PRIVATE_DIR
# 2. Package. The default agent network is no-network (see below).
python3 -m pcnsl.prediction_export task --public PRIVATE_DIR/myd88-fold0.public.json \
  --gold PRIVATE_DIR/myd88-fold0.gold.json --out TASKS_DIR \
  [--agent-allowed-host api.anthropic.com] [--base-image IMAGE@sha256:... --tabpfn-checkpoint /opt/...]
# 3. Validate and pack locally (no upload)
.venv-valkyrie/bin/python scripts/validate_exports.py TASKS_DIR CHECK_DIR
```

In Python, use `build_eval_fold(dataset, gene, fold)` and then `export_task(public, gold, out_dir, ...)`.
The input is the `prediction_data.load_dataset` contract: `case_ids`, `feature_names`,
`X` (numbers or null), `labels` (gene → 0/1 list) and `feature_groups` (overlapping groups are allowed).
Feature values pass through `prediction_eval.canonical_matrix`, which rounds to 6 significant digits.
These are the same numbers every comparator arm sees. Feature names, including names with
spaces, do not change any values. `export_task` rejects a payload whose values are not
already canonical.

**Keep `*.gold.json` and `*.crosswalk.json` on FAC/SCS.** The crosswalk maps per-task
row IDs to dataset case IDs and is never written into a task. A task folder holds real
held-out labels in `tests/gold.json`, so treat the task folder itself as patient-level
data until it is uploaded under an approved data-sharing decision.

## Task layout and who sees what

| Path | Audience | Contents |
|---|---|---|
| `instruction.md` | agent | Task, file contract, scoring, runtime. No solution code. |
| `environment/Dockerfile`, `environment/data/{train,test}.csv`, `feature_groups.json`, `README.md` | agent (Docker build context) | Training rows with labels; test rows **without** labels |
| `tests/gold.json`, `tests/grade.py`, `tests/test.sh` | verifier only | Held-out labels; stdlib grader |
| `solution/solve.sh`, `prevalence_baseline.py` | oracle only | Predicts training prevalence (a plumbing check; expected reward 0.5) |

Leakage controls, each covered by a test:
- Test rows carry only `row_id` and features.
- Agent-visible bytes are identical when the held-out labels are flipped.
- Row IDs are fresh per (seed, gene, fold), and row order is shuffled without reference to labels.
- No original case IDs, dataset metadata, dates or host paths reach the task.
- Feature names that look like identifiers, dates or paths are rejected (for example tokens `id`, `mrn`, `date`, `path`, or 8+ digit runs).
- The test-set positive count is never shown to the agent.

`task_manifest(task)` returns the SHA-256 of every file, tagged with its audience.

## Scoring

Reward file `/logs/verifier/reward.json` = `{"reward": AUROC or 0, "valid_submission": 1|0}`.
- The submission must be `/workspace/output/predictions.csv` with header exactly `row_id,probability` and one row per test ID.
- Probabilities must be finite numbers in [0, 1]. Missing, extra or duplicate rows, non-numeric values, NaN or inf, blank rows, extra columns, symlinks and files over 1 MB are all invalid.
- Nothing is clipped, rescaled or repaired. AUROC is never flipped below 0.5.
- There is no pass threshold.
- `metrics.json` and the verifier stdout (which Valkyrie keeps as `verifier_output`) also record `average_precision`, `brier`, `n_test`, `n_test_positive`, the submission error and the predictions SHA-256.

Metrics are implemented in stdlib and checked against hand-computed fixtures:
- AUROC: Mann–Whitney, with ties counted as ½.
- AP: step-wise over distinct thresholds, without interpolation.
- Brier: mean squared error.

The same functions are copied verbatim into `grade.py`, so offline aggregation can import them from `prediction_export`.

Why AP and Brier are not reward keys: Valkyrie's `mean_rewards` counts a missing key as 0.0. For Brier, that would score an invalid submission as perfect.

**Primary analysis is not the Valkyrie headline.** Valkyrie averages per-fold `reward`, and invalid submissions count as 0. With about 13 test patients per fold, per-fold AUROC is very noisy. Root should compute pooled out-of-fold AUROC, AP and Brier from:
- the carried `/workspace/output` artifacts,
- the private gold,
- the crosswalk.

Report the valid-submission rate separately. Report comparator differences (prevalence, logistic regression, TabPFN from `prediction_eval`) on the same patients, separately from the agent reward. The task reward contains no comparator.

## Platform assumptions (from source, not yet observed on hosted Valkyrie)

I read these in the official `vals-ai/valkyrie` source at commit `1fe5c33d8c625540b1ea4f71e5ec159c1d813b48`, under `services/tracker/src/tracker/services/datasets/`. The separate-verifier mode does **not** appear in the public `.mdx` docs, only in the source.

1. **Separate verifier.** `task.toml` sets `[verifier] environment_mode = "separate"` and has no `tests/Dockerfile`. `separate_verifier.verifier_environment` therefore falls back to the agent's image source (`VerifierKind.AGENT`): a **fresh sandbox** is built from the same `environment/Dockerfile`, and `tests/` is uploaded only there (`upload_tests=True`). In shared mode, `grading.grade_task` uploads `tests/` into the agent's own sandbox after the agent finishes, where any lingering agent process could read or tamper.
2. **Artifact carry.** The top-level setting `artifacts = ["/workspace/output"]` makes `stage_artifacts` tar that folder in the agent sandbox. `_carry` unpacks it at the same path in the verifier sandbox, with a tar data filter. Nothing else from the agent sandbox is carried, except a non-empty `/logs/artifacts`, by convention.
3. **Rewards.** `/logs/verifier/reward.json` takes priority over `reward.txt`. Values must be finite numbers, and `reward` is the primary key (`rewards.py`). If the verifier exits non-zero without writing a reward file, Tracker records a `VerifierResultError`: an infrastructure error, not a score.
4. **Network.** `stage_egress` uses the stage setting when one is given, otherwise the environment setting. The verifier is set to `no-network`. **The agent defaults to `no-network`**, which fails closed. Harnesses such as the registry `claude_code` agent run *inside* the task sandbox (agent contract), so a no-network task cannot reach a model API and the run fails rather than running open. For a hosted frontier run, pass `--agent-allowed-host` with the model API host(s) the chosen harness actually uses. The instruction then names those hosts, and otherwise says there is no network. Two things are unverified:
   - whether Modal honours allowlist egress, and which hosts the harness needs (telemetry, auth). The local Docker provider supports only unrestricted `"*"` egress.
   - The image build (`pip install`) runs during image build, not in the agent stage.
5. **Fail-closed check.** `grade.py` refuses to score (exit 2, no reward) if `/solution` or `/bundle` exists. The oracle uploads `/solution` into the agent sandbox (`dataset_tasks.py`), and agent bundles install under `/bundle/NAME`. Neither should exist in a fresh verifier sandbox. This is a heuristic derived from the source:
   - It catches a Tracker that ignores `environment_mode` and grades in the shared sandbox.
   - It does not prove isolation, and a false positive turns every task into an infrastructure error.
   - The first oracle smoke run should confirm a reward of 0.5 with `valid_submission` 1.
   - If the hosted Tracker rejects or ignores separate mode, these tasks must not be scored. Do not drop the check to make them pass.
6. **Validation done.** The SDK `task_problems` reports no problems, `pack_task` succeeds, and `scripts/validate_exports.py` passes. `task.toml` parses with the pinned Tracker `TaskConfig` (pydantic): `verifier.is_separate` is True and the artifact source is `/workspace/output`. This does not show that the hosted Tracker version behaves the same way.

## Runtime and dependencies (prepared outside the agent run)

- **Environments only.** Per Jin's rule, every dependency lives in a project virtualenv or conda environment, never in a system Python, even inside a container. The exporter installs nothing on the host.
- **Default image.** `python:3.12-slim` (a tag, not a digest). At **image build time** the Dockerfile:
  - creates `/opt/benchmark-venv`;
  - installs pinned `numpy==2.1.3`, `scipy==1.14.1`, `pandas==2.2.3`, `scikit-learn==1.5.2` through `/opt/benchmark-venv/bin/python -m pip`;
  - puts that venv first on `PATH`, so the agent, oracle and verifier all use its `python3`;
  - sets `PIP_NO_INDEX=1`.

  A build-time check fails the build if `python3` resolves to system Python (`sys.prefix` is `/usr` or `/usr/local`) or if an import is missing. Docker is unavailable on teal, so the image has not been built here.
- **Custom `--base-image`.** The exporter adds no install step. The image must already have its own venv or conda environment (with numpy, scipy, pandas, scikit-learn, plus TabPFN if declared) first on `PATH`. The same build check rejects a system-Python `python3`.
- **TabPFN.** This is opt-in only, and only with a caller-supplied prebuilt `--base-image` (pin it by digest) whose on-`PATH` environment already contains `tabpfn` and its checkpoint. The Dockerfile then:
  - asserts at build time that `import tabpfn` works and that the checkpoint file exists, failing the build otherwise;
  - sets `TABPFN_MODEL_CACHE_DIR` and the offline/telemetry environment variables;
  - never downloads anything.

  The environment-variable names have not been checked against a specific TabPFN version. The real guarantee is the no-network or allowlisted agent stage. Before use, check the TabPFN licence and checkpoint terms for redistribution inside an uploaded image. The instruction mentions TabPFN only when it is present.
- **Resources.** 2 CPU, 4096 MB memory, 1800 s agent time and 120 s verifier time. Change them in `_task_toml` if pilots need different values; any change makes a new task version.

## Limitations

- One fold per task. Small folds make per-task AUROC noisy, and inference belongs in the pooled offline analysis with uncertainty.
- Across folds of the same gene, a patient's training row in one task is a held-out row in another. Each task's sandbox sees only its own data, and IDs are re-drawn per task. An agent with memory across tasks could still in principle match feature vectors. Run tasks independently.
- The verifier scores only the probability file. It does not check that the agent's own code produced the file, or how.
- The endpoint is reported qualifying alteration versus no qualifying report. It is not biological wild type. No clinical claim follows from any score.
- Nothing has run on hosted or local Valkyrie, and there is no image build or oracle evidence yet.

## Addendum: pooling agent submissions (`pcnsl/prediction_aggregate.py`)

This closes review blocker 3. Run it on the data host after a Valkyrie run, using the carried `/workspace/output/predictions.csv` for each fold task:

```bash
python3 -m pcnsl.prediction_aggregate --dataset DATASET.json --gene MYD88 \
  --private-dir PRIVATE_DIR --submission 0=RUN/fold0/predictions.csv ... --submission 4=RUN/fold4/predictions.csv \
  [--comparator training_prevalence --comparator logistic_regression] --out REPORT.json
```

- **Inputs:** the source dataset, plus every fold's `public`/`gold`/`crosswalk` JSON from `prediction_export fold`. The output is the aggregate-only report of `prediction_eval.run_evaluation`, which contains no row IDs, case IDs or probabilities. It refuses to overwrite an existing report.
- **Integrity checks.** These raise an error, and nothing is scored. Each fold's bundle must:
  - match its gene and fold;
  - have a crosswalk that covers exactly its rows, one-to-one, with known cases;
  - have test and training cases equal to `make_folds(seed 20261114)` for that fold;
  - have every training label, held-out gold label and feature row equal to the source dataset's canonical values.

  A bundle that is self-consistent but built on a different split is rejected.
- **Agent submissions.** Each file is parsed with the task grader's own parser and matched to patients **by case key through the crosswalk; row order is ignored**. A missing file makes the agent's status `partial`. A malformed file, or one carrying another task's row IDs (wrong gene or fold), makes it `error`. Either way, the report keeps per-fold metrics for the valid folds and gives **no pooled out-of-fold score**. With all 5 folds valid, the report gives:
  - pooled out-of-fold AUROC, AP and Brier;
  - per-fold metrics, and the mean, minimum and maximum within-fold AUROC;
  - patient-bootstrap intervals, which carry the same caveat: conditional on the fitted folds, not an interval for a new cohort.
- **Comparators.** `prediction_eval` arms run on the identical folds inside the same `run_evaluation` call. They therefore share the split fingerprint and bootstrap resamples, and paired AUROC differences are reported. Pairing happens only when the comparator representation (`--feature-group`) equals the columns the agent saw (all columns). Otherwise comparators are not run, and the report says why.
- **Limits.**
  - It aggregates one gene per call; across-gene summaries are left to the caller.
  - It does not fetch Valkyrie artifacts.
  - It does not distinguish infrastructure failures from agent failures beyond "file missing". Check run logs before treating a missing fold as an agent failure.
