# Deck-builder assignment

You are the delegated slide-deck worker, requested by Jin. Use Claude Opus 5.5 at
high effort. Read and follow /home/jkwei/.claude/skills/build-pptx/SKILL.md and its
required references. Use Jin's bespoke PPT builder, not a generic PPT generator.

Create an INTERNAL prototype comparison deck for Jin, who knows his own research.
This is a hackathon-preparation experiment review, not a full research talk: omit
the multi-slide foundational literature introduction. Use bespoke diagrams and
data figures, comprehensive speaker notes, and the skill's visual QA. Keep the
deck to about 6 slides. Do not fabricate performance or call scripted baselines
frontier agents. No external-site deployment, posting, or messages.

Read README.md, results/20261113-opus55-dev-v1c/summary.json,
results/20261113-opus55-workflow-dev/summary.json, and (when ready)
results/20261113-opus55-workflow-heldout/summary.json. The held-out run is currently
running; while authoring, use completed per-case result.json files, and refresh
all numbers before final render. Wait at most 5 minutes for held-out summary; if
absent, label it pending rather than assuming a result.

Core story:
- Event: Vals Build Your Own Eval requires a benchmark on Valkyrie exposing tasks
  frontier models still get wrong; demos Nov 15. Source https://www.vals.ai/hackathon
- Three candidates: research-claim audit, calibrated longitudinal change, report
  evidence reconciliation. Synthetic data only, informed by Jin's research failure patterns.
- Iteration 1: four tool-agent tasks, including both flawed and clean audit controls.
  Actual model claude-opus-5-5, effort high. ALL FOUR passed. Not a failure benchmark yet.
- Iteration 2: add cohort joins/exclusions/revisions, mixed units and age norms,
  finding-specific addenda. ALL FOUR development tasks passed. Do not hide wins.
- Official Valkyrie SDK validated/packed 12 task folders per variant. All 12
  exported reference/verifier roundtrips passed. Hosted Valkyrie has NOT run.
- Local CLI traces capture actual model IDs, tool calls, answers, code, usage.
  Two initial infrastructure failures made no model calls; exclude them from model accuracy.
- Honest recommendation: no demonstrated frontier gap in these versions. Keep
  the harness; next test should require repairing an underspecified analysis
  repository or reconciling much longer evidence chains, with defensible hidden tests.

Output under results/deck/:
COMPARISON.pptx, source markdown/layout, bespoke figures, slide preview images
if tools permit, and a brief build-status.json naming model and QA results.
Do not modify benchmark code, tests or earlier result artifacts.
No need to wait for further permission; Jin explicitly authorized prototypes and
asked for you and this skill whenever decks are needed.

Use locally available Python environments with python-pptx/matplotlib, or create
a project-local venv if needed. Do not install system packages or alter shared skills.
Use a bounded workflow; prioritize a correct, reviewable small deck. Cite sources
and label all synthetic schematics as synthetic/illustrative where relevant.
