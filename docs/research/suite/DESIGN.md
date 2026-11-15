# Clinical deliverables suite: design and worker contract

Coordinator: Claude session "neo" on teal. Fixed on 2026-11-14 after the landscape,
dataset and platform reviews in this folder. Workers: read this file, then your own brief.

## Claim the suite has to earn

Frontier coding agents are asked to deliver clinical-grade artifacts from real
medical data (a registration, a mask, a measurement in physical units, calibrated
risks) and are scored with clinical metrics and workflow time limits against a
specialist system on the same hidden cases. Segmentation alone is already covered by
prior work (see `landscape.md`), so registration and measurement are required parts.

A gap is judged against the specialist on the same hidden cases, never against the
threshold alone. Per-case families (registration, segmentation, measurement):
compare the agent with the specialist on the cases the specialist passes, and
report the paired difference with an interval. Cohort families (ECG, ICU risk):
the specialist must meet every gate part and the agent must miss at least one. If
no comparator passes (pharyngitis), the task is excluded from scoring and kept as
a worked example. If both pass, it stays as a control.

Amended 2026-11-14 after the comparators were run and before any agent run: the
specialists pass 4 of 6 registration cases and 3 of 6 spleen cases, so the first
wording ("specialist clears the threshold") could not be applied per task. No
threshold was changed.

Reward for cohort families: `clinically_acceptable` is 1 only if every gate part
is met, otherwise 0. The fraction of parts met is reported in `metrics.json` as
`gate_fraction`, so a constant predictor cannot earn partial reward.

## Families

| Key | Data (licence) | Deliverable | Clinical limit | Specialist comparator |
|---|---|---|---|---|
| `reg_resect` | RESECT, pre-operative MRI to intra-operative ultrasound (CC BY 4.0) | registered landmark positions per case | target registration error in mm; 2 minutes per case | tuned classical registration we run; published challenge results as context |
| `seg_spleen` | Medical Segmentation Decathlon Task09 Spleen CT (CC BY-SA 4.0) | NIfTI mask and volume in mL | overlap, boundary error, volume error; minutes per case | TotalSegmentator (not trained on these cases) |
| `measure_hc18` | HC18 fetal head ultrasound (CC BY 4.0) | head circumference in mm | absolute error in mm; seconds per image | classical ellipse fit and/or small trained model |
| `ecg_ptbxl` | PTB-XL 12-lead ECG (CC BY 4.0) | calibrated class probabilities | discrimination, calibration, worst subgroup; milliseconds per ECG | xresnet1d-style model trained on folds 1-8 |
| `risk_icu` | PhysioNet/CinC 2012 ICU mortality (ODC-BY) | calibrated mortality risk | challenge scores, calibration, net benefit | SAPS-I, gradient-boosted trees, TabPFN if a checkpoint is usable |
| `seg_vessel` (if capacity) | CHASE_DB1 retinal vessels, two observers (CC BY 4.0) | vessel mask | overlap and centreline overlap vs second human observer | Frangi filter and/or small U-Net |

UCSF PCNSL imaging and genetics stay on the private servers and are reported
separately. Nothing from that release goes into a hosted task image.

## Task contract (every family)

The agent's workspace holds public inputs: `README.md` with the clinical task and
output format, development cases with references where the task has them, and no
hidden-case references. The agent must leave a self-contained, offline pipeline at
`/workspace/output/pipeline/` with entry point `run.sh INPUT_DIR OUTPUT_DIR`.

A separate verifier runs that pipeline on hidden cases under a wall-clock limit set
by the grader, as an unprivileged user, and never trusts timing the pipeline
reports. It grades against hidden references and compares with the specialist's
stored outputs and measured runtime for the same hidden cases.

`reward.json` is flat and finite with exactly these keys, each in [0,1]:
`reward`, `ran`, `valid`, `within_time`, `clinically_acceptable`, `quality`,
`vs_specialist`. Raw values in mm, mL or seconds go in `metrics.json`. Default
scalar: `reward = clinically_acceptable` if `ran`, `valid` and `within_time` are
all 1, otherwise 0.

Two tiers per family where it makes sense:
- **build**: no specialist model in the image; standard scientific Python only. The agent must build the method from the labelled development cases. This is the main task.
- **toolbox** (optional control): the specialist tool is in the image, offline. Measures operating a tool correctly, not building one.

## Splits and selection

Seed 20261114. Each family fixes development (public, with references) and hidden
cases before any agent run, records the case lists and hashes, and never moves a
case between them. Clinical thresholds and time limits are fixed from the
literature (`metrics-review.md`) or the dataset's own inter-observer figures before
any agent result is seen, with the source recorded. No threshold is tuned on agent results.

## Rules for every worker

- Repo rules in `AGENTS.md` bind you: project environments only, no AI attribution, no commits or pushes.
- Data goes under `/home/jkwei/data/vals-suite/<family>/`, never in Git. Keep the licence file and a `SOURCE.md` with URL, date, checksum and licence next to it.
- Each family uses its own conda environment `vals-suite-<family>` created from `suite/families/<family>/environment.yml` (python=3.12 + pip, everything via `pip: - -r requirements.txt`, `--override-channels -c conda-forge`). Do not install into another worker's environment.
- You own only `suite/families/<family>/`, `tests/suite/test_<family>.py` and `docs/research/suite/<family>.md`.
- Shared code is in `suite/core/` (metrics, geometry, runner, reward, export), built by another worker in parallel. Read `suite/README.md` for the plug-in interface when it exists and use the core. If it is not ready when you need it, write a small family-local grader to the contract above and say so in your report.
- No model API calls, no Valkyrie commands that change platform state, no logins, no licence acceptance on anyone's behalf. The single GPU on this machine (RTX 3060, 12 GB) is shared: check `nvidia-smi` first, keep jobs short, and say what you used.
- Report measured facts and mark anything unverified. A baseline that fails to clear the clinical threshold is a finding to report, not something to tune away after seeing hidden cases.
