# Round 4: more models, preregistration

Written 2026-11-15 04:00 EST by the coordinator, at Jin's request, before any round-4 run.
Nothing below may change after a result is seen; changes go at the bottom with time and reason.

## Question

Do the round-3 findings (fetal head gap, early stopping below the bar) hold for other frontier
models: Claude Fable 5.2 and OpenAI's newest Codex models (named by Jin as Astra, Sol and Luna;
exact API model IDs to be confirmed and recorded before their first run)?

## Arms and attempts, fixed now

| Model | Harness | Datasets | Attempts |
|---|---|---|---|
| `anthropic/claude-fable-5-2` | `claude_code_noweb-v1.0.0` (unchanged) | `suite/clinical-v1@2` (5 tasks), `suite/vessel-v1@1` | 3 full runs of clinical-v1, 1 of vessel |
| Codex models (up to 3) | Codex harness with web search off | OpenAI-network twins of the same tasks (below) | same as Fable |

Fable runs first; Codex runs need an OpenAI API key stored by Jin as a Valkyrie secret.

## OpenAI-network twins

The task images allow only `api.anthropic.com`. Codex needs `api.openai.com`. The twins change only
`allowed_hosts` in each task.toml; data, hidden cases, instruction, grader, limits and specialist
outputs are byte-identical, checked by a diff before pushing. The Codex agent must have web search
disabled, checked in a trace before results are read. Codex results are reported per model and are
never pooled with Claude results; the harness differs, which is stated next to every comparison.

## Rules

As round 3: every attempt counts, nothing rerun for a better number, one relaunch only for an
infrastructure failure, gap rule from DESIGN.md, local regrade for raw values. Budget: stop and
report if round-4 Anthropic spend passes $80 or OpenAI spend passes the credit Jin has.
Deadline: runs that have not started by 09:00 EST are dropped and reported as not run.

## Changes after registration

None yet.
