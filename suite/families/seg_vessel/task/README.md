# Retinal vessel segmentation from colour fundus photographs (CHASE_DB1)

## Clinical task

Retinal vessel maps from fundus photographs are used to measure vessel calibre and tortuosity, which
relate to cardiovascular risk (the images come from the Child Heart and Health Study in England). A
vessel map is only useful if it is as good as a trained human grader's. Your job is to build a
pipeline that takes one colour fundus photograph of a child's eye and returns a binary vessel mask.

## Data

`/workspace/data/dev/` holds {{N_DEV}} development images from {{N_DEV_CHILDREN}} children (both eyes of each
child). Each case folder `dev/<case>/` contains:

- `image.jpg`: the colour fundus photograph, 999 x 960 pixels (width x height), RGB JPEG, as released.
- `label_1stHO.png`: the **first human observer's** vessel mask (1-bit PNG, white = vessel). **This is
  the reference you are scored against.**
- `label_2ndHO.png`: a second, independent human observer's mask of the same image, for context.

`dev/cases.csv` lists `case, child, eye, dice_2ndHO, cldice_2ndHO`: the child (A to J; both eyes of a
child are correlated, so keep a child's two images together when you validate) and how well the second
observer agreed with the first on that image.

The {{N_HIDDEN}} hidden images come from {{N_HIDDEN_CHILDREN}} other children of the same study, same camera and size.
A hidden case's `INPUT_DIR` contains only `image.jpg`. There is no field-of-view mask; metrics are
computed over the whole image.

## What to deliver

Your pipeline must write:

- `OUTPUT_DIR/mask.png`: a single-channel PNG (mode `1` or `L`) of exactly the input's size,
  999 x 960, with values in {0, 1} or {0, 255}; nonzero = vessel.

Rules for the pipeline:

- One image per call: `run.sh INPUT_DIR OUTPUT_DIR`.
- {{LIMIT}} seconds of wall-clock time per image on {{CPUS}} CPUs and {{MEM_GB}} GB RAM, no GPU, no network.
- The image's Python environment has numpy, scipy, scikit-image, scikit-learn, Pillow, pandas{{TORCH_LINE}}.
- Optional development-set diagnostics may go in `/workspace/output/visible_predictions/`; they are not scored.

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
images the second observer's Dice ranges from {{DICE2_MIN}} to {{DICE2_MAX}} (mean {{DICE2_MEAN}}) and clDice
from {{CL2_MIN}} to {{CL2_MAX}} (mean {{CL2_MEAN}}); the hidden images' values are similar but not shown.

The headline score is the fraction of hidden images meeting the bar, and it is 0 unless every hidden
image produced a valid mask inside the time limit. The mean Dice is also reported.

## Licence

CHASE_DB1, Kingston University London with St George's, University of London. Creative Commons
Attribution 4.0 (`/workspace/data/LICENSE-CC-BY-4.0.txt`, `ATTRIBUTION.md`).
