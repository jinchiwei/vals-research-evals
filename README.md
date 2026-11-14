# Research-agent eval prototypes for Vals

Research-agent evaluation preparation for the
[Vals AI hackathon](https://www.vals.ai/hackathon), November 14–15, 2026.
The target is **Build Your Own Eval**, which requires a benchmark on Valkyrie
for a task frontier models still get wrong. These are preparation prototypes;
the public event page does not establish whether pre-event code may be submitted.

## Real-data PCNSL prototype

[PCNSL tabular prototype](pcnsl/README.md) reuses the existing SCS cohort and
feature pipeline. It runs fixed baselines and builds local prediction tasks.
Patient-level data remain on SCS. The latest run uses 33 patients with exact scan
and paired-sample matches to the Box release candidate: three experiments, 154
verified task bundles, and separate legacy/reported-pathogenic endpoints.
See the [matched-cohort findings](pcnsl/results/20261114-box-matched-v2/REPORT.md).
Final published-archive identity and live frontier-agent evaluation remain pending.

## Current result for the original synthetic tasks

**No frontier-model failure demonstrated yet.** Opus 5.5 at high effort solved
all 12 local task attempts across the original version, a harder workflow version,
and the frozen workflow version on held-out seed 101. All 12 saved analyses also
reproduced correct outputs when replayed in clean, network-isolated workspaces.
Keep the harness, but strengthen or replace these tasks before presenting them
as a benchmark of frontier-model failures. Hosted Valkyrie execution remains pending.

- [HTML results report](results/REPORT.html)
- [Comparison deck](results/deck/COMPARISON.pptx) and [slide previews](results/deck/COMPARISON_qa/)
- [Experiment record](docs/EXPERIMENTS.md)
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
