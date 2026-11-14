# PCNSL Box candidate matching and rerun

**Goal:** Validate exact selected scans, paired samples, legacy labels and spatial feature values against the Box candidate; rerun the local benchmark on a defensible matched cohort.

**Execution:** Inline, already authorized by the user. Private rows and crosswalks remain on SCS/FAC. Only code and aggregate outputs return to teal. No SCS-to-teal route and no credential copy/reconnect.

**Inputs:** Existing private `release_candidate/` metadata, internal strict40 cohort audit, and Box `pcnsl_radiomics/dataset_manuscript/bids_dir_for_aws_anon/derivatives/pyalfe/`.

**Checks fixed before comparison:**
- Match the exact strict scan, not merely the patient.
- Match the collection date of the paired tumor specimen.
- Compare legacy any-listed-gene labels; report pathogenic/likely-pathogenic labels separately, without silently changing endpoints.
- Compare all ten FLAIR spatial features with absolute tolerance 1e-6 and relative tolerance 1e-5; report mismatches rather than selecting favorable patients after looking at prediction scores.
- Build rerun inputs from Box features for the scan/sample matched cohort. Do not replace mismatching Box values with internal values.
- Keep published archive identity and redistribution clearance separate from Box/internal equivalence.

**Implementation tasks:**
- [x] Inspect schemas and exact scan/sample/label agreement; save only aggregate report on teal.
- [x] Download only needed SummaryLesions CSVs through FAC, verify hashes after streaming to private SCS workspace.
- [x] Add tests for summary-table parsing, exact field matching, missing/duplicate features, gene tokenization, and selected baseline handling.
- [x] Implement release adapter and extend benchmark to configurable baselines and truthful fold-count reporting.
- [x] Run complete new tests on SCS and existing tests on teal; verify real-data outputs and source hashes.
- [x] Run the Box-derived matched prototype and compare with frozen internal controls on the same folds.
- [x] Report remaining identity/label/feature differences and the limits on a public frontier-agent evaluation.

Completed: 33 exact scan/sample matches; 396/396 legacy labels agree; 273/330
spatial values differ. Three fixed-baseline experiments yielded 154 verified
tasks and 495 prediction artifacts replayed. All 17 PCNSL and 12 existing tests
passed. Patient-level inputs stay on SCS/FAC; only aggregate/schema outputs were
copied to teal. Published archive identity and a frontier-agent trial remain
separate, unresolved work; no public benchmark or model failure is claimed.

A rare-target class-coverage audit found one-class training folds in v1. A
synthetic regression test reproduced the issue. The v2 splitter stratifies
unique patients first and requires both classes in every train/test fold. The
same cohort, label policies, baseline specifications and seeds are retained.
