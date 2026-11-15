# Clinical deliverables suite: plan and status

Updated 2026-11-15. Demos are Sunday 2 PM. Design and task contract:
[DESIGN.md](DESIGN.md).

## The idea

Frontier coding agents get real public medical data and must deliver a clinical
artifact: a registration, a mask, a measurement in physical units, or calibrated
risks. A separate verifier runs the agent's pipeline on hidden cases under a
clinical time limit. It scores the result with clinical metrics against a
specialist system run on the same cases.

## Task families

| Family | Data (licence) | Specialist on hidden cases | Role |
|---|---|---|---|
| `reg_resect`: pre-op MRI to intra-op ultrasound registration | RESECT (CC BY 4.0) | 4 of 6 under 2 mm; 6.18 → 3.03 mm mean error | scored |
| `seg_spleen`: CT spleen mask + volume in mL | MSD Task09 (CC BY-SA 4.0) | TotalSegmentator 3 of 6; Dice 0.939 | scored |
| `measure_hc18`: fetal head circumference in mm | HC18 (CC BY 4.0) | U-Net 100% within tolerance; 2.05 mm error | scored |
| `ecg_ptbxl`: calibrated 12-lead ECG classes with subgroups | PTB-XL (CC BY 4.0) | meets all 3 gate parts; AUROC 0.921 | scored |
| `risk_icu`: calibrated ICU mortality risk | PhysioNet 2012 (ODC-By) | gradient boosting meets all 4 parts; AUROC 0.873 | scored (control in both hosted runs) |
| `triage_pharyngitis`: bacterial sore throat from photo + symptoms | Shojaei 2025 (CC BY 4.0) | no comparator passes; labels are physician votes | not scored: worked example of label and shortcut problems |

UCSF PCNSL imaging and genetics stay on FAC/SCS and are reported separately
(`pcnsl/`). No UCSF data goes to Valkyrie or GitHub.

## Done

- Literature reviews: [metrics](metrics-review.md), [benchmark landscape](landscape.md), [datasets](dataset-survey.md), [platform](platform-brief.md).
- Shared grading core (`suite/core/`): metrics, hidden-case runner with a wall-clock limit, seven-key reward, Harbor exporter with a leak check.
- Six families built with specialist and simple comparators, graders self-checked, all seven tasks exported and validated ([integration](integration.md)). Full suite: 214 tests pass, 1 skipped (2026-11-15).
- Local pilot runner: sandboxed Claude Code with only the Anthropic API reachable ([local pilots](local-pilots.md)).
- First hosted Valkyrie runs: toy task oracle and Sonnet 5.5 agent both reward 1.0; agent API cost $0.045 ([hosted smoke](hosted-smoke.md)).
- Local pilot 1 on fetal head and registration ([pilot1-results](pilot1-results.md)). Found our instruction bug: the session limit was not stated.
- Hosted oracle checks on instructions v2 and v3: every expected reward reproduced; agent network limited to the model API ([hosted-oracle1](hosted-oracle1.md), [instructions-v3](instructions-v3.md)).
- Hosted run 1, instructions v2, `suite/clinical-v1@1` ([hosted-agents1](hosted-agents1.md)): five of ten attempts killed by the unstated session limit and classed not interpretable.
- Instructions v3 published as `suite/clinical-v1@2` (tag `instr2`), stating the session limit and that the pipeline is graded as found.
- **Hosted run 2 (headline)**, instructions v3, runs `1f2e6208-…` (Opus 5.5) and `5110a198-…` (Sonnet 5.5) ([hosted-agents2](hosted-agents2.md)): ten graded attempts, no infrastructure failure, all ten traces read, no web use. Gap shown on fetal head for both models and on registration for Sonnet 5.5 (no-op pipeline); Opus 5.5 matches the specialist on registration and spleen; ECG and ICU are controls. Every agent stopped with 48 to 96 % of its session unused. API cost $3.77.
- Figures for every source (`scripts/make_suite_figures.py`, `docs/figures/suite/`).
- README results section written from hosted run 2, with earlier runs summarised separately. The opening overview paragraph is still left for Jin.
- Demo deck built with Jin's build-pptx skill: `results/suite-deck/CLINICAL_SUITE.pptx`.

## Running now

Nothing. No agent or oracle run is in progress.

## Next

1. Jin writes the README overview paragraph and his overview slide.
2. Jin reviews the README results and the deck before the demo.
3. Commit and push. The repository stays private unless Jin changes it.
4. Optional, not before the demo: repeat attempts per task and model for run-to-run variance, larger hidden sets for registration and spleen, effort set to high, and a task version that tells the agent to use its remaining time (a new version, not pooled).

## Rules kept throughout

- One attempt per task and model, fixed before running; failures are kept, nothing is rerun for a better number.
- Clinical thresholds are fixed from the literature or stated as our own convention before any agent result is seen.
- A gap is claimed only against the specialist on the same hidden cases.
- All installs go in project environments. Commits carry the human Git identity only.
