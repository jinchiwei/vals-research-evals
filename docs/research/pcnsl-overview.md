# UCSF PCNSL and brain-imaging research-agent work (previous README)

This file is the repository README as it stood before the clinical deliverables suite became the
hackathon submission. It was moved here on 2026-11-14 with its content unchanged; only relative links
were rewritten so they resolve from `docs/research/`. Shell commands below run from the repository root.
The submission placeholder quoted below refers to that earlier README; the submission overview now sits
at the top of the [main README](../../README.md).

## Original README

### Quantitative brain-imaging research-agent evals for Vals

> **Submission placeholder — Jin must write the opening overview paragraph himself.**
> The official track requires an entirely human-written opening paragraph.
> The technical documentation below is preparation material, not that paragraph.

Research-agent evaluation preparation for the
[Vals AI hackathon](https://www.vals.ai/hackathon), November 14–15, 2026.
The target is **Build Your Own Eval**, which requires a benchmark on Valkyrie
for a task frontier models still get wrong. These are preparation prototypes;
the [exact track instructions](hackathon-prompt.md) are saved here.
The assigned Valkyrie organization is `hackathon-neuronetwork-b91c517178`.
Hosted authentication and execution have not yet been verified.

The [current implementation plan](../superpowers/plans/2026-11-14-real-prediction.md)
prioritizes a real prediction workflow packaged as Harbor agent tasks, with direct
frontier-model prediction as a supporting comparison. Judging covers novelty,
execution, difficulty, importance, and clear presentation of measured results.

## Current scope: execute the brain-imaging workflow

The main benchmark now tests frontier **agents** doing quantitative imaging work:
produce a lesion mask, measure lesion burden and diffusion correctly, and carry
those measurements through a reproducible workflow. Standard metrics such as Dice,
volume error and ADC error score the requested artifacts. Running a segmentation
network alone would evaluate that network; this suite evaluates the agent's use of
the available data and tools. See [the revised scope](imaging-suite-scope.md).

Genetic prediction remains a separate research track. The public-release pilot
has not established a reliable frontier-specific predictive gap. IRF4 currently
has only **two qualifying positives** under the audited endpoint, and its original
label definition is being reconciled before any IRF4-centered evaluation.

## Completed genetic-prediction pilot and its limits

Jin's original question is whether frontier models can predict held-out mutation
status from the available imaging, PyALFE/radiomics features and clinical variables,
compared with his actual TabPFN-based workflow. The twelve all-pass local attempts
below tested highly scaffolded synthetic code repair. **They did not test this
prediction question.** A subsequent real direct-prediction pilot is now complete:
see the [Versa results](../../pcnsl/results/20261114-versa-pilot/REPORT.md),
[cached TabPFN comparison](../../pcnsl/results/20261114-tabpfn-pilot/REPORT.md), and
[fixed conventional controls](../../pcnsl/results/20261114-prediction-baselines/REPORT.md).
The ten-feature logistic-regression baseline also does not reproduce the full
historical feature pipeline.

Keep two comparisons separate: (1) a frontier model predicts probabilities from
the same allowed training examples and test features as tabular baselines, and
(2) a frontier agent uses scientific tools, potentially including PyALFE and
TabPFN, to construct and execute the prediction workflow. The latter measures the
agent-plus-tools system. Use identical patient splits, hidden test labels,
documented tool budgets and prespecified gene eligibility; avoid selecting genes
on the final test results. Verify positive/negative ascertainment rather than
silently treating an absent mutation row as biological wild type.

Poor held-out performance is a valid measured outcome. A specific frontier
capability gap needs comparison with attainable performance and uncertainty;
near-chance results across all systems do not establish bad genetic labels or
prove the absence of biological signal. Existing repair tasks remain controls.
Versa routes were checked with four synthetic health calls; four real requests
then ran on SCS. GPT-5.2 returned valid probability objects; Opus 5.5's responses
failed the frozen format rule but contained individually valid JSON blocks,
scored only as post-hoc diagnostics. Single-fold scores are not model rankings.
No real agent-with-tools prediction task has yet run on Valkyrie.

## Current PCNSL benchmark suite

The [benchmark design](benchmark-design.md) maps **30 proposed
failure mechanisms** to evidence, graders and valid controls. Four executable
synthetic task families test endpoint reconstruction, statistical claims,
image geometry/ADC, and an integrated manuscript audit. These measure faithful
execution and repair under documented scientific rules; they do not establish
unprompted discovery of methodological flaws.

- [PCNSL literature review](pcnsl-literature.md) and
  [research-agent evaluation review](evaluation-literature.md)
- [Search methods and coverage](literature-search-method.md)
- [Hosted data scope and provenance](data-scope.md)
- [Latest pilot evidence](../../results/20261114-repair-pilots/)
- [Claude-authored PCNSL deck](../../results/pcnsl-frontier-deck/PCNSL_FRONTIER.pptx)
- [Valkyrie execution checklist](valkyrie-integration.md)

**Current result: all 12 new local model attempts passed**, including integrated
clean controls and held-out seed 101. Ten attempts have frozen source/case
records; two endpoint attempts remain exploratory. All ten frozen submissions
also passed stricter replay (40 fixtures, zero new model calls). This is a
working capability/control suite, **not yet a demonstrated frontier-failure
benchmark**. The final exporter produces 16 SDK-validated tasks.

The actual UCSF hosted v1.0 archive is downloaded, SHA-256 checked and ZIP-CRC
verified on FAC DS6. It contains 150 patients and 64 patients with mutation
records; 63 have FLAIR summary features. Five inspected clinical files and 33
inspected feature files match the Box candidate byte-for-byte. This establishes
identity of those files, not equivalence of whole releases or clinical eligibility.
Patient-level records remain on FAC/SCS; Git contains code, source references and
aggregate results. See the [hosted inventory](../../pcnsl/results/20261114-hosted-release/aggregate_inventory.json).
The [fixed public-data baseline](../../pcnsl/results/20261114-hosted-release/REPORT.md)
used all 63 eligible patients: mean pooled out-of-fold AUROC across three seeds
was 0.6684 for MYD88 and 0.4434 for CD79B. These are descriptive internal results
for reported qualifying alterations, with unadjudicated scan/specimen timing;
they establish neither clinical utility nor a frontier-agent failure.

Generate the new executable tasks without uploading:

```bash
python3 -m repair_evals.export --out dist/repair-tasks \
  --families endpoint claims geometry integrated --seeds 11 101 --variants flawed valid
.venv-valkyrie/bin/python scripts/validate_exports.py dist/repair-tasks results/package-check
.venv-valkyrie/bin/python scripts/valkyrie_preflight.py --tasks dist/repair-tasks
```

Local model pilots require Linux bubblewrap namespaces and existing CLI logins:

```bash
python3 scripts/run_repair_pilot.py --out exp/my-integrated-pilot \
  --families integrated --seed 11 --backends claude codex --timeout 600 --budget 5
```

The runner saves private case/source snapshots, detects source drift, and reruns
submitted programs on four hidden inputs. Raw traces and workspaces are ignored
by Git. CLI usage estimates are not billing statements. Follow the bounded
[research plan](../superpowers/plans/2026-11-14-frontier-suite.md); do not tune on
held-out outcomes or count fixtures as independent model trials.

**Hosted Valkyrie has not run.** Organizer access is pending; packaging and local
custom pilots must not be presented as completed platform execution. The
exported verifier assumes a trusted runtime; its root/container path still needs
provider smoke testing. Local bubblewrap tests do not establish adversarial security.

## Real-data PCNSL prototype

[PCNSL tabular prototype](../../pcnsl/README.md) reuses the existing SCS cohort and
feature pipeline. It runs fixed baselines and builds local prediction tasks.
Patient-level data remain on SCS. The latest run uses 33 patients with exact scan
and paired-sample matches to the Box release candidate: three experiments, 154
verified task bundles, and separate legacy/reported-pathogenic endpoints.
See the [matched-cohort findings](../../pcnsl/results/20261114-box-matched-v2/REPORT.md).
The inspected source files now match the hosted archive; original internal
cohort-selection and endpoint caveats remain. Live frontier-agent evaluation of
patient-level records has not been performed.

## Current result for the original synthetic tasks

**No frontier-model failure demonstrated yet.** Opus 5.5 at high effort solved
all 12 local task attempts across the original version, a harder workflow version,
and the frozen workflow version on held-out seed 101. All 12 saved analyses also
reproduced correct outputs when replayed in clean, network-isolated workspaces.
Keep the harness, but strengthen or replace these tasks before presenting them
as a benchmark of frontier-model failures. Hosted Valkyrie execution remains pending.

- [HTML results report](../../results/REPORT.html)
- [Comparison deck](../../results/deck/COMPARISON.pptx) and [slide previews](../../results/deck/COMPARISON_qa/)
- [Experiment record](../EXPERIMENTS.md)
- Valkyrie task bundles can be regenerated with the export commands below; ZIP archives are not tracked.

The deck was authored by Claude Opus 5.5 at high effort with Jin's `build-pptx`
skill. It is an internal preparation review, not a claim of submission readiness.

## Candidates

| Family | Capability | Controls | What this v0 does not establish |
|---|---|---|---|
| Would You Publish This? (`audit`) | Execute an audit of an image predictor's incremental discrimination beyond acquisition protocol | Confounded predictor and genuine within-protocol signal | General discovery of arbitrary research flaws; causal claims; raw-image understanding |
| Brain Change Detective (`change`) | Combine scanner calibration, irregular follow-up and known measurement uncertainty | Stable, declining, scanner-shift, and insufficient-precision subjects | Clinical validity of the synthetic decision threshold |
| Report Evidence Detective (`reports`) | Reconcile exam chronology, later signing, addenda, negation and uncertainty | Present, resolved, uncertain, unassessed, and newly present findings | Natural clinical language coverage; current templates are small and authored |

All data in the original three synthetic families are invented. No ADNI/NACC/UCSF data, embeddings, checkpoints, reports,
or patient identifiers are included. Domain failure patterns informed the tasks.

## Run locally (Python 3.11+, standard library only)

```bash
python3 -m unittest discover -s tests -v
python3 -m research_evals smoke --out results/my-controls
python3 -m research_evals export --out dist/my-tasks --seeds 11 23 37
python3 -m research_evals export --out dist/workflow-tasks --workflow --seeds 11 23 37
```

The smoke loop evaluates three **scripted controls**, not LLMs. It records a
hypothesis and keep/reject decision for each, selects on development seeds
11/23/37, then evaluates the selected control on held-out seeds 101/211/307.
Results are append-only JSONL plus summary JSON. Existing result directories
are not overwritten. Touch `RESULT_DIRECTORY/STOP` to stop before the next iteration.

## Live frontier-agent pilot

On Linux with bubblewrap, the native Claude executable, and an existing Claude login:

```bash
python3 -m research_evals pilot --out results/my-opus-pilot \
  --model claude-opus-5-5 --effort high --seed 11 --max-tasks 4 \
  --timeout 240 --budget 3
```

This is a **local tool-agent pilot, not hosted Valkyrie execution**. The agent
gets Read/Write/Edit/Bash, a Python runtime and synthetic input.json. Its filesystem
does not contain the repository, generator, private grader or answer key. Hooks,
skills, MCP and memory are disabled. Existing Claude credentials are mounted read-only
for authentication; they are not copied into results. Network remains available.
Use only trusted synthetic tasks with this runner; it is not a hostile-agent security benchmark.

Four tasks maximum, $3 per-task usage ceiling by default, 240-second wall-clock
limit per task. The CLI reports estimated dollar usage even when using a subscription;
this is not a claim about the user's bill. A missing model or login stops the run.
The trace records tool calls, returned model identifiers, usage and final artifacts.
Touch `RESULT_DIRECTORY/STOP` or its parent's `STOP` to stop before the next case.

`--prompt-variant audit-check` adds a documented self-check instruction. Tune on
development cases only. Once the prompt and task version are frozen, run a new seed
with `--seed 101`; do not use that result to tune and still call it held-out.

The second-round `--workflow` variant preserves each underlying scientific answer
while adding realistic preprocessing work: repeated events, training-subject exclusions,
duplicate exports, revised diagnosis labels, mixed volume units, age norms and finding-specific
addenda. Use `--workflow` with either `export` or `pilot`.

The official CLI requires Python 3.12. It is installed locally in `.venv-valkyrie/`.
Validate and pack without uploading:

```bash
.venv-valkyrie/bin/python scripts/validate_exports.py dist/workflow-tasks results/my-package-check
python3 scripts/verify_isolated.py dist/workflow-tasks
python3 scripts/replay_analyses.py
python3 scripts/build_report.py
```

## Valkyrie integration

The exporter writes each case as a self-contained Harbor-format task folder:

```
TASK_ID/
  instruction.md
  task.toml
  environment/Dockerfile
  environment/input.json
  tests/test.sh
  tests/grade.py
  tests/expected.json
  solution/solve.sh
  solution/research_evals/...
```

Valkyrie supports publishing these task folders as a dataset. Each task's Docker
build context contains **only** the public input and runtime definition. Tests and
solutions must be mounted only during their respective verifier/oracle phases.
Never give the full exported task directory to an evaluated agent as its workspace.

After obtaining the event's Valkyrie account, Modal setup and provider key:

```bash
valkyrie login
valkyrie dataset push research-evals/development ./dist/my-tasks --tag v0.1
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/examples/claude_code-v1.0.0
valkyrie secret set anthropic-api-key
# Set MODEL_ID to the exact frontier model enabled by the organizers.
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset research-evals/development@v0.1 --model "$MODEL_ID" \
  --provider modal -s ANTHROPIC_API_KEY anthropic-api-key --slice 0:4 --concurrency 1
```

This project does not upload, publish, create accounts or configure billing.
The official CLI and hosted service must accept a dataset before it can be called
a completed Valkyrie integration. Local schema/format checks alone are insufficient.

References: [Valkyrie dataset guide](https://docs.valkyrie.vals.ai/benchmarks/datasets),
[Valkyrie repository](https://github.com/vals-ai/valkyrie),
[Harbor task format](https://docs.harborframework.com/tasks/overview).

## Grading and scientific limits

The immutable verifier compares structured artifacts with hidden numerical or
authored semantic gold answers. Numeric tolerance is 1e-4. Missing/duplicate IDs,
nonfinite numbers and incorrect evidence fail. Each item must satisfy every required
field; task reward is fraction of correct items. `resolved` requires all items.
Local summary selection uses equal weight per benchmark family.

This is artifact correctness, **not proof the submitted analysis.py reproduces it**;
inspect the recorded execution trace as well. Text explanations receive no keyword
points. For report tasks, the instruction specifies an exact full-sentence quote;
that narrow contract is a limitation, not a general semantic similarity metric.

For the recorded local pilot, `scripts/replay_analyses.py` additionally reruns each
saved analysis on its original input in a fresh network-isolated filesystem with
no answer key. All 12 recorded analyses reproduced full-credit outputs. That is
stronger evidence for these local runs; the exported hosted grader still scores
artifacts and does not automatically perform this replay.

Generated seed variants share task templates; they test numerical/permutation
generalization, not entirely unseen task families. Do not claim a broad leaderboard
from four tasks or one model. Inspect every failure: infrastructure errors and
ambiguous gold labels are not model reasoning failures. If frontier agents solve a
family, strengthen the task for a real workflow reason or discard it; do not hide wins.

## Deck preference

If a deck is created, delegate to Claude Opus 5.5 at high effort using Jin's
`~/.claude/skills/build-pptx/SKILL.md`, including its bespoke layouts, speaker notes
and visual QA. Do not substitute a generic deck or silently change the requested model.
