# Speaker notes — PCNSL_FRONTIER

Each `## ` heading matches the start of a slide title. `scripts/add_notes.py` copies these into the PPTX notes pane.

## Do research agents make valid PCNSL claims?

Internal briefing for the Vals Build Your Own Eval track. It covers what we built, what the evidence shows, and what we will and won't claim. Evidence snapshot (final refresh, 2026-11-14): repair-pilot report and strict replay (results/20261114-repair-pilots/, FINALIZED), 16-task packaging validation (results/20261114-repair-suite-v2-packaging/), hosted-release baseline (pcnsl/results/20261114-hosted-release/), and the implementation review (docs/research/implementation-review.md). Bottom line up front: a useful, prepared capability and control suite, with no demonstrated frontier failure.

## The ask

The official page (https://www.vals.ai/hackathon) asks for a benchmark on Valkyrie of a task frontier models still get wrong. It says judging is demo-based and does not publish weighted criteria, so we don't invent any. Submissions close Sunday Nov 15, 2 PM Pacific. Our honest status: tasks, controls and a 16-archive package are ready, but every model attempt this round passed: 12 of 12, of which 10 are frozen and 2 exploratory. We have no demonstrated frontier failure and no hosted Valkyrie run.

## What we score

This is the core design principle. The capability we care about is producing a correct, defensible research artifact: cohort, endpoint, image and feature handling, evaluation, and a bounded conclusion. If MRI carries little information about a mutation, a valid analysis that reports a null or inconclusive result earns full credit. A high AUROC from a leaked split or the wrong endpoint earns nothing. The matrix is a schematic of the scoring principle, not data.

## Four data objects

These four objects must never be merged by assumption. (1) Hosted v1.0 archive: we received the full 16,659,458,958 bytes, ZIP CRC passed, and the SHA-256 4a45cbad… is pinned. On FAC we produced an aggregate inventory and a fixed 63-patient baseline (shown later in Results); patient-level records stayed on FAC and nothing from the archive is model-facing yet. (2) Box candidate: a release-preparation copy. 5/5 metadata files and 33/33 FLAIR summary files are byte-identical to the hosted archive, but whole-release equivalence is not established. (3) Internal pipeline features: 273 of 330 values differ from Box, and the cause is unresolved. These serve only as a matched control. (4) Synthetic counterfactual tasks: every frontier pilot used these. No patient records were sent to any model.

## Hosted v1.0 inventory

All numbers come from the aggregate inventory. 150 patients each have T1, CE-T1, FLAIR and ADC. 64 have genomic records, and 63 of those also have all ten FLAIR spatial features finite. No DSC/CBV was detected, so perfusion-replication tasks are out of scope. The chart compares any-listed variant rows with reported qualifying alterations (reported, Pathogenic/Likely Pathogenic, origin not "Not Detected"). IRF4 has 9 any-listed but only 2 qualifying, which is too sparse for five-fold prediction. A negative here means "no qualifying record". It does not mean biological wild type, and the assay denominator is not verified. The inventory is not an identity or privacy clearance.

## Prior work exists

PCNSL MRI–genotype studies already exist. Zhou 2026 (n=92, ADC + DSC/CBV, same-cohort AUC 0.652–0.861) and the 2016 LOC abstract (n=50, no location association) are examples. Related work predicts BCL6 rearrangement, Ki-67, or PCNSL vs GBM; those are different endpoints. On the agent side, BLADE, ScienceAgentBench, SciIntegrity-Bench, ReplicatorBench, PaperBench and PAPERBENCHX already cover analysis validity, honesty, replication and replay. We do not claim to be the first anything. The narrow contribution is clinical imaging–genomic semantics plus executable repair plus matched controls, packaged for Valkyrie. Whether that is hard for frontier models is still unproven. The literature search was focused, not systematic.

## Thirty candidate mechanisms

B01–B30 come from benchmark-design.md. The grouping into six families and the filled/outline mapping are my reading of the task protocol text, which is why the figure is labeled schematic. Filled means an executable task's protocol requires the agent to handle that mechanism. It does not mean the mechanism caused a failure: every such task was passed by both models. The 13 outlined mechanisms are proposals only.

## Three repair families

Endpoint: build the cohort for a reported-pathogenic endpoint from specimens, report revisions and scan timing. Unassayed genes must stay unknown, never negative. Claims: audit frozen prediction runs for patient overlap with fitting, transforms or selection, late freezes and score direction, then apply Holm across every planned hypothesis. Geometry: compute volume and ADC in physical space across differing affines, frames and units. The integrated audit composes these into one manuscript repository with transitive identities and artifact ancestry. All four are synthetic tasks with independent references.

## How an attempt is scored

One attempt is one agent run. The agent receives the repository and the protocol; hidden fixtures, references and graders are kept outside its workspace. The submitted program is replayed on four new synthetic cohorts that only the verifier holds, and the attempt passes only if all four match the reference. Four fixtures are four replays of one submission. They are not four attempts and they are not patients. The clean twin checks that the agent does not damage a correct repository. This harness is a local isolated runner, not Valkyrie.

## Pilot results

These are final numbers from results/20261114-repair-pilots/REPORT.md, summary.json and strict-replay.json. This round had 12 model attempts and all 12 passed. Ten are frozen: claims and geometry (2 families × 2 models), plus integrated flawed, the integrated clean twin, and the integrated held-out seed 101 (3 × 2 models). Both held-out seed 101 attempts, one per model, are in the chart and both passed. The two endpoint attempts are exploratory because the generator changed mid-run, so they are excluded from the frozen denominator rather than reconstructed.

Each attempt's submitted program was replayed on four hidden fixtures. Those 40 frozen fixture replays are reruns of 10 submissions, not 40 attempts. A later strict replay re-ran all 10 frozen submissions on the same 40 fixtures with zero new model calls under the final limits: 8 CPU seconds, 12 wall seconds, 512 MiB address space and 1 MB accepted JSON output. All 10 passed.

The tile for the earlier 12/12 is a separate, historical Opus-only round on the original workflow tasks. It is not pooled into these denominators. The report's interpretation: the protocol supplies the scientific rules, so this measures faithful implementation and repair across connected evidence, not autonomous methodological discovery.

## Both models passed every task

Both models passed every cell, including both integrated held-out seed 101 attempts. Each cell is one attempt; "4/4" is four hidden-fixture replays of that one submission. Claude's response confirmed claude-opus-5-5 at high effort. GPT-6 Astra was requested as gpt-6-astra at high effort, but the Codex CLI emitted no response model ID, so its identity is request-pinned only. The Claude CLI usage estimate across the round was about $2.54 (an estimate, not a bill); Codex ran on an existing ChatGPT login, so no cost was recorded. With one attempt per cell, wall-clock times are descriptive and not a speed or capability ranking. The endpoint row is exploratory and not pooled.

## Hosted-release baseline

This is the actual hosted-release-only baseline, computed on FAC from the hosted v1.0 archive alone, with no Box or internal-cohort inputs. Patient-level data and predictions stayed on FAC; only aggregates came back. Design: 63 patients, one row each; ten FLAIR spatial-fraction features; a fixed logistic regression (C=1, liblinear, no hyperparameter search, no feature selection); median imputation and scaling fitted only on training folds; five-fold stratified patient CV repeated at three prespecified seeds (11, 23, 37).

Results, as pooled out-of-fold AUROC: MYD88 (46 qualifying / 17 no qualifying report) mean 0.6684, seed range 0.6547–0.6829. CD79B (20 / 43) mean 0.4434, seed range 0.4314–0.4605. The gray diamonds are a training-prevalence control: 0.4565 for MYD88 and 0.4860 for CD79B. It can fall below 0.5 because each fold uses its own training prevalence. The range spans three correlated seed runs and is not a confidence interval. Scores were never flipped after seeing outcomes.

What the label means: a reported qualifying alteration (reported, Pathogenic/Likely Pathogenic, origin not "Not Detected") versus no qualifying report. It is not biological wild type and does not prove full assay coverage. IRF4 was excluded before fitting because it had only two positives. Scan–specimen timing was not clinically adjudicated. FAC job 3067508 ran the ten audit/baseline tests, and all ten passed.

What we do not claim: external validation, clinical utility, a confirmed imaging–genotype discovery, or any frontier-model failure. This is also separate from the historical 33-patient Box-subset baseline, which is now in Appendix D. Its value for the eval is as an anchor for a future real-data task, where an agent must reconstruct this cohort and labels correctly even though prediction is weak.

## Execution evidence ladder

Each row is a different level of evidence. SDK packaging: 16 task archives (endpoint, claims, geometry and integrated; two seeds each; flawed and valid variants) passed official SDK validation with zero problems on CLI 2026.11.12.2 / SDK 0.34.0. This replaces the earlier 12-archive check, which excluded the integrated task. Packaging is not execution. Local pilots: 12/12 attempts passed (10 frozen + 2 exploratory), with 40/40 frozen fixture replays. These are real agent runs, but not on Valkyrie. Strict replay: the 10 frozen submissions re-passed all 40 fixtures under 8 s CPU, 12 s wall, 512 MiB and 1 MB output, with no model calls.

Grader review: every fix from the implementation review is in place. Replay timeouts are now classed as resource limits, invalid submissions are separated from infrastructure errors, resource limits are disclosed, and the frozen oracle is exported. The final local suite ran 60 tests: 59 passed and one numerical test was skipped locally for a missing dependency. That same numerical test ran inside FAC's separate 10/10 audit/baseline suite. The two suites overlap, so we don't add them up as 70 independent validations.

Still open: the root/container verifier path is untested, and the Valkyrie oracle smoke and hosted frontier run are waiting on organizer access and credits. The read-only preflight found no Docker daemon or provider credentials locally, which is expected. No platform run ID, dataset upload or submission exists. The launch sequence is in docs/research/valkyrie-integration.md.

## Next steps

Decision: keep the harness and the passing controls, and do not pitch this version as a frontier-failure benchmark. A truthful demo shows the research question, the task, the executable verifier, the clean twin and the held-out seed, and states plainly that both models passed all 12 attempts (10 frozen + 2 exploratory). The 16 archives are packaged and validated but not yet executed on the platform. Once access arrives: run oracle smoke first, then the frontier tasks, and record run IDs, dataset digests and rewards. Next experiment, per the final report: tasks that require expert-adjudicated research decisions from genuine evidence, with a clear contract but less procedural scaffolding, frozen as a new development version. Held-out results stay held out. If that version also passes, stop at the predeclared cap and report it as a capability result rather than manufacturing difficulty.

## Appendix A

Domain sources are in docs/research/pcnsl-literature.md and pcnsl-sources.json. Several clinical studies were available only as abstracts. Reported AUROCs come from different cohorts, endpoints and splits, so they were not pooled.

## Appendix B

Evaluation sources are in docs/research/evaluation-literature.md and evaluation-sources.json. Search method: four broad queries returned 49 raw records. That is not 49 unique studies. No Semantic Scholar records appear in the saved lists. Primary-source follow-up was added on top. There is no PRISMA flow and no claim of exhaustiveness.

## Appendix C

Limitations are listed explicitly. Two of them changed in this refresh. First, all 16 archives, including the integrated task, now pass SDK packaging; that is still not execution. Second, the hosted-release baseline is descriptive internal CV only. Provenance hashes for every input are in build-status.json.

## Appendix D

This is the historical schematic, moved here from Results so that it doesn't get confused with the 63-patient hosted-release baseline. It uses the 33-patient exact-matched Box subset, which is small, retrospective, single-institution and cross-validation only. Switching IRF4 from "any listed" (4 positives, 4 folds) to "reported pathogenic" (2 positives, 2 folds) changes the problem before any model is fit. The legacy and reported-pathogenic AUROCs are deliberately not on the slide: they use different labels and folds, and neither establishes prediction. These results support no clinical-utility, generalization or frontier-failure claim.
