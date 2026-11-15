# Clinical deliverables suite: plan and status

Updated 2026-11-14, evening. Demos are Sunday 2 PM. Design and task contract:
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
| `risk_icu`: calibrated ICU mortality risk | PhysioNet 2012 (ODC-By) | gradient boosting meets all 4 parts; AUROC 0.873 | scored (likely control) |
| `triage_pharyngitis`: bacterial sore throat from photo + symptoms | Shojaei 2025 (CC BY 4.0) | no comparator passes; labels are physician votes | not scored: worked example of label and shortcut problems |

UCSF PCNSL imaging and genetics stay on FAC/SCS and are reported separately
(`pcnsl/`). No UCSF data goes to Valkyrie or GitHub.

## Done

- Literature reviews: [metrics](metrics-review.md), [benchmark landscape](landscape.md), [datasets](dataset-survey.md), [platform](platform-brief.md).
- Shared grading core (`suite/core/`): metrics, hidden-case runner with a wall-clock limit, seven-key reward, Harbor exporter with a leak check.
- Six families built with specialist and simple comparators, graders self-checked, all seven tasks exported and validated ([integration](integration.md)). Full suite: 191 tests pass.
- Local pilot runner: sandboxed Claude Code with only the Anthropic API reachable ([local pilots](local-pilots.md)).
- First hosted Valkyrie runs: toy task oracle and Sonnet 5.5 agent both reward 1.0; agent API cost $0.045 ([hosted smoke](hosted-smoke.md)).

## Running now

1. Local agent pilots: fetal head and registration, Claude Opus 5.5 and Sonnet 5.5, one attempt each.
2. Hosted: put the task environment's Python first on the agent's PATH, prepare an agent with web tools disabled, push the five scored tasks, run each oracle once.

## Next

1. Hosted agent runs on the five scored tasks with Opus 5.5 and Sonnet 5.5, one attempt each, only where the oracle reproduces its expected reward. Every trace is read and checked for web use.
2. Results: per-task tables of agent against specialist on the same hidden cases, with intervals, and figures.
3. README rewrite with results. The opening overview paragraph is left for Jin to write.
4. Deck with Jin's build-pptx skill.
5. Commit and push. The repository stays private unless Jin changes it.

## Rules kept throughout

- One attempt per task and model, fixed before running; failures are kept, nothing is rerun for a better number.
- Clinical thresholds are fixed from the literature or stated as our own convention before any agent result is seen.
- A gap is claimed only against the specialist on the same hidden cases.
- All installs go in project environments. Commits carry the human Git identity only.
