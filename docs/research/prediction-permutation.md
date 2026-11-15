# Label-permutation null for the fixed logistic-regression pipeline

`pcnsl/prediction_permutation.py` asks one question: does the **fixed L2 logistic regression pipeline** (`prediction_eval.LogisticRegressionArm`: C=1, lbfgs, no tuning, train-fold imputation and scaling) find more signal for a prespecified gene than it finds when that gene's labels are randomly reassigned among the same patients?

It calibrates that pipeline only. It is **not** a null for TabPFN, direct frontier prediction or Harbor agents. Each of those needs its own valid null, or a paired comparison on identical folds and patients (`prediction_aggregate`).

## Prespecified design

| Item | Value |
|---|---|
| Genes | MYD88, CD79B (CLI default `--genes`) |
| Features | All 439 released features (`feature_group="all"`), canonical 6 significant digits |
| Permutations | 199 per gene (`--permutations`), permutation seed 20261115 (`--seed`) |
| Unit | Patient. The dataset must have one row per patient (it currently has 64), and repeated patient keys are rejected. Class counts are preserved. |
| Splits | `make_splits` (split seed 20261114) is **recomputed on each permuted label vector**, using the same stratified procedure as the observed run |
| Pipeline per run | `prediction_eval.run_evaluation(..., bootstrap=0)` with the logistic-regression arm, so imputation and scaling are fitted inside each training fold |
| Statistics | Pooled out-of-fold AUROC (one-sided, higher) and Brier score (one-sided, lower) |
| p-value | `(1 + #{null at least as extreme, ties inclusive}) / (199 + 1)`; the smallest attainable value is 0.005 |
| Never done | Score flipping, gene, feature or setting selection on results, or reruns of failed permutations |

## Output (aggregate only)

For each gene, the report gives:
- the observed AUROC, AP and Brier;
- the raw null AUROC and Brier values (aggregate metrics, no patient rows);
- a null summary: mean, SD, quantiles;
- the two p-values;
- the count of distinct null split fingerprints, as evidence that splits were recomputed.

The design block records:
- the pipeline settings and numpy and scikit-learn versions;
- the Python version;
- SHA-256 of `prediction_eval.py`, `prediction_permutation.py` and the dataset file;
- the dataset's own source hashes.

If any permutation (or the observed run) fails, that gene is marked `error` and gets **no p-values**. If the pipeline is unavailable (numpy or scikit-learn missing), the run stops with an error. The command refuses to overwrite an existing report.

```bash
# Data host only, inside the project's environment (no global installs):
ENV_PYTHON -m pcnsl.prediction_permutation --dataset DATASET.json --out REPORT.json
```

## Interpretation and caveats

- **Multiple comparisons.** Two genes × two metrics are reported without adjustment. Each p-value is a per-test value, conditional on this 64-patient cohort and its fixed fold procedure.
- **Meaning of a small p-value.** It says only that this pipeline's pooled AUROC (or Brier) is unusual under exchangeable labels. It says nothing about clinical utility or generalisation, or about whether any other method or agent would do better or worse.
- **Below-chance results.** Pooled AUROC below 0.5 can occur under the null with small n. The null distribution is the reference; a below-chance observed value is not evidence of anti-signal.
- **Labels and features are fixed.** Labels are "reported qualifying alteration vs no qualifying report", with the scan/specimen-pairing and panel-coverage caveats from `prediction-protocol.md`. The features are the released expert-mask derivatives.

## Verification

Tests: `tests/test_prediction_permutation.py`, 14 tests on synthetic data with 2–19 permutations. They cover:
- plus-one p-values with ties;
- permutations that preserve counts, are reproducible and depend on the seed;
- the arm refit and splits recomputed for every permutation;
- a minimum p-value for a planted-signal gene, and a non-small p-value for a null gene;
- no flipping of an inverted model;
- no p-values after a failed permutation, and an error for an unavailable pipeline;
- rejection of repeated patients;
- an aggregate-only report;
- the CLI defaults and refusal to overwrite.

Most tests use a stdlib stand-in arm. One CLI test runs the real logistic-regression arm and needs numpy and scikit-learn. It passed in an existing conda environment (Python 3.12.8, scikit-learn 1.8.0) and is skipped on hosts without them; nothing was installed.

Mutation checks confirmed the tests fail when each of these is broken:
- tie inclusion;
- per-permutation seeding;
- label permutation;
- the no-p-values-after-failure rule.

No patient data or model calls were used.
