# Claude deck assignment: PCNSL research-agent evaluations for Vals

Jin explicitly requested that Claude author all decks using his own PPT builder.
Use Claude Opus 5.5 at high effort. Any Claude worker is acceptable; no need to
message an existing chat. Use and follow these resources:

- `/home/jkwei/arcadia/superstack/skills/build-pptx/SKILL.md`
- its `plan_prompt.md`, required references, and `tests/fixture_realistic.md`
- Jin's shared branding through the builder; do not modify shared skills

Write ONLY under `results/pcnsl-frontier-deck/`. Create an approximately 12-slide
internal research/hackathon briefing, plus a compact reference appendix if useful.
This replaces neither the earlier prototype comparison deck nor its recorded results.
Deliver `PCNSL_FRONTIER.pptx`, markdown, layout sidecar, figures, rendered PDF/PNG
previews, speaker notes, and `build-status.json` with provenance and actual QA.
Use named layouts, readable figures and concise takeaways; avoid dense prose on slides.
Read previews with the image-capable Read tool and correct visible clipping/overlap.
All visualizations must reflect measured evidence or be clearly labeled schematic.

Read these inputs (only aggregate reports, never raw patient data or credentials):

- `docs/research/benchmark-design.md`
- `docs/research/pcnsl-literature.md` and `pcnsl-sources.json`
- `docs/research/evaluation-literature.md` and `evaluation-sources.json`
- `docs/research/literature-search-method.md`
- `docs/research/data-scope.md`
- `docs/research/valkyrie-integration.md`
- `results/20261114-repair-pilots/` JSON and REPORT.md if present
- `pcnsl/results/20261114-hosted-release/` aggregate reports if present
- `results/20261114-repair-suite-v1-packaging/validation.json`
- `pcnsl/results/20261114-box-matched-v2/REPORT.md` for historical context only

The final control/held-out pilots are running while you begin authoring. Work on
the literature, methods, diagrams and structure first. Before final rendering,
check for `results/20261114-repair-pilots/FINALIZED`; when present, reread REPORT.md
and use its final numbers. If absent, wait in short intervals for at most five
minutes while doing useful deck work. If it remains absent, label this a draft
and mark those results pending rather than guessing. The parent will finalize
the evidence shortly. The integrated development trial is complete: both models
passed all four hidden fixtures.

Core story:

1. Vals **Build Your Own Eval** requires a benchmark **on Valkyrie** of a task
   frontier models still get wrong. Official public judging is demo-based;
   do not invent weighted criteria. Cite https://www.vals.ai/hackathon.
2. Evaluate whether agents make **valid, reproducible research claims** from a
   PCNSL workflow. Low biological predictability is NOT an agent failure.
   A correct null/inconclusive result can receive full credit.
3. Public PCNSL MRI/genomics offers domain-grounded contracts. Separate the
   actual hosted archive, the Box candidate, internal pipeline and synthetic
   counterfactual tasks. Never label a private candidate automatically public.
4. Literature review: existing radiogenomic studies and scientific-agent
   benchmarks already exist. No "first scientific integrity benchmark" claim.
   Explain our proposed narrow contribution and concrete gaps, not generic novelty.
5. Thirty proposed mechanisms span genomic denominators, chronology/identity,
   geometry/units, leakage, statistical inference and claim validity. A catalog
   is not thirty implemented or empirically failing tasks.
6. Three executable repair controls: endpoint/cohort, statistical claims,
   image geometry/ADC. Integrated manuscript audit is the current harder candidate.
7. Honest evidence: original twelve historical Opus attempts all passed. In
   the new basic-repair pilots, both models passed all three families. Endpoint
   attempts are exploratory (generator changed during execution); frozen claims
   and geometry comprise FOUR agent attempts, each passing FOUR replay fixtures.
   A fixture is not a new model attempt, and repeated templates are not patients.
8. Use latest final aggregate report for the integrated experiment; do not
   invent a failure or infer results from an absent file. Show model wins too.
   Codex model request is pinned gpt-6-astra/high; its CLI did not emit a response
   model ID. Claude response confirms claude-opus-5-5/high.
9. Hidden new-cohort replay checks executable repairs; clean controls check
   unnecessary damage. Packaging checks are not Valkyrie execution. Root
   container verifier path remains untested unless a final report says otherwise.
10. Hosted Valkyrie is pending organizer access/credits, per Jin's instruction
    to prepare everything meanwhile. The SDK package and launch checklist are ready;
    do not imply any platform run ID, upload, submission or hosted frontier result.
11. End with the concrete demo/readiness decision and the next experiment.

Historical PCNSL baselines (33-patient exact matched subset, IRF4 endpoint
sensitivity) are contextual only. No clinical utility, generalizability, or
frontier-model failure can be inferred from those small retrospective results.
Prefer a schematic of the endpoint/validation mistake to an inflated AUC headline.

Build environment already available:

```
PYTHONPATH=/tmp/vals-deck-pydeps python3.12 ...
PATH=/tmp/lo-qa/bin:$PATH PYTHONPATH=/tmp/vals-deck-pydeps python3.12 \
  /home/jkwei/arcadia/superstack/skills/build-pptx/build.py \
  --input PATH.md --output PATH.pptx --qa
```

Set MPLCONFIGDIR to a writable directory under the output or /tmp. The ordinary
repo `.venv` does not have python-pptx; use the existing temporary dependency set.
Reuse existing runtime, no system package installation, external posting, email,
other-agent messages, credentials, or raw patient files. No AI Git attribution.
Prioritize evidence accuracy and readable slides. Record limitations explicitly.
