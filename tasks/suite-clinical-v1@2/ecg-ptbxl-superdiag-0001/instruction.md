# 12-lead ECG triage: calibrated diagnostic probabilities

## Session limit and what is graded (read first)

- **Your session lasts at most 30 minutes** (1800 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **560 seconds of wall-clock time for the whole hidden set (one run); the run is killed at 1120 seconds**
  (details under "What you must leave behind" below).

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

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs

`INPUT_DIR` holds `signals.npz` and `meta.csv` for every hidden ECG (development format;
`meta.csv` has only `record_id`, `age`, `sex`). Write `OUTPUT_DIR/predictions.csv` with header exactly
`record_id,NORM,MI,STTC,CD,HYP` and one row per `record_id`, each value a finite probability in [0, 1].

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **the whole hidden set in one call**: `INPUT_DIR` holds all 1,000 hidden records,
laid out like the development input folder, and the pipeline writes the required files into
`OUTPUT_DIR`. After you finish, a separate grader sandbox runs your pipeline once on that hidden
set, which you have never seen, and scores the outputs against hidden references. Rules:

- **Time limit: 560 seconds of wall-clock time for the whole hidden set**, measured by
  the grader on 4 CPU(s) and 8192 MB RAM. A run that finishes after the limit but before 1120 s is graded but does not count as on time; at 1120 s it is killed. Timing you report yourself is ignored.
- **Offline.** The grader has no network. Use only the image's Python environment, `/opt/benchmark-venv/bin/python3`
  (packages: numpy==2.1.3, scipy==1.14.1, pandas==2.2.3, scikit-learn==1.5.2, torch==2.5.1+cpu). Call it by this absolute path in `run.sh`; it is also
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

The grader checks that the outputs exist, pass the format checks and were produced inside the
time limit, then computes the cohort metrics on the hidden set. The clinical gate has several
parts (stated above). The headline score is 1 only if the outputs are valid, on time, and meet
**every** part of the gate; otherwise it is 0. Meeting some parts earns no partial credit. Your
results are also compared with a xresnet1d-style CNN specialist on the same hidden set.
