# Experiment record — 2026-11-13

## Purpose and decision rule

Find a viable candidate for Vals' Build Your Own Eval track. A valid candidate
must expose a substantive failure by a current frontier model under reasonable
tool access, while passing a defensible reference solution. Packaging alone does
not establish difficulty. Infrastructure and grader defects do not count as model errors.

All experiments use invented data. The biomedical motivation comes from research
workflows; no clinical records or derived patient features enter any model context.

## Scripted harness checks

Three strategies (naive, adjusted, careful) were evaluated in a bounded sequence.
The best development strategy was selected before evaluating held-out seeds.
These are fixed diagnostic scripts, not autonomous LLMs. Their failures validate
controls but are not evidence for the hackathon's frontier-model criterion.

## Iteration 1: procedural tasks

Hypothesis: numerical conditioning, uncertainty, and report chronology might
expose model weaknesses even with explicit task definitions.

Result: Claude Opus 5.5, high effort, with Bash/Read/Write/Edit, solved 4/4 tasks
on development seed 11: confounded audit, clean audit, change panel, report panel.
Model identifiers and tool calls are preserved in `20261113-opus55-dev-v1c`.

Decision: reject this version as a demonstrated frontier-failure benchmark.
Keep it as a harness smoke test and simple control condition.

## Iteration 2: workflow reconstruction

Hypothesis: the first version did too much preprocessing. Add real workflow
obligations while preserving the underlying answers:

- Audit: exclude training participants; select earliest eligible visit; deduplicate
  exports; join highest-revision labels; retain literal negative category `None`.
- Change: convert mixed cm3/mm3; account for attained-age norms and scanner
  calibration; propagate known measurement variance into normalized slopes.
- Reports: distinguish exam time from signing time; apply corrections only to
  the findings an addendum actually addresses.

Result: the same frontier tool agent solved 4/4 development tasks. Logs in
`20261113-opus55-workflow-dev`. No hidden failures were discarded.

Decision: freeze this version for a seed-101 held-out check, with no further
prompt, generator, metric, threshold, or grader changes based on that check.
This evaluates numerical/permutation generalization, NOT unseen task families.
The held-out result is recorded in `20261113-opus55-workflow-heldout/summary.json`.

Held-out result: 4/4 passed. Across the three live runs, Opus 5.5 solved 12/12
tasks (including both audit controls in every run). Estimated CLI usage summed
to about $1.51; this is a usage estimate, not a billing claim. These pilots do
not establish a frontier-model failure in any of the three candidate families.

## Infrastructure failures

The first local pilot could not mount the native CLI under a read-only /usr.
The second lacked WSL's symlink target for /etc/resolv.conf. Both were fixed and
verified before the live run; neither produced a model response. They remain
in the record and are excluded from model-performance claims.

Valkyrie CLI 2026.11.12.2 and SDK 0.34.0 require Python 3.12. The initial Python
3.13 installation failed cleanly; the project-local `.venv-valkyrie` uses 3.12.

## Framework requirements and remaining gap

The official SDK's task discovery, validation and packaging accepted all 12
exported tasks in each version. Separate isolated solution and verifier phases
produced full rewards on all 12. This validates the local task contract.

No hosted Valkyrie run, Modal provider setup, account creation or upload has
occurred. The public event page does not clarify eligibility of pre-event code.
Disclose these preparation prototypes and confirm that rule with organizers.

## Next research pivot

The tested transformations did not defeat Opus. More CSV rows or arbitrary
time pressure would not establish a more meaningful task. The next experiment
should test a different capability: repairing an analysis repository whose
methodological mistakes are not enumerated in the task prompt, or integrating
long evidence chains with competing scientific explanations. Such a benchmark
needs independent test fixtures and expert review, rather than simply extending
the current templates. Do not advertise any current family as an unsolved task.

Nearby work includes DSBench (https://arxiv.org/abs/2409.07703) and
RealDataAgentBench (https://github.com/patibandlavenkatamanideep/RealDataAgentBench).
The current prototypes make no novelty claim over those benchmarks.
