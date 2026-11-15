# Fetal head circumference in mm from 2D ultrasound (HC18)

## Session limit and what is graded (read first)

- **Your session lasts at most 45 minutes** (2700 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **10 seconds of wall-clock time per hidden case**
  (details under "What you must leave behind" below).

# Fetal head circumference from 2D ultrasound

## Why this matters

Head circumference (HC) is one of the standard fetal biometry measurements. In the first half of
pregnancy it is used to date the pregnancy (gestational age). Later it is plotted on growth charts
to detect growth restriction, macrocephaly and microcephaly. The sonographer freezes a
transventricular plane of the head, then fits an ellipse to the outer border of the skull, and the
machine reports the ellipse's perimeter in millimetres. Errors of a few millimetres shift the
estimated age by days. In settings without a trained sonographer, an automatic measurement may be
the only measurement available.

We want a tool that does this step automatically. It receives the frozen frame and the pixel size
and must return HC in mm fast enough to use during the scan.

## What you have

`/workspace/data/dev/` holds 152 development images from routine Dutch prenatal scans across all
three trimesters (HC18 dataset; licence in `LICENSE-DATA.md`). Each case folder has:

- `image.png`: 8-bit greyscale B-mode image, about 800 x 540 pixels.
- `case.json`: `case_id` and `pixel_size_mm` (square pixels; it varies a lot between images because
  of the depth setting, from about 0.05 to 0.4 mm).
- `annotation.png`: the sonographer's ellipse drawn as a white outline on black, the same size as
  the image (development cases only).

`/workspace/data/dev/references.csv` lists `case_id,pixel_size_mm,hc_mm,stratum,band` for the
development cases. `hc_mm` is the reference circumference the sonographer's ellipse gives.
`stratum` is a head-size tertile and `band` is a rough size band. Both are for your own error
analysis; hidden cases do not come with them.

Hidden cases are other images from the same source and population, drawn from different
examinations. They have the same `image.png` and `case.json` and no annotation.

## What to deliver

Leave a self-contained, offline pipeline in `/workspace/output/pipeline/` with entry point
`run.sh INPUT_DIR OUTPUT_DIR`. It must process **one** image folder per call. The exact file
contract is in the "Output format" section below.

- It may use only the image's Python (`/opt/benchmark-venv`: numpy, scipy, scikit-image,
  scikit-learn, Pillow, pandas, nibabel, SimpleITK) and files inside `/workspace/output/pipeline/`.
  There is no network, no pip and no GPU. Nothing outside that folder survives into grading.
- If you fit any parameters or train a model, store them in that folder. The grader copies the
  folder into a fresh sandbox and runs it as an unprivileged user.
- You may put your own predictions for development cases in `/workspace/output/visible_predictions/`.
  They are not scored.

## Time limit

Each image must finish within **10 seconds of wall-clock time**, measured by the grader from
process start, Python start-up included. Four CPUs are available. For comparison, an experienced
sonographer takes about 10.7 s to measure HC by hand (Han et al., BMC Pregnancy Childbirth 2024).
A tool slower than that is no help during a scan.

## How you are scored

On each hidden image the grader compares your `hc_mm` with the sonographer's reference.

- **Clinically acceptable**: the absolute error is at most **4.9 % of the reference HC**. This is
  the inter-observer 95 % limit of agreement for HC between trained sonographers (Sarris et al.,
  Ultrasound Obstet Gynecol 2012). The task's bar is at least 90 % of hidden images within that
  tolerance.
- **Quality**: the mean over images of `max(0, 1 - |error mm| / 7.26)`. This is 0.5 at the
  inter-observer mean absolute difference on this dataset (3.6 mm) and 0 at twice that.
- **Validity**: every image needs exactly one finite `hc_mm` between 40 and 400 mm. A missing row,
  NaN, or a value in pixels or centimetres makes that image invalid. A single invalid image makes the
  headline reward 0 (see below), not just one miss; in the reported quality it scores 0.
- **Time**: each image must finish within the limit.

The headline reward is the fraction of hidden images that are clinically acceptable. It is zero
unless every image ran, was valid and finished in time. Error is also reported by head-size
subgroup, and your result is compared with a specialist system run on the same hidden images.

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs per case

Each hidden case is a folder `INPUT_DIR` with:

- `image.png`: 8-bit greyscale 2D ultrasound image (about 800 x 540 pixels).
- `case.json`: `{"case_id": "case_xxxxxx", "pixel_size_mm": <float>}`. Pixels are square.

`run.sh INPUT_DIR OUTPUT_DIR` must write `OUTPUT_DIR/measurement.csv`, a CSV with exactly this
header and one row:

```
case_id,hc_mm
case_xxxxxx,174.32
```

`hc_mm` is the head circumference in **millimetres** (a finite number). Values outside
40-400 mm are treated as invalid (that is what an answer in
pixels or centimetres looks like). Limit: 10 s wall clock per image, measured by the grader
from process start, on 4 CPUs, no GPU, no network.

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **one case**: it reads `INPUT_DIR` (laid out exactly like a development case's
input folder) and writes the required files into `OUTPUT_DIR`. After you finish, a separate
grader sandbox runs your pipeline on 83 hidden cases you have never seen and scores
the outputs against hidden references. Rules:

- **Time limit: 10 seconds of wall-clock time per case**, measured by the
  grader on 4 CPU(s) and 8192 MB RAM. A case that exceeds it is killed and fails.
  Timing you report yourself is ignored.
- **Offline.** The grader has no network. Use only the image's Python environment, `/opt/benchmark-venv/bin/python3`
  (packages: numpy==2.1.3, scipy==1.14.1, nibabel==5.3.2, SimpleITK==2.4.0, scikit-image==0.24.0, scikit-learn==1.5.2, pillow==11.0.0, pandas==2.2.3). Call it by this absolute path in `run.sh`; it is also
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
unet comparator on the same hidden cases.
