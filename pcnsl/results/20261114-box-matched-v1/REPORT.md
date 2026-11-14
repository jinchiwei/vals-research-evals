# PCNSL matched Box-candidate prototype — November 14, 2026

**Superseded by the v2 patient-stratified rerun.** A subsequent class-coverage
audit found two one-class training folds in the reported-pathogenic experiment
(one each for PRDM1 and TP53), plus one-class test folds across several targets.
The original grouped splitter used its documented prevalence fallback, so the
saved predictions and grader checks below are reproducible, but this split
design is unsuitable for the intended modelling tasks. The corrected splitter
stratifies unique patients before expanding to rows and requires both classes
in every train/test fold. Keep these results for provenance; use v2 for reporting.

**Local prototype complete; no demonstrated frontier-model failure or hosted Valkyrie run.**

We found the release-preparation dataset on Box through the existing FAC connection, copied only the needed metadata and feature CSVs to the private SCS prototype, and ran three fixed-baseline experiments. Patient rows, crosswalks, dates, labels, task inputs and predictions remain on SCS/FAC. This directory contains aggregates and schema only.

## What matched

- Box metadata: 150 subjects, 64 with mutation records.
- 35 strict40 patients overlap, all with the exact selected scan. Two have different tumor-sample dates and were excluded before fitting; 33 remain.
- All 396 legacy gene labels and all 66 age/sex values agree.
- 273 of 330 spatial feature values differ across 31 patients at the predeclared tolerances (absolute 1e-6, relative 1e-5). Region-wise correlations are 0.993–1.000. Simple percentage conversions do not explain the mismatch; the processing cause is unresolved.
- The Box runs use the actual Box feature values. Internal values are a separate matched control; they were not substituted into the candidate.
- Five metadata hashes and 33 feature hashes verified. Box release-preparation files have not been verified identical to the published controlled-access archive.

## Experiment design

Five fixed baselines: training prevalence; age/sex logistic regression; spatial/age logistic regression; spatial/age/sex logistic regression; shallow spatial/age/sex random forest. Twelve features total, with train-only imputation and scaling. Seeds 11/23/37; patient-grouped stratified CV with 2–5 folds according to minority-class count. No post-hoc probability reversal, model tuning against test outcomes, or gene selection by score. Legacy Box and internal comparisons use identical rows, labels and folds.

The two Box endpoints intentionally mean different things:

1. **Legacy any-listed:** the gene appears in any mutation-table row. This can include uncertain, unclassified or unreported variants; it reproduces the existing audit.
2. **Reported pathogenic:** reportedalteration=True, Pathogenic/Likely Pathogenic, and geneticorigin is not Not Detected. A negative means no qualifying table row, not proof of biological wild type. This policy does not prove somatic origin.

## Legacy endpoint: all targets

Mean pooled out-of-fold AUROC across three seeds. Spatial models below include age and sex. These are development estimates from historically studied patients, not independent validation.

| Gene | Positive / 33 | Folds | Age/sex | Box spatial | Internal spatial |
|---|---:|---:|---:|---:|---:|
| IRF4 | 4 | 4 | 0.813 | 0.899 | 0.899 |
| KMT2D | 13 | 5 | 0.272 | 0.360 | 0.358 |
| PRKDC | 12 | 5 | 0.279 | 0.426 | 0.421 |
| MYD88 | 25 | 5 | 0.422 | 0.643 | 0.650 |
| CD79B | 11 | 5 | 0.361 | 0.631 | 0.618 |
| ZFHX3 | 8 | 5 | 0.830 | 0.532 | 0.540 |
| LRP1B | 11 | 5 | 0.325 | 0.477 | 0.470 |
| BTG1 | 9 | 5 | 0.230 | 0.369 | 0.378 |
| ETV6 | 8 | 5 | 0.620 | 0.525 | 0.518 |
| CDKN2A | 18 | 5 | 0.251 | 0.353 | 0.362 |
| PRDM1 | 7 | 5 | 0.136 | 0.482 | 0.452 |
| TP53 | 6 | 5 | 0.391 | 0.270 | 0.259 |

## Reported-pathogenic endpoint

PRKDC and ZFHX3 have zero positives; LRP1B has one. They were excluded by the minimum two-per-class rule. The nine remaining targets still include extremely sparse labels.

| Gene | Positive / 33 | Folds | Age/sex AUROC | Spatial AUROC | Spatial split range |
|---|---:|---:|---:|---:|---:|
| IRF4 | 2 | 2 | 0.737 | 0.634 | 0.629–0.645 |
| KMT2D | 10 | 5 | 0.378 | 0.514 | 0.470–0.570 |
| MYD88 | 24 | 5 | 0.509 | 0.642 | 0.593–0.713 |
| CD79B | 9 | 5 | 0.284 | 0.515 | 0.463–0.565 |
| BTG1 | 4 | 4 | 0.319 | 0.264 | 0.121–0.534 |
| ETV6 | 3 | 3 | 0.700 | 0.796 | 0.767–0.833 |
| CDKN2A | 17 | 5 | 0.283 | 0.265 | 0.184–0.375 |
| PRDM1 | 4 | 4 | 0.351 | 0.342 | 0.086–0.483 |
| TP53 | 3 | 3 | 0.367 | 0.519 | 0.133–0.722 |

IRF4 illustrates the endpoint problem: legacy spatial AUROC is 0.899 with four positives and four folds; reported-pathogenic AUROC is 0.634 with two positives and two folds, while age/sex alone is 0.737. These are different labels and fold configurations, so this is not a controlled estimate of the effect of filtering variants. Neither figure establishes useful mutation prediction. The prior larger-cohort audit found strong sex confounding and no genes surviving its full multiplicity correction.

The split ranges above are not confidence intervals. Repetitions are correlated. There is no permutation or multiplicity analysis in this prototype, and the strongest-looking target must not be selected as a discovery. Below-chance predictions are retained, not reversed using held-out outcomes.

## Verification

- 16 PCNSL unit tests and 12 existing project tests passed.
- 154 task bundles checked: 59 Box legacy, 59 internal controls, 36 Box reported-pathogenic. These are overlapping CV tasks, not 154 independent cohorts.
- All 495 per-seed/model/target prediction files rescored, and all 165 aggregate model/target summaries checked.
- Test labels absent from agent inputs; patient groups never cross train/test folds; every patient tested exactly once per target for the exported seed.
- All reference grader replays matched. Source/code hashes match. All private run artifacts have owner-only permissions.
- Original research inputs and outputs were not modified. No SCS-to-teal connection or credential reconfiguration was created.

## Hackathon interpretation and remaining work

The [Vals Build Your Own Eval track](https://www.vals.ai/hackathon) requires a benchmark on Valkyrie for a task frontier models still get wrong. This prototype provides real task inputs, fixed controls and scoring, but does not yet satisfy that requirement: there has been no real-data frontier-agent trial or hosted Valkyrie execution.

A defensible next evaluation is whether a research agent defines the endpoint correctly, prevents leakage, compares against demographics, handles sparse labels and reports uncertainty honestly. Low predictive accuracy alone does not establish agent failure when the features may contain little usable signal. Score scientifically justified negative findings as valid outcomes.

Before a real-data model/API or hosted evaluation, verify final published-archive identity and applicable use conditions. Mount only an isolated task input and hide source data, other CV folds, gold labels, earlier results and the internal control. Existing task folders are an artifact layout, not a sandbox. Use independent sessions for overlapping tasks.

## Files and reproducibility

- Private SCS root: `/data/rauschecker2/jkw/tmp/vals-pcnsl-prototype/`.
- Private run: `runs/20261114-box-matched-v1/`.
- [Comparison and provenance](comparison.json), [feature diagnostics](feature_diagnostics.json), [verification](verification.json).
- [Box legacy results](box_legacy/SUMMARY.md), [matched internal results](internal_matched_legacy/SUMMARY.md), [reported-pathogenic results](box_reported_pathogenic/SUMMARY.md).
- [Adapter and run commands](../../README.md). Each result folder also includes AUROC, average precision, Brier, log loss and split ranges in aggregate JSON.
