# PCNSL research-agent benchmark: literature and evidence map

Review date: 2026-11-14. Companion machine-readable bibliography: `pcnsl-sources.json`.

## Recommendation

Build an evaluation of **whether a research agent can produce a scientifically valid, reproducible PCNSL radiogenomics analysis**. Its primary score should measure correct labels, cohort construction, image/feature handling, statistical evaluation, and interpretation. Mutation-prediction performance is a secondary scientific outcome: weak signal or an inconclusive experiment is not itself an agent failure.

Direct MRI prediction of MYD88/CD79B has already been studied; novelty cannot rest on being the first to attempt it. The defensible proposed contribution is an executable, expert-adjudicated benchmark of consequential research mistakes using a versioned public multimodal release, paired clean controls, and realistic repository tasks. Whether current frontier agents actually fail these tasks remains an empirical question.

This is a focused primary-source evidence review, not a registered systematic review. Searches covered PCNSL radiogenomics, MYD88/CD79B/IRF4, radiomics validation, clinical timing, genomic interpretation, and reporting standards, followed by publisher/PubMed/repository verification. Reviews and commercial summaries were not used as evidentiary substitutes. Several studies were available only as abstracts; those limitations are marked below. No patient records were submitted to a search service.

## Public data: advertised scope versus verified contents

The AWS registry advertises 150 patients, T1, contrast-enhanced T1, FLAIR and ADC, lesion annotations, radiomics, and clinical information. It lists CC BY 4.0 and a controlled-access download for `ucsf-dmi/pcnsl-dataset_v1.0.zip`. The registry's wording should not be interpreted as an unrestricted anonymous object listing. [D01](https://registry.opendata.aws/ucsf-pcnsl/)

The official tutorial describes **processed derivatives, not raw MRI**, with FLAIR and T1Post reference spaces, connected-component masks, three families of lesion statistics, and eight clinical/dictionary CSVs. Its example refers to 64 genomic subjects. Its example bucket differs from the registry's current object location. [D02](https://github.com/rauschecker-sugrue-labs/UCSF-PCNSL)

The companion acquisition work reports the official landing page identifies DOI `10.58078/C2RP4V`, version 1.0, 150 subjects and 64 with UCSF500. The JavaScript page was not independently rendered in this literature workstream. A companion release audit also reports a 149-subject release-preparation branch. Neither a newer branch nor a private candidate establishes what is in the hosted archive. Freeze archive hash, access date, manifest, distinct subject/session counts, dictionary versions, and inclusion rules before building answer keys. **No claim that the public archive has passed an identity/privacy audit is made here.** [D03](https://imagingdatasets.ucsf.edu/dataset/4)

| Potential research target | What must be verified in the downloaded archive |
|---|---|
| MYD88/CD79B/IRF4 classification | Actual assayed denominator, assay/report semantics, variant class, sample-to-scan mapping, sufficient positive and negative patients. |
| Diffusion analysis | ADC scaling/units, reference image, mask alignment, acquisition parameters, definition of relative ADC and reference tissue. |
| Perfusion replication | DSC and CBV are not in the advertised four-sequence release; their availability cannot be assumed. |
| PCNSL versus GBM diagnosis | A PCNSL-only cohort provides no GBM reference population. A separately sourced comparator creates a potential source/site confound. |
| Ki-67, BCL6 rearrangement, survival, response | Dedicated pathology/outcome fields and ascertainment are required. Mutation tables and medication records cannot substitute. |
| Treatment-naive baseline | Scan, biopsy, specimen, and actual treatment dates must support the rule; order dates alone are insufficient. |
| Generalization | Single-institution random folds are internal testing. External testing requires independently sampled patients and compatible labels. |

## Evidence that directly shapes the benchmark

| Source | Cohort, input, endpoint and result | Interpretation and limitation |
|---|---|---|
| **P01 Zhou et al., 2026**, [Cancer Imaging](https://link.springer.com/article/10.1186/s40644-026-01145-2) | Retrospective 92 PCNSL; MYD88-positive 60, CD79B-positive 52, co-mutant 40. ADC and DSC/CBV measures; stratified fivefold evaluation; reported AUC range 0.652–0.861. | Direct genotype comparator. Same-cohort testing does not establish external validity. Perfusion availability is a replication constraint. Reviewed abstract and supplement descriptions; accepted early article, not yet final Version of Record when accessed. |
| **P02 LOC network, 2016**, [Neuro-Oncology abstract](https://academic.oup.com/neuro-oncology/article-abstract/18/suppl_4/iv78/2222977) | Fifty treatment-naive patients; manually segmented enhancement registered to MNI152; Sanger genotyping. MYD88 18, CD79B 15, TERT 6 positive. Voxelwise analysis used permutation and FDR. | No MYD88/CD79B location association was reported. A negative location analysis neither proves absence of all imaging signal nor makes these labels impossible. Conference-abstract evidence only. |
| **P03 Li et al., 2025**, [Blood Cancer Journal](https://www.nature.com/articles/s41408-025-01421-7) | Genomic study of 176 patients across five centers, with discovery 58, validation 82, external Chinese cohort 36. BMI subtype involves combinations of BTG1, MYD88 and IRF4. | Supports molecular relevance of IRF4, not an established MRI-to-IRF4 predictor. Genomic subtype, individual gene status, and prognosis are different endpoints. |
| **P04 CNS lymphoma landscape, 2022**, [Nature Communications](https://www.nature.com/articles/s41467-022-30050-y) | Genomic/transcriptomic study of 51 CNS lymphomas with systemic lymphoma comparators. Reports recurrent MYD88/CD79B alterations and CDKN2A loss in PCNSL. | The full CNS cohort is not interchangeable with a pure PCNSL cohort. Copy-number loss, hotspot substitution, EBV-associated disease and secondary CNS involvement require explicit distinctions. Abstract/indexed primary text reviewed. |
| **P05 Liu et al., 2025 print / 2024 online**, [Clinical Radiology](https://pubmed.ncbi.nlm.nih.gov/39615185/) | 102 PCNSL, 31 BCL6-rearrangement positive; CE-T1 and FLAIR radiomics. Random 7:3 development/test split; reported logistic-regression AUC 0.935/0.923. | Rearrangement is not protein expression or any BCL6 sequence variant. Random holdout is not external testing. Abstract only; full feature-selection nesting not verified. |
| **P06 Liu et al., 2024**, [European Journal of Radiology](https://pubmed.ncbi.nlm.nih.gov/38976966/) | 341 PCNSL: training 286, external 55 from two other centers; CE-T1/FLAIR; Ki-67 proliferation index. Combined nomogram AUC 0.877/0.866. | A useful externally tested phenotype comparator, not a mutation-prediction result. Ki-67 cutoff and labeling protocol must be checked before replication. Abstract only. |
| **P07 Nenning et al., 2023**, [Neuro-Oncology Advances](https://pmc.ncbi.nlm.nih.gov/articles/PMC10676053/) | 133 Austrian patients with MRI from nine sites, 83 included after imaging quality assessment, plus external South Korean 44. CE-T1 radiomic survival-risk model and DNA-methylation analysis. | Methylation predicting radiomic risk groups is not MRI predicting a named mutation. External univariable association and independently significant adjusted prediction are different claims and require inspecting the model-specific results. Indexed full-text passages reviewed. |
| **P08 Xia et al., 2021 print / 2020 online**, [JMRI](https://pubmed.ncbi.nlm.nih.gov/32864825/) | 240 patients: 111 PCNSL, 129 GBM. CE-T1/FLAIR/ADC with two vendors; cross-vendor train 149/test 91. CE-T1+ADC reported cross-vendor AUC 0.943. | Diagnosis task, not radiogenomics. Demonstrates why scanner-separated evaluation can differ from random mixed-vendor testing. Abstract/primary article metadata reviewed. |

Relevant standards are **P09 IPCG MRI/PET consensus** for acquisition and response comparability; **P10 EHA–ESMO** for diagnostic context and biopsy/steroid/treatment timing; **P11 AMP/ASCO/CAP** for somatic variant interpretation; **P12 IBSI** for feature definitions; **P13 Vabalas** and **P14 Varoquaux** for small-sample evaluation; **P15 CLAIM** and **P16 TRIPOD+AI** for transparent reporting. They motivate test design but are not ready-made scoring oracles. CLAIM and TRIPOD+AI are reporting guidance, not proof that a chosen algorithm or clinical claim is valid.

## Endpoint contract before any modeling

Specify patient, episode, specimen, assay, variant classes, positivity rule, observation window, and allowed missingness for every target. Preserve a reason for each exclusion.

| Target | Required distinction |
|---|---|
| MYD88 | Any qualifying MYD88 alteration versus L265P specifically; reported variant versus assayed absence. |
| CD79B | Qualifying alterations versus any string match; explicit co-mutation AND rule when combined with MYD88. |
| IRF4 | Sequence alteration versus protein/MUM1 expression, rearrangement, or a multigene subtype. This review found no verified direct MRI-to-IRF4 study; that is a search limitation, not proof none exists. |
| BCL6 | Rearrangement versus protein expression versus SNV/indel; no silent transfer of a published label definition. |
| Ki-67 | Pathology proliferation percentage and prespecified threshold; not a mutation label. |
| CNV | Gene deletion/amplification is a different variant class from point mutation. |
| Negative | Eligible, adequately assessed and negative under the release's reporting convention. No row, no sequencing, failed assay, and no report are not automatically wild-type. |

The somatic clinical-significance tiers in AMP/ASCO/CAP are not a universal mapping to germline pathogenicity terminology. Determine what the actual UCSF field means. A reported-pathogenic proxy can be a valid benchmark endpoint if named honestly and its limitations are retained. [P11](https://pmc.ncbi.nlm.nih.gov/articles/PMC5707196/)

## Proposed failure-mode suite

These are **candidate tasks**, not demonstrated frontier failures. Each should have a realistic user request, minimal necessary context, a clean control, and executable assertions where possible. Hidden tests should accept equivalent scientifically correct solutions rather than match one implementation.

| ID | Failure opportunity | Objective oracle / correct resolution |
|---|---|---|
| F01 | Combine two release versions or count rows as patients | Manifest/hash and distinct identifier reconciliation; refuse silent merging. Use a clean single-version control. |
| F02 | Many-to-many join duplicates patients with several variants or lesions | Declared join cardinality, one prediction per eligible patient, known aggregate counts. |
| F03 | Treat unsequenced subjects as wild-type | Explicit assay/report eligibility; three-state labels; verified denominators. |
| F04 | Conflate any listed variant with pathogenic alteration or L265P | Dictionary-grounded label specification and independent truth table covering relevant variant classes. |
| F05 | Choose the nearest MRI even when it follows treatment or belongs to another episode | Prespecified chronology and episode linkage; ambiguous dates excluded or analyzed separately. |
| F06 | Equate medication orders with administration | Separate order/administration evidence and temporal exposure classification; unknown exposure remains unknown. |
| F07 | Infer real elapsed intervals from incompatibly shifted dates | Read de-identification/date conventions; test preserved within-subject intervals only when documented. No speculative century correction. |
| F08 | Split lesions, sessions or slices from one patient across folds | Patient groups disjoint across every preprocessing, tuning and test partition. |
| F09 | Use a mask in the wrong image space | Shape plus affine/orientation checks and reference-space identity; visual QC where necessary. Equal array shape alone is insufficient. |
| F10 | Interpolate component labels as continuous intensities or count label sum as volume | Discrete-label preservation; foreground voxel count times voxel volume; known small phantom oracle. |
| F11 | Misread units or summary-table orientation | Dictionary and sidecar parsing; known unit conversions and independent feature recomputation. Do not apply one vendor's correction globally. |
| F12 | Average lesion means without weighting when target is total-tumor mean | Explicit patient-level aggregation; known unequal-volume lesion fixture; missing lesion values handled deliberately. |
| F13 | Impute, scale, harmonize or select features before the split | Inspect fitting boundaries and held-out perturbation tests; train-fold-only transformations, including feature selection. |
| F14 | Optimize on test predictions or use a fixed hyperparameter after choosing it on all data | Nested tuning or a genuinely untouched test partition; development and final results separately tracked. |
| F15 | Force an AUROC when one class is absent or use infeasible folds | Feasible grouped splits verified on unique patients; undefined metrics explicitly reported; no fabricated 0.5 fallback. |
| F16 | Reverse probability direction or use class labels as probability scores | Class-index contract, known scored fixture, and threshold-free versus thresholded metric checks. |
| F17 | Report the best of many genes/features/seeds without accounting for search | Preregister primary endpoint; report full search; appropriate multiplicity/sensitivity analysis; full-pipeline patient-label permutation when used. |
| F18 | Treat folds, tasks or repeated seeds as independent patients | Patient-level uncertainty; cluster correlated benchmark variants by source case; no standard-error-of-folds as a reliable patient-performance interval. |
| F19 | Call random holdout external validation or claim a second hospital from a different scanner | Explicit source, institution, period and split descriptors; check claimed independence. |
| F20 | Claim disease discrimination from an all-PCNSL cohort | Identify missing comparator; do not fabricate controls. A separately sourced comparator needs domain-confound analysis. |
| F21 | Reproduce DSC/CBV findings from ADC alone | Acknowledge absent modality; clearly label a diffusion-only partial replication with changed estimand. |
| F22 | Build OS/PFS from medication end dates or ignore censoring | Verified time origin, event definition, follow-up and censoring; decline unsupported survival modeling. |
| F23 | Claim imaging replaces biopsy or predicts benefit from association alone | Distinguish association, discrimination, prognosis, treatment interaction and demonstrated utility; evidence-backed bounded conclusion. |
| F24 | Invent literature support or merge different studies' sample sizes | Citation-to-claim checks, correct endpoint/modality/cohort/validation extraction, and acknowledgment of abstract-only access. |

F01–F16 can often be graded deterministically once the actual release is audited. F17–F24 need a mixture of reproducible statistical checks and blinded expert adjudication. Assertions about a real cohort's treatment status, clinical diagnosis, or valid negative genetics need source documentation and domain review; a synthetic truth table alone cannot validate those clinical assumptions.

## Experiments worth running first

1. **Repository repair:** a realistic label-loader or grouping bug embedded in an otherwise working analysis; require a patch, tests, and an analysis memo. Test whether the clean repository is left scientifically intact. Measure repair correctness and collateral regressions, not just whether the agent mentions leakage.
2. **Result adjudication:** present plausible competing analyses with different genotype denominators, preprocessing boundaries, uncertainty or endpoint definitions. Require an evidence-backed choice and a corrected result. Include clean analyses so reflexive rejection is penalized.
3. **Image/feature consistency:** on audited local data, compare precomputed features against independently recomputed geometry/intensity features and mismatched-space controls. External APIs receive only permitted task artifacts; raw header payloads are not needed to score these tasks.
4. **Bounded radiogenomics study:** predefined MYD88/CD79B endpoints; demographics-only, simple ADC/volume, and tabular-radiomics baselines; nested patient-grouped evaluation; patient-level uncertainty; label-permutation and confound checks. Count IRF4 cases before declaring an evaluable prediction endpoint. A sound null/inconclusive result receives full methodological credit.
5. **Cross-paper replication reasoning:** ask what can and cannot be reproduced from P01, P05–P08 with the audited release. This tests whether an agent notices missing perfusion, comparator diagnoses, molecular assays and outcomes rather than inventing them.

First establish human/expert achievable performance and run a small blinded frontier pilot. Expand only after observing reproducible errors under clear tasks. Keep development scenarios separate from held-out error families and source cases; generated variants of one bug are not independent discoveries. Measure clean-control specificity, successful complete repair, severity-weighted failure rate, calibrated abstention, and reproducibility across reruns. Log model/version, tool availability, budget, prompt, seed and environment. Do not claim contamination resistance merely because prompts were newly written: the public dataset and literature may be in model training.

## Evidence boundaries and remaining questions

- Publication success in a small retrospective cohort does not establish a clinically actionable genetic predictor; the public release may support a narrower estimand.
- Missing genomic testing can be informative. Compare assayed versus unassayed groups descriptively; adjustment cannot magically identify unobserved labels or remove all selection bias.
- Steroids, biopsy and therapy can affect imaging and diagnostic ascertainment. Use documented timing as a cohort rule or sensitivity analysis, not an invented universally safe interval. [P09](https://doi.org/10.1093/neuonc/noab020), [P10](https://doi.org/10.1002/hem3.89)
- Radiomics values depend on processing choices. IBSI definitions and computational references help test extraction; they do not guarantee stability under different scanners, segmentations or disease populations. [P12](https://doi.org/10.1148/radiol.2020191145)
- Small samples give uncertain generalization estimates; increasing repeated folds does not create more patients. The inference plan should be frozen before tuning. [P13](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0224365), [P14](https://pubmed.ncbi.nlm.nih.gov/28655633/)
- No public external PCNSL MRI cohort with matching comprehensive genotype labels was verified in this review. That is an unresolved resource constraint, not a claim of nonexistence.

## Additional primary references

- **P09** Barajas et al. (2021). *Consensus recommendations for MRI and PET imaging of primary central nervous system lymphoma: guideline statement from the IPCG*. Neuro-Oncology 23:1056–1071. [DOI](https://doi.org/10.1093/neuonc/noab020).
- **P10** EHA–ESMO (2024). *Primary central nervous system lymphomas: Clinical Practice Guideline for diagnosis, treatment and follow-up*. HemaSphere 8:e89. [DOI](https://doi.org/10.1002/hem3.89).
- **P11** Li et al. (2017). *Standards and Guidelines for the Interpretation and Reporting of Sequence Variants in Cancer: AMP/ASCO/CAP consensus*. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC5707196/).
- **P12** Zwanenburg et al. (2020). *The Image Biomarker Standardization Initiative: Standardized Quantitative Radiomics for High-Throughput Image-based Phenotyping*. Radiology. [DOI](https://doi.org/10.1148/radiol.2020191145).
- **P13** Vabalas et al. (2019). *Machine learning algorithm validation with a limited sample size*. PLoS ONE 14:e0224365. [DOI](https://doi.org/10.1371/journal.pone.0224365).
- **P14** Varoquaux (2018; online 2017). *Cross-validation failure: Small sample sizes lead to large error bars*. NeuroImage 180:68–77. [DOI](https://doi.org/10.1016/j.neuroimage.2017.06.061).
- **P15** Tejani et al. (2024). *Checklist for Artificial Intelligence in Medical Imaging (CLAIM): 2024 Update*. Radiology: AI 6:e240300. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11304031/).
- **P16** Collins et al. (2024). *TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods*. BMJ 385:e078378. [DOI](https://doi.org/10.1136/bmj-2023-078378).
