# Hosted PCNSL v1.0: verified acquisition, audit and fixed baseline

Completed 2026-11-14 on FAC DS6. All patient-level records and predictions stayed on FAC; only code, schemas and aggregate results were returned. No frontier model received these records.

## Verified acquisition

- Archive: 16,659,458,958 bytes; SHA-256 `4a45cbad0eee0cd7a3e6827c866f4041aeafb641a85ba6bed6304e3ce311138f`.
- Extraction completed at 20:40:38 UTC with CRC verification: 3,592 files, 17,612,455,015 uncompressed bytes.
- The persistent downloader initially lacked the SSH session's proxy settings. An owner-only proxy configuration fixed the transfer; existing partial bytes were retained.
- Full evidence: [acquisition.json](acquisition.json), [aggregate_inventory.json](aggregate_inventory.json).

## What is actually available

150 imaging patients and 150 sessions; T1, CE-T1, FLAIR and ADC for each patient in two registered spaces; 300 connected-component masks. No DSC/CBV image sequence was detected. There are 291 summary, 300 per-lesion, and 293 radiomics CSVs. All 149 available FLAIR summaries contain the ten declared spatial features with finite values.

Genomics has 2,469 records for 64 patients; all have imaging and one observed collection-date string, but only 63 have FLAIR summaries. This does not prove complete gene coverage, a unique specimen, or clinically valid scan–specimen pairing.

Exactly **5/5 metadata/dictionary files and 33/33 staged FLAIR summary files match Box byte-for-byte**. Existing 33-patient Box-derived baselines use a source-byte-matched subset for these inputs. Their internal crosswalk-based selection remains historical/internal; whole-release equivalence and independent external validation are not established.

The archive contains metadata/clinical fields that should not enter the agent package. JSON PatientName and PatientBirthDate fields were empty where present; patient/scan identifiers, dates, UIDs, descriptions and device information were also present. Counts establish presence only, not whether values were replaced or shifted. No identifying values were emitted.

## Fixed public-source baseline

One row per patient; 63 patients; ten FLAIR spatial fractions. No internal cohort inputs, Box data substitution, demographic date derivation, feature selection or hyperparameter search. Three prespecified seeds (11, 23, 37), five stratified patient folds; median imputation and scaling fitted only to training folds; fixed logistic regression `C=1`, `solver=liblinear`, `max_iter=1000`.

The endpoint is **reported qualifying alteration versus no qualifying report** among patients with mutation records: reported flag true, Pathogenic/Likely Pathogenic, origin not Not Detected. It is **not mutant versus biological wild type** and does not prove full assay coverage. MYD88 has 46 positive / 17 no qualifying report; CD79B 20 / 43. IRF4 has two qualifying positives and was excluded before fitting.

| Gene | Baseline | Pooled OOF AUROC: seeds 11 / 23 / 37 | Mean | Seed range |
|---|---|---|---|---|
| MYD88 | training_prevalence | 0.4565 / 0.4565 / 0.4565 | 0.4565 | 0.4565–0.4565 |
| MYD88 | spatial_logreg | 0.6829 / 0.6547 / 0.6675 | 0.6684 | 0.6547–0.6829 |
| CD79B | training_prevalence | 0.4860 / 0.4860 / 0.4860 | 0.4860 | 0.4860–0.4860 |
| CD79B | spatial_logreg | 0.4314 / 0.4605 / 0.4384 | 0.4434 | 0.4314–0.4605 |

Mean and range summarize three correlated seed runs; **the range is not a confidence interval**. The prevalence control uses each training fold's own class fraction. Its pooled OOF predictions therefore differ between folds and can yield AUROC below 0.5; it is not a globally constant score. Neither baseline's scores were flipped after observing outcomes.

These are descriptive internal-CV results with unadjudicated clinical scan–specimen timing, small selected genomic cohorts and limited features. They do not establish clinical utility, statistically confirmed imaging-genotype discovery, external generalization or a frontier-agent failure.

## Verification and next executable task

FAC SLURM CPU job **3067508** completed with exit `0:0` in 20 seconds; the baseline itself took 3.26 seconds. **All ten audit/baseline tests passed**, including synthetic numeric signal recovery, rare-target exclusion, cohort uniqueness, finite-feature eligibility, hash identity, privacy boundaries and proxy configuration restrictions. See [baseline-validation.json](baseline-validation.json) and [baseline.aggregate.json](baseline.aggregate.json).

A real-data agent task can now reconstruct the 64-record / 63-feature cohort and correct reported-alteration labels from a locally sanitized package of randomized IDs, normalized categories and these numeric features. Its verifier can check labels, missingness handling, one-patient-one-row joins, training-only preprocessing, fixed folds and bounded interpretation. This measures research correctness even when prediction is weak. The field-level sanitization contract is in [data-scope.md](../../../docs/research/data-scope.md); patient data currently remain on FAC and no external model calls are made.
