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

All entries below were written by the round-4 worker (Claude Opus 5.5, `claude-opus-5-5`) before any round-4 result
was read. Evidence: `exp/suite-hosted-models4/`.

1. **2026-11-15 03:45 EST. Fable model ID confirmed: `anthropic/claude-fable-5-2`** (API ID `claude-fable-5-2`, list
   price $8 / $40 per MTok, twice Opus 5.5). `run start` accepted it and the first assistant message of the vessel run
   reports `"model":"claude-fable-5-2"`. The vessel run (`f59ed1c7-…`, 03:29 EST) doubled as the one cheap check; it is
   the planned vessel attempt, not an extra one. The three clinical runs were launched at 03:33 EST. `suite/clinical-v1@2`
   was addressed by its tag `@instr2` (same version 2, digest `f7d7cd08f525`, confirmed in each start output).
2. **2026-11-15 03:45 EST. Codex model IDs confirmed** (two independent sources agree: OpenAI's model pages
   `developers.openai.com/api/docs/models/<id>.md` and the model catalog `models-manager/models.json` shipped in Codex
   CLI 0.167.0; copies in `exp/suite-hosted-models4/model-id-evidence/`):
   - Astra = **`gpt-6-astra`** ("our most capable model"; $10 in / $1 cached / $50 out per MTok; Codex default
     reasoning effort `low`);
   - Sol = **`gpt-6.1-sol`** (newest Sol; `gpt-6-sol` is listed as "previous generation"; $2 / $0.10 / $10; default
     effort `low`);
   - Luna = **`gpt-6-luna`** (no newer Luna exists; $0.10 / $0.01 / $0.50; default effort `medium`).
   Each is run at Codex's own default reasoning effort for that model, as Claude Code ran at its default effort.
3. **Codex harness: `codex_noweb-v1.0.0`** (`agents/codex_noweb/`, pushed to the org; the stock registry
   `codex-v1.0.0` was also installed, unused). The stock agent does **not** disable web search: Codex 0.167.0
   defaults `web_search` to `cached`, and with the stock `--sandbox danger-full-access` it resolves to `live`, an OpenAI
   hosted tool that the task allowlist cannot block. The variant differs from stock only in: `-c web_search="disabled"`
   on `codex exec` plus the same line in `~/.codex/config.toml`; Codex pinned to `@openai/codex@0.167.0` (what the
   stock "published at least 7 days ago" rule resolved to today); the three model IDs added to the contract's
   `choices`; the bundle name. The pushed bundle was downloaded back and is byte-identical to `agents/codex_noweb/`.
   API cost for Codex is computed from the token counts in each trace at the list prices above (the stock cost hook
   uses model-library 0.1.25, which has no GPT-6 prices); requests over 272K input tokens and cache writes are billed
   higher by OpenAI and are not separable in Codex's usage totals, so the figure is a lower bound.
4. **OpenAI-network twins pushed:** `suite/clinical-openai-v1@v1` from `dist/suite-tasks-v3-openai/` and
   `suite/vessel-openai-v1@v1` from `dist/suite-tasks-vessel-v1-openai/`. `diff -r` against the originals shows only
   the six `allowed_hosts` lines (`exp/suite-hosted-models4/twin-diff.txt`). Oracle checks: see `hosted-models4.md`.
5. **2026-11-15 03:50 EST. OpenAI secret present.** `valkyrie secret list` shows `openai-api-key` (stored by Jin;
   value never read or printed). Codex runs use `-s OPENAI_API_KEY openai-api-key`, the stock contract's variable.
   The first Codex launch (`gpt-6-astra` on the vessel twin) doubles as the check that the key and the agent work;
   it is the planned vessel attempt, not an extra one. If the key lacks credit or access to a model, that model is
   stopped and reported; no other model is substituted.
6. **Order of checks (deviation).** The vessel twin oracle (`c2a22bed-…`, started 03:44 EST, finished 03:46 EST) had
   reproduced the original rewards before any Codex run started. The clinical twin oracle (`644c08bd-…`, started 03:49:55
   EST) had **not** finished when the nine Codex clinical-twin runs were launched at 03:52:18–03:52:57 EST (vessel-twin
   Codex runs: 03:50:17 and 03:52 EST). If that oracle does not reproduce the original rewards on every task, the Codex clinical results are reported
   as unvalidated in `hosted-models4.md` and the coordinator is told before any write-up uses them. **Outcome:** the
   clinical twin oracle finished at 03:57:38 EST and all seven reward keys of all five tasks equal the original
   `hosted-oracle-instr2` values (to the 4 decimals reported there), so the Codex clinical results stand as validated.
7. **2026-11-15 04:13 EST. OpenAI rate limiting (infrastructure failure) and the relaunch rule.** The OpenAI account
   allows 1,000,000 tokens per minute per model. With all twelve Codex runs launched together (about ten tasks per
   model at once), Astra and Sol tasks hit "Rate limit reached for gpt-6-astra / gpt-6.1-sol … tokens per min (TPM):
   Limit 1000000". Codex retried five times, then ended with `turn.failed` and exit code 1. Valkyrie labels these
   failure_category "agent". They are classed as **infrastructure failures**: an API quota, not agent behaviour. The
   Astra vessel check run (`c299cbca-…`) failed this way at 08:59Z, about 8 minutes into the task. Decisions (coordinator,
   04:13 EST):
   - Nothing is stopped. Running Astra and Sol tasks finish or fail on their own.
   - Each task that failed on the rate limit gets **one relaunch**, with these rules:
     - It is a new single-task run (`run start --task-ids <task> --concurrency 1`). `run retry` is not used, so the
       original error record stays.
     - At most one active relaunch run per model at a time.
     - A model's relaunches start only after all of that model's original runs have finished.
   - Relaunches not started by 09:00 EST are dropped and reported as not run.
   - Luna is left as is unless it is also rate-limited.
   - The OpenAI tier is not raised for this round.
   - Tasks that did not error, but whose traces show rate-limit retries, are marked "ran under rate limiting" and
     reported as they are, without a relaunch.
   - Relaunch run IDs are recorded below before any relaunched result is read.
7a. **2026-11-15 05:13 EST. Astra relaunches on hold.** Reason: Astra costs about $3-13 per completed task
   at list price, and the cost of the rate-limited Astra tasks is unknown, because Codex reports usage only for a
   completed turn. The total cannot be checked against the OpenAI credit Jin has. The decision is pending with Jin
   (coordinator, 05:13 EST). No further Astra relaunch starts until his answer is relayed. If none arrives before
   09:00 EST, the Astra relaunches are dropped and reported as not run, for this reason. Astra's original runs were
   left to finish as they were.

   The hold arrived just after the Astra relauncher's first launch: `astra-vessel-r-seg-vessel` (`cf0f7587-…`)
   started at 05:13 EST, before the relauncher was paused (SIGSTOP at 05:14 EST; the process was paused, not killed).
   Times: the relaunch run's recorded start was 05:13:58 EST; the hold reached this worker at about 05:13 EST and the
   relauncher was paused at 05:14:07 EST. The coordinator's ruling (05:14 EST): `cf0f7587` is a valid preregistered
   relaunch, runs to completion and counts normally. It is the only Astra relaunch unless Jin's answer comes back
   before 09:00 EST. Otherwise the rest are "not run (budget hold)" and the paused relauncher is then killed. Sol relaunches continue as planned. Luna had no
   rate-limited failures, so it has no relaunches.
7b. **2026-11-15 05:16 EST. Schedule change** (coordinator). Reason: Jin is unavailable from about 07:00 EST. This
   was decided on his availability alone, without reference to any result.
   - No new relaunch starts after 05:45 EST, for any model. Relaunches not started by then are reported as
     "not run (schedule)".
   - Astra: no further relaunches unless the coordinator says otherwise before 05:45. The running vessel relaunch
     `cf0f7587` finishes normally.
   - Snapshot at 06:15 EST. `hosted-models4.md` and `.json` are written from everything terminal by then; anything
     still running is marked "pending at snapshot".
   - Runs that finish after the snapshot are still collected and appended as a dated addendum. The snapshot numbers
     are not changed.
   - Mechanism: at 05:45 EST the worker pauses its own Sol relauncher (SIGSTOP), and later kills it and the paused
     Astra relauncher. The relaunch running at 05:45, if any, continues to completion.
8. **Relaunch log** (one single-task run per rate-limited task, appended as each starts; its result is not read
   before it is listed here). Format: relaunch dir, run ID, original run, start time EST.
   - `sol-4a-r-reg-resect` `f6147eb4-e1f3-420f-8d8a-59272e80a81b` (orig `53a8d2c5-…`), 05:03.
   - `astra-vessel-r-seg-vessel` `cf0f7587-1eb1-445f-bfc0-d74c839d10be` (orig `c299cbca-…`), 05:13.
   - `sol-4a-r-measure-hc18` `39ab4e63-8358-4709-a3cf-68b1bae0fb03` (orig `53a8d2c5-…`), 05:32.
   - 05:45 cut-off (change 7b): Sol relauncher paused at 05:45:02 EST; no relaunch started after 05:45. Three relaunches in total (above). All other rate-limited tasks: Astra "not run (budget hold)", Sol "not run (schedule)".
