# Pre-operative MRI to intra-operative ultrasound registration for brain shift (RESECT)

## Session limit and what is graded (read first)

- **Your session lasts at most 45 minutes** (2700 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **120 seconds of wall-clock time per hidden case**
  (details under "What you must leave behind" below).

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

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs per case

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

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **one case**: it reads `INPUT_DIR` (laid out exactly like a development case's
input folder) and writes the required files into `OUTPUT_DIR`. After you finish, a separate
grader sandbox runs your pipeline on 6 hidden cases you have never seen and scores
the outputs against hidden references. Rules:

- **Time limit: 120 seconds of wall-clock time per case**, measured by the
  grader on 4 CPU(s) and 16384 MB RAM. A case that exceeds it is killed and fails.
  Timing you report yourself is ignored.
- **Offline.** The grader has no network. Use only the image's Python environment, `/opt/benchmark-venv/bin/python3`
  (packages: numpy==2.1.3, scipy==1.14.1, nibabel==5.3.2, SimpleITK==2.4.0, scikit-image==0.24.0, scikit-learn==1.5.2). Call it by this absolute path in `run.sh`; it is also
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
MIND-feature rigid registration (classical, CPU) on the same hidden cases.
