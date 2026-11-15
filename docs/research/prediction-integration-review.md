# Independent integration review: prediction_data → prediction_eval → prediction_export

Reviewer: Claude Code, Opus 5.5 (`claude-opus-5-5`), 2026-11-14. Read-only review: no code edits, model calls, subagents or patient data. Scope:
- `pcnsl/prediction_data.py`, `pcnsl/prediction_eval.py` and `pcnsl/prediction_export.py`;
- the aggregate catalog `pcnsl/results/20261114-prediction-data/` and the FAC baseline report `pcnsl/results/20261114-prediction-baselines/` (job 3067848);
- the segmentation docs and the exact track prompt.

I wrote `prediction_export.py`, so this review of that module is not independent. The checks below are mechanical, so others can rerun them.

Revised 2026-11-14 after root's scientific correction: the permutation-null scope and the below-chance wording.

No packages or tools were installed for this review or for the exporter work. Checks used system `python3` (stdlib only) and the existing repo-local `.venv-valkyrie`. Per Jin's 2026-11-14 instruction, any later dependency must go inside a project, conda or virtualenv environment, or inside the task's container image. That includes nibabel, nnU-Net, PyRadiomics, TabPFN, uv and the Valkyrie CLI. Never install them system-wide, globally or at user level.

## Checks run (aggregate artifacts and synthetic data only)

| Check | Result |
|---|---|
| All 439 released feature names against the exporter's name validator | 0 rejected; longest is 71 characters; names with region spaces and `(voxels)` units pass. Values are not changed by names. |
| All 8 catalog feature groups (`spatial` 120 … `all` 439) | Valid names; every member is a known feature |
| Exporter AUROC/AP/Brier vs `prediction_eval` on 300 random tie-heavy cases | Maximum absolute difference 0 |
| Fold mapping | `build_eval_fold` takes `make_folds(dataset, gene, seed=20261114)[k]['test']`, the same call every comparator arm uses. Its test confirms that crosswalked held-out case IDs equal that fold's test rows. Default `min_class_count=5` matches the pilot spec. |
| Feature values | The exporter applies `canonical_matrix` (6 significant digits) and rejects non-canonical payloads. The track B (agent) task therefore sees the same numbers as the logistic regression, TabPFN and track A arms. |
| Row/label alignment in `load_dataset` | `patients` is shuffled once, then `X`, `labels` and `case_ids` are all built in that same order. Row order is independent of labels, and `make_folds` orders by a SHA-256 key, not by row order. |
| Exported task visibility | Gold labels exist only in `tests/`. The agent's build context and instruction are byte-identical under flipped held-out labels (exporter tests). |

## Blockers (must be resolved before a scored hosted agent run)

1. **The source data is public, so internet access means label lookup.** UCSF-PCNSL v1.0 is open data on AWS, including the mutation table and the feature CSVs. An agent with network access could download the release and match its 439 rounded feature values to a subject, recovering the held-out label exactly. Only a network policy keeps the task from being trivially leaky. The instruction also names the cohort.
   - **Gate:** use the exporter's default agent `no-network`, or an allowlist containing only the model API host. Before scoring, show on the actual provider that egress beyond that host is blocked; the local Docker provider supports only unrestricted egress.
   - If the allowlist cannot be shown to hold, do not score track B. Consider removing the cohort name from the instruction (a new version), although that is not sufficient on its own.
2. **Separate-verifier support is unverified on hosted Valkyrie.** It appears only in the Tracker source at commit `1fe5c33`, not in the public docs. The run order must be: dataset push → oracle on one task (expected `reward` 0.5, `valid_submission` 1) → frontier agent. If the hosted Tracker ignores separate mode, the verifier's marker check should produce an infrastructure error. Do not remove that check to get scores.
3. **There is no aggregator for the agent track.** The primary analysis needs code that joins each task's carried `/workspace/output/predictions.csv` with the private gold and crosswalk, then pools out-of-fold predictions per gene. It would then call the same `prediction_eval` metrics, bootstrap and paired-difference code against the logistic regression, TabPFN and prevalence arms on the same patients. Without it, the only output is Valkyrie's mean per-fold reward, which:
   - counts invalid submissions as 0;
   - is not the prespecified pooled metric.
4. **The track B budget is not prespecified.** `prediction-pilot-v1.json` bounds track A (4 prediction calls, 8192 tokens). It says nothing about Valkyrie agent runs. Before launching, record:
   - the tasks (gene × fold; the pilot is MYD88 and CD79B fold 0, so 2 tasks);
   - the harness and agent version, and the exact model ID;
   - concurrency, the 1800 s timeout, and the retry policy (none);
   - a cost ceiling;
   - that a failed run is reported, not rerun.

   A full run is 10 genes × 5 folds = 50 tasks per model, and only that scale gives pooled out-of-fold metrics.
5. **Redistribution terms and the TabPFN image.** Before `valkyrie dataset push` of task folders that hold patient-level rows and labels, confirm that the UCSF-PCNSL licence and terms permit redistributing derived rows to the hackathon organization. For TabPFN, the checkpoint licence must permit baking it into an uploaded image. Neither the default image nor a TabPFN image has been built (no Docker on teal).

## Limitations (report; don't block on them)

- **Metric granularity.** A fold has about 13 patients. In MYD88 fold 0 there are about 4 negatives; in CD79B about 4 positives. A per-task AUROC therefore moves in steps of roughly 1/36 and is not interpretable alone. Use pooled out-of-fold estimates with patient-bootstrap intervals, plus mean within-fold AUROC.
- **Below-chance controls are possible under the null; they are not evidence of anti-signal.** With small n, stratified folds and an L2 logistic regression (C=1) on 439 features and about 51 training rows, pooled cross-validated AUROC below 0.5 can occur by chance when there is no signal. CD79B 0.347, KMT2D 0.350 and CDKN2A 0.424 therefore do not establish anti-signal. They also do not establish a universal, systematic below-chance bias for logistic regression; root's synthetic null check (mean about 0.49, SD about 0.13) is consistent with noise. `prediction-protocol.md` already notes that a label-permutation null is missing. A permutation null for the *fixed* logistic regression pipeline calibrates **that pipeline only**. It is not a chance reference for TabPFN, the direct-LLM arm or the agent. Each adaptive or model pipeline needs its own valid null, or must be judged through paired comparisons on identical folds and patients (the aggregator's paired differences). Never use a null to pick genes.
- **Attainable performance is not established.** The controls are full-feature logistic regression MYD88 0.562 and CD79B 0.347, with TabPFN pending. If no arm beats its own valid null, or no arm differs in paired comparison, then an agent near 0.5 shows only that no tested method found signal at n=64. It is not a frontier failure.
- **Feature semantics.** All imaging features are PyALFE summaries, individual-lesion aggregates and shape/first-order radiomics computed by the release from its expert reference masks. They are not raw-image understanding, and they inherit annotation quality. That matters for the segmentation follow-up.
  - Sex is the only clinical variable; age is excluded for date-shift reasons.
  - One patient lacks the FLAIR summary.
  - CDKN2A and CDKN2B labels are partly co-derived: delimiter-split gene tokens and likely co-deletion. They are not independent endpoints.
- **Label semantics.** The labels mean a qualifying pathogenic or likely-pathogenic report versus no report, among patients in the mutation table. Panel coverage and scan/specimen timing are unverified (`metadata` flags both as False).
- **Pseudonyms are reversible.** `case_ids` come from `random.Random(20261114)` over sorted public subject keys, and the seed is recorded in the metadata. Anyone with the public release can reproduce the mapping. This is harmless because the exporter and track A re-key rows and never emit `case_ids`, but do not describe them as anonymization.
- **Cross-task overlap.** Each patient is a training row in 4 of the 5 fold tasks for a gene. Isolated sandboxes prevent cross-task lookup only if agents have no shared memory.
- **What is graded.** Only the probability file is graded, not how it was made. Inspect the traces.

## Does the task meet the track criteria?

The real task is defined and has integrity: train on labeled rows, predict held-out probabilities, grade held-out AUROC/AP/Brier with labels the agent cannot see. It is not a code-repair task, a checklist or a thresholded pass, and it uses identical folds and values across arms.

| Criterion | Assessment |
|---|---|
| Execution | Strong once blockers 1–3 are closed. Leakage tests and the separate verifier are good material for the demo. |
| Importance | Plausible (radiogenomics in a rare lymphoma). The claim must stay at "reported alteration from released derived features". |
| Novelty | Moderate. Agentic tabular radiogenomics with fail-closed grading is uncommon, but the task form is standard. |
| **Difficulty** | **Not yet demonstrable.** The track asks for tasks frontier models get wrong. That needs a comparator showing performance is attainable, beyond that comparator's own valid null, and the current controls do not show it. An agent at chance would then be a measured null, not a frontier failure. Present it that way. Do not choose favourable genes or add artificial difficulty. |

## Segmentation extension as the next increment

This is viable, and it is the more interpretable path to "frontier models get it wrong", because Dice against an anatomical reference has a well-defined meaning and ceiling. The smallest honest increment:

1. **MRI → lesion mask in one reference space.** Use a few held-out patients and the same Harbor pattern: separate verifier, only `/workspace/output` carried, no-network agent, gold masks only in `tests/`. Grade validity, Dice, lesion-level detection and volume error. Start with the FLAIR-space abnormality mask, but only after confirming the target definition: the audit could not establish whether the FLAIR and T1Post mask families are the same lesion definition.
2. **Gates specific to this repo:**
   - **Size:** per-patient images are tens of MB gzipped, so check them against Tracker's `DATASET_TASK_UPLOAD_MAX_BYTES`.
   - **Grader:** the grader needs NIfTI reading. Either bake nibabel into a pinned verifier image, or parse NIfTI-1 with stdlib.
   - **Tools:** the agent toolbox must be offline (SimpleITK/nibabel exist on FAC; nnU-Net and PyRadiomics do not).
   - **Mask leakage:** confirm that skull-stripping, cropping and normalization did not use the masks.
   - **Licence:** the same redistribution check as blocker 5.
3. **Later:** reference-mask features vs agent-mask features feeding the *same* frozen predictor and folds. Once a predictor shows non-null signal, this localizes error propagation.

Do not start the segmentation extension until the tabular track's network gate (blocker 1) and the oracle run are done. It reuses that same infrastructure.
