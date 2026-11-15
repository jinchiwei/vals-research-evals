# Public PCNSL mutation prediction pilot

User authorized implementation, bounded experimentation and Claude Code Opus 5.5 high workers. This round answers the actual prediction question; historical synthetic repair results remain separate.

## Frozen first round

- Source: verified hosted v1.0 release on FAC DS6; no internal cohort substitution.
- Unit: one patient. Genomically unobserved patients are never negative examples.
- Endpoint: reported pathogenic/likely pathogenic qualifying alteration versus no qualifying report, among genomically observed patients. This is not an assertion of biological wild type or complete assay coverage.
- Include every gene with at least five patients in each class; publish exclusions. Establish eligibility before model fitting.
- Use released numeric PyALFE summary/radiomics features and defensible clinical variables. Exclude identifiers, dates, free text and unsupported age calculations. Distinguish reuse of released features from rerunning image extraction.
- Fixed five-fold patient-stratified CV, seed 20261114. Each gene uses identical folds and feature representation across comparator arms. Imputation, scaling and any feature selection are fit on training rows only.
- Conventional controls: training prevalence and fixed logistic regression. Specialized foundation-model comparator: actual TabPFN, with installed version/checkpoint and runtime reported. Missing software is an infrastructure blocker, never a substituted model.
- Frontier track A: direct probability prediction from labeled training rows and unlabeled test features. No tools or held-out labels. Exact prompts, model deployments, usage and malformed responses recorded privately.
- Frontier track B: an agent may build/run the pipeline using tools, including TabPFN. This measures the complete agent/tool system and is reported separately from track A.
- Primary reports: pooled out-of-fold AUROC, average precision and Brier score, plus class counts, fold sizes, missingness, execution errors and comparator differences. No flipping scores below 0.5, test-driven prompt changes, or selecting only successful genes.
- First live prediction pilot: MYD88 and CD79B, one prespecified fold, at most two verified Versa deployments (four prediction calls total), max 8192 output tokens per call, no automatic retries. This is an engineering pilot, not a benchmark ranking. Full five-fold/all-eligible-gene evaluation follows only after payload/response validation and resource review; any changes create a new version.
- Synthetic Versa health probes: at most four short calls. Log separately from prediction attempts.
- Payload preflight: estimate token size before transmission; if rich feature table exceeds deployment capacity, stop that arm and prespecify a shared training-only representation before any scored run. Do not silently drop features for only one arm.
- All patient rows, crosswalks, prompts containing rows and individual predictions stay on FAC/SCS. Only schemas, source hashes, aggregate metrics and code return to teal/Git.
- No clinical-use, general frontier-failure, or absent-biological-signal claim from this small internal pilot. A defensible capability gap requires appropriate comparator performance and uncertainty, not merely low AUROC.

## Ownership and completion

- Dataset worker: `prediction_data.py`, extraction tests and aggregate feature audit.
- Neo Claude: `prediction_eval.py`, split/preprocessing/parser tests, scientific protocol.
- Neuronetwork Claude on SCS: live Versa deployment/client discovery, synthetic health checks, TabPFN runtime discovery. Teal initiates transfers; no new SCS-to-teal connection.
- Root: integration, bounded pilot launch, aggregate review and Valkyrie packaging alignment.
- Claude alone authors subsequent slides using Jin's build-pptx skill; refresh after actual prediction evidence exists.

Hosted Valkyrie execution remains pending organizer access. Local preparation and cluster pilots do not imply a hosted submission. Record actual worker/model identities and preserve human-only Git attribution.
