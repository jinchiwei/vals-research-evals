---
title: "Clinical deliverables: coding agents against specialist systems"
eyebrow: "VALS AI HACKATHON · BUILD YOUR OWN EVAL · 2026"
subtitle: "Real medical tasks, clinical metrics, clinical time limits, a specialist on the same hidden cases"
name: "Jinchi Wei"
org: "Vals AI hackathon · Build Your Own Eval track"
date: "2026-11-15"
theme: slate
no_intro_figures: true
---

## Overview

Slot for the presenter's own overview, to be written and spoken by Jin.

---

## Clinical evaluation — what a generic benchmark score leaves out

- **Clinical metric in units:** registration error in mm, organ volume in mL, head circumference in mm, calibrated risk
- **Clinical time limit:** a pipeline that is accurate but late is not usable
- **Specialist baseline:** the bar is a specialist system on the same hidden cases, not a leaderboard

---

## Task contract and the seven task families

![Task contract](figures/fig_contract.png)

- Registration, spleen, fetal head, retinal vessels, ECG, ICU risk, treatment effect

---

## Agent vs specialist — three attempts per task and model

![Headline](figures/fig_headline.png)

- Fetal head: gap shown in 3 of 3 attempts for both models

---

## Fetal head circumference — error per hidden image, six attempts

![Fetal head per image](figures/fig_hc18.png)

- Specialist 83/83; agents 35 to 74 of 83

---

## One trace — Opus 5.5 on fetal head stops at 11.6 of 45 minutes

![Timeline](figures/fig_timeline.png)

- Cross-validation "about 60% … well below the 90% target"; hidden 42 %

---

## Stated time pressure — early endings and two instruction tests

![Instruction tests](figures/fig_elicitation.png)

- "I stopped there because of the session limit." at 8 of 45 minutes

---

## Retinal vessels — near-parity with the specialist

![Vessel per image](figures/fig_vessel.png)

- Opus 5/8, Sonnet 4/8, specialist 6/8; no gap shown

---

## Limits and how to run

- Three attempts per task and model; 6 hidden cases for registration and spleen
- `valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@instr2`

---

# Backup

---

## Gap verdicts — every attempt, specialist-passed cases

- Per-attempt verdicts

---

## Reward keys for every headline attempt

![Reward keys](figures/fig_reward_keys.png)

- All seven reward keys for the 30 headline attempts

---

## Session use — every attempt in every workstream

![Session use](figures/fig_session.png)

- No attempt used its whole session

---

## Sonnet 5.5 on registration — a no-op pipeline after 3 minutes

- Shipped a copy of the input landmarks; mean TRE 6.18 mm, the uncorrected error

---

## Why the numbers can be trusted

- Hidden cases only on the verifier; oracle rewards reproduced on Valkyrie; network limited to the model API

---

## Earlier runs — the session-limit bug and its fix

- Hosted run 1 and local pilot 1 did not state the session limit

---

## Report labelling — excluded from scoring, worked example

![Report labels](figures/fig_report_label.png)

- Opus 5.5 beat the specialist but missed the F1 bar by 0.01

---

## Treatment effect — a control family

![Causal](figures/fig_causal.png)

- Specialist and all six agent attempts pass

---

## PCNSL mutation prediction — no method above chance

![PCNSL](figures/fig_pcnsl.png)

- No comparator succeeds, so no frontier gap can be shown

---

## Dataset selection — licence, clinical bar, specialist, size

![Funnel](figures/fig_funnel.png)

- About 40 datasets screened

---

## Cost and run identifiers

- API cost by round; Modal cost not reported

---

## Clinical thresholds and their sources

- Every family's bar and its source
