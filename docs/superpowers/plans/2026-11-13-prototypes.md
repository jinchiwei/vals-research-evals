# Three research-agent eval prototypes

User authorized implementation and autonomous iteration; no additional design gate.

Goal: compare three candidate benchmarks for Vals' Build Your Own Eval track:
research-claim auditing, longitudinal measurement reasoning, report evidence reconciliation.

Architecture: zero-dependency Python generators and hidden deterministic graders;
Harbor task folders consumed by Valkyrie. Synthetic inputs only. Public inputs and
private answers are separate. Model agents produce answer.json using filesystem/code tools.

Execution: implement inline. Keep benchmark rules fixed within each version. Develop
on seeds 11/23/37, evaluate selected candidates once on held-out seeds 101/211/307.
Record failures and revisions rather than silently replacing results. STOP file ends loops.

- [x] Tests: hand-checked AUC, scanner correction, report chronology, invalid answers,
  hidden-answer exclusion from environments, clean and flawed controls.
- [x] Implement generators, reference solutions, deliberately weak baselines and grader.
- [x] Export tasks, run isolated reference/verifier integration and schema validation.
- [x] Run bounded frontier-agent pilot with existing login, preserving traces/model IDs.
- [x] Inspect failures, revise on development cases, then run held-out pilot.
- [x] Produce comparison report; distinguish scripted checks from frontier-model results.

Outcome: 12/12 live Opus 5.5 high-effort tasks passed, including held-out seed 101.
No frontier failure demonstrated. Infrastructure/format prototype is complete;
selecting a sufficiently difficult hackathon submission remains open.

Constraints: no clinical data/checkpoints, no model-failure claims without live evidence,
no publishing/submission. Hosted Valkyrie execution requires its account and provider setup.
Pre-event work eligibility is not stated on the public event page; disclose preparation.
Decks, if produced: Claude Opus 5.5 high, using ~/.claude/skills/build-pptx/SKILL.md.
