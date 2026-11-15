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
  NaN, or a value in pixels or centimetres makes that image invalid, and it then counts as a miss.
- **Time**: each image must finish within the limit.

The headline reward is the fraction of hidden images that are clinically acceptable. It is zero
unless every image ran, was valid and finished in time. Error is also reported by head-size
subgroup, and your result is compared with a specialist system run on the same hidden images.
