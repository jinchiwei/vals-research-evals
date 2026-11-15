# Average treatment effect on the treated with a valid 95% interval (semi-synthetic ICU data)

## Session limit and what is graded (read first)

- **Your session lasts at most 45 minutes** (2700 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **960 seconds of wall-clock time for the whole hidden set (one run)**
  (details under "What you must leave behind" below).

# Treatment effect on the treated, with a valid 95% interval (semi-synthetic ICU data)

## Why this exists

An ICU research group runs many observational comparisons: patients who received some intervention
versus patients who did not, adjusting for what was charted at admission. They want one automated,
re-runnable analysis that, given such a dataset, returns the average effect of the intervention on the
patients who received it, with a 95% interval they can put in a paper. The interval is the deliverable as
much as the point estimate: across many analyses, about 95% of the reported intervals should contain the
true effect, and the intervals should be narrow enough to be useful.

Real observational data never reveal the true effect, so the method is checked on semi-synthetic data:
the covariates are real ICU patients, while the treatment assignment and the outcome were simulated from
the covariates, so the true effect of every dataset is known to the grader.

Build the pipeline that does this analysis. The deliverable is the pipeline, not a notebook or a report.

## Data you have (`/workspace/data/`)

- `dev/input/<dataset_id>/data.csv`: 32 development datasets, 2,000 rows each. Columns:
  - `z`: treatment (1 treated, 0 control);
  - `y`: outcome (continuous; its units and scale differ from dataset to dataset);
  - 24 covariates, all measured before or at the time of treatment and all complete (no missing values):
    `age` (years), `female` (1/0), `weight_kg`, `mech_vent` (mechanical ventilation in the window, 1/0),
    `hr_first`, `hr_max` (heart rate, beats/min), `map_first`, `map_min` (non-invasive mean arterial
    pressure, mmHg), `temp_first`, `temp_max` (deg C), `gcs_first`, `gcs_min` (Glasgow coma scale),
    `bun_first` (mg/dL), `creatinine_first` (mg/dL), `glucose_first` (mg/dL), `hco3_first` (mmol/L),
    `hct_first` (%), `potassium_first`, `sodium_first` (mmol/L), `platelets_first` (1000/uL),
    `wbc_first` (1000/uL), `magnesium_first` (mmol/L), `urine_total_ml`, `icu_type` (1 coronary care,
    2 cardiac surgery recovery, 3 medical, 4 surgical; a category, not a number).
- `dev/reference/truth.csv`: `dataset_id,satt`, the true effect on the treated for each development dataset.
- `LICENSE-DATA.md`: licence and citation of the covariate source.

The covariates come from adult ICU stays of the PhysioNet/Computing in Cardiology Challenge 2012
(MIMIC-II): first or extreme values of routine measurements, cleaned and with missing values filled by the
median. The hidden datasets use **different patients** from the development datasets, drawn the same way.

### How the datasets were simulated (in words; the generating code is not available)

The design follows the 2016 Atlantic Causal Inference Conference competition (Dorie et al., Statistical
Science 2019). Each dataset is one draw from one of several settings that vary:

- whether treatment assignment depends on the covariates linearly or through nonlinear terms
  (powers, interactions, thresholds);
- whether the outcome depends on the covariates linearly or nonlinearly;
- the share treated (about 35% or about 65%);
- overlap: in some settings a region of covariate space contains only controls (nobody there could be
  treated); every treated patient has comparable controls;
- how many of the covariates that drive treatment also drive the outcome (confounding alignment);
- whether the treatment effect is the same for everyone or varies with the covariates;
- how strongly the covariates drive treatment (confounding strength).

Treatment is assigned only through the observed covariates (no unmeasured confounding). The 32
development datasets cover every setting twice; the 48 hidden datasets cover every setting three times,
in a random order, under random dataset ids.

## The estimand

**SATT**, the sample average treatment effect on the treated: for the treated units of the dataset,
the mean of E[Y(1) - Y(0) | X], i.e. the average over the treated patients of the expected outcome under
treatment minus the expected outcome without it, given their covariates. Report it in the outcome's own
units (the same units as `y`).

## Clinical gate (all parts must hold, over the 48 hidden datasets)

Errors are measured in units of each dataset's outcome standard deviation (the sd of `y` in that dataset):

1. **Coverage:** your 95% interval contains the true SATT in at least 85% of the hidden datasets
   (at least 41 of 48).
2. **Accuracy:** root mean squared error of your point estimates at most **0.10** outcome sd.
3. **Bias:** the mean signed error at most **0.05** outcome sd in absolute value.
4. **Informative intervals:** mean interval length at most **0.50** outcome sd.

The headline score is 1 only if your outputs are valid, on time, and meet all four parts; otherwise 0.

## What to deliver

A self-contained, offline pipeline at `/workspace/output/pipeline/` with entry point
`run.sh INPUT_DIR OUTPUT_DIR`. `INPUT_DIR` holds one folder per dataset, `INPUT_DIR/<dataset_id>/data.csv`,
laid out exactly like `/workspace/data/dev/input/`. It is called **once for all 48 hidden datasets**, with a
time limit of 20 seconds per dataset (960 seconds for the whole run) on 4 CPUs. The output format is below.

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs

`run.sh INPUT_DIR OUTPUT_DIR` must write `OUTPUT_DIR/estimates.json`:

```json
{"estimand": "SATT",
 "datasets": {"<dataset_id>": {"estimate": 1.23, "ci_lower": 0.98, "ci_upper": 1.48}, ...}}
```

- one entry for **every** dataset folder in `INPUT_DIR` (keys are the folder names);
- `estimate` is the SATT in the outcome's own units; `ci_lower`/`ci_upper` bound your 95% interval;
- all three are finite numbers with `ci_lower <= estimate <= ci_upper`.

A missing dataset, a non-finite number or a malformed file makes the whole output invalid (score 0).
The pipeline is called once on all 48 hidden datasets; the time limit covers all of them.

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **the whole hidden set in one call**: `INPUT_DIR` holds all hidden records,
laid out like the development input folder, and the pipeline writes the required files into
`OUTPUT_DIR`. After you finish, a separate grader sandbox runs your pipeline once on that hidden
set, which you have never seen, and scores the outputs against hidden references. Rules:

- **Time limit: 960 seconds of wall-clock time for the whole hidden set**, measured by
  the grader on 4 CPU(s) and 8192 MB RAM. Timing you report yourself is ignored.
- **Offline.** The grader has no network. Use only the image's Python environment, `/opt/benchmark-venv/bin/python3`
  (packages: numpy==2.1.3, scipy==1.14.1, pandas==2.2.3, scikit-learn==1.5.2). Call it by this absolute path in `run.sh`; it is also
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
results are also compared with a cross-fitted doubly robust (AIPW) specialist estimator on the same hidden set.
