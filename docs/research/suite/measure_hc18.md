# measure_hc18: fetal head circumference in mm (HC18)

Worker: Claude Opus 5.5 (claude-opus-5-5), 2026-11-14, on teal. Code: `suite/families/measure_hc18/`.
Tests: `tests/suite/test_measure_hc18.py` (18 tests, synthetic, pass). Data: `/home/jkwei/data/vals-suite/measure_hc18/`
(`SOURCE.md` there). Environment: `vals-suite-measure_hc18`. `conda env create` rejects `--override-channels`, so the
env was made with `conda create --override-channels -c conda-forge python=3.12 pip` plus `pip install -r requirements.txt`.
torch 2.5.1+cu121 was then added for the U-Net comparator only; it is not in the task image.

## Verified data facts

Measured in `split/data_check.json`, made by `data_check.py`.

- **Source.** Zenodo 1327317, CC BY 4.0, confirmed from the record API (`metadata.license.id = cc-by-4.0`).
  The MD5s of all four files match Zenodo, and the SHA-256s are in `SOURCE.md`.
- **Images.** 999 labelled training images and 335 test images. The test CSV has only
  `filename,pixel size(mm)`, so there are no public test references. Hidden cases therefore come from the
  training set.
- **Size.** 8-bit greyscale PNG. 975 of 999 images are 800×540; the other 24 range from 738 to 800 by
  539 to 563.
- **Pixel size.** 0.0494 to 0.3933 mm, median 0.128 mm. The paper says 0.052 to 0.326 mm; the training CSV
  is wider.
- **Annotations.** `NNN_HC_Annotation.png` is a binary (0/255) ellipse outline a few pixels thick.
  Reference HC runs from 44.3 to 346.4 mm, median 174.1 mm. The distribution is concentrated: the
  tertile cuts are 165.7 and 181.6 mm, because most images come from 20-week scans.
- **HC reproduces exactly.** A least-squares ellipse (skimage `EllipseModel`) fitted to all outline pixels,
  perimeter by Ramanujan II, times the pixel size, matches the CSV. Mean absolute difference 0.006 mm,
  95th percentile 0.016 mm, maximum 0.046 mm, consistent with 2-decimal rounding. There is no units or
  geometry bug.
- **No per-image trimester or gestational age** in the release. The paper's Table 1 gives counts only:
  training 165/693/141 and test 55/233/47 for trimesters 1/2/3. Approximate HC bands (<100, 100 to 260,
  ≥260 mm) give 184/676/139, which is close but not the same thing. The bands are descriptive only.
- **Repeat images.** 806 filename prefixes; 642 have one image, 141 two, 17 three and 6 four
  (`NNN_2HC.png` and so on). The paper says all images from one examination went to the same side, so we
  treat the prefix as the examination. Whether two prefixes can be the same woman is unverified:
  1,334 images came from 551 women.

## Split

`split.py`, seed 20261114. The unit is the filename prefix, so no prefix straddles the split.
Stratified by HC tertile, with cut points from all 999 images.

| Side | Images | Prefixes | Tertile small / mid / large | Bands <100 / 100–260 / ≥260 |
|---|---|---|---|---|
| Development (public, with annotation and HC) | 152 | 121 | 50 / 52 / 50 | 28 / 105 / 19 |
| Hidden (grader only) | 83 | 70 | 29 / 27 / 27 | 15 / 51 / 17 |
| Pool (U-Net training only, never shipped) | 764 | rest | | |

- **Opaque IDs.** Case IDs (`case_xxxxxx`) are drawn from one random space for development and hidden
  cases.
- **Re-encoding.** Images are re-encoded as metadata-free greyscale PNG with pixel values unchanged.
- **Records.** The lists, source filenames and per-file SHA-256 hashes are in `split/split.json`.
  Hidden references SHA-256: see `hidden_references_sha256` in that file. Reference values are not in Git.

## Fixed rules, set before any comparator or agent result

| Item | Value | Source |
|---|---|---|
| Per-image tolerance | absolute error ≤ 4.9 % of reference HC | Inter-observer 95 % limits of agreement for HC, ±4.9 % (Sarris et al., Ultrasound Obstet Gynecol 2012;39:266–273, INTERGROWTH-21st). **Taken from the abstract via search results; full text not read.** |
| Family clinical bar | ≥ 90 % of hidden images within tolerance | A second trained observer meets the 95 % limits on 95 % of images by construction. Set 5 points lower because HC18 images are routine scans, not standardised study images. A design choice, stated in advance. |
| Time limit | 10 s wall clock per image, measured by the grader, Python start-up included, 4 CPUs | Manual HC takes a senior sonographer 10.66 s and a junior 12.34 s (Han et al., BMC Pregnancy Childbirth 2024, Table 7, PMC10885506). A tool slower than the human it replaces is no use during a scan. |
| Quality | mean over images of clip(1 − abs error / 7.26 mm, 0, 1) | Gives 0.5 at the HC18 paper's own inter-observer mean absolute difference (observer 2 vs 1: 1.8 / 3.7 / 5.4 mm by trimester, Table 4; 3.63 mm weighted by test-set trimester counts), and 0 at twice that. |
| Validity | one finite `hc_mm` per image in [40, 400] mm | Fetal HC from about 11 weeks to term. An answer in pixels (≥ 3× the mm value) or in cm falls outside. |
| vs_specialist | min(1, quality / specialist quality) | suite/core rule |
| Reward | `clinically_acceptable` if `ran = valid = within_time = 1`, else 0 | DESIGN.md |

The family grader (`grader.py`) implements the suite/core `grade_case` interface and keeps a local
`score`/`grade` for the self-checks. Both give identical numbers: the dry run of the exported verifier on
the classical pipeline matched to the 4th decimal.

## Comparators on hidden cases (n = 83)

Both comparators ran through the grader's clock on teal (WSL2), with 4 threads and the pipeline copied to
local disk. The specialist is the U-Net, chosen because it had the better development-set result
(MAE 2.66 vs 9.03 mm), decided before the hidden runs (`split/specialist_choice.json`).

| | U-Net (specialist) | Classical |
|---|---|---|
| Mean absolute error, mm (95 % bootstrap CI) | **2.05 (1.65–2.45)** | 13.74 (7.87–21.12) |
| Median absolute error, mm | 1.51 | 3.48 |
| Within 4.9 % (95 % bootstrap CI) | **1.00 (1.00–1.00)** | 0.76 (0.66–0.84) |
| Bland-Altman bias, 95 % limits of agreement (mm) | −0.23, −5.7 to +5.2 | −2.0, −68.7 to +64.7 |
| Errors > 20 mm | 0 | 11 |
| Worst tertile | large: MAE 3.11 mm, 100 % within | large: MAE 22.5 mm, 78 % within (small: 62 % within) |
| By band <100 / 100–260 / ≥260 mm: MAE | 1.24 / 1.65 / 4.00 | 25.4 / 4.9 / 29.8 |
| Quality | 0.717 | 0.437 |
| Reward | 1.00 | 0.76 |
| CPU runtime per image (median, max) | 1.75 s, 2.19 s | 0.24 s, 0.36 s |

The paired comparison of U-Net against classical gives Wilcoxon p = 1.5e-9 on absolute error. In McNemar's
test on "within tolerance", 20 images were discordant and all of them favoured the U-Net (p = 1.9e-6).

**The specialist clears the clinical bar**: 100 % of images within tolerance against a bar of 90 %. The
classical pipeline does not (76 %). Its failures are gross mis-detections on small first-trimester heads and
large third-trimester heads.

**Context from the literature.** These numbers are not directly comparable: the published figures are on the
official 335-image test set, and ours are on 83 training-set images.
- van den Heuvel 2018 system C: absolute difference 2.8 ± 3.3 mm overall, and 3.1 / 2.4 / 4.8 mm by trimester.
- The paper's second observer: 1.8 / 3.7 / 5.4 mm by trimester.
- Moccia et al.: 1.95 mm (secondary source; the leaderboard was not read).

Our U-Net's 2.05 mm sits within that range.

### How the comparators were built

- **Classical** (`pipelines/classical/`). numpy, scipy and scikit-image only. A bright-ridge map (smoothed
  image minus a local background), then 4,000 RANSAC 5-point conic hypotheses with shape and size limits,
  scored by ridge contrast along the ellipse. Then three rounds of least-squares refinement on nearby ridge
  points. The scale factor 1.03 (ridge centre to annotated contour) is the median ratio on 151 development
  images, and nothing else was tuned. This is also the task's `solution/` (an oracle built only from
  agent-visible material), which shows the contract can be met.
- **U-Net** (`unet/`, `pipelines/unet/`). About 1.9 M parameters, input 224×320. It segments the filled
  ellipse, then an ellipse is fitted to the 0.5 iso-contour, mapped back to original pixels, and the
  perimeter multiplied by the pixel size.
  - Trained on the 764 pool images for 40 epochs (326 s on the RTX 3060; other GPU use was 0.6 GB), and
    validated on the development cases (Dice 0.975).
  - It never saw hidden images.
  - It needs torch, so it cannot run in the build-tier image. Its hidden outputs and grader-measured
    runtimes are stored and shipped as `tests/specialist/`.

## Grader self-check on the real hidden cases (`self_check.py`, `split/self_check.json`)

| Pipeline | reward | ran | valid | within_time | clinically_acceptable | quality |
|---|---|---|---|---|---|---|
| oracle (reference lookup) | **1.00** | 1 | 1 | 1 | 1.00 | 1.00 |
| pixels (perfect geometry, forgets pixel size) | 0 | 1 | 0 (83/83 invalid) | 1 | 0 | 0 |
| constant (development mean, 174.43 mm) | 0.31 | 1 | 1 | 1 | 0.31 | 0.16 |
| slow (correct, sleeps 12 s; first 5 hidden cases) | 0 | 1 | 0 | 0 (5/5 timed out) | 0 | 0 |

**The constant answer still gets 31 %** within a relative tolerance, because HC18 is dominated by mid-trimester
heads. It is far below the 90 % bar, but it is the floor to quote: an agent at about 0.3 has learned nothing.

## Export (Harbor)

`spec.py` returns the suite/core `FamilySpec` (task `measure-hc18-0001`, 4 CPUs, 8 GB, 10 s per case).

- **Contents.** `environment/data/` holds the README, LICENSE-DATA.md and 152 development cases
  (21 MB). `tests/` holds 83 hidden inputs and references, the specialist outputs and the vendored grader
  (13 MB).
- **Checks.** `export_task` passed its leak check, and the local verifier dry run reproduced the family grader.
- **Not run.** `scripts/validate_exports.py` and the Tracker `check_taskconfig.py` were not run by this worker.

## Limitations and unverified items

- **Sarris 2012 ±4.9 %** is quoted from the abstract (one listing of the same study says 5.1 %); the full text
  was not read. The tolerance is lenient in mm for large heads (about 17 mm at 340 mm). A specialist passing
  100 % suggests this family may end up as a **control** if agents also pass. The expected discriminating
  failure is units (pixels) or gross mis-detection.
- **Prefix = examination**, from the paper's split statement. Patient identity across prefixes is unknown.
- **Contamination.** Hidden images are public HC18 training images. With no network they cannot be looked
  up, but a model could in principle have memorised HC18 values.
- **Runtime environment.** Runtimes were measured on teal (WSL2), not on the Modal verifier. The U-Net time
  is dominated by torch import.
- **Trimester.** Per-image trimester is not available. Subgroups are HC tertiles (the primary split) and
  approximate HC bands.
- **Timed-out cases.** The family-local grader discards a timed-out case's output. suite/core grades it for
  validity. Either way the reward is 0.
- **Not done.** No hosted run and no Docker build.
