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
