# Brain-shift correction: register pre-operative MRI to intra-operative ultrasound

## Why this matters

During glioma surgery the neuronavigation system shows the surgeon where they are on the
pre-operative MRI. Once the skull and dura are open, the brain moves and deforms ("brain shift"),
by several millimetres and sometimes more than a centimetre. The navigation display is then wrong,
in exactly the region the surgeon is operating on. Our team acquires a tracked 3D ultrasound sweep
after dura opening and before resection. We need software that re-aligns the pre-operative MRI to
that ultrasound so the navigation targets (tumour margins, vessels, eloquent structures) are shown
where they really are now.

It has to work while the patient is on the table: **at most 2 minutes per case, on 4 CPU cores,
no GPU, no network**. A correction that is late is not used. The accuracy target is a mean error
under **2 mm** at the expert landmarks: below that, navigation accuracy counts as restored (the
figure used in the intra-operative ultrasound literature).

## What you have

`/workspace/data/dev/<case>/` holds four development cases. `input/` is laid out exactly as your
pipeline will receive a hidden case; `reference/` holds the answer.

| File | Content |
|---|---|
| `input/mri_t1.nii.gz` | Pre-operative contrast-enhanced T1-weighted MRI |
| `input/mri_flair.nii.gz` | Pre-operative T2 FLAIR MRI, in the same world frame as the T1 |
| `input/us.nii.gz` | Intra-operative 3D B-mode ultrasound (after dura opening, before resection), reconstructed from a tracked freehand sweep. Voxels outside the sweep are 0. |
| `input/landmarks_mri.csv` | Expert anatomical landmarks (about 15 per case) in the MRI |
| `reference/landmarks_us.csv` | The same landmarks as placed by the expert in the ultrasound |

All images are already placed in one patient world frame by the navigation system: loading the
MRI and the ultrasound with their headers gives the alignment the surgeon would see without any
correction. The difference between `landmarks_mri.csv` and `landmarks_us.csv` is the uncorrected
error (brain shift plus navigation error), between 2.6 and 4.6 mm (mean) on these four cases.
The hidden cases come from the same hospital and protocol. Their uncorrected error can be larger.

Data: RESECT database (Xiao et al., Med Phys 2017), CC BY 4.0; see `/workspace/data/LICENSE-DATA.md`.
Cases are renamed and header text is cleared; voxel data are unchanged.

### Coordinates: read this carefully

Every landmark coordinate is a **world position in millimetres in RAS+**: +x towards the
patient's right, +y anterior, +z superior. This is the NIfTI sform/qform convention:
`nibabel.load(f).affine @ [i, j, k, 1]` maps a voxel index to these coordinates.
ITK and SimpleITK use **LPS** physical points, (x_lps, y_lps, z_lps) = (-x, -y, z). If you work in
SimpleITK, convert on the way in and back on the way out.

CSV format, for both input and output:

```
id,x,y,z
L01,50.1644,-31.7197,34.8453
```

## What you must deliver

A self-contained, offline pipeline in `/workspace/output/pipeline/` with the entry point

```
bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR
```

It processes **one case**. `INPUT_DIR` contains `mri_t1.nii.gz`, `mri_flair.nii.gz`, `us.nii.gz` and
`landmarks_mri.csv`, with no `landmarks_us.csv`. The pipeline must write:

- `OUTPUT_DIR/landmarks_us.csv`: for **every** id in the input `landmarks_mri.csv`, the position of that
  anatomical point in the **ultrasound**, after correcting for brain shift. Use RAS world mm, the
  same convention as the input. Header `id,x,y,z`, one row per landmark, the same ids, no extras.
- Optional: `OUTPUT_DIR/displacement_ras.nii.gz`, a dense displacement field (X, Y, Z, 3) in RAS mm,
  if your method produces one. It is used only to report folding.

The landmarks you are given are evaluation points, not a registration aid. Estimate the brain
shift from the images and then move the landmarks with it. A "registration" that uses only the
landmark coordinates has no information about the shift.

Rules for the pipeline:
- It runs later on hidden cases in a fresh copy of this image, as an unprivileged user, with no
  network. Only `/workspace/output/` is carried over (at most 512 MB). It may use the Python in
  `/opt/benchmark-venv` (`python3` on PATH: numpy, scipy, nibabel, SimpleITK, scikit-image,
  scikit-learn) and files inside `pipeline/`. It must not use anything else you installed or downloaded.
- It must finish each case within **120 seconds** of wall-clock time on 4 CPU cores. The grader's own
  clock is used, and over-time cases are killed and score as failures. Load and import time count.
- Put any predictions you make on development cases in `/workspace/output/dev_predictions/` if you
  like; they are not scored.

## How it is scored

For each hidden case the grader runs your pipeline and compares your `landmarks_us.csv` with the
expert ultrasound landmarks:

- **valid**: the file parses; it has exactly the input landmark ids; every coordinate is finite;
  every point lies within the ultrasound volume (plus a 10 mm margin). A wrong coordinate convention
  usually fails this check.
- **within time**: produced within 120 s.
- **target registration error (TRE)**: the mean Euclidean distance in mm between your points and the
  expert's, per case. The initial (uncorrected) error is reported alongside.
- **clinically acceptable**: mean TRE < 2.0 mm and lower than the uncorrected error.
- The task score is the fraction of hidden cases that are clinically acceptable, and it counts only
  if every case ran, was valid and was on time. A specialist registration method is run on the same
  hidden cases under the same limits for comparison.
