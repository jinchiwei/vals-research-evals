# Revised scope: quantitative brain-imaging agents

Jin's 2026-11-14 steering: prioritize segmentation and useful brain-imaging measurements; do not keep expanding mutation prediction where strong signal has not been established. Familiar scientific metrics are legitimate scoring rules. The benchmark unit is the frontier agent completing a real task with a fixed toolbox and hidden references.

## Coherent task families

| Task | Agent input and deliverable | Scoring | Readiness |
|---|---|---|---|
| MRI to lesion mask | Sanitized processed MRI, declared target compartment, offline tools; produce a NIfTI mask | Dice, volume error, lesion detection and false positives, geometry validity | 150 patients, 300 masks, 1,200 geometry pairs checked; target/provenance/tool overlap audit ongoing |
| Lesion quantification | Images and a supplied reference mask; produce a reproducible measurement table | Volume in mL, instance/connected-component counts under explicit definitions, ADC statistics with established units | Scorer and physical-unit audit in progress |
| End-to-end measurement | MRI to mask to measurement table using the same extractor | Stage-specific errors and downstream measurement error against reference-mask measurements | Depends on first two families; no performance claim yet |
| Genetic prediction (separate research track) | Labeled patient features and held-out test features; produce probabilities with or without tools | AUROC, average precision, Brier; matched comparators and endpoint caveats | Four direct-model calls and real TabPFN/conventional controls complete; no established frontier-specific gap |

Do not invent longitudinal targets: the audited release has one session per patient. Regional or ventricular measurements need the required atlas/tissue references and spatial definitions before becoming tasks. Do not invent physical ADC units from the name of a file.

## What makes this an agent benchmark

The evaluated model chooses and operates tools, handles images and their spatial metadata, builds/runs its analysis and writes the requested artifact. The scorer checks that artifact against hidden references. Run the same task/tool budget with different frontier agents through Harbor/Valkyrie; keep the specialist segmentation system's standalone score as a comparator, not as the frontier model's score.

A supplied-tool reproduction task measures workflow execution. A segmentation generalization task additionally requires held-out reference annotations and audited pretrained-model overlap. These are different claims. If the tool produced the original masks, reproducing it is not evidence of new anatomical generalization.

## Pilot and selection discipline

- Freeze three development patients using seed 20261114 before imaging-agent results. Keep the remaining patients separate for later held-out evaluation.
- Use complete, realistic tasks with clear deliverables, not injected code bugs or prompts that supply the correct algorithm step by step.
- Preserve easy tasks as controls if frontier agents pass them. Do not manufacture difficulty by breaking tools, obscuring necessary units, or withholding ordinary documentation.
- Label development-case selection and subsequent revisions. Score untouched cases only after fixing task/tool/reference versions.
- Keep segmentation, quantification, execution errors and biological prediction separate; do not collapse unrelated metrics into a conveniently chosen weighted score.
- Hosted runs require an actual working sandbox, isolated verifier, verified model-API-only egress or no public internet, and a fixed budget. Packaging tests are not hosted evidence.

## IRF4

The current public-release endpoint (reported alteration, pathogenic/likely pathogenic, not Not Detected) has two positives among 64 observed genomic patients. This fails the existing five-per-class eligibility rule. The earlier internal IRF4 endpoint/cohort was different; Jin's October audit also identified a strong sex association. Reconcile the original definition before adding IRF4. Do not broaden labels merely to obtain more positives, and do not infer biological wild type from absence of a qualifying report.

## Submission

Follow the exact [official prompt](hackathon-prompt.md): novelty, execution, difficulty, importance, clear results, Harbor tasks and Valkyrie execution. Jin must personally write the opening README paragraph. Claude uses Jin's build-pptx skill for slides. All new dependencies remain in project-specific environments, including inside generated task images.
