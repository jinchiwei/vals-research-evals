# Fixed public-release conventional controls

FAC CPU job **3067848 completed (0:0)**. These are conventional-model controls, not frontier-model results. The data contain 64 patients and 439 features. Five fixed patient-stratified folds, seed 20261114; no tuning or AUROC flipping. Numeric inputs are rounded to six significant digits consistently across arms.

| Gene | Full-feature logistic AUROC | Mean within-fold AUROC | Sex-only logistic AUROC | Full-feature Brier |
|---|---:|---:|---:|---:|
| BTG1 | 0.674 | 0.727 | 0.332 | 0.109 |
| CARD11 | 0.649 | 0.614 | 0.498 | 0.194 |
| CD79B | 0.347 | 0.344 | 0.434 | 0.488 |
| CDKN2A | 0.424 | 0.384 | 0.403 | 0.473 |
| CDKN2B | 0.419 | 0.425 | 0.520 | 0.458 |
| ETV6 | 0.604 | 0.555 | 0.592 | 0.156 |
| KMT2D | 0.350 | 0.346 | 0.466 | 0.421 |
| MYD88 | 0.562 | 0.556 | 0.499 | 0.313 |
| PRDM1 | 0.376 | 0.414 | 0.179 | 0.226 |
| TP53 | 0.444 | 0.433 | 0.203 | 0.108 |

The full-feature fixed logistic model does not establish a robust attainable-performance ceiling. More features do not by themselves establish more predictive signal. TabPFN and frontier comparisons remain pending. These outcomes do not establish invalid genetic labels, impossibility of prediction, or a frontier-model failure.

Pooled out-of-fold AUROC can be affected by fold-specific score offsets, particularly with small class counts or weak sex-only models. Mean within-fold AUROC is also reported; neither replaces independent validation. Detailed reports include average precision, training-prevalence controls, patient bootstrap intervals conditional on fitted folds, and paired differences. Ten genes were retained by a prespecified count rule, not selected for high AUROC. Bootstrap intervals are descriptive and unadjusted for multiple genes.

Gene labels mean a qualifying alteration was reported versus no qualifying report among genomically observed patients. They do not establish wild type, complete panel coverage, or validated scan/specimen timing. Only aggregate reports were transferred from FAC.

Reproduce with scripts/run_prediction_baselines.py and scripts/prediction-baselines-fac.sbatch. manifest.json records exact dataset, evaluator, runner, and report hashes. No frontier API calls occurred in this run.
