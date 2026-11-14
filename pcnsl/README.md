# PCNSL tabular research-agent prototype

This reuses Jin's existing PCNSL cohort audit and feature loader on SCS. It is a
real-data **internal development prototype**, not a verified public dataset,
clinical predictor, or demonstrated frontier-model failure.

**Latest:** the [November 14 matched-cohort report](results/20261114-box-matched-v2/REPORT.md)
uses Box-derived features for 33 patients whose exact selected scan and paired
tumor-sample date agree with the internal pipeline. All 396 legacy labels agree;
273/330 spatial values differ, so Box and internal inputs are kept separate.
Three runs completed with 154 verified tasks and 495 prediction files replayed.
The Box-derived runs contain 59 legacy tasks and 36 reported-pathogenic tasks;
the remaining 59 are matched internal controls. No frontier agent has seen these data.

The scientific question is whether a research agent can build and honestly
evaluate mutation predictors from existing MRI features. The latest research
pipeline found no gene surviving its full multiple-testing correction; IRF4
was strongly confounded with sex. A high selected AUROC is not a discovery.

## Run on SCS

Code and private run artifacts:
`/data/rauschecker2/jkw/tmp/vals-pcnsl-prototype/`

```bash
cd /data/rauschecker2/jkw/tmp/vals-pcnsl-prototype
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/data/rauschecker1/jkw/envs/genet/bin/python -m unittest discover -v
/data/rauschecker1/jkw/envs/genet/bin/python scs_adapter.py --out runs/NEW_RUN_NAME
# Matched Box candidate: requires private release_candidate inputs on SCS.
/data/rauschecker1/jkw/envs/genet/bin/python run_release.py --out runs/NEW_MATCHED_RUN
/data/rauschecker1/jkw/envs/genet/bin/python verify_release.py runs/NEW_MATCHED_RUN
```

The run refuses to overwrite a previous output directory and reads research
inputs without editing them. The original scs_adapter.py run uses strict40: one scan per patient,
paired-tumor-sample labels, and all 12 existing targets. Subject identifiers,
dates, feature rows, labels, and per-patient predictions stay on SCS. The private
prototype directory has owner-only permissions.

## Original strict40 controls and metrics

- Six fixed controls: training prevalence; age/sex logistic regression;
  spatial/age logistic regression; spatial/age/sex logistic regression;
  all-feature logistic regression; shallow all-feature random forest.
- Seeds 11, 23, 37; patient-grouped stratified five-fold CV.
- Mean pooled out-of-fold AUROC, average precision, Brier score and log loss.
  Probability direction is fixed; no post-hoc score flipping.
- Training-fold-only median imputation and scaling. Unknown sex stays missing.
  Full-feature controls keep constant/sparse numeric features instead of applying
  the historic cohort-wide filters, so their width differs from the old 227.

These are historically studied patients: CV is development evidence, not an
untouched confirmation cohort. Fold ranges are not confidence intervals. This
quick run does not redo permutation/multiplicity analysis or supersede it.

## Matched Box candidate controls

`run_release.py` selects 33 exact scan/sample matches before looking at scores.
Five fixed baselines use 12 features: training prevalence, age/sex logistic
regression, spatial/age logistic regression, spatial/age/sex logistic regression,
and a shallow spatial/age/sex random forest. There is no duplicated all-feature
control. Seeds remain 11, 23, 37; fold count adapts to the smaller class (2–5).
The v2 splitter stratifies unique patients first, then expands to their rows;
both classes must appear in every training and test fold. This fixes one-class
folds found during the v1 rare-target audit; v1 remains preserved for provenance.
The Box legacy and internal legacy runs use identical patients, labels and folds.

Endpoints are explicit in each task's input and instructions:

- **Legacy any-listed:** a gene appears in any mutation-table row, including VUS,
  unclassified and unreported alterations. This reproduces the old audit labels.
- **Reported pathogenic:** `reportedalteration=True`, classification Pathogenic
  or Likely Pathogenic, and origin is not Not Detected. This is a table-derived
  reported-alteration endpoint, not proof of somatic origin or biological wild type.

All 12 legacy targets run. The stricter analysis has nine evaluable targets;
PRKDC and ZFHX3 have zero positives, and LRP1B has one, so they are excluded before
model fitting under the minimum two-per-class rule. Tiny counts remain a major
limitation even for included targets.

## Agent contract

The original strict40 run creates 60 local tasks (12 genes × five folds).
Matched runs record their actual task and fold counts in `aggregate_results.json`:

```
agent/input.json          # train features/labels; test features WITHOUT labels
agent/instruction.md      # prediction and reproducibility task
private/gold.json         # verifier-only test labels
reference/submission.json
reference/score.json
```

Submission format: a list of `{ "id": "case-001", "probability": 0.4 }`.
The grader rejects duplicate, missing or extra IDs, nonfinite probabilities and
values outside [0,1]. One-class test folds have undefined AUROC/AP; model-level
evaluation pools predictions across all folds before calculating metrics.

```bash
python benchmark.py TASK/private/gold.json submission.json
```

This layout **is not a filesystem sandbox**. A real frontier trial must expose
only `agent/`, hiding original data, answers, previous results and other tasks.
Overlapping CV tasks need independent sessions. Do not send internal patient
rows to model APIs or publish a Valkyrie dataset before verifying release/use
conditions. No live frontier trial or hosted Valkyrie run is claimed here.

## Public matching

Update, November 14: Box access works on FAC via `scs2box:`. The release-preparation
folder is `pcnsl_radiomics/dataset_manuscript/`, containing
`csvs_for_amazon_anonymized/` and `bids_dir_for_aws_anon/`. Five metadata/dictionary
files were downloaded and copied with verified hashes into the private SCS
`release_candidate/` directory. Actual counts: 150 subjects, 64 with mutation
records. The existing exact linkage found 60 of the research 67 patients and
35 of strict40, with no ambiguous matches. See
[aggregate access/overlap record](results/20261114-box-access.json).
All 35 overlap patients have the exact selected scan, but two have a different
tumor-sample date. The resulting 33-patient cohort has exact agreement across all
396 legacy labels. All age/sex values agree; 273/330 spatial values differ across
31 patients (absolute tolerance 1e-6, relative tolerance 1e-5). Correlations are
0.993–1.000, but the values are not interchangeable. Simple 100×/0.01× unit changes
do not explain the mismatch; its underlying processing cause is unresolved.
The adapter therefore reads the actual Box features instead of substituting
internal values. All five metadata and 33 feature-file hashes were verified.

Tasks use age, sex and the same ten FLAIR spatial lesion-fraction features as the
existing pipeline. `provenance.json` records metric mappings against the cached
public imaging dictionary and hashes of the source files.

**Box equivalence does not establish published-archive identity.** The Box
release-preparation folder has not been compared with the final controlled-access
archive. Historical overlap is confirmed, so this is not independent validation.

Next: compare the retrieved Box candidate against the final release at
https://imagingdatasets.ucsf.edu/dataset/4. Prefer building directly from those
files. Download access does not itself establish redistribution or API-use
permission. A real frontier trial and hosted Valkyrie execution remain pending.
Poor mutation prediction alone does not demonstrate an agent failure: the
evaluation must distinguish limited biological signal from an agent's errors in
endpoint definition, leakage control, modelling or scientific interpretation.

Only code, schema and aggregate reports belong in the teal preparation project.
