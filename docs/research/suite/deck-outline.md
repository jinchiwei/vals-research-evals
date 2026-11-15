# Deck outline: clinical deliverables suite (3-minute demo plus backup)

First written 2026-11-14 as an outline. Updated 2026-11-15 to the hosted run 2 results
(`hosted-agents2.json`; dataset `suite/clinical-v1@2`, instructions v3) and built with Jin's `build-pptx`
skill as [`results/suite-deck/CLINICAL_SUITE.pptx`](../../../results/suite-deck/CLINICAL_SUITE.pptx).
Source: `results/suite-deck/CLINICAL_SUITE.md`, its `.layout.json` sidecar, and `results/suite-deck/src/`
(`make_figs.py` draws every figure from `hosted-agents2.json`; `make_layout.py` writes the slides and
speaker notes; `finalize.py` adds cover and closing notes). Every number on a slide is read from the cited
file, not from this outline.

Timing: 9 main content slides after the cover in about 3 minutes; slides 4 to 7 carry the result.

## Main slides (as built)

| # | Title | Message | Evidence | Figure |
|---|---|---|---|---|
| 1 | Clinical deliverables: coding agents against specialist systems | Cover | — | none |
| 2 | Overview | Reserved for Jin's own words; not drafted | — | none |
| 3 | Clinical evaluation — what a generic benchmark score leaves out | Clinical deliverables are judged in units, in time and against a specialist on the same cases | `metrics-review.md` | shape diagram |
| 4 | Task contract and the five scored tasks | Agent leaves a pipeline; a hidden verifier runs it under a clinical time limit and compares with the specialist | README task contract and families table | `fig_contract.png` plus task cards |
| 5 | Agent vs specialist — hosted run 2, same hidden cases | Gap on fetal head for both models; Opus matches the specialist on registration and spleen (underpowered); ECG and ICU controls | `hosted-agents2.json` | `fig_headline.png` |
| 6 | Fetal head circumference — error per hidden image | 83/83 vs 35/83 and 64/83; paired differences with intervals | `hosted-agents2.json` | `fig_hc18.png` |
| 7 | One trace — Opus 5.5 on fetal head stops at 11.6 of 45 minutes | It estimated about 60 % against a 90 % bar and ended its turn; hidden 42 % | `hosted-agents2.md` trace findings | `fig_timeline.png` |
| 8 | Session use — when each agent ended its turn | All ten attempts ended with 48 to 96 % of the session unused | `hosted-agents2.json` | `fig_session.png` |
| 9 | Registration and spleen per case; ECG and ICU controls | Per-case agreement for Opus; Sonnet no-op and mislocalisation; controls | `hosted-agents2.json` | `fig_percase.png` |
| 10 | Limits and how to run | One attempt, small hidden sets, default effort, regraded raw values, public data; Valkyrie commands | README | none |

## Backup slides (as built)

| # | Title | Evidence |
|---|---|---|
| B1 | Gap verdicts — paired differences on specialist-passed cases | `hosted-agents2.md` "Gap verdicts" |
| B2 | Reward keys for every attempt — hosted run 2 | `hosted-agents2.json` |
| B3 | Sonnet 5.5 on registration — a no-op pipeline after 3 minutes | `hosted-agents2.md` "reg_resect · Sonnet" |
| B4 | Why the numbers can be trusted | `hosted-oracle1.md`, `instructions-v3.md`, `hosted-agents2.md` |
| B5 | Earlier runs — the session-limit bug and its fix | `hosted-agents1.md`, `pilot1-results.md`, `instructions-v3.md` |
| B6 | Cost and run identifiers | `hosted-agents2.md` "Cost"; README "Run identifiers" |
| B7 | Clinical thresholds and their sources | README families table |

The skill's Thank-You slide is last, after the backup slides.

## Rebuild

```bash
cd results/suite-deck
~/miniconda3/envs/vals-suite/bin/python src/make_figs.py
~/miniconda3/envs/vals-suite/bin/python src/make_layout.py
~/miniconda3/envs/vals-suite/bin/python ~/.claude/skills/build-pptx/build.py \
  --input CLINICAL_SUITE.md --output CLINICAL_SUITE.pptx --qa   # --qa needs soffice and pdftoppm on PATH
~/miniconda3/envs/vals-suite/bin/python src/finalize.py
```

## Original outline (2026-11-14, superseded)

### Main slides

| # | Title (draft) | Message | Evidence (file) | Figure |
|---|---|---|---|---|
| 1 | Clinical deliverables: coding agents vs specialist systems | Title, team, track ("Build Your Own Eval"), Valkyrie org | `docs/research/hackathon-prompt.md` | none |
| 2 | Overview | Jin's own words; this slide is spoken by Jin and not generated | the human-written README paragraph (once written) | none |
| 3 | The task: deliver, not answer | The agent gets real public data and must leave a pipeline that produces a clinical artifact (mm, mL, calibrated risk); a separate verifier runs it on hidden cases under a clinical time limit | README "How the benchmark works"; `DESIGN.md` task contract | simple diagram: workspace (dev cases) → `run.sh` → verifier on hidden cases → seven-key reward; build with the deck skill, no data |
| 4 | Five clinical tasks, five specialists | Registration, spleen mask and volume, fetal head circumference, 12-lead ECG, ICU mortality; each with a published or declared threshold and a specialist run on the same hidden cases | README families table; `task-manifest.json` | table (family, deliverable, threshold, time limit, specialist result) |
| 5 | Headline: agent vs specialist **[pending]** | Per task, Opus 5.5 and Sonnet 5.5 against the specialist on the headline clinical metric, threshold drawn | `hosted-agents2.json` | `docs/figures/suite/hosted2_headline.png`; fallback `pilot1_headline.png`, labelled "local pilot" |
| 6 | Where the reward is lost **[pending]** | Separate delivery (ran, valid, on time) from clinical acceptability; show which tasks fail where | `hosted-agents2.json` | `hosted2_reward_keys.png`; fallback `pilot1_reward_keys.png` |
| 7 | Per case: gross errors, not boundary error | Fetal head: Opus 5.5 median error 2.05 mm (equal to the specialist mean) but six of 83 images off by 45 to 233 mm; the specialist passes every image | `pilot1-results.md` (trace analysis, per-case table); hosted per-case figure when available | `pilot1_per_case_measure_hc18.png` or `hosted2_per_case_measure_hc18.png` |
| 8 | A failure mode in one trace | Registration, Opus 5.5: spent the session sweeping settings, wrote `run.sh` 2.5 minutes before the end, never ran it; `python3 -I` broke the import, every hidden case failed in 0.2 s. State that version 1 never told the agent its session limit (our bug) and that version 3 fixes it | `pilot1-results.md` "reg_resect · claude-opus-5-5"; `instructions-v3.md` | short code excerpt (`exec python3 -I "$HERE/main.py"` and the `ModuleNotFoundError` line); add one hosted failure when available |
| 9 | Controls and exclusions | Where agent and specialist both pass (expected for ICU risk), the task is a control; pharyngitis is excluded because its labels are physician votes and the phone model stands in for the city | `PLAN.md`; `triage_pharyngitis.md`; gap verdicts from `hosted-agents2.json` **[pending]** | small table: task, verdict (gap shown / no gap / control / not interpretable) |
| 10 | Why the numbers can be trusted | Hidden cases only on the verifier; oracle rewards reproduced on Modal for all five tasks; agent network limited to the model API (PyPI and web unreachable); web tools removed from the agent; thresholds fixed before any agent result; one attempt, nothing rerun | `hosted-oracle1.md`; `instructions-v3.md`; `prespec.txt` in `exp/suite-hosted-agents1/` | none, or the oracle table |
| 11 | What it adds, and its limits | Combination not covered elsewhere: coding-agent harness, artifacts beyond segmentation, time limits as gates, same-case specialist (ReX-MLE, AutoMedBench, HealthAgentBench as nearest work). Limits: one attempt, 6 hidden cases for registration and spleen, public data | `landscape.md` sections 2 and 4; README "Limitations" | none |

### Backup slides

| # | Title (draft) | Message | Evidence (file) | Figure |
|---|---|---|---|---|
| B1 | Why each metric | TRE not image similarity; Dice plus volume; calibration and net benefit, not AUROC alone; worst subgroup; time as a gate | `metrics-review.md` sections 1(a) to 1(h) | none |
| B2 | The gap rule, exactly | Per-case: paired bootstrap on the cases the specialist passes, interval below 0; cohort: specialist meets every gate part, agent misses one | `DESIGN.md`; `pilot1-results.md` "Gap rule" | none |
| B3 | Thresholds and their sources | Which bounds are cited and which are our convention | README families table; family documents | table |
| B4 | Reward keys for every run **[pending]** | Full seven-key table for every hosted attempt | `hosted-agents2.json` | `hosted2_reward_keys.png` |
| B5 | Registration per case **[pending]** | Agent and specialist TRE per hidden case against the 2 mm line | `hosted-agents2.json` | `hosted2_per_case_reg_resect.png` |
| B6 | Spleen per case **[pending]** | Agent and specialist Dice per hidden case against 0.94 | `hosted-agents2.json` | `hosted2_per_case_seg_spleen.png` |
| B7 | Local pilot 1 in full | Four runs, gap verdicts with intervals, what the registration zeros do and do not show | `pilot1-results.md` | `pilot1_headline.png` |
| B8 | Task version history | v1/v2 did not state the session limit; v3 does; results are reported per version and not pooled | `instructions-v3.md`; `hosted-agents1.md` (when written) | none |
| B9 | Cost and run identifiers | API cost from traces at list prices; Modal cost not reported by Valkyrie; Valkyrie run IDs | README "Run identifiers"; `hosted-oracle1.md` "Cost" | none |
| B10 | Data and licences | Six public datasets and their licences; no UCSF data on the platform or in Git | README "Data and licences" | none |

### Notes for the deck builder

- Label every result slide with its source: "hosted, task version 3", "hosted, task version 2" or
  "local pilot 1". Do not mix sources in one chart.
- Do not call the pilot 1 registration zeros a capability gap (see `pilot1-results.md`, gap verdict notes).
- Do not write or paraphrase the overview paragraph; slide 2 is Jin's.
- Regenerate figures first: `~/miniconda3/envs/vals-suite/bin/python scripts/make_suite_figures.py`.
