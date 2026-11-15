# seg_spleen: CT spleen segmentation and volumetry

Worker: Claude Opus 5.5 (claude-opus-5-5), 2026-11-14, on teal. Family code:
`suite/families/seg_spleen/`. Tests: `tests/suite/test_seg_spleen.py`. Data (outside Git):
`/home/jkwei/data/vals-suite/seg_spleen/` (`SOURCE.md`, `data_check.json`, `split.json`,
`staged/`, `specialist/`, `selfcheck/`). `suite/core/` was empty when this was built, so the
grader is family-local (`grader.py`) and follows the DESIGN.md contract. Core landed near the end:
`grader.py` now also exposes the core plug-in (`REQUIRED_OUTPUTS`, `CLINICAL_THRESHOLD`,
`PRIMARY_METRIC`, `grade_case`, symlink-safe), tested, but **no `FamilySpec` builder yet**:
`family.json` carries the same information for whoever wires the core exporter.
`metrics-review.md` (checked at the end) recommends mean of Dice and NSD as the organ primary
metric and has no spleen threshold; this family keeps Dice as primary per the brief, reports
NSD at 2 mm, and takes thresholds from the source in section 4. Its HD95 convention (max of the
two directed 95th percentiles) matches ours.

## 1. Data: verified facts

Source: MSD Task09_Spleen, `https://msd-for-monai.s3-us-west-2.amazonaws.com/Task09_Spleen.tar`,
1,610,352,640 bytes, SHA-256 `dfeba347…fa65e60`, downloaded 2026-11-14 without sign-in.
`dataset.json`: release "1.0 06/08/2018", reference "Memorial Sloan Kettering Cancer Center",
licence "CC-BY-SA 4.0", 41 training (labelled), 20 test (unlabelled). Licence text: CC BY-SA 4.0
legal code fetched from creativecommons.org (the bucket has no `LICENSE` object; `NoSuchKey`).
The archive contains 107 macOS `._*` files; ignored.

Checked on all 41 labelled cases (`data_check.json`):

| Property | Finding |
|---|---|
| Orientation | RAS for all 41 (nibabel `aff2axcodes`) |
| Units, header | spatial unit mm; qform_code = sform_code = 1; no scl scaling |
| Grid | 512 × 512 in-plane for all; 31–168 slices |
| Spacing | in-plane 0.61–0.98 mm; slice spacing 1.5, 1.6, 2.5, 3, 4, 5, 7, 7.5 or 8 mm (strongly anisotropic) |
| Intensity | stored float32 but every value is an integer; range −1024 to 3072: Hounsfield units |
| Labels | values {0, 1} only; label on the image grid in all cases |
| Spleen | one connected component in 40 cases; one case has 2 (largest holds > 99.99 %) |
| Spleen median HU | 35 to 153 across cases (contrast timing varies a lot) |
| Spleen volume | 55.8 to 501.6 mL; median 209.5, mean 243.4; 9 of 41 above 314 mL |

Volumes are voxel count × |det(affine[:3,:3])| / 1000.

## 2. Split (seed 20261114)

Method: the 41 source IDs sorted numerically, permuted with `numpy.random.default_rng(20261114)`,
first 8 development, next 6 hidden, remaining 27 unused. Task IDs re-drawn with
`default_rng(20261115)`. Full lists with SHA-256 of source and staged files: `split.json`.

| Task ID | Source | Spacing (mm) | Slices | Spleen mL | Spleen median HU |
|---|---|---|---|---|---|
| dev_5012 | spleen_62 | 0.68 × 0.68 × 5 | 80 | 275.9 | 103 |
| dev_3893 | spleen_2 | 0.79 × 0.79 × 5 | 90 | 305.4 | 89 |
| dev_3115 | spleen_3 | 0.74 × 0.74 × 5 | 40 | 158.1 | 147 |
| dev_8150 | spleen_46 | 0.63 × 0.63 × 5 | 99 | 180.9 | 114 |
| dev_5864 | spleen_22 | 0.97 × 0.97 × 1.5 | 148 | 274.4 | 114 |
| dev_3211 | spleen_17 | 0.61 × 0.61 × 2.5 | 95 | 90.7 | 153 |
| dev_4164 | spleen_21 | 0.73 × 0.73 × 2.5 | 89 | 133.3 | 128 |
| dev_3538 | spleen_61 | 0.77 × 0.77 × 5 | 101 | 163.3 | 97 |
| hidden (6) | 24, 44, 47, 56, 59, 63 | 0.70–0.95 in-plane; 5 or 7 mm | 33–94 | 55.8–426.7 | 42–142 |

The hidden set is harder than the development set in two ways that came from the seeded
draw, not from selection: it holds two splenomegaly cases (426 mL) above the largest
development spleen (305 mL) and two small, low-attenuation spleens (median 42 and 50 HU,
below every development case). This is kept as drawn.

**Staging (identical for development and hidden):** in-plane crop to the bounding box of the
largest body component (HU > −500, projected over z) plus 10 mm; all slices kept; int16 HU;
uint8 label; affine translated for the crop; qform/sform code 1; `descrip`, `aux_file`,
`intent_name`, `db_name` blanked. The crop removes table and air only and asserts that no
spleen voxel is lost; it is not spleen-dependent, so the task is not made easier. Staged size:
development 154 MB, hidden 94 MB (8 to 25 MB per case).

## 3. Tasks

Contract (both tiers): `run.sh INPUT_DIR OUTPUT_DIR`; input `image.nii.gz`; output
`mask.nii.gz` (0/1, input grid) and `volume.json` `{"spleen_volume_ml": x}`. Agent-facing
brief: `suite/families/seg_spleen/task/README.md` (placeholders filled by the exporter).

**build (main).** Image: python 3.12 slim, `/opt/benchmark-venv` with numpy, scipy, nibabel,
SimpleITK, scikit-image, scikit-learn, pandas (suite pins) and **CPU-only PyTorch 2.15.0, no
weights** (`torch-2.15.0+cpu` cp312 wheel exists on the PyTorch CPU index, 210 MB). Reason
for including torch: the classical reference reaches only Dice 0.41 on hidden cases (section 6), so without a
learning library the task measures a missing tool, not a missing skill; with torch, training a
small network on 8 labelled scans on 4 CPUs within the agent's hour is possible but hard,
which is the frontier question. No pretrained model is present. `family.json` has
`include_torch` to build the no-torch variant. Per-case limit **300 s** on 4 CPUs, 16 GB.
Estimated image: about 0.45 GB base + scientific stack, about 0.9 GB with CPU torch, plus 154 MB
of development data (not built: no Docker on teal).

**toolbox (control).** Feasible. Same image plus TotalSegmentator 2.18.0 and the weights
needed for `--roi_subset spleen`: Dataset291 (organs, 242 MB), Dataset297 (3 mm, 159 MB),
Dataset298 (6 mm, 159 MB), about 560 MB; the other parts (vertebrae, cardiac, muscles, ribs)
are not needed. Licence: `total` task Apache-2.0; no licence key or login was asked for at
any point. Limit 300 s per case (section 5: CPU full mode takes 28–37 s on 4 threads). Estimated
image about 1.5 GB (CPU torch, TotalSegmentator dependencies, 560 MB weights, 154 MB data).

## 4. Thresholds (fixed before any agent run; not tuned)

Source: Humpire-Mamani GE, Bukala J, Scholten ET, Prokop M, van Ginneken B, Jacobs C. *Fully
automatic volume measurement of the spleen at CT using deep learning.* Radiology: Artificial
Intelligence 2020;2(4):e190102 (PMC8082410). An independent observer against the reference on
50 CT scans: Dice 0.964 ± 0.012 (95 % CI 0.961–0.967); mean relative absolute volume
difference 3.93 %. Their deep-learning system: Dice 0.962, 4.39 %.

- **Dice ≥ 0.94** = observer mean − 2 SD (0.964 − 0.024).
- **|relative volume error| ≤ 10 %**: the paper gives only the mean absolute difference. If the
  signed error is N(0, s) then E|e| = s·√(2/π), so s = 4.93 % and the 95th percentile of |e| is
  1.96 s = 9.65 %, rounded to 10 %. The normality assumption is ours.
- A hidden case is clinically acceptable if both hold and the output is valid and on time.
- Reported, not thresholded: NSD at 2 mm, HD95 in mm. Table 1 of the paper (HD95, ASSD) could
  not be read (PMC captcha, RSNA 403), so no boundary threshold is set.

## 5. Specialist: TotalSegmentator 2.18.0 (`total`, `--roi_subset spleen`)

Not trained on MSD (Basel data only, per the dataset survey). Masks for the grader were made on
the RTX 3060 (shared with other workers' jobs at the time), full (1.5 mm) model. All runs used
`run_case` from the grader (grader clock, `run.sh` contract), so timings include process
start, model load and I/O.

Hidden cases (aggregate), GPU full mode:

| Metric | Value |
|---|---|
| Mean Dice (min) | **0.939** (0.892) |
| Mean NSD @ 2 mm | 0.917 |
| Mean HD95 | 3.9 mm |
| Mean abs. relative volume error | 4.3 % (max 8.6 %) |
| Clinically acceptable | **3 / 6 (0.50)** |
| Wall time per case, GPU | median 59 s, max 89 s (GPU and CPUs shared with other workers) |

The specialist fails the Dice limit on the three smallest spleens (56, 78, 119 mL; Dice 0.93,
0.94 (0.9364), 0.89) while passing volume on all six. By DESIGN.md's rule this family is
therefore **not yet a demonstrated frontier gap on its own**: the specialist does not clear the
threshold on every hidden case. It still serves as a graded comparison (`vs_specialist`,
`quality`). We did not move the threshold.

CPU timing, 4 threads, `taskset -c 0-3`, OMP/ITK threads = 4, TotalSegmentator `-nr 4 -ns 4`.
Other workers' jobs were running on the same 16 cores (load average 20–35), so these are
pessimistic:

| Mode | Cases | Wall s per case | Dice (same cases) | Note |
|---|---|---|---|---|
| CPU full, 4 threads | hid_1392, hid_4506, hid_8298 | 37.5, 32.2, 28.1 | 0.936, 0.962, 0.927 | masks identical to GPU full |
| CPU fast (3 mm), 4 threads | all 6 hidden | 35.8–57.0 (median 52.5) | mean 0.851; hid_1392 (7 mm slices, 33 slices) 0.47 | heavier load during this run; fast fails on 3/6 more than full does |

Full mode on 4 CPUs finishes in under 40 s, so fast mode is not needed. **Toolbox limit: 300 s
per case** (same as build; at least 5 × the measured CPU full time, per platform-brief 3.3).
Full mode with `--roi_subset spleen` first runs the 6 mm model to crop, then the organ model
only on that crop, which is why it beats the fast model on wall time here.

Development cases, GPU full mode (per case):

| Case | Dice | NSD 2 mm | HD95 mm | Vol. error | Acceptable | Wall s |
|---|---|---|---|---|---|---|
| dev_3115 | 0.938 | 0.904 | 3.3 | +0.8 % | no (Dice) | 41.7 |
| dev_3211 | 0.944 | 0.883 | 2.5 | −3.1 % | yes | 43.1 |
| dev_3538 | 0.953 | 0.950 | 2.3 | −1.7 % | yes | 51.5 |
| dev_3893 | 0.954 | 0.924 | 2.5 | −1.2 % | yes | 64.8 |
| dev_4164 | 0.946 | 0.882 | 2.5 | −6.0 % | yes | 44.7 |
| dev_5012 | 0.946 | 0.903 | 2.7 | −3.2 % | yes | 36.2 |
| dev_5864 | 0.963 | 0.962 | 2.0 | +3.0 % | yes | 37.6 |
| dev_8150 | 0.944 | 0.933 | 2.3 | −4.4 % | yes | 34.4 |

Development: mean Dice 0.948, 7/8 acceptable. Systematic small under-segmentation (volume
errors mostly negative) is consistent with a boundary-convention difference between Basel
training labels and MSD labels.

## 6. Classical reference (no deep learning)

`classical/pipeline/segment.py`: body mask; in-plane location prior (64 × 64 histogram of
spleen projections in body-bounding-box coordinates, from development masks, Gaussian σ 1.5
bins); median-filtered HU window from development spleen percentiles; per-slice erosion; 3D
components scored by prior; geodesic regrowth in an adaptive HU window around the chosen
seed; hole filling. Fitted on development cases only (`classical/fit.py`, log in
`classical/fit_log.json`). Parameters in `classical/pipeline/params.json`.

Grid (development only): erosion 5 or 8 mm × score {prior mass, mean prior × log size}, prior
floor 0.25, window ±40 HU; an earlier 4 mm / floor 0.03 run gave dev Dice 0.21 and a 5 mm /
floor 0.10 run 0.24. Best: 8 mm, prior mass, dev Dice 0.618. Then run through the grader's
runner (4 threads, cores pinned):

| Set | Mean Dice (min) | NSD 2 mm | Mean HD95 | Mean abs. vol. error | Acceptable | Wall s/case |
|---|---|---|---|---|---|---|
| Hidden (6) | **0.409** (0.000) | 0.373 | 159 mm | 443 % | **0 / 6** | median 22, max 38 |
| Development (8, fitted on) | 0.618 (0.000) | 0.449 | 56 mm | 75 % | 0 / 8 | median 30, max 53 |

Development per case (Dice / volume error): dev_3115 0.887 / −3 %; dev_3211 0.095 / +395 %;
dev_3538 0.000 / −18 %; dev_3893 0.892 / −0.1 %; dev_4164 0.830 / +20 %; dev_5012 0.636 / +78 %;
dev_5864 0.929 / −1 %; dev_8150 0.680 / +81 %. On hidden cases it picks the wrong organ in 3 of 6
(Dice 0.00–0.10) and gets 0.65–0.88 on the rest.

Diagnosis: the in-plane prior has no z component, so stomach, left kidney and bowel at other
levels share the spleen's (u, v) position, and HU-window bridges to these organs survive a 5 to
8 mm erosion. This is a first pass under the time budget, not a ceiling for classical methods
(a z reference from the lung bases, or per-slice tracking from a seed, would be next). It
answers the coordinator's question: a quick classical pipeline lands far below the specialist,
so the build tier is not trivially solvable without learning.

## 7. Grader and self-check

`grader.py`: Dice; NSD at 2 mm and symmetric HD95 from surface voxels (6-connected
erosion border) with anisotropic EDT inside the padded joint bounding box; volume error from the
reported mL. Validity: mask present, 3D, unit mm (or unknown), same shape and affine as the
input (atol 1e-3 mm), values ⊂ {0, 1}, `spleen_volume_ml` finite, non-negative, not bool, and
within max(1 %, 0.5 mL) of mask voxels × voxel volume. Runner: `bash run.sh` in a new session
under the grader's monotonic clock and `timeout`; process group killed after each case; as root
it drops to uid 65534 with `setpriv` and kills leftovers with `pkill -u 65534`. Reward keys and
gating as DESIGN.md; `reward.json` written as zeros first.

Self-check on the 6 real hidden cases (`selfcheck/run_selfcheck.py`, result in
`/home/jkwei/data/vals-suite/seg_spleen/selfcheck/selfcheck.json`):

| Pipeline | reward | ran | valid | within_time | quality | Result |
|---|---|---|---|---|---|---|
| oracle (hidden labels) | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | PASS |
| empty mask | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 | PASS |
| wrong volume (voxel count) | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | PASS (e.g. "126135 mL inconsistent with mask (356.60 mL)") |
| too slow | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | PASS (limit 5 s, sleep 8 s to save time; same code path) |

`tests/suite/test_seg_spleen.py`: 21 tests on synthetic ellipsoids (metrics, anisotropic
volume, rotated affine, threshold edges, wrong grid, non-binary, metre units, wrong-unit
volumes, end-to-end oracle/empty/wrong-volume/timeout, reward contract, core `grade_case` adapter
with a planted symlink). All pass.

## 8. Export spec

`suite/families/seg_spleen/family.json`: source, licence and attribution; agent-visible files
(`staged/dev` → `environment/data/dev`, generated `volumes.csv`, licence, attribution);
verifier-only files (`staged/hidden` → `tests/hidden`, `grader.py`, `harbor/test.sh`,
`harbor/grade_entry.py`, `specialist/summary_hidden.json` → `tests/specialist.json`,
`tests/grading.json`); `solution/` = classical pipeline; per-tier pins, `task.toml` fields,
limits. `grade_entry.py` fails closed if `/solution` or `/bundle` exists, makes `/tests`
root-only, copies the pipeline to `/eval/pipeline`, and runs cases as uid 65534. Hidden
references never enter `environment/`.

## 9. Limitations and unverified items

- **Not built or run in a container** (no Docker on teal); image sizes are estimates. `setpriv`,
  `pkill` presence in the image is asserted by the platform template, not checked here.
- The Harbor oracle (`solution/`) is the classical pipeline and scores far below 1.0; the 1.0
  oracle exists only as the local self-check with hidden labels.
- CPU timings were taken while other workers loaded the machine; re-measure on an idle
  machine or in the verifier.
- Toolbox tier: TotalSegmentator writes `config.json` (prediction counter) into
  `TOTALSEG_HOME_DIR`; with a read-only `/opt/totalseg_home` this may fail. Unverified; the
  exporter should make that file writable or copy the home into `$HOME` at run time.
- The first TotalSegmentator run sent its default anonymous usage ping before
  `send_usage_stats` was set to false in our `totalseg_home/config.json`. All later runs had it
  off. The toolbox image must ship that config.
- MSD is public and famous; an agent cannot see hidden cases, and the pipeline runs offline, so
  memorisation can only help through general knowledge.
- Single-rater MSD labels; thresholds come from a different dataset's inter-observer study.
- The volume threshold relies on our normality assumption (section 4).
- Small hidden set (6): one case moves `clinically_acceptable` by 0.17.
