# Claude: final evidence refresh and visual QA

Continue the existing deck in `results/pcnsl-frontier-deck/`; preserve its design.
Write only inside that output directory. Use Jin's same build-pptx skill and
existing `scripts/rebuild.sh`/layout/figure pipeline as applicable. No benchmark
code changes. This is the final evidence refresh after concurrent jobs finished.

Read the final evidence:

- `results/20261114-repair-pilots/REPORT.md`, `summary.json`, `strict-replay.json`
- `results/20261114-repair-suite-v2-packaging/validation.json`, `preflight.json`
- `pcnsl/results/20261114-hosted-release/REPORT.md`, `baseline.aggregate.json`, `baseline-validation.json`
- `docs/research/implementation-review.md`

Required corrections, if not already applied:

1. New model round is **12/12 attempts passed, 10 frozen + 2 exploratory**.
   Include both integrated held-out seed 101 attempts in figures, tables, notes.
   Four hidden fixtures are replays, not four model attempts. Original historical
   12 Opus attempts are separate; don't silently pool them into these denominators.
2. Stricter replay passed **10/10 frozen submissions, 40 fixtures**, with zero
   new model calls. Final limits: 8 CPU / 12 wall seconds, 512 MiB, 1 MB output.
3. Final **16 task archives** (four families including integrated × two seeds ×
   flawed/valid) passed official SDK validation. Replace stale "12 archives" or
   "integrated not packaged" statements throughout slides, markdown, notes and
   build-status. This still does not establish root/container or Valkyrie execution.
4. Add one compact content slide for the **actual hosted-release-only baseline**:
   63 patients, 10 spatial features, fixed C=1 logistic regression; train-fold-only
   scaling/imputation; five-fold internal CV repeated at three prespecified seeds.
   Mean pooled OOF AUROC MYD88 **0.6684**, range **0.6547–0.6829**;
   CD79B **0.4434**, range **0.4314–0.4605**. Range across seeds is NOT a confidence
   interval. IRF4 excluded (two positives). Reported qualifying alteration vs no
   qualifying report, NOT biological wild type. Scan/specimen timing not clinically
   adjudicated. No score flipping, external-validation, clinical-utility or
   frontier-failure claim. This is separate from the historical 33-patient baseline.
   The historical schematic can remain as context or move to appendix.
5. Current validation: local suite 60 tests, 59 passed and one numerical test
   skipped locally; that numerical test was included in ten passing FAC checks.
   Don't sum overlapping test sets as independent validations. Grader review fixes
   are implemented; root/provider path and hosted runs remain pending access.

Ensure the new slide and any changed figures render cleanly. Re-render preview
PDF/PNGs and inspect changed slides at full size; add complete speaker notes and
update build-status hashes/provenance. Keep the honest conclusion: useful prepared
capability/control suite, **no demonstrated frontier failure**. No external upload,
publishing, messages, credentials or system installs.
