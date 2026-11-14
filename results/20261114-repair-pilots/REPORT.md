# PCNSL repair pilots: evidence and decision

**12/12 local agent attempts passed.** Of these, 10/10 have frozen private case/source snapshots. No frontier-model failure has been demonstrated in this round.

These are local isolated CLI experiments, **not Valkyrie runs**. Both backends were configured at high effort: response-confirmed `claude-opus-5-5`, and request-pinned `gpt-6-astra` (the Codex CLI did not emit a response model identifier).

| Experiment | Model | Outcome | Hidden fixtures | Seconds |
|---|---|---|---|---|
| endpoint / flawed / exploratory | claude | pass | 4/4 | 82.21 |
| endpoint / flawed / exploratory | codex | pass | 4/4 | 110.56 |
| claims / flawed | claude | pass | 4/4 | 70.39 |
| claims / flawed | codex | pass | 4/4 | 131.43 |
| geometry / flawed | claude | pass | 4/4 | 75.18 |
| geometry / flawed | codex | pass | 4/4 | 114.97 |
| integrated / flawed | claude | pass | 4/4 | 95.87 |
| integrated / flawed | codex | pass | 4/4 | 163.12 |
| integrated / clean | claude | pass | 4/4 | 200.33 |
| integrated / clean | codex | pass | 4/4 | 159.94 |
| integrated / flawed / held-out 101 | claude | pass | 4/4 | 89.28 |
| integrated / flawed / held-out 101 | codex | pass | 4/4 | 133.03 |

## Interpretation

The initial hypothesis was that executable repository repair would expose errors hidden by simple answer scoring. Both models repaired the separate endpoint, inference and geometry tasks. We then combined endpoint construction, selected scans, transitive patient identities, model-artifact ancestry, regenerated permutation nulls, multiplicity correction and manuscript reconciliation. The integrated development trial also passed, so the frozen version proceeded to a valid control and a new seed without further task or prompt tuning.

The protocol supplies the scientific rules. The measured capability is faithful implementation and repair across connected evidence, not autonomous methodological discovery. `findings.md` and general clinical judgement are not graded. A valid control is scored on preserved behavior; textual edits alone are not a regression.

**Keep the harness and passing controls; do not pitch this version as an established frontier-failure benchmark.** The next candidate should require expert-adjudicated research decisions from genuine evidence, with a clear task contract but less procedural scaffolding. Freeze that as a new development version. Do not turn these held-out results into tuning data and retain the held-out label.

## Evidence boundaries

- Four hidden fixtures are reruns of one submitted program, not four independent agent attempts. They contain new cohorts and an order counterfactual within the same task family.
- The two endpoint attempts are exploratory: their generator changed while the run was active. They are excluded from the frozen denominator rather than silently reconstructed.
- Model budget was 600 seconds per attempt; Claude's configured usage-estimate cap was $5. Historical local replay used 20 seconds per fixture, a 2 MB output limit and no explicit CPU/address-space cap. Subsequent stricter replay is reported separately; it does not rewrite these manifests.
- Infrastructure, budget exhaustion and invalid submissions require separate classification. A zero reward alone is not a scientific reasoning failure. See the implementation review.
- Data acquisition/audit and fixed real-data baselines are separate experiments. These model inputs are wholly synthetic and do not validate clinical utility or mutation predictability.
- Root/container verifier execution and actual hosted Valkyrie execution remain pending. Local SDK packaging is not platform execution.

## Reproduction

Aggregate manifests and results accompany this report. Private source/case snapshots, raw traces and submitted workspaces remain under `exp/20261114_pcnsl-frontier-suite/` on teal. `scripts/run_repair_pilot.py` creates a new immutable run directory and detects source drift. `scripts/summarize_repair_results.py` regenerates this report without new model calls.
