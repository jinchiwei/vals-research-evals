# 12-lead ECG triage: calibrated diagnostic probabilities

## Why this exists

Our hospital's ECG management system receives every resting 12-lead ECG from the wards and the
emergency department. We want an automated module that, the moment a tracing arrives, attaches a
probability for each of five diagnostic groups. The probabilities feed two things: a worklist that
pushes ECGs likely to show **myocardial infarction (MI)** to the top of the cardiologist over-read
queue, and a risk display where a stated 30 % must mean roughly 30 %. A module that ranks well but
reports badly calibrated numbers, or that works for men and fails for women or older patients, is
not usable here. Please build it from the labelled ECGs below and leave it as a self-contained
pipeline.

## The data you have

`/workspace/data/dev/` holds 8,000 development ECGs with labels.

| File | Contents |
|---|---|
| `signals.npz` | Array `signals`, int16, shape (8000, 1000, 12): 10 s at **100 Hz**, values in **microvolts** (divide by 1000 for mV). Lead order: I, II, III, aVR, aVL, aVF, V1, V2, V3, V4, V5, V6. Row *i* is the *i*-th row of `meta.csv`. |
| `meta.csv` | `record_id`, `age` (years; 90 means "over 89"), `sex` (`M`/`F`), `patient_group` (same code = same patient; some patients have several ECGs), `ptbxl_fold` (1-8, the source dataset's patient-level folds) |
| `labels.csv` | `record_id`, then 0/1 for `NORM`, `MI`, `STTC`, `CD`, `HYP` |

Labels are cardiologist statements (SCP-ECG codes) grouped into five diagnostic superclasses:
**NORM** normal ECG, **MI** myocardial infarction (acute or old), **STTC** ST/T-wave change,
**CD** conduction disturbance (bundle branch blocks, AV blocks and similar), **HYP** chamber
hypertrophy/enlargement. A record belongs to a class if any of its diagnostic statements maps to
that class, so labels are **multi-label** (about a quarter of records have two or more). Every
record has at least one class. Development prevalences: NORM 44 %, MI 26 %, STTC 25 %, CD 23 %,
HYP 12 %. Some development labels came from a single reading; the hidden labels are all
human-validated.

Source: PTB-XL 1.0.3 (Wagner et al., Scientific Data 2020; PhysioNet), CC BY 4.0. Record IDs were
re-drawn. See `/workspace/data/LICENSE-DATA.md`.

## What you must deliver

A pipeline at `/workspace/output/pipeline/` with entry point

```
bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR
```

- `INPUT_DIR` contains `signals.npz` and `meta.csv` in exactly the development format, but
  `meta.csv` has only `record_id`, `age`, `sex`. There are about 1,000 hidden ECGs from patients
  who are **not** in the development set. No labels.
- It must write `OUTPUT_DIR/predictions.csv`:

```
record_id,NORM,MI,STTC,CD,HYP
h1a2b3c4,0.912,0.031,0.050,0.044,0.020
...
```

  The header must be exactly that. One row per `record_id` in `INPUT_DIR/meta.csv`, each once.
  Every value is a probability: a finite decimal number in [0, 1]. The five classes are separate
  yes/no questions, so a row need not sum to 1. Hard 0/1 labels are allowed but will score badly
  on calibration.
- The grader runs the pipeline **once for the whole hidden set**, offline, as an unprivileged user,
  with the image's Python (`/opt/benchmark-venv`: numpy, scipy, pandas, scikit-learn, CPU-only
  PyTorch). It may use only files inside `/workspace/output/pipeline/`: no network, no `pip`,
  nothing you left elsewhere (the grader runs in a fresh container). The working directory and
  `HOME` are scratch. 4 CPUs, no GPU.
- Keep `/workspace/output` under 500 MB.
- You may put your own development predictions or notes in `/workspace/output/notes/`; they are not
  scored.

## Limits

- **Time:** the whole run must finish within **60 s + 0.5 s per ECG** on the grader's clock
  (560 s for 1,000 ECGs), including interpreter start-up and model loading. The workflow reason:
  the interpretation has to be on the screen before the 10-second tracing is printed and the
  patient leaves the couch, and it has to keep up with a hospital's whole ECG stream on modest
  hardware. A run that is killed or overruns scores 0.
- **Your own time:** about 30 minutes of working time, a few CPUs, no GPU, no internet.

## How it is scored

The grader parses `predictions.csv` strictly. A missing, duplicated or unknown `record_id`, a wrong
header, or any value that is not a finite number in [0, 1] makes the submission invalid.

On the hidden ECGs it computes:

- **Discrimination:** AUROC for each class and their mean (macro AUROC). `quality` maps macro AUROC
  linearly from 0.5 (chance) to 0.928 (a published deep-learning result on this data), clipped
  to [0, 1].
- **Calibration:** expected calibration error per class (10 equal-width probability bins, weighted
  by bin size), averaged over the five classes; also Brier score and calibration slope and
  intercept.
- **Subgroups:** macro AUROC for men, women and three age bands (under 55, 55-69, 70 and over).

The acceptance gate has three parts, all fixed before any model was run:

1. **MI operating point:** at the threshold where specificity for MI is 90 %, sensitivity for MI
   must be at least **70 %**.
2. **Calibration:** mean expected calibration error over the five classes at most **0.05**.
3. **Subgroup consistency:** overall macro AUROC minus the worst subgroup's macro AUROC at most
   **0.05**.

The submission is **clinically acceptable only if all three parts are met**; meeting some parts
earns no partial credit (the fraction met is reported). The final `reward` is 1 if the pipeline
ran, produced valid output, finished within the time limit and is clinically acceptable;
otherwise it is 0. A specialist system is evaluated on the same hidden ECGs for comparison.
