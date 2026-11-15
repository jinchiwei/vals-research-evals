# triage_pharyngitis: sore-throat triage from a phone throat photo and symptoms

Worker: Claude Opus 5.5 (claude-opus-5-5), 2026-11-14, teal. Clean-room: built only from the public
dataset, the published paper and code written here. Nothing was read from the private strepnet or
curiedx folders.

## Verdict

- **Licence gate: passed.** The dataset is CC BY 4.0 on figshare. That allows redistribution, including
  commercial use and adapted versions, provided we credit the source, link the licence and say what we
  changed. So a subset can go inside a task image uploaded to a third-party platform.
- **Built**: the data checks, the split, the gate, the grader, the four comparators, the self-check, the
  tests and the export (`triage-pharyngitis-0001`).
- **No comparator clears the clinical gate on the hidden patients.** Under DESIGN.md this family is a
  "both fail" case: either the task is too hard or the labels lack signal. The label findings below point
  to the labels. I recommend it as a calibration and validity control, not as evidence of a frontier gap.

## Licence and ethics findings

- **Repository.** Springer Nature figshare, doi:10.6084/m9.figshare.28163513.v1. It is the only version,
  published 2025-08-14. Its `license` field reads "CC BY", https://creativecommons.org/licenses/by/4.0/.
- **Key clause.** CC BY 4.0 §2(a)(1) grants the right to "reproduce and Share the Licensed Material, in
  whole or in part; and ... produce, reproduce, and Share Adapted Material", subject to attribution
  (§3(a)). The legal code is saved next to the data.
- **The article has a different licence.** The article is CC BY-NC-ND 4.0. We redistribute none of its
  text or figures.
- **Consent and ethics (paper, Methods).**
  - Patients gave "informed written consent ... including permission for anonymized clinical data and
    images to be used in current and future research and publications internationally".
  - Ethics approval: IR.BPUMS.REC.1403.282.
  - Direct identifiers were removed, and "facial features ... were obscured or cropped".
- **What I found myself.**
  - **Privacy:** 216 of the 741 released JPEGs carry EXIF GPS coordinates. Others carry capture
    timestamps, and the camera make and model are present in most files.
  - **What we did about it:** we remove all EXIF, XMP and comment segments losslessly before anything is
    redistributed. The pixels are unchanged and a test verifies this.
  - **Faces:** a thumbnail review of all 741 images showed intraoral crops, with lips and teeth in some.
    I saw no faces. This was a thumbnail check only.
  - **Recommendation:** the coordinator may want to tell the authors and figshare about the GPS
    metadata.
- **Consent caveat.** Consent covers "research and publications". A benchmark on a third-party platform
  is research use, but I did not check this with the authors.
- **ResNet-50 weights.** We use torchvision IMAGENET1K_V2. The code is BSD-3. Whether ImageNet's terms
  pass on to the trained weights is unclear, which is the usual caveat (unverified).

## Verified data facts (from the release, not the paper)

| Item | Value |
|---|---|
| Rows / images | 742 rows, 741 images. Patient 666 has no image. One image per patient. Folder names vary (`001.jpg`, two timestamped names). |
| Image formats | 740 JPEG, 1 PNG saved with a .jpg name (RGBA). |
| Image width, px (p5 / p50 / p95; min to max) | 400 / 1263 / 2674; 289 to 5688. |
| Image height, px (p5 / p50 / p95; min to max) | 294 / 864 / 2314; 137 to 4762. |
| Images under 224 px on the short side | 12 |
| Brightness and sharpness spread | Mean luma p5 to p95: 80 to 173. Laplacian variance at 256 px, p5 to p95: 39 to 506. Blurred and lip-focused photos are kept deliberately. |
| Devices (EXIF) | Samsung SM-G998B (S21 Ultra): 388. Xiaomi 2201117SG: 290 (the paper says Redmi 8 Pro). No EXIF: 63. |
| Symptoms | 20 binary fields, no missing values. Sore throat 45%, cough 33%, rhinorrhea 28%, fever 21%. Paper Fig 3a reports different percentages, apparently as shares of all symptom mentions. |
| Age, sex | Age 2 to 83, median 28. 376 M / 365 F among the patients with images. No missing values. |
| Physician votes per patient | 3 to 9: 312 have 4 votes, 250 have 5, 136 have 6, 37 have 9, 6 have 8 and 1 has 3. The paper says 4 to 9. |
| Labels | There is no final-label column. Strict majority bacterial: 105. Exact ties: 100. Unanimous: 234 (paper: 182), of which only 8 are bacterial. |
| Device confound | Bacterial share by our label: Xiaomi 44%, Samsung 15%. Device stands in for city. |
| Labels versus clinical rules | Patients with cough are labelled bacterial more often (37% vs 23% in the hidden set), and patients with fever less often (21% vs 30%). The partial McIsaac score ranks the hidden patients inversely (AUROC 0.41). |

## Reference label

- **Definition.** bacterial = 1 when at least half of the physician calls are "Bacterial", so ties count
  as bacterial. This gives 205 of 742 patients.
- **Why ties count as bacterial.** If half the panel would act, a triage aid should send the patient for
  a swab.
- **Sensitivity analysis.** The strict-majority label (105 positives) is also scored as a secondary
  metric.
- **Label quality is the main limitation.** The label is a physician panel's judgement from a photo plus
  the symptom list, with one physician examining in person. There is no culture and no rapid antigen
  test. This has four consequences:
  - We measure agreement with that panel, not with bacteriology.
  - The symptoms the agent sees also informed the label, which is incorporation bias.
  - The label runs against the Centor and McIsaac items.
  - The 100 unresolved ties make the class boundary partly arbitrary.

## Split

- **Method.** Seed 20261114. Patient-level split with one image per patient. It is stratified by label
  × device and was made with `prepare_data.py`.
- **Paper split.** The paper fixes no split; it reports 3-fold CV. Its suggested test set of 182
  unanimous cases would hold about 8 positives, so I did not use it.

| Set | n | Bacterial | Ties | Female | Age < 15 | Devices (Samsung / Xiaomi / unknown) |
|---|---|---|---|---|---|---|
| Development | 561 | 155 (27.6%) | 74 | 279 | 158 | 294 / 219 / 48 |
| Hidden | 180 | 50 (27.8%) | 26 | 86 | 44 | 94 / 71 / 15 |

- **Records.** The patient-ID lists and SHA-256 hashes are in `suite/families/triage_pharyngitis/split/split.json`.
  - Hidden patient-ID hash: `9fb04c7f…0ba957`
  - Hidden case-ID hash: `dc141733…f8e9`
- **Case IDs.** They are re-drawn and are not the release's patient_ID.

## Clinical framing and gate

The gate was fixed in `grader.py` before any comparator or agent result was seen.

- **Use.** A front-desk or phone triage aid that decides who should get a rapid antigen test (RADT) and
  possibly antibiotics, and who can be sent home with supportive care. This is rule-out triage, so missed
  bacterial cases cost more than extra swabs.
- **The four gate components** (`acceptable` = all four met):

| Component | Requirement | Source and rationale |
|---|---|---|
| Operating point | Specificity ≥ 0.40 at the empirical point with sensitivity ≥ 0.85 | 0.85 matches the pooled RADT sensitivity against culture, 85.6% (Cohen et al., Cochrane CD010502, 2016; verified via the review abstract and PubMed 27374000), so the aid should miss no more than the test it gates. The 0.40 specificity floor is a stated design choice, not from the literature: the aid must spare at least 40% of non-bacterial patients a swab, or it adds little over swabbing everyone. |
| Calibration | ECE (10 bins) ≤ 0.10 and slope in [0.5, 2.0]. An undefined slope fails unless the classes are perfectly separated. | Van Calster et al. 2019 (moderate calibration is what decisions need); metrics-review §(c). The numeric bounds are a design choice sized for n = 180. |
| Net benefit | At p_t = 0.15 (refer if p ≥ 0.15), net benefit strictly above both treat-all and treat-none | Vickers & Elkin 2006. The 15% threshold is a design choice: McIsaac 1998 does not test or treat at low scores, where the GAS probability is roughly 10% or less. That exact probability is from memory and unverified. |
| Worst subgroup | At the component-1 threshold, sensitivity ≥ 0.70 in every group with ≥ 10 bacterial cases (sex; age < 15 / ≥ 15; device) | Underdiagnosis framing (metrics-review §(e)). Device is included because it is the site and shortcut proxy here. |

- **Time limit.**
  - The budget is 60 s plus 2 s per patient on 2 CPUs, which is 420 s for the 180 hidden patients,
    measured on the grader's monotonic clock.
  - A phone or front-desk answer should arrive within seconds. No published numeric standard exists
    (metrics-review §(g)), so this is a design choice.
- **Quality.** quality = clip((AUROC − 0.5)/0.5, 0, 1).
- **Validity.** Exactly one finite probability in [0, 1] per case in `predictions.json`, parsed with
  `pcnsl.prediction_eval.parse_probabilities`. Nothing is repaired.

## Comparators on the hidden patients (n = 180, 50 bacterial)

All comparators were fitted on development patients only, with 5-fold CV for C and calibration by
logistic fit. Each was run as a pipeline under `suite.core.runner` (CPU, 2 threads, teal). Bootstrap
95% intervals use 2000 resamples.

| Comparator | AUROC [95% CI] | Specificity at sensitivity ≥ 0.85 [CI] | ECE | Slope | Brier | NB gain at 0.15 [CI] | Worst-group sensitivity | Gate | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| (a) partial McIsaac, dev event rate per score | 0.595 [0.508, 0.684] | 0.03 [0.01, 0.36] | 0.039 | 1.74 | 0.197 | 0.000 | 0.92 (age < 15) | 2/4 | 0.4 s |
| (b) symptoms logistic regression | 0.585 [0.485, 0.684] | 0.13 [0.07, 0.28] | 0.026 | 1.04 | 0.197 | −0.002 [−0.014, 0.007] | 0.79 (Samsung) | 2/4 | 0.2 s |
| (c) frozen ResNet-50 + linear head | 0.657 [0.567, 0.746] | 0.33 [0.23, 0.52] | 0.041 | 0.83 | 0.191 | 0.012 [−0.012, 0.032] | 0.71 (Samsung) | 3/4 | 40.7 s |
| (d) image logit + symptoms stacker (specialist) | 0.674 [0.582, 0.758] | 0.39 [0.12, 0.58] | 0.070 | 1.55 | 0.189 | 0.006 [0.002, 0.011] | 0.64 (Samsung) | 2/4 | 35.3 s (19.3 s in the self-check) |
| constant development prevalence | 0.500 | 0.00 | 0.001 | n/a | 0.201 | 0 | 1.00 | 1/4 | 0.3 s |
| overconfident (b) with logits × 6 | 0.585 | 0.13 | 0.306 | 0.17 | 0.299 | −0.022 | 0.79 | 1/4 | 0.2 s |

- **Development CV AUROC:** rule 0.52, symptoms 0.56, image 0.69, combined 0.67.
- **Paper baselines** (3-fold CV on all images, image only): AUC 0.554 to 0.645. DenseNet121 scored
  0.645 ± 0.031.
- **Comparison with the paper.** Our image comparators (0.66 to 0.67 hidden, 0.69 CV) are in the same
  range. A frozen pretrained backbone does about as well as the paper's fine-tuned networks.
- **Within one phone the image signal is weak.** Image AUROC is 0.51 on Xiaomi and 0.64 on Samsung.
  Part of the pooled AUROC is probably the device confound (device → city → labelling prevalence).
- **Strict-majority label.** Every comparator scores AUROC ≤ 0.55 on it.

## Grader self-check

These runs went through the exported task and `suite.core.grading.grade_task`, on the real hidden
cohort.

| Pipeline | Result | Reward |
|---|---|---|
| Oracle (labels as 0.98 / 0.02) | 4/4 components met | 1.0 |
| Shipped solution (= comparator d) | AUROC 0.674 reproduced, 2/4 components, valid and on time | 0 |
| Constant prevalence | 1/4 components | 0 |
| Overconfident | Quality 0.17 but fails calibration | 0 |
| Too slow (sleeps past a 30 s test limit) | Killed at 30.0 s; ran = within_time = 0 | 0 |
| NaN output | Rejected as invalid (`non_finite_number`) | 0 |

- Results are in `split/self_check.json`.
- Tests: `tests/suite/test_triage_pharyngitis.py` (synthetic data only) gives 7 passed in the family
  env. In the core env 6 pass and the xlsx test is skipped because openpyxl is missing.

## Task, image and export

- **Build tier.** We include CPU torch 2.5.1, torchvision 0.20.1 and ImageNet ResNet-50 weights (98 MB):
  - They are a general-purpose image backbone that any clinical engineer would reach for.
  - Leaving them out would turn the task into "train a CNN from 561 photos on 2 CPUs", which no one would
    do in practice.
  - Nothing trained on throat images is supplied.
- **Agent brief.** It is in `task_readme.md` and is also written to `/workspace/data/README.md`.
- **Export.** `spec.py` builds the `FamilySpec`.
  - Hidden inputs and labels go only under `tests/`.
  - The export passes `check_no_leak` and is at `DATA/dist/triage-pharyngitis-0001`.
- **Size.**
  - `environment/` is 236 MB: 561 dev images and 98 MB of weights.
  - `tests/` is 47 MB.
  - The image was not built (no Docker on teal). The estimate is about 1.4 to 1.6 GB with the CPU
    torch wheel.
- **Grading unit.** The hidden set is one grader case, "cohort", because the metrics are defined over
  the cohort. As a result, `reward.clinically_acceptable` is 0 or 1. The fraction of components met is
  in `metrics.json` as `gate_fraction`. Reporting the fraction as the reward key would need a cohort hook
  in `suite/core/grading.py`, which belongs to another worker.
- **Export instruction text.** The generic instruction text says "one case" and "fraction of hidden
  cases". The README says plainly that the call covers the whole cohort.

## Limitations (label quality first)

1. **Labels.**
   - The reference is physician opinion, without microbiology.
   - The symptoms seen by the agent also informed the label.
   - Ties had to be resolved by our own rule.
   - The labels run opposite to validated Centor and McIsaac items (cough, fever).
   - A model can therefore score well here and still be wrong about strep.
2. **Device and city confound.** It is not removable with 2 sites, and the per-device AUROCs are near
   chance for Xiaomi.
3. **Small hidden set.** With 50 positives, the operating-point specificity CI spans about 0.12 to 0.58
   for comparator d. Gate passes and fails near the thresholds are noisy.
4. **Missing exam items.** Centor and McIsaac exam items (exudate, nodes) are not recorded, so comparator
   (a) is a partial rule.
5. **Optimistic operating point.** The operating point is chosen empirically on the hidden set.

## Unverified items

- The McIsaac probability strata used to justify p_t = 0.15.
- Whether ImageNet's terms bind the weights.
- The Docker build and the image size.
- Whether the authors meant "bacterial" as GAS specifically.
- The paper's figure percentages (read from text only).

## Files

- `suite/families/triage_pharyngitis/`:
  - `records.py`: loading, labels, lossless EXIF strip.
  - `prepare_data.py`: data checks and split.
  - `grader.py`: gate and `grade_case`.
  - `pipeline_src/predict.py`: comparator and failure pipelines.
  - `comparators.py`.
  - `spec.py`.
  - `self_check.py`.
  - `task_readme.md`.
  - `split/*.json`: aggregate only.
- Data and outputs are under `/home/jkwei/data/vals-suite/triage_pharyngitis/`. See `SOURCE.md` there.
