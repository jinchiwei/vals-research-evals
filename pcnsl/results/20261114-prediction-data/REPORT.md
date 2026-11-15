# Public prediction extraction, 2026-11-14

FAC CPU job **3067798** completed with exit code **0:0**. The actual hosted release produced **64 unique genomic patients and 439 numerical features**: 438 imaging-derived features and released sex. Age is excluded because consistent date-shift semantics were not established. Sex was mapped for all 64 patients, and no feature is wholly missing.

There are 128 potential summary measurements, 64 released shape/first-order radiomics measurements, 246 individual-lesion aggregates and one clinical feature. One patient lacks a FLAIR summary and remains included using other available imaging features; missing measurements are null. Exact names, missingness, source hashes and overlapping feature selections are in `catalog.aggregate.json`.

Of 460 observed gene tokens, ten meet the prespecified five-per-class eligibility rule:

| Gene | Qualifying positive | No qualifying report |
|---|---:|---:|
| BTG1 | 7 | 57 |
| CARD11 | 12 | 52 |
| CD79B | 20 | 44 |
| CDKN2A | 37 | 27 |
| CDKN2B | 24 | 40 |
| ETV6 | 9 | 55 |
| KMT2D | 18 | 46 |
| MYD88 | 46 | 18 |
| PRDM1 | 7 | 57 |
| TP53 | 5 | 59 |

These are record-derived endpoints, not proof of biological wild type or comprehensive panel coverage. Clinical scan/specimen pairing remains unverified. This is the input dataset, not a model-performance result.

The private dataset remains only on FAC at `/mnt/fac/CX500002_DS6/jkw/vals-research-evals/prediction-data-20261114/dataset.private.json`. No patient rows, private join keys, or crosswalk were transferred into this repository.

Six extractor boundary tests pass. Initial restricted-sandbox full `unittest discover -s tests` ran 66 tests with one repair-runner sandbox failure and one numerical-dependency skip. The parent agent reran the extractor and repair-runner tests outside the nested sandbox: **9/9 passed**, resolving that failure as an execution-environment restriction. Local pytest is unavailable. `git diff --check` passes. No model API calls occurred in this extraction.
