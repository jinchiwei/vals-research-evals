# Quantitative brain-imaging agent tasks: scorer prototype

Status, 2026-11-14:
- `pcnsl/imaging_eval.py` is a **scorer and task contract only**, tested on synthetic arrays.
- No real image or mask has been read.
- No Harbor task has been packaged, and nothing has run on Valkyrie.
- No segmentation method is proposed or validated.

The genetics work (track A and B pilots, controls and the permutation null) remains as a historical pilot and is unchanged. Genetics expansion has stopped.

## What the release actually provides (source-based)

Sources:
- the [AWS registry entry](https://registry.opendata.aws/ucsf-pcnsl/);
- the [official tutorial](https://github.com/rauschecker-sugrue-labs/UCSF-PCNSL);
- the release data dictionary;
- the read-only header audit (`segmentation-audit.md`, `pcnsl/results/20261114-prediction-data/segmentation-audit.aggregate.json`).

What is established:
- **The images are processed derivatives, not raw MRI.** For 150 patients, T1, T1Post, FLAIR and ADC are skull-stripped and co-registered into two reference spaces (FLAIR and T1Post): 1,200 images in total.
- **There are two mask families**, `*_FLAIR_abnormal_seg_comp.nii.gz` and `*_T1Post_abnormal_seg_comp.nii.gz` (150 each). Integer labels 1–N denote distinct connected-component lesions in that space.
- **Geometry matches.** The header audit found all 1,200 mask–image pairs share shape and affine (rtol 1e-5, atol 1e-4). This shows matching grids, not annotation validity.

**Root's actual-data audit (aggregate facts, reported to this worker; not rerun here):**
- All 300 mask headers declare `xyzt_units` spatial unit **unknown**.
- All 300 same-space ADC images declare spatial **mm** (time sec).
- All 1,200 mask–image pairs have matching shapes and affines.
- All 300 masks are finite, positive-integer and non-empty: 157 binary, 143 with multiple instances.
- The ADC dictionary states **raw units**, with scl_slope 1 and scl_inter 0.

**Unverified, so these gate any scored task:**
1. Whether the T1Post masks are an enhancing-tumor target or the same FLAIR abnormality resampled. The names (`abnormal_seg` in both) and the dictionary do not settle it, so the two must never be pooled or treated as different targets until verified.
2. The annotation protocol and expert review.
3. Whether skull-stripping, registration, cropping or intensity normalisation used the lesion masks. Mask-guided preprocessing could leak the target into the images.
4. Physical ADC units. The dictionary says "raw units" (slope 1, intercept 0), which does not establish mm²/s, so ADC is reported image-native only.
5. Whether any candidate pretrained segmentation model was trained on this public cohort.

## Task 1: segmentation (MRI → lesion mask)

**Agent inputs:** the four sequences in **one** reference space, starting with FLAIR space once item 1 is resolved:
- the mask is withheld;
- file names carry no subject or session IDs;
- NIfTI text fields and extensions are scrubbed (`descrip`, `aux_file`, `intent_name`, `db_name`, extensions), with geometry preserved.

**Output:** `/workspace/output/lesion_mask.nii.gz` on exactly the given grid. The shape must be identical and the affine within rtol 1e-5 / atol 1e-4. Values must be finite, non-negative integers; any positive voxel counts as lesion.

**Scoring** (`score_segmentation`; any violation of the contract is `SubmissionError`, scored as an invalid case):
- **Dice** on binarised masks. Prespecified as the primary metric. If both masks are empty, Dice is 1.0; if exactly one is empty, 0.0.
- **Volume** = voxel count × |det(affine[:3, :3])| / 1000, in mL, after converting the NIfTI spatial unit to mm (`validate_volume`: mm, meter or micron are converted; `unknown` is rejected unless explicitly allowed and recorded). This is correct for anisotropic, oblique and flipped grids. The report gives the reference and submitted volumes, the signed and absolute error in mL, and the relative error (None if the reference is empty).
- **Lesion detection** on **26-connected** components, by **any-voxel overlap**:
  - A reference lesion is detected if any submitted voxel touches it.
  - A submitted component that overlaps no reference lesion is a false positive.
  - Lesion sensitivity is None with no reference lesions; precision is None with no submitted lesions. F1 is 0 when sensitivity is 0.
  - Count error = submitted − reference.
  - Merges and splits are not penalised beyond the count error. This lenient rule is stated, not hidden.
- **Two different counts, never conflated.** The released reference keeps instance IDs, so `reference_distinct_labels` counts **distinct positive IDs** (not the maximum label; contiguity of each ID is not assumed or verified). Detection uses **26-connected components** of the binarised masks, the prespecified rule for predicted binary masks. The two can differ: one ID can span several components, or several IDs can touch.

### Mask spatial units: explicit inheritance

Because the released masks declare unknown spatial units, `inherit_spatial_units`, or `load_mask_with_reference` with nibabel, lets a mask inherit the spatial unit **only** from a caller-supplied reference image that:
- declares a known unit (mm, meter or micron);
- has the same shape;
- has an affine within rtol 1e-5 / atol 1e-4.

The function returns provenance: the resolved unit, its source (`mask header` or `inherited from same-grid reference image`), the mask's header unit, the reference unit, the grid match and the tolerance. It raises an error when:
- there is no reference;
- the reference also has unknown or unsupported units;
- the grid differs;
- the mask and reference declare conflicting known units.

mm is never assumed silently. For the release, the intended reference is the same-space ADC image, which declares mm.

## Task 2: measurement (images + given mask → numbers)

**Agent inputs:** the mask and the ADC image on the same grid (plus the other sequences).

**Output:** `/workspace/output/measurements.json`, an object with exactly the keys `total_lesion_volume_ml`, `component_count_26`, `distinct_label_count`, `adc_native_mean`, `adc_native_median`, `adc_native_p5`.

**Definitions given to the agent.** These define the quantities; they do not give the answers.
- Volume follows the determinant rule above.
- `component_count_26` counts 26-connected components of voxels > 0. `distinct_label_count` counts distinct positive label IDs in the given mask. These are separate quantities.
- ADC statistics are **image-native**: voxel values as loaded, including any NIfTI `scl_slope`/`scl_inter` intensity scaling, with no unit conversion. Neither that intensity scaling nor mm spatial units establishes mm²/s. Until the release proves its ADC units, report these only as image-native values. They are over mask voxels with finite ADC.
- The 5th percentile uses linear interpolation (numpy `linear`).

**Grading** (`reference_measurements`, `grade_measurements`):
- Both counts must match exactly; the other fields must be within 0.1 % relative.
- The report gives per-field absolute errors and `fraction_correct`.
- Malformed JSON, missing or extra keys, NaN, a non-integer count, or string values make the answer invalid (score 0). Nothing is coerced.

Expected difficulty is honest: frontier agents may well compute these correctly. This task tests faithful quantitative execution on real geometry (anisotropic or oblique affines, non-finite ADC voxels, multi-lesion masks). It is not a claimed frontier failure, and no bugs or misleading instructions are planted.

## Development cases

Root has frozen three development patients in a FAC manifest (seed 20261114), from 150 eligible, before any imaging-agent result. Held-out cases and any tuning rule must likewise be fixed before scoring. Root's full voxel-array audit of the 300 masks is still running.

## Packaging plan (not implemented)

Reuse the `prediction_export` Harbor pattern:
- a separate verifier, with reference masks only in `tests/`;
- only `/workspace/output` carried to the verifier;
- a no-network agent, or an allowlist limited to the model API;
- `/opt/benchmark-venv` with pinned numpy, scipy and nibabel (the verifier needs nibabel to read NIfTI);
- an oracle that copies or computes the reference only in `solution/`.

Check per-task archive size against Tracker's `DATASET_TASK_UPLOAD_MAX_BYTES`. Select a small fixed set of cases before seeing any model output. Report Dice distributions with a declared fixed comparator tool, not a success threshold chosen afterwards. The release licence must permit redistributing the images in an uploaded dataset.

## Verification

`tests/test_imaging_eval.py` has 22 tests; 21 run here, and the nibabel round-trip skips without nibabel. They cover:
- determinant volume, including a flipped −6 mm³ grid, and degenerate affines;
- spatial-unit conversion (micron and meter to mm);
- unit inheritance: a valid mm reference resolves an unknown-unit mask with recorded provenance. Absent, unknown-unit, wrong-shape or wrong-affine references are rejected, as are conflicting declared units;
- distinct instance-ID count vs max label and vs 26-connected components;
- Dice on a 2-of-4 overlap fixture, plus the empty cases;
- corner-touching voxels forming a single lesion under 26-connectivity;
- a merge + false-positive detection fixture (sensitivity 1, precision 2/3, F1);
- grid, NaN, negative, fractional and 4D rejection;
- equivalence of label and binary submissions;
- reference ADC stats (mean and median 250, p5 = 115 by linear interpolation), with non-finite exclusion;
- strict answer grading;
- unit and affine validation.

Run: `PYTHONPATH=/tmp/vals-prediction-deps python3.12 -m unittest tests.test_imaging_eval`. That path is a temporary project-local dependency directory (numpy 2.5.4, scipy 1.18.1); nothing was installed globally.

Mutation checks were run without bytecode caching (`-B`). Each of these broke a test:
- 6-connectivity;
- a signed determinant;
- 5 % tolerance;
- accepting a float count;
- the nearest-rank percentile;
- false positives counted from reference lesions;
- both-empty Dice set to 0;
- dropping the label validation;
- dropping the grid check;
- counting the maximum label instead of distinct IDs;
- skipping unit conversion;
- reporting the component count as the label count;
- assuming mm when no reference is supplied;
- accepting an unknown-unit reference;
- skipping the inheritance grid check;
- skipping the unit-agreement check.
