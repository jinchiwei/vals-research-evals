# Spleen segmentation and volumetry from abdominal CT

## Session limit and what is graded (read first)

- **Your session lasts at most 60 minutes** (3600 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **300 seconds of wall-clock time per hidden case**
  (details under "What you must leave behind" below).

## Why this matters

Spleen volume is the measurement behind several clinical decisions: confirming
splenomegaly, following portal hypertension and haematological disease, and judging
response to treatment in myelofibrosis, where a 35 % fall in spleen volume is the usual
response criterion. Measuring it by hand means outlining the organ on every slice,
which takes a radiologist several minutes per scan. We want an automatic tool that
returns a spleen mask a reader can check, and a volume in millilitres they can put in
the report, within a few minutes of the scan arriving.

You are building that tool. There is no pretrained medical model in this environment
and no internet. You have the scientific Python stack in `/opt/benchmark-venv`
(numpy, scipy, scikit-image, SimpleITK, nibabel, scikit-learn, pandas, and CPU-only PyTorch with no pretrained weights)
and a handful of labelled scans.

## Data

`/workspace/data/dev/<case>/` holds 8 contrast-enhanced abdominal CT scans
(portal-venous phase) with expert spleen masks:

- `image.nii.gz`: CT in Hounsfield units, int16, RAS orientation, units mm.
- `label.nii.gz`: uint8, 1 = spleen, 0 = everything else, on the same grid.

What you should know about the scans:

- Slice thickness varies from 1.5 to 8 mm between scans; in-plane pixels are about
  0.6 to 1 mm. Voxels are far from isotropic.
- Each scan has been cropped in-plane to the patient's body outline with a margin,
  to remove the table and air. All slices are kept. The hidden scans were cropped by
  the same rule. The crop does not centre on the spleen.
- Spleen sizes in the development cases run from about 90 to 300 mL. Real patients,
  including the hidden ones, can have larger or smaller spleens.
- Contrast timing varies, so spleen attenuation differs from scan to scan.

`/workspace/data/dev/volumes.csv` lists the reference spleen volume of each
development case, computed as voxel count times voxel volume.

## How it is scored


After you finish, the grader runs your pipeline once on each of several hidden scans
that you never see, from the same source and prepared the same way.

Per scan:

- **Dice overlap** with the expert mask.
- **Volume error**: (your volume − reference volume) / reference volume.
- **Boundary**: normalised surface distance at 2 mm and 95th-percentile Hausdorff
  distance in mm are reported, not thresholded.
- A scan is **clinically acceptable** if Dice ≥ 0.94 **and** the absolute volume
  error is ≤ 10 %, the outputs are valid, and it finished within the time limit.
  These limits come from published reader agreement for spleen outlining on CT: a
  second expert reader reaches about 0.96 Dice and 4 % volume difference.

A scan's output is **invalid** if a file is missing, the mask is not on the input
grid, the mask holds values other than 0 and 1, or the volume is not a finite number
consistent with the mask in mL.

The headline score is the fraction of hidden scans that are clinically acceptable,
counted only if every hidden scan ran, produced valid output and finished in time.
Mean Dice and a comparison with a specialist segmentation tool are also recorded.

Test your pipeline end to end on the development cases the way the grader will run
it, including the time limit, before you finish.

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs per case

The pipeline must write:
1. `OUTPUT_DIR/mask.nii.gz`: the spleen mask, values 0 and 1 only, **on the input
   grid** (same shape and the same affine as `image.nii.gz`, spatial units mm).
2. `OUTPUT_DIR/volume.json`: `{"spleen_volume_ml": <number>}`, the spleen volume in
   millilitres. It must agree with your own mask: voxel count times voxel volume,
   within 1 % (or 0.5 mL for tiny masks). A volume in voxels or in mm³ is wrong.

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **one case**: it reads `INPUT_DIR` (laid out exactly like a development case's
input folder) and writes the required files into `OUTPUT_DIR`. After you finish, a separate
grader sandbox runs your pipeline on 6 hidden cases you have never seen and scores
the outputs against hidden references. Rules:

- **Time limit: 300 seconds of wall-clock time per case**, measured by the
  grader on 4 CPU(s) and 16384 MB RAM. A case that exceeds it is killed and fails.
  Timing you report yourself is ignored.
- **Offline.** The grader has no network. Use only the image's Python environment, `/opt/benchmark-venv/bin/python3`
  (packages: numpy==2.1.3, scipy==1.14.1, nibabel==5.3.2, SimpleITK==2.4.0, scikit-image==0.24.0, scikit-learn==1.5.2, pandas==2.2.3, torch==2.15.0+cpu). Call it by this absolute path in `run.sh`; it is also
  first on `PATH` (login and non-login shells) here and in the grader. Use only that interpreter
  and files inside
  `/workspace/output/pipeline/`. Nothing else you create or install in this sandbox exists there.
- The pipeline runs as an unprivileged user with a fresh, empty `HOME`; write only to `OUTPUT_DIR`
  and `$TMPDIR`.
- Only `/workspace/output/` is carried to the grader; it must stay under 512 MiB compressed and 20 000 files.
  Optional diagnostics on development cases may go in `/workspace/output/visible_predictions/`;
  they are not scored.
- Network access in this sandbox is limited to the model API (api.anthropic.com).

## How you are scored

Per hidden case the grader checks that the outputs exist, pass format and geometry checks, were
produced inside the time limit, and meet the clinical threshold stated above. The headline score
is the fraction of hidden cases meeting the clinical threshold, and it is 0 unless every hidden
case produced valid outputs inside the time limit. Your results are also compared with a
TotalSegmentator specialist (not trained on these cases) on the same hidden cases.
