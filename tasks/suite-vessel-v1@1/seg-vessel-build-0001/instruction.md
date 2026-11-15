# Retinal vessel segmentation from fundus photographs (CHASE_DB1)

## Session limit and what is graded (read first)

- **Your session lasts at most 60 minutes** (3600 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **60 seconds of wall-clock time per hidden case**
  (details under "What you must leave behind" below).

## Clinical task

Retinal vessel maps from fundus photographs are used to measure vessel calibre and tortuosity, which
relate to cardiovascular risk (the images come from the Child Heart and Health Study in England). A
vessel map is only useful if it is as good as a trained human grader's. Your job is to build a
pipeline that takes one colour fundus photograph of a child's eye and returns a binary vessel mask.

## Data

`/workspace/data/dev/` holds 20 development images from 10 children (both eyes of each
child). Each case folder `dev/<case>/` contains:

- `image.jpg`: the colour fundus photograph, 999 x 960 pixels (width x height), RGB JPEG, as released.
- `label_1stHO.png`: the **first human observer's** vessel mask (1-bit PNG, white = vessel). **This is
  the reference you are scored against.**
- `label_2ndHO.png`: a second, independent human observer's mask of the same image, for context.

`dev/cases.csv` lists `case, child, eye, dice_2ndHO, cldice_2ndHO`: the child (A to J; both eyes of a
child are correlated, so keep a child's two images together when you validate) and how well the second
observer agreed with the first on that image.

The 8 hidden images come from 4 other children of the same study, same camera and size.
A hidden case's `INPUT_DIR` contains only `image.jpg`. There is no field-of-view mask; metrics are
computed over the whole image.

## How it is scored


Each hidden image is compared with the first observer's mask using two measures:

- **Dice**: 2|P ∩ R| / (|P| + |R|) over vessel pixels.
- **clDice** (centreline Dice; Shit et al., CVPR 2021): the harmonic mean of the fraction of your mask's
  skeleton that lies inside the reference mask and the fraction of the reference's skeleton that lies
  inside your mask (skeletons from `skimage.morphology.skeletonize`). It rewards connected, complete
  vessel trees, including thin vessels.

**Clinical bar, per image:** your Dice **and** your clDice must each be at least the second human
observer's Dice and clDice against the first observer **on that same image**. That is, the pipeline has
to agree with the reference grader at least as well as another trained human did. On the development
images the second observer's Dice ranges from 0.739 to 0.817 (mean 0.774) and clDice
from 0.760 to 0.888 (mean 0.832); the hidden images' values are similar but not shown.

The headline score is the fraction of hidden images meeting the bar, and it is 0 unless every hidden
image produced a valid mask inside the time limit. The mean Dice is also reported.

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs per case

The pipeline must write:
- `OUTPUT_DIR/mask.png`: a single-channel PNG (mode `1` or `L`) of exactly the input's size,
  999 x 960, with values in {0, 1} or {0, 255}; nonzero = vessel.

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **one case**: it reads `INPUT_DIR` (laid out exactly like a development case's
input folder) and writes the required files into `OUTPUT_DIR`. After you finish, a separate
grader sandbox runs your pipeline on 8 hidden cases you have never seen and scores
the outputs against hidden references. Rules:

- **Time limit: 60 seconds of wall-clock time per case**, measured by the
  grader on 4 CPU(s) and 8192 MB RAM. A case that exceeds it is killed and fails.
  Timing you report yourself is ignored.
- **Offline.** The grader has no network. Use only the image's Python environment, `/opt/benchmark-venv/bin/python3`
  (packages: numpy==2.1.3, scipy==1.14.1, nibabel==5.3.2, SimpleITK==2.4.0, scikit-image==0.24.0, scikit-learn==1.5.2, pillow==11.0.0, pandas==2.2.3, torch==2.15.0+cpu). Call it by this absolute path in `run.sh`; it is also
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
small U-Net specialist trained on the development images on the same hidden cases.
