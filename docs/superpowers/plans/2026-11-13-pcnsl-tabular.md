# PCNSL tabular research benchmark implementation plan

> Execute inline in this Codex session. The user requested implementation on SCS using the existing PCNSL pipeline.

**Goal:** Run a real-data local prototype with the existing strict pretreatment cohort, public-compatible feature definitions, reproducible baselines, and an agent prediction contract.

**Architecture:** Code lives in `pcnsl/` and is copied to an isolated SCS prototype directory. The adapter reads the existing cohort audit and named feature table without changing the research pipeline. Patient-level data and predictions remain on SCS; only code, schema and aggregate results return to teal.

**Tech stack:** Python, NumPy, pandas, scikit-learn, unittest; existing SCS genet environment.

**Spec:** User request: reuse the full PCNSL feature-encoded tabular pipeline, get data and prototype on SCS, match what is publicly available.

## Constraints

- No reverse connection from SCS to teal, no data upload or publication.
- Internal strict40 is a development cohort, not a verified public-release subset or an untouched external validation cohort.
- Match feature semantics to the public dictionary; report unresolved cohort membership and version equivalence explicitly.
- Preprocessing is fit only on training folds; predictions are never flipped using held-out labels.
- Primary prototype uses one scan per patient and paired-sample labels. Cohort construction remains the existing pipeline's responsibility.
- No API model sees patient rows. This iteration builds the local data/scoring prototype; no frontier failure claim without an actual agent trial.

## Review focus

- Missing mutation labels must not become negatives.
- Duplicate patients must not cross evaluation folds.
- Prediction IDs must match exactly, with finite probabilities in [0,1].
- Global preprocessing must not see held-out data.
- Matching public feature names does not authorize releasing internal rows.

## Tasks

- [x] Add failing tests for patient separation, label/probability validation, scoring direction, train-only preprocessing and task input exclusion of test labels.
- [x] Implement `pcnsl/benchmark.py`: input validation, grouped folds, fixed baseline models, aggregate scoring, and local task bundles with separate private answer keys.
- [x] Implement `pcnsl/scs_adapter.py`: read existing canonical loaders/cohort, retain named public-compatible spatial features, report provenance and schema compatibility, write local-only data with pseudonymous benchmark IDs.
- [x] Run the nine new tests on SCS and the 12 existing synthetic tests on teal; all pass. Teal's default environment lacks NumPy, so the new scientific tests run in the existing SCS genet environment. Run all 12 genes against fixed baselines on frozen folds, without selecting a purported winning gene.
- [x] Create `pcnsl/README.md` documenting commands, metric interpretation, public-release access gap, and next agent-evaluation step.
- [x] Verify all 60 task bundles, reproduce reference grading, check patient separation and owner-only permissions, and confirm SCS/teal code hashes match. Copy back only aggregate results, feature names and provenance.

## Execution record

- SCS run: `/data/rauschecker2/jkw/tmp/vals-pcnsl-prototype/runs/20261113-v1`.
- 40 patients; 12 genes; 6 fixed baselines; 3 fixed 5-fold repetitions; 72 aggregate model/target summaries; 60 local task bundles.
- 12 public-schema-compatible task features; 233 numeric features in the internal full-feature controls.
- Public release access, exact public membership and label/value equivalence remain unresolved. No public export, model-API patient-data transfer, or live frontier-agent run performed.
