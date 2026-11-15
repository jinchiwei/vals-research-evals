# 48-hour ICU in-hospital mortality risk (calibrated)

## Session limit and what is graded (read first)

- **Your session lasts at most 45 minutes** (2700 seconds) of wall-clock
  time. When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is whatever is in `/workspace/output/pipeline/` when the session ends**, exactly as
  it is at that moment. Nothing is finished, fixed or rerun for you afterwards. If `run.sh` is missing
  or does not work at that moment, the score is 0.
- We recommend putting a working `run.sh` in place early and improving it afterwards.
- Separately, the grader limits your pipeline to **300 seconds of wall-clock time for the whole hidden set (one run)**
  (details under "What you must leave behind" below).

# 48-hour ICU in-hospital mortality risk

## Why this exists

We want a mortality risk score for adult ICU stays computed at the 48-hour mark. The unit uses it in
two ways. Each morning, every patient who has reached 48 hours gets a risk that the attending can
read on the ward round. Patients above 20% get flagged for a senior review and a goals-of-care
discussion. The units already compute SAPS-I, so a new tool earns its place only if it tells us
more than SAPS-I does, gives risks we can quote to a family (a stated 30% has to mean roughly 30%),
and works in every ICU, not only on average.

Build the pipeline that does this. The deliverable is the pipeline, not a notebook or a report.

## Data you have (`/workspace/data/`)

- `dev/input/<RecordID>.txt`: 4,000 adult ICU stays, one file each. This is set A of the
  PhysioNet/Computing in Cardiology Challenge 2012 (MIMIC-II, Beth Israel Deaconess, 2001-2008).
- `dev/reference/Outcomes-a.txt`: one row per stay with columns
  `RecordID,SAPS-I,SOFA,Length_of_stay,Survival,In-hospital_death`. Your target is
  `In-hospital_death` (1 = died in hospital). SAPS-I and SOFA were computed by the challenge
  organisers. They, length of stay and survival are **not** available for the stays your pipeline
  will score, so your pipeline cannot read them. `-1` in this file means missing (for `Survival`,
  `-1` means no recorded death).
- `LICENSE-DATA.md`: the licence (ODC-BY 1.0) and citation.

Each record file is a long-format CSV covering the first 48 hours after ICU admission:

```
Time,Parameter,Value
00:00,RecordID,132539
00:00,Age,54
00:00,Gender,0
00:00,Height,-1
00:00,ICUType,4
00:00,Weight,-1
00:07,GCS,15
00:07,HR,73
...
```

- `Time` is elapsed `HH:MM` since ICU admission, from `00:00` to `48:00`.
- The six general descriptors come first at `00:00`: RecordID, Age (years), Gender (0 female,
  1 male), Height (cm), ICUType (1 coronary care, 2 cardiac surgery recovery, 3 medical,
  4 surgical) and Weight (kg). `-1` means unknown.
- Then come irregularly sampled observations of up to 36 variables (vital signs, laboratory values,
  urine output, mechanical ventilation, and Weight again as a time series). Units are those of the
  challenge's documentation: physionet.org/content/challenge-2012/1.0.0. You do not have
  internet access, so here is the variable list: Albumin, ALP, ALT, AST, Bilirubin, BUN,
  Cholesterol, Creatinine, DiasABP, FiO2, GCS, Glucose, HCO3, HCT, HR, K, Lactate, Mg, MAP,
  MechVent, Na, NIDiasABP, NIMAP, NISysABP, PaCO2, PaO2, pH, Platelets, RespRate, SaO2, SysABP,
  Temp, TroponinI, TroponinT, Urine, WBC, Weight.
- This is real charted data. Many variables are missing for many patients. Some patients have
  almost nothing beyond the descriptors. Some values are physiologically impossible or entered
  in the wrong units. Look before you trust.

## What to deliver

Leave a self-contained, offline pipeline at `/workspace/output/pipeline/` with the entry point

```
bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR
```

- `INPUT_DIR` holds record files in the format above, named `<RecordID>.txt`, and nothing else.
  The hidden stays come from the same source population as your development stays. Their
  RecordIDs are different numbers, so read the ID from the file name or the RecordID line.
- Write `OUTPUT_DIR/predictions.csv`: a header line `RecordID,risk`, then exactly one row per
  input file. `risk` is your predicted probability of in-hospital death, a finite number in [0, 1].
  There are no extra columns and no duplicate or missing IDs. Any violation makes the whole
  submission invalid.
- The grader runs your pipeline once on the hidden stays (about 4,000), in a fresh container with
  the same Python environment (`python3` = `/opt/benchmark-venv`: numpy 2.1.3, scipy 1.14.1,
  pandas 2.2.3, scikit-learn 1.5.2). The run has no network and runs as an unprivileged user.
  Only `/workspace/output` is carried over. Anything you installed or left elsewhere will be
  missing, so put fitted model files inside `pipeline/`. Keep `/workspace/output` under 200 MB.
- **Time limit: 300 seconds of wall-clock time for the whole hidden set, on 4 CPUs.** That is the
  ward-round budget for refreshing every bed. The clock includes Python start-up and loading your
  model. Do not retrain anything heavy at prediction time.
- You may put diagnostics for the development stays in `/workspace/output/notes/`. They are not
  scored.

## How it is scored

All scoring uses the hidden stays and their true outcomes.

- **Discrimination**: AUROC. `quality = clip(2*AUROC - 1, 0, 1)`.
- **Clinical gate.** Four components, each pass or fail, decided on the point estimate. The score
  is the fraction you pass.
  1. **Beats SAPS-I on the challenge's event-1 score.** The grader flags the K stays with the
     highest risk, where K is your own expected number of deaths, `round(sum of risks)`. It then
     computes min(sensitivity, positive predictive value). The score must be at least 0.321,
     which is SAPS-I's score on the same stays plus 0.05.
  2. **Calibration.** Fit a logistic regression of the outcome on logit(risk). The calibration
     slope must lie between 0.8 and 1.2. The calibration-in-the-large intercept (slope fixed at
     1) must lie between -0.2 and 0.2 on the logit scale.
  3. **Decision usefulness.** At a decision threshold of 0.20 (flag for senior review), net
     benefit must be greater than both treat-none (0) and treat-all.
  4. **No unit left behind.** The worst AUROC across ICU type (1-4) and sex must be no more than
     0.10 below your overall AUROC.
- The task counts as **clinically acceptable only when all four components pass**. The fraction
  you pass is also reported. `reward` = clinically acceptable (1 or 0), but only if the pipeline
  ran, wrote a valid file, and finished within the time limit. Otherwise `reward` is 0.
- We also compare you with a specialist model built by our team on the same development data.
  We report that comparison, but it does not change `reward`.

Event 2 of the original challenge (a Hosmer-Lemeshow statistic) and the Brier score are reported
too, but they are not gated.

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs

`INPUT_DIR` holds the record files of every stay to score (`<RecordID>.txt`, same format as
`/workspace/data/dev/input/`). `run.sh` must write `OUTPUT_DIR/predictions.csv`: header `RecordID,risk`,
then exactly one row per input file, `risk` a finite probability of in-hospital death in [0, 1].
The pipeline is called once on the whole hidden cohort (about 4,000 stays); the time limit covers all of it.

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **the whole hidden set in one call**: `INPUT_DIR` holds all 4,000 hidden records,
laid out like the development input folder, and the pipeline writes the required files into
`OUTPUT_DIR`. After you finish, a separate grader sandbox runs your pipeline once on that hidden
set, which you have never seen, and scores the outputs against hidden references. Rules:

- **Time limit: 300 seconds of wall-clock time for the whole hidden set**, measured by
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
results are also compared with a gradient-boosted specialist model on the same hidden set.
