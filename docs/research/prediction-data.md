# Actual public PCNSL prediction inputs

`pcnsl.prediction_data.load_dataset(root, seed=20261114, min_class_count=5)` reads the hosted UCSF-PCNSL release directly on FAC. It never reads the internal research cohort, its crosswalks, or its feature values. Patient-level output stays on FAC; only feature names, aggregate missingness, gene counts and content-manifest hashes belong in this repository.

The returned object contains `case_ids`, `feature_names`, numeric-or-null `X`, `labels` (gene to binary vector), `feature_groups` (group to feature names), and aggregate `metadata`. Rows are shuffled unique patients; case names are seeded random 96-bit tokens, not hashes of patient identifiers. These are pseudonyms, not a claim that feature rows are anonymous. No crosswalk is saved. Patient IDs and session IDs are private join keys only. Dates, accessions, clinical free text, imaging paths and PyRadiomics diagnostics are excluded from model inputs.

## Feature families

The original SCS canonical loader was inspected read-only at `dev/genet/exp/20260325_allfeatures_loo/generate_figures.py`, along with the later spatial-analysis method. Its families were regional fractions; intensity/distance/first-order measurements; all numerical MRI measurements; and age/sex. The public extractor follows those families without copying the internal cohort or its numerical values.

For features associated with the FLAIR and T1Post reference-space masks, the extractor retains:

- Released summary metrics: total and regional volumes, regional fractions, lesion count/burden, relative T1/T1Post/FLAIR/ADC signals, ADC summary measurements, enhancement and ventricular distances.
- Released PyRadiomics `original_shape_*` and `original_firstorder_*` measurements, with a fixed allowlist. The inspected public schema does not contain texture matrices or wavelet radiomics, so none are invented.
- Individual-lesion features collapsed to one patient row: sum additive volumes, volume-weighted means of remaining measurements, and the largest lesion's measurements. The largest lesion is chosen by segmented volume, not outcome. Lesion count is retained. Weighted means use the available finite measurements and their volumes; absent measurements are null. A sum is null if any contributing lesion measurement is missing. A missing/zero/negative lesion volume fails extraction rather than fabricating weights.
- Released sex mapped Female=1, Male=0, other/missing=null. An entirely unobserved sex column is omitted. Age is excluded: the dictionary identifies birth and scan dates but does not establish a common date-shift policy that would justify subtraction.

`feature_groups` contains overlapping selections `spatial`, `intensity`, `morphology`, `radiomics`, `lesion_aggregates`, `clinical`, `all_imaging` and `all`. The full matrix is intentionally broader than the historical ten-fraction baseline; feature-selection and imputation must be fit within training folds. Duplicated concepts across summary and individual aggregates are retained transparently and should be assessed by ablation, not silently selected using held-out outcomes.

Multiple scans or duplicate feature files for a patient/sequence/family are rejected. Missing summary or radiomics files yield nulls; patients with other available imaging features remain eligible. Patients without mutation records never receive negative labels. Unknown imaging columns fail closed, even when their values are numerical. Recognized nonfinite/missing numerical values become JSON null; arbitrary text in a numerical metric fails extraction.

## Labels and limitations

A positive is a reported alteration whose classification is pathogenic or likely pathogenic and whose genetic origin is not `not detected`. Gene fields are tokenized. Duplicate variant records count once per patient. Every observed gene is catalogued; an endpoint enters `labels` only when at least five included patients are positive and at least five have no qualifying report.

The negative class means **no qualifying report among patients with mutation records**. It does not prove biological wild type, assay coverage, or a complete negative panel. Labels combine released records at patient level; this does not establish scan/specimen pairing, pretreatment status or a fixed temporal prediction horizon. Those limitations remain explicit metadata and prevent interpreting this internal benchmark as clinically validated mutation prediction.

No normalization, imputation, target-based feature selection, fitted predictor or model API call occurs during extraction. The private matrix is suitable for an explicitly limited internal prediction experiment, not for claiming out-of-distribution clinical performance. Future validated temporal/panel annotations can define stricter cohorts without substituting private records.

## Verification

The extractor's fixtures exercise duplicate-patient/variant records, genomically unobserved patients, duplicate scan mappings, multilesion volume weighting, missing numeric values, leaked numeric identifiers, invalid free text and gene thresholds. The aggregate catalog records actual cohort sizes, all feature names, missingness and source hashes after the FAC run. A feature manifest hash hashes sorted content hashes without releasing per-patient filenames or a patient-to-file mapping.

See [the segmentation audit](segmentation-audit.md) for image/mask feasibility and unresolved target/provenance definitions.
