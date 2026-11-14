# Hosted PCNSL v1.0: audit scope and model-facing extract contract

Audit date: 2026-11-14. This document separates public source documentation, actual local inventory, and eligibility for model-facing evaluation. The original archive and patient-level tables remain on FAC.

## Acquisition and current evidence

The requested destination is `/mnt/fac/CX500002_DS6/jkw/data/ucsf-pcnsl/hosted-v1.0-20261114/`. The acquisition worker owns the archive, signed download credential, extraction and status. The inventory script never reads the signed URL, never changes research originals, and does not extract or repair the archive.

Expected object: `pcnsl-dataset_v1.0.zip`, 16,659,458,958 bytes, S3 Last-Modified 2026-04-13, dataset DOI `10.58078/C2RP4V`. These are acquisition metadata, not the acquisition date of any patient image. The archive's SHA-256 and successful extraction must be recorded by the acquisition worker before interpreting the inventory as complete.

**Actual hosted inventory completed at 20:40:38 UTC:** all 16,659,458,958 archive bytes received; ZIP CRC checks passed; 3,592 files extracted (17,612,455,015 bytes; 5,543 ZIP entries including directories). Archive SHA-256: `4a45cbad0eee0cd7a3e6827c866f4041aeafb641a85ba6bed6304e3ce311138f`. Aggregate evidence is in [acquisition.json](../../pcnsl/results/20261114-hosted-release/acquisition.json) and [aggregate_inventory.json](../../pcnsl/results/20261114-hosted-release/aggregate_inventory.json).

The transfer initially stalled because the detached user service lacked the SSH session's proxy environment. The corrected worker reads an owner-only, allowlisted proxy configuration. The resumed service completed without changing the source or discarding the partial archive.

| Observed hosted content | Count / interpretation |
|---|---|
| Imaging patients and sessions | 150 patients, 150 sessions. |
| T1, CE-T1, FLAIR, ADC | Each present for all 150 patients; 300 files per sequence across two reference spaces. No DSC/CBV sequence detected in this inventory. |
| Registration spaces and masks | 600 image files per FLAIR/T1Post reference space; 300 connected-component mask files. Geometry/annotation validity is not established by file presence. |
| Lesion summaries | 291 files across 149 patients; fewer than two per patient. |
| Per-lesion features / radiomics | 300 per-lesion CSVs across 150 patients; 293 radiomics CSVs across 150 patients. |
| Clinical tables | Demographics 150 rows; biopsy/diagnosis timing 150; diagnosis history 174,174; administered medications 228,110 covering 144 patients; ordered medications 120,047 covering 149. |
| Genomic records | 2,469 rows across 64 patients, all with imaging and one distinct observed collection-date string per patient. This is not a verified complete-assay denominator. |
| Genomics plus FLAIR summary | 63 patients, all with all ten declared spatial metrics finite; one genomic patient lacks a FLAIR summary. All 149 available FLAIR summaries passed this finite-metric check. |
| Qualifying reported alterations in these 63 | MYD88 46, CD79B 20, IRF4 2; any-listed counts are 47, 22, 9 respectively. Negative means no qualifying record under this endpoint, not biological wild type. |
| Box comparison | Exactly 5/5 metadata/dictionary files and 33/33 staged FLAIR summary files have identical SHA-256 hashes; no missing, different or ambiguous matches. |
| Bundled documentation | No README, LICENSE, or dataset-description document matched the inspector's standard names. The license evidence comes from the external official registry; archive filename alone does not establish all release metadata. |

The existing 33-patient Box-derived analyses can now be described as using a **source-byte-matched subset of the hosted release** for those verified input files. Their selection still uses the internal scan/specimen crosswalk; they are not an independent external cohort, and this comparison does not reclassify internal-control feature values as public-source features.

Of 1,200 inspected metadata JSONs, PatientName and PatientBirthDate keys were present but empty in 600. PatientID, accession, study/series/SOP UIDs and several date fields were nonempty in 600; study descriptions were nonempty in 1,200. Device serial numbers, station names and protocol descriptions also occur. These are **field-presence observations**, not a determination whether identifiers were replaced or dates shifted. Clinical birth/death dates and diagnosis/medication text are also present. Exclude all of these from the proposed agent package; a broad de-identification clearance is not claimed.

The official sources advertise 150 patients, four MRI sequences and 64 genomic subjects. Public tutorial instructions describe derivatives rather than raw MRI. Companion release-preparation material mentions a cleaned 149-subject revision; that is a reason to pin bytes and provenance, not permission to substitute another release. See [the literature/source review](pcnsl-literature.md) and [official registry](https://registry.opendata.aws/ucsf-pcnsl/).

## What the inspector establishes

`pcnsl/inspect_hosted.py` uses only the Python standard library and reads the extracted tree on FAC. It reports aggregate counts for distinct image subjects/sessions, source sequences, reference spaces, lesion masks and feature families; clinical schema names and nonempty counts; mutation-record subjects, controlled classification categories, sample-date multiplicity, and prespecified gene counts. It reports selected sensitive JSON field names and nonempty-file counts without outputting values. Exceptions suppress path/value details. Symlinks are skipped.

The Box comparison reads only the existing FAC staging directory. Five metadata/dictionary files and available lesion-summary files are matched by relative identity and compared with SHA-256. A match proves those files are byte-identical. It does not prove that entire releases match, establish an independent patient cohort, validate diagnoses or confer permission to transmit source records to a model service. Missing and ambiguous matches remain explicit.

The inventory does not validate image geometry, pixel-level identifiers, complete DICOM de-identification, assay completeness, annotation quality, diagnosis adjudication or treatment-naive status. JSON checks use a fixed field allowlist; an absent flag is not proof of absent identifying content. No original clinical row, date, patient identifier, free text, UID or patient-specific filename belongs in a committed audit output.

## Proposed model-facing extract, built only from hosted files

This is a specification, not an assertion that these extracts already exist or have passed field-level sanitization and validation. The current workflow keeps patient-level data on FAC and makes no external model calls.

| Output | Allowed fields | Construction and exclusions |
|---|---|---|
| `participants.json` | `case_id`, age at selected baseline, documented sex category or unknown; cohort inclusion flag where adjudicated | Generate new random pseudonymous IDs on FAC, independent of released IDs and internal research codes. Keep the crosswalk private. Derive age locally from documented fields; do not expose birth date, exact calendar dates, ZIP codes or free-text demographics. |
| `scans.json` | Random `scan_id`, `case_id`, relative study day, sequence-presence flags, QC flags, numeric acquisition parameters needed for the task | Choose one prespecified baseline or retain visits with patient grouping. Relative day zero is within patient, not a shared calendar origin. Retain only reviewed acquisition parameters and categorical scanner/site aliases; exclude original accession, UID, patient name, protocol/free-text descriptions and raw DICOM headers. |
| `specimens.json` | Random `specimen_id`, `case_id`, relative collection day, documented specimen type, assessment/completeness state | Do not infer a passed assay from a mutation row. Missing panel coverage or assay status must remain unknown. Do not invent full revision history or report dates absent from the release. |
| `variants.json` | Random specimen link, prespecified gene, normalized classification category, reported flag, detection category where documented | A dictionary-grounded mapping is required. Exclude raw report text and precise rare-variant strings when unnecessary. Sequence variants, CNV and rearrangements remain distinct. Use explicit unknown states. |
| `features.csv` | `case_id`, `scan_id`, frozen numeric feature list, availability flags | Start with the ten previously defined FLAIR regional lesion fractions, tumor volume/ADC summaries only when dictionary and geometry support them, plus required covariates. No clinical dates, source paths, research split labels or report-derived outcomes masquerading as predictors. |
| `geometry.json` | Numeric affine matrices, shape, voxel spacing, units, scale/offset, reference-frame labels; small synthetic arrays for repair tasks | Actual images stay local unless a separate reviewed image export is prepared. Strip all incidental metadata from any later image export. Synthetic geometry fixtures need no patient source content. |
| `task/` | Instructions, train features/labels where needed, unlabeled test features, executable starter code | Per-task IDs may differ. Hidden test labels, crosswalks, previous answers, unrelated folds and raw source files must be inaccessible to the agent sandbox. |

The earlier Box feature mapping was `percentage_volume_in_{Frontal,Parietal,Occipital,Temporal,AnteriorTemporal,MiddleTemporal,PosteriorTemporal,Parietal_Occipital,CorpusCallosum,CorpusCallosum_Rostrum}`. The hosted dictionary and tables must confirm these metrics before reuse. Do not silently replace hosted values with internal-pipeline values.

### Endpoint and time contracts

For each prediction endpoint, freeze the selected tumor specimen and scan rule before model evaluation. A convenient but explicitly limited endpoint is **reported qualifying alteration**: `reportedalteration=True`, classification Pathogenic/Likely Pathogenic, and genetic origin not Not Detected. It is not proof that an unlisted gene is biologically wild type. Count label eligibility and class sizes at the patient level after selection, not across all variant rows or repeated specimens.

Date differences are valid only if the release's date-shifting convention preserves the intervals used. Validate birth/diagnosis/scan/specimen relationships locally without outputting dates. When the convention or chronology cannot be established, exclude that derived claim or use a synthetic documented timeline task. Do not apply heuristic century repairs without a release-specific justification.

Ordered and administered medications are separate evidence. An order alone cannot establish exposure. A missing administration record cannot prove absence of corticosteroids or systemic therapy. Consequently treatment-naive labels require an explicit ascertainment rule and uncertainty state.

## Real-data anchor task now supported by the hosted records

**Proposed task: reconstruct and audit a release-derived reported-alteration cohort, then evaluate a fixed numeric baseline.** Give the agent a deliberately bounded, locally prepared package: randomized case IDs for the release population, a mutation-record-presence roster, normalized variant categories for MYD88/CD79B, and the ten declared FLAIR spatial features. The verifier retains the privately constructed cohort and labels. Do not label the roster as proof that every gene was tested.

The correct reconstruction has 64 people with mutation records and 63 with available FLAIR summary files; all 63 also have all ten required numeric features finite. Within the 63 file-overlap cohort, the reported-qualifying MYD88 endpoint is 46 positive / 17 no qualifying report, and CD79B is 20 / 43. The task should preserve the difference between any-listed variants and qualifying reported variants, prevent duplicate variant rows from multiplying patients, and explain why the remaining release subjects cannot simply be called wild type. IRF4 has two qualifying positives and is excluded from five-fold prediction before fitting.

This anchor can test label construction and missingness directly without exposing headers, exact dates, variant prose, raw sequencing records, or internal research crosswalks. Source-derived numeric task data remain on FAC pending field-level sanitization and validation; this workflow makes no external model calls. The benchmark does not require pretending that biopsy/sample timing has been completely adjudicated: its primary endpoint is explicitly record-derived. If timing is added, use only documented relative intervals and make unresolved pairing an exclusion/uncertainty state.

## Completed fixed descriptive baseline

A public-source-only baseline ran on FAC in CPU batch job **3067508**, exit `0:0`; all ten audit/baseline tests passed on the research environment. The experiment used 63 unique patients, the ten finite FLAIR spatial features, five stratified patient folds, and seeds 11/23/37. Training-fold-only median imputation and scaling preceded fixed `C=1` logistic regression; training prevalence was the control. No hyperparameter search, demographics, internal cohort inputs, model API or patient-row transfer was used.

| Gene | Baseline | Pooled OOF AUROC: seeds 11 / 23 / 37 | Mean | Seed range |
|---|---|---|---|---|
| MYD88 | training_prevalence | 0.4565 / 0.4565 / 0.4565 | 0.4565 | 0.4565–0.4565 |
| MYD88 | spatial_logreg | 0.6829 / 0.6547 / 0.6675 | 0.6684 | 0.6547–0.6829 |
| CD79B | training_prevalence | 0.4860 / 0.4860 / 0.4860 | 0.4860 | 0.4860–0.4860 |
| CD79B | spatial_logreg | 0.4314 / 0.4605 / 0.4384 | 0.4434 | 0.4314–0.4605 |

The mean and range are descriptive across correlated seeds, not confidence intervals. Fold-specific training prevalence can produce pooled OOF AUROC below 0.5 because its predictions vary across folds; it is not a global constant. No score flipping occurred. The endpoint remains qualifying report versus no qualifying report, not wild type; clinical scan–specimen timing is not adjudicated. These results do not establish a frontier-agent failure. Full evidence: [hosted-release report](../../pcnsl/results/20261114-hosted-release/REPORT.md).

## Task eligibility gates for Valkyrie

| Task family | Minimum evidence | Current eligibility after hosted inventory |
|---|---|---|
| Synthetic research-repository repair | Independent reference implementation, valid controls, held-out fixtures, sandboxed execution | Can proceed without hosted patient records. This is frontier agent workflow evaluation, not real-data mutation validation. |
| Release/schema/label audit | Completed hosted inventory, dictionaries, reviewed model-facing schema and synthetic or approved redacted examples | Supported for local package preparation; no raw header or clinical-row transmission. |
| Tabular mutation analysis | Verified patient/sample mapping, endpoint semantics, feasible class counts, numeric feature extraction | 63 people have all ten finite spatial features and mutation records; clinical scan/specimen adjudication remains explicit. Methodological correctness can be scored even if prediction is inconclusive. |
| Image-mask geometry repair | Known image/mask spaces, affine/unit oracle, synthetic fixtures or reviewed local imaging access | Synthetic tasks available; actual-data task depends on geometry audit. |
| Perfusion genotype replication | DSC/CBV present and documented | No DSC/CBV detected in the hosted sequence inventory. ADC-only analysis is a partial replication with a different input set. |
| PCNSL versus GBM diagnosis | Independently adjudicated comparator cohort and source-confound design | Not supported by a PCNSL-only release. |
| OS/PFS or treatment-benefit prediction | Defined time origin, event/censoring data, follow-up and appropriate design | Not established by medication and diagnosis-history tables. |
| Assay-aware report-revision repair | Verified panel coverage, assay status and revision chronology | Use synthetic fixtures unless the release actually supplies these fields; never invent a real-data ground truth. |

A local reference run is not a frontier-model result, and passing an inventory is not a clinical validation. Benchmark claims must state model/version, actual evaluation interface, human baseline, clean-control specificity, and unresolved data limitations.
