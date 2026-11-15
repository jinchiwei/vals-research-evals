# Hosted model runs 4: Claude Fable 5.2 and three Codex models on the headline suite

Written 2026-11-15 by a Claude Code worker for the coordinator (model: **Claude Opus 5.5, `claude-opus-5-5`**).
Binding document: [`round4-prereg.md`](round4-prereg.md). Its "Changes after registration" section lists every
deviation, with times. Machine-readable values: [`hosted-models4.json`](hosted-models4.json). Raw evidence is in
`exp/suite-hosted-models4/` (git-ignored).

**Snapshot 06:15 EST** (rendered 06:22; every run in this report was terminal by 05:47 EST). Prereg change 7b set this cut-off because Jin is unavailable from about 07:00 EST.
- Every number below is from attempts that were terminal at the snapshot.
- Anything still running is marked "pending at snapshot".
- Later results go in the dated addendum at the end, and the snapshot numbers are not changed.

## Summary

- **Fable 5.2 (16 attempts, all graded, no infrastructure failure).**
  - Fetal head shows a gap in 3 of 3 attempts, as it did for Opus and Sonnet: 77, 74 and 67 of 83 images, while the
    specialist passes 83.
  - Registration and spleen show no gap in any attempt (0 of 3 each). Fable is the best Claude model on both, with
    mean reward 0.444 and 0.389 (Opus: 0.333 and 0.222).
  - ECG misses the MI operating point once (MI sensitivity 0.693 against a 0.70 bar), the same near-threshold miss
    Opus had.
  - ICU passes 3 of 3 (control holds). Vessel: 5/8, no gap shown, equal to Opus.
- **Fable still stops early.**
  - All 15 clinical attempts ended on their own, using 3–69 % of the session; vessel used 76 %.
  - Two fetal head attempts stopped below their own measured bar and said they were out of time when they were not.
    One said "I ran out of session time before diagnosing this" at 27 % of the session.
- **Codex results depend on the OpenAI account's rate limit.**
  - With the 12 Codex runs launched together, Astra and Sol hit the limit of 1M tokens per minute per model.
  - 9 Astra and 8 Sol tasks died on it. These are infrastructure failures (prereg change 7) and are not scored.
  - Astra has no scored registration or fetal head attempt. Sol has none for fetal head and one for registration: its
    4a relaunch, which ran alone with 0 rate-limit events, scored reward 0.833 (5/6 under 2 mm, mean TRE 1.89 mm,
    no gap). That is the best registration attempt of any model in rounds 3–4; Opus's best was 0.667.
  - Several Astra and Sol tasks that finished also show rate-limit retries ("ran under rate limiting").
  - **The OpenAI quota ran out at about 05:46 EST.** Three relaunches started:
    - Sol 4a registration finished and is graded.
    - Astra vessel (`cf0f7587`) and Sol 4a fetal head (`39ab4e63`) both ended at 05:46:40–05:46:53 with "Quota
      exceeded. Check your plan and billing details." They are infrastructure failures and not scored.
- **Luna (gpt-6-luna) never hit the limit, and all 16 attempts are graded.**
  - Gap in 3 of 3 attempts on registration, spleen, fetal head and ECG. Vessel: gap (2/8). ICU passes 3 of 3.
  - It is the weakest of the four round-4 models on every per-case task.
- **Astra and Sol where graded.**
  - ECG and ICU pass every attempt.
  - Spleen: Astra 0 of 3 attempts with a gap, Sol 2 of 3.
  - Vessel: Sol 6/8, the best vessel result of any model, with no gap shown.
  - Both used far more of the session than the Claude models (spleen 85–97 %).
- **Web.** No Fable trace offered or used a web tool. Every Codex trace has 0 `web_search` items, because web
  search was disabled in the harness, and no network-like commands.
- **API cost of graded and failed attempts (list price).**
  - Fable: $16.85.
  - OpenAI, completed tasks only: Astra $60.29, Sol $10.31,
    Luna $0.95.
  - Tasks that died on the rate limit or the session limit report no usage, so the OpenAI figures are a lower bound.
    The account's billing page has the real total.

## Design and what changed

**Fable** ran exactly as in round 3:
- dataset `suite/clinical-v1@instr2` (version 2, digest `f7d7cd08f525`) and `suite/vessel-v1@v1` (version 1);
- agent `claude_code_noweb-v1.0.0` (Claude Code 2.1.325, `--disallowedTools "WebFetch WebSearch"`, $8 cap);
- Modal, at the default effort;
- model `anthropic/claude-fable-5-2`. The ID was confirmed by the first run (prereg change 1).

```
valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/clinical-v1@instr2 --provider modal \
  --model anthropic/claude-fable-5-2 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 3 -l hosted-models4<a|b|c>-fable
(vessel: --dataset suite/vessel-v1@v1 --concurrency 1 -l hosted-models4-fable-vessel)
```

**Codex** used the agent `codex_noweb-v1.0.0` (`agents/codex_noweb/`, prereg change 3).
- It is the registry `codex-v1.0.0` with web search disabled (`-c web_search="disabled"` and
  `~/.codex/config.toml`). The stock agent does not disable it: Codex 0.167.0 defaults to `cached` search, and
  `--sandbox danger-full-access` turns that into `live`.
- Codex is pinned to 0.167.0, and every trace reports `codex-cli 0.167.0`.
- Each model runs at Codex's own default reasoning effort: Astra `low`, Sol `low`, Luna `medium`.
- Model IDs: `gpt-6-astra`, `gpt-6.1-sol` and `gpt-6-luna`, confirmed from OpenAI's model pages and Codex's model
  catalog (prereg change 2).
- **Harness difference.** Codex results come from a different harness (Codex CLI, not Claude Code), with its own tools,
  prompts and effort defaults. They are compared with the Claude models only side by side and never pooled.

```
valkyrie run start --agent codex_noweb-v1.0.0 --dataset suite/clinical-openai-v1@v1 --provider modal \
  --model <gpt-6-astra|gpt-6.1-sol|gpt-6-luna> -s OPENAI_API_KEY openai-api-key --concurrency 3 -l hosted-models4<a|b|c>-<m>
(vessel: --dataset suite/vessel-openai-v1@v1 --concurrency 1 -l hosted-models4-<m>-vessel)
```

**OpenAI-network twins** (prereg change 4).
- `dist/suite-tasks-v3-openai/` and `dist/suite-tasks-vessel-v1-openai/` are byte copies of the originals, except that
  `allowed_hosts` is `["api.openai.com"]`.
- `diff -r` shows only those six lines (`exp/suite-hosted-models4/twin-diff.txt`).
- The twin oracles reproduce the original oracle rewards on every task and key:
  - clinical `644c08bd-…`: reg 0.6667, spleen 0, hc18 0.759, ECG 0, ICU 1.0, plus quality and vs_specialist to 4 dp;
  - vessel `c2a22bed-…`: 0.75, quality 0.8374, vs_specialist 1.0.
- The Codex clinical runs started before the clinical oracle had finished. That order is recorded in prereg change 6.

**Rate limiting, relaunches, holds and the schedule** (prereg changes 7, 7a, 7b and 8).
- **Rate limit.** All 12 Codex runs started together at 03:50–03:52 EST. Astra and Sol then exceeded OpenAI's limit of
  1M tokens per minute per model. Codex retried 5 times, then ended with `turn.failed` and exit 1, which Valkyrie
  records as an "agent" failure.
- **Classification.** These are classed as infrastructure failures. Each gets one relaunch: a single-task run at
  concurrency 1, one per model at a time, started only after that model's original runs had finished.
- **Astra hold.** At 05:13 EST Astra relaunches were put on hold for budget reasons. One Astra relaunch, the vessel
  task `cf0f7587-…`, had started at 05:13:58 and counts normally.
- **Schedule.** No relaunch started after 05:45 EST. A rate-limited task without a relaunch is "not run (budget hold)"
  for Astra or "not run (schedule)" for Sol.
- **Quota exhausted.** At about 05:46 EST the OpenAI account ran out of quota ("Quota exceeded. Check your plan and
  billing details."). The two relaunches still running then, Astra vessel and Sol 4a fetal head, failed on it.

**Collection and regrade** follow `hosted-agents3.md` (`fetch_task.sh`, `regrade_one.sh` and the pilot's bubblewrap
no-network grading path).
- Vessel uses the regrade and gap code in `exp/seg_vessel/analyse.py`, with output redirected here.
- Regrade agreement:
  - reward, ran, valid, within_time and clinically_acceptable match the hosted grade in every graded attempt except
    Luna 4a fetal head;
  - 9 attempts differ only in quality and vs_specialist, by 1e-6 to 2e-3. These pipelines have no fixed seeds or
    use multithreaded inference.
  - In Luna 4a fetal head, 7 of 83 images did not run or exceeded the per-case limit on teal's slower, shared CPU, so the
    local reward is 0. On the hosted grade every image ran, with reward 0.843.
  - For that attempt, the raw MAE uses the 76 images with a local value.
- The hosted grade decides. Raw values in physical units come from the regrade.
- Agent time is the agent process time. For a task killed at the session limit, it is Valkyrie's
  `agent_run_duration`.
- Session used = agent time / the task's limit (reg, hc18 and ICU 2,700 s; spleen and vessel 3,600 s; ECG 1,800 s).

**Gap rule** (DESIGN.md, as in `hosted-agents3.md`).
- Per-case tasks use a 95 % paired bootstrap of per-case pass, agent minus specialist, on the cases the specialist
  passes:
  - "gap" means the interval excludes 0;
  - "no gap shown" means the agent failed some of those cases, but the interval includes 0;
  - "no gap" means the agent failed none.
- Cohort tasks: "gap" means the agent misses a gate part that the specialist meets.

## Runs

| Attempt dir | Model | Dataset | Run id | Label | Started (EST) | State at snapshot |
|---|---|---|---|---|---|---|
| fable-4a | claude-fable-5-2 | suite/clinical-v1@2 | `00116bcf-f7e3-4da9-8d29-7cabeca09f58` | R1 (hosted-models4a-fable) | 03:31 | terminal |
| fable-4b | claude-fable-5-2 | suite/clinical-v1@2 | `d2b413c6-9095-489e-8925-76129132af98` | R2 (hosted-models4b-fable) | 03:31 | terminal |
| fable-4c | claude-fable-5-2 | suite/clinical-v1@2 | `9ff6ff83-1d5f-4268-9d4e-353e48e7ac33` | R3 (hosted-models4c-fable) | 03:31 | terminal |
| fable-vessel | claude-fable-5-2 | suite/vessel-v1@1 | `f59ed1c7-bc77-48d1-8a79-e7ea56eed649` | V1 (hosted-models4-fable-vessel) | 03:29 | terminal |
| astra-vessel | gpt-6-astra | suite/vessel-openai-v1@1 | `c299cbca-ca1b-42a7-9987-de1bcd14f140` | hosted-models4-astra-vessel | 03:50 | terminal |
| astra-4a | gpt-6-astra | suite/clinical-openai-v1@1 | `22f34a74-c95c-44e7-9637-b0af38251086` | hosted-models4a-astra | 03:52 | terminal |
| sol-4a | gpt-6.1-sol | suite/clinical-openai-v1@1 | `53a8d2c5-5c34-4927-82cc-0e65a2bdd2f6` | hosted-models4a-sol | 03:52 | terminal |
| luna-4a | gpt-6-luna | suite/clinical-openai-v1@1 | `a98af7c8-3a19-4518-af16-bdba9f979b40` | hosted-models4a-luna | 03:52 | terminal |
| sol-vessel | gpt-6.1-sol | suite/vessel-openai-v1@1 | `484fea83-7193-4309-ada5-9c872ddafbd7` | hosted-models4-sol-vessel | 03:52 | terminal |
| luna-vessel | gpt-6-luna | suite/vessel-openai-v1@1 | `75a56b4e-2418-4c76-960b-b4e5a1d547d2` | hosted-models4-luna-vessel | 03:52 | terminal |
| astra-4b | gpt-6-astra | suite/clinical-openai-v1@1 | `57cfd94d-c7a1-4caa-84c2-c1e59181b5d7` | hosted-models4b-astra | 03:52 | terminal |
| sol-4b | gpt-6.1-sol | suite/clinical-openai-v1@1 | `04a63778-6710-4c57-886e-858caf9cf8ff` | hosted-models4b-sol | 03:52 | terminal |
| luna-4b | gpt-6-luna | suite/clinical-openai-v1@1 | `cffb941f-1d37-4ba3-88d6-4d9787f6262d` | hosted-models4b-luna | 03:52 | terminal |
| astra-4c | gpt-6-astra | suite/clinical-openai-v1@1 | `bdc5d418-12c5-4887-95dd-2293908798a6` | hosted-models4c-astra | 03:52 | terminal |
| sol-4c | gpt-6.1-sol | suite/clinical-openai-v1@1 | `e1f27d93-42d6-4fec-8b2b-9e9f3be23c99` | hosted-models4c-sol | 03:52 | terminal |
| luna-4c | gpt-6-luna | suite/clinical-openai-v1@1 | `2c84b465-478f-45e4-bb4b-eabf97c7e358` | hosted-models4c-luna | 03:52 | terminal |
| sol-4a-r-reg-resect | gpt-6.1-sol | suite/clinical-openai-v1@1 | `f6147eb4-e1f3-420f-8d8a-59272e80a81b` | relaunch of 53a8d2c5-5c34-4927-82cc-0e65a2bdd2f6 | 05:03 | terminal |
| astra-vessel-r-seg-vessel | gpt-6-astra | suite/vessel-openai-v1@1 | `cf0f7587-1eb1-445f-bfc0-d74c839d10be` | relaunch of c299cbca-ca1b-42a7-9987-de1bcd14f140 | 05:13 | terminal |
| sol-4a-r-measure-hc18 | gpt-6.1-sol | suite/clinical-openai-v1@1 | `39ab4e63-8358-4709-a3cf-68b1bae0fb03` | relaunch of 53a8d2c5-5c34-4927-82cc-0e65a2bdd2f6 | 05:32 | terminal |

Oracle checks on the twins: clinical `644c08bd-463f-415b-a6c1-85bb4e9487ab`, vessel `c2a22bed-8442-4010-a4ef-bcd9e6366b33` (both FINISHED, rewards equal to the originals).

## Per-attempt results

- Rewards are the hosted grades.
- The headline is the raw value from the local regrade.
- Slots 4a, 4b and 4c are attempts R1–R3, the three full runs. Vessel has one attempt.
- Rows marked "infra failure (rate limit)" are not scored. Their relaunch, if any, appears in the row below. A
  relaunch marked "infra failure (OpenAI quota exhausted)" is not scored either.

| Task | Model | Slot | reward | ran | valid | within_time | clinically_acceptable | quality | vs_specialist | Headline (raw, local regrade) | Agent time | Session used | API cost | Gap | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reg | claude-fable-5-2 | 4a | 0.333 | 1 | 1 | 1 | 0.333 | 0.312 | 0.941 | 2/6 < 2 mm; mean TRE 2.47 mm | 934 s | 35 % | $1.07 | no gap shown |  |
| reg | claude-fable-5-2 | 4b | 0.500 | 1 | 1 | 1 | 0.500 | 0.336 | 1.000 | 3/6 < 2 mm; mean TRE 2.34 mm | 1024 s | 38 % | $1.00 | no gap shown |  |
| reg | claude-fable-5-2 | 4c | 0.500 | 1 | 1 | 1 | 0.500 | 0.307 | 0.926 | 3/6 < 2 mm; mean TRE 3.47 mm | 990 s | 37 % | $1.07 | no gap shown |  |
| spleen | claude-fable-5-2 | 4a | 0.167 | 1 | 1 | 1 | 0.167 | 0.923 | 0.983 | 1/6; Dice 0.923; abs vol err 6.1 % | 2490 s | 69 % | $2.34 | no gap shown |  |
| spleen | claude-fable-5-2 | 4b | 0.333 | 1 | 1 | 1 | 0.333 | 0.928 | 0.988 | 2/6; Dice 0.928; abs vol err 6.7 % | 2134 s | 59 % | $1.67 | no gap shown |  |
| spleen | claude-fable-5-2 | 4c | 0.667 | 1 | 1 | 1 | 0.667 | 0.943 | 1.000 | 4/6; Dice 0.943; abs vol err 3.3 % | 2174 s | 60 % | $1.45 | no gap |  |
| hc18 | claude-fable-5-2 | 4a | 0.928 | 1 | 1 | 1 | 0.928 | 0.620 | 0.865 | 77/83; MAE 3.8 mm (median 2.0) | 726 s | 27 % | $1.22 | gap |  |
| hc18 | claude-fable-5-2 | 4b | 0.892 | 1 | 1 | 1 | 0.892 | 0.615 | 0.858 | 74/83; MAE 4.4 mm (median 2.2) | 752 s | 28 % | $0.92 | gap |  |
| hc18 | claude-fable-5-2 | 4c | 0.807 | 1 | 1 | 1 | 0.807 | 0.565 | 0.788 | 67/83; MAE 11.1 mm (median 2.0) | 1006 s | 37 % | $0.91 | gap |  |
| ecg | claude-fable-5-2 | 4a | 0.000 | 1 | 1 | 1 | 0.000 | 0.939 | 0.956 | gate 2/3; AUROC 0.902; MI sens 0.693; ECE 0.026; gap 0.024 | 1006 s | 56 % | $0.97 | gap |  |
| ecg | claude-fable-5-2 | 4b | 1.000 | 1 | 1 | 1 | 1.000 | 0.963 | 0.980 | gate 3/3; AUROC 0.912; MI sens 0.724; ECE 0.026; gap 0.027 | 1094 s | 61 % | $0.94 | no gap |  |
| ecg | claude-fable-5-2 | 4c | 1.000 | 1 | 1 | 1 | 1.000 | 0.973 | 0.990 | gate 3/3; AUROC 0.916; MI sens 0.732; ECE 0.029; gap 0.027 | 776 s | 43 % | $0.56 | no gap |  |
| icu | claude-fable-5-2 | 4a | 1.000 | 1 | 1 | 1 | 1.000 | 0.751 | 1.000 | gate 4/4; AUROC 0.875; slope 1.05; NB 0.072 | 96 s | 4 % | $0.51 | no gap |  |
| icu | claude-fable-5-2 | 4b | 1.000 | 1 | 1 | 1 | 1.000 | 0.743 | 0.998 | gate 4/4; AUROC 0.872; slope 1.02; NB 0.069 | 119 s | 4 % | $0.43 | no gap |  |
| icu | claude-fable-5-2 | 4c | 1.000 | 1 | 1 | 1 | 1.000 | 0.750 | 1.000 | gate 4/4; AUROC 0.875; slope 1.04; NB 0.072 | 80 s | 3 % | $0.49 | no gap |  |
| vessel | claude-fable-5-2 | vessel | 0.625 | 1 | 1 | 1 | 0.625 | 0.831 | 0.993 | 5/8; Dice 0.831; clDice 0.858 | 2741 s | 76 % | $1.29 | no gap shown |  |
| reg | gpt-6-astra | 4a | – | – | – | – | – | – | – | – | 560 s | 21 % | – | – | infra failure (rate limit) |
| reg | gpt-6-astra | 4b | – | – | – | – | – | – | – | – | 1037 s | 38 % | – | – | infra failure (rate limit) |
| reg | gpt-6-astra | 4c | – | – | – | – | – | – | – | – | 356 s | 13 % | – | – | infra failure (rate limit) |
| spleen | gpt-6-astra | 4a | 0.333 | 1 | 1 | 1 | 0.333 | 0.929 | 0.990 | 2/6; Dice 0.929; abs vol err 7.0 % | 3064 s | 85 % | $9.39 | no gap shown |  |
| spleen | gpt-6-astra | 4b | 0.333 | 1 | 1 | 1 | 0.333 | 0.901 | 0.960 | 2/6; Dice 0.902; abs vol err 11.9 % | 3480 s | 97 % | $12.87 | no gap shown |  |
| spleen | gpt-6-astra | 4c | 0.167 | 1 | 1 | 1 | 0.167 | 0.775 | 0.825 | 1/6; Dice 0.775; abs vol err 19.1 % | 3412 s | 95 % | $12.80 | no gap shown | ran under rate limiting (3 events) |
| hc18 | gpt-6-astra | 4a | – | – | – | – | – | – | – | – | 393 s | 15 % | – | – | infra failure (rate limit) |
| hc18 | gpt-6-astra | 4b | – | – | – | – | – | – | – | – | 777 s | 29 % | – | – | infra failure (rate limit) |
| hc18 | gpt-6-astra | 4c | – | – | – | – | – | – | – | – | 652 s | 24 % | – | – | infra failure (rate limit) |
| ecg | gpt-6-astra | 4a | 1.000 | 1 | 1 | 1 | 1.000 | 0.983 | 1.000 | gate 3/3; AUROC 0.921; MI sens 0.740; ECE 0.027; gap 0.029 | 1435 s | 80 % | $2.92 | no gap | ran under rate limiting (8 events) |
| ecg | gpt-6-astra | 4b | 1.000 | 1 | 1 | 1 | 1.000 | 0.966 | 0.984 | gate 3/3; AUROC 0.914; MI sens 0.728; ECE 0.033; gap 0.032 | 1529 s | 85 % | $3.62 | no gap | ran under rate limiting (15 events) |
| ecg | gpt-6-astra | 4c | 1.000 | 1 | 1 | 1 | 1.000 | 0.986 | 1.000 | gate 3/3; AUROC 0.922; MI sens 0.756; ECE 0.028; gap 0.026 | 1730 s | 96 % | $6.15 | no gap | ran under rate limiting (6 events) |
| icu | gpt-6-astra | 4a | 1.000 | 1 | 1 | 1 | 1.000 | 0.745 | 0.999 | gate 4/4; AUROC 0.872; slope 0.99; NB 0.073 | 949 s | 35 % | $4.39 | no gap | ran under rate limiting (26 events) |
| icu | gpt-6-astra | 4b | 1.000 | 1 | 1 | 1 | 1.000 | 0.748 | 1.000 | gate 4/4; AUROC 0.874; slope 1.02; NB 0.071 | 1776 s | 66 % | $8.16 | no gap | ran under rate limiting (11 events) |
| icu | gpt-6-astra | 4c | – | – | – | – | – | – | – | – | 857 s | 32 % | – | – | infra failure (rate limit) |
| vessel | gpt-6-astra | vessel | – | – | – | – | – | – | – | – | 464 s | 13 % | – | – | infra failure (rate limit) |
| vessel | gpt-6-astra | vessel | – | – | – | – | – | – | – | – | 1902 s | 53 % | – | – | infra failure (OpenAI quota exhausted); relaunch |
| reg | gpt-6.1-sol | 4a | – | – | – | – | – | – | – | – | 228 s | 8 % | – | – | infra failure (rate limit) |
| reg | gpt-6.1-sol | 4a | 0.833 | 1 | 1 | 1 | 0.833 | 0.414 | 1.000 | 5/6 < 2 mm; mean TRE 1.89 mm | 1457 s | 54 % | $1.41 | no gap | relaunch |
| reg | gpt-6.1-sol | 4b | – | – | – | – | – | – | – | – | 199 s | 7 % | – | – | infra failure (rate limit) |
| reg | gpt-6.1-sol | 4c | – | – | – | – | – | – | – | – | 299 s | 11 % | – | – | infra failure (rate limit) |
| spleen | gpt-6.1-sol | 4a | 0.000 | 1 | 1 | 1 | 0.000 | 0.897 | 0.956 | 0/6; Dice 0.897; abs vol err 13.4 % | 3451 s | 96 % | $2.34 | gap |  |
| spleen | gpt-6.1-sol | 4b | 0.333 | 1 | 1 | 1 | 0.333 | 0.925 | 0.986 | 2/6; Dice 0.925; abs vol err 6.8 % | 3116 s | 87 % | $1.18 | no gap shown |  |
| spleen | gpt-6.1-sol | 4c | 0.167 | 1 | 1 | 1 | 0.167 | 0.900 | 0.959 | 1/6; Dice 0.900; abs vol err 14.3 % | 3225 s | 90 % | $1.27 | gap |  |
| hc18 | gpt-6.1-sol | 4a | – | – | – | – | – | – | – | – | 519 s | 19 % | – | – | infra failure (rate limit) |
| hc18 | gpt-6.1-sol | 4a | – | – | – | – | – | – | – | – | 814 s | 30 % | – | – | infra failure (OpenAI quota exhausted); relaunch |
| hc18 | gpt-6.1-sol | 4b | – | – | – | – | – | – | – | – | 656 s | 24 % | – | – | infra failure (rate limit) |
| hc18 | gpt-6.1-sol | 4c | – | – | – | – | – | – | – | – | 407 s | 15 % | – | – | infra failure (rate limit) |
| ecg | gpt-6.1-sol | 4a | – | – | – | – | – | – | – | – | 539 s | 30 % | – | – | infra failure (rate limit) |
| ecg | gpt-6.1-sol | 4b | 1.000 | 1 | 1 | 1 | 1.000 | 0.991 | 1.000 | gate 3/3; AUROC 0.924; MI sens 0.744; ECE 0.028; gap 0.036 | 1439 s | 80 % | $0.63 | no gap | ran under rate limiting (1 events) |
| ecg | gpt-6.1-sol | 4c | 1.000 | 1 | 1 | 1 | 1.000 | 1.000 | 1.000 | gate 3/3; AUROC 0.928; MI sens 0.756; ECE 0.030; gap 0.029 | 709 s | 39 % | $0.50 | no gap | ran under rate limiting (27 events) |
| icu | gpt-6.1-sol | 4a | 1.000 | 1 | 1 | 1 | 1.000 | 0.745 | 1.000 | gate 4/4; AUROC 0.873; slope 1.06; NB 0.069 | 1102 s | 41 % | $0.67 | no gap | ran under rate limiting (12 events) |
| icu | gpt-6.1-sol | 4b | – | – | – | – | – | – | – | – | 860 s | 32 % | – | – | infra failure (rate limit) |
| icu | gpt-6.1-sol | 4c | 1.000 | 1 | 1 | 1 | 1.000 | 0.740 | 0.994 | gate 4/4; AUROC 0.870; slope 0.99; NB 0.072 | 800 s | 30 % | $0.59 | no gap | ran under rate limiting (1 events) |
| vessel | gpt-6.1-sol | vessel | 0.750 | 1 | 1 | 1 | 0.750 | 0.821 | 0.981 | 6/8; Dice 0.821; clDice 0.870 | 3552 s | 99 % | $1.72 | no gap shown | ran under rate limiting (9 events) |
| reg | gpt-6-luna | 4a | 0.167 | 1 | 1 | 1 | 0.167 | 0.207 | 0.626 | 1/6 < 2 mm; mean TRE 3.43 mm | 1145 s | 42 % | $0.07 | gap |  |
| reg | gpt-6-luna | 4b | 0.167 | 1 | 1 | 1 | 0.167 | 0.254 | 0.766 | 1/6 < 2 mm; mean TRE 3.13 mm | 502 s | 19 % | $0.05 | gap |  |
| reg | gpt-6-luna | 4c | 0.000 | 1 | 1 | 1 | 0.000 | 0.234 | 0.707 | 0/6 < 2 mm; mean TRE 3.25 mm | 1335 s | 49 % | $0.13 | gap |  |
| spleen | gpt-6-luna | 4a | 0.000 | 1 | 1 | 1 | 0.000 | 0.842 | 0.897 | 0/6; Dice 0.842; abs vol err 13.2 % | 1353 s | 38 % | $0.06 | gap |  |
| spleen | gpt-6-luna | 4b | 0.000 | 1 | 1 | 1 | 0.000 | 0.515 | 0.548 | 0/6; Dice 0.515; abs vol err 36.7 % | 3600 s | 100 % | – | gap | stopped at the session limit (TIMEOUT) |
| spleen | gpt-6-luna | 4c | 0.000 | 1 | 1 | 1 | 0.000 | 0.875 | 0.932 | 0/6; Dice 0.875; abs vol err 15.8 % | 2947 s | 82 % | $0.09 | gap |  |
| hc18 | gpt-6-luna | 4a | 0.843 | 1 | 1 | 1 | 0.843 | 0.502 | 0.701 | 70/83; MAE 9.4 mm (median 2.9) | 1609 s | 60 % | $0.10 | gap |  |
| hc18 | gpt-6-luna | 4b | 0.807 | 1 | 1 | 1 | 0.807 | 0.511 | 0.712 | 67/83; MAE 12.8 mm (median 2.6) | 919 s | 34 % | $0.10 | gap |  |
| hc18 | gpt-6-luna | 4c | 0.578 | 1 | 1 | 1 | 0.578 | 0.261 | 0.364 | 48/83; MAE 16.7 mm (median 6.4) | 1465 s | 54 % | $0.12 | gap |  |
| ecg | gpt-6-luna | 4a | 0.000 | 1 | 1 | 1 | 0.000 | 0.956 | 0.973 | gate 2/3; AUROC 0.909; MI sens 0.681; ECE 0.032; gap 0.034 | 262 s | 15 % | $0.01 | gap |  |
| ecg | gpt-6-luna | 4b | 0.000 | 1 | 1 | 1 | 0.000 | 0.899 | 0.915 | gate 2/3; AUROC 0.885; MI sens 0.610; ECE 0.033; gap 0.035 | 1098 s | 61 % | $0.04 | gap |  |
| ecg | gpt-6-luna | 4c | 0.000 | 1 | 1 | 1 | 0.000 | 0.939 | 0.956 | gate 2/3; AUROC 0.902; MI sens 0.630; ECE 0.032; gap 0.033 | 494 s | 27 % | $0.02 | gap |  |
| icu | gpt-6-luna | 4a | 1.000 | 1 | 1 | 1 | 1.000 | 0.718 | 0.964 | gate 4/4; AUROC 0.859; slope 1.06; NB 0.066 | 314 s | 12 % | $0.02 | no gap |  |
| icu | gpt-6-luna | 4b | 1.000 | 1 | 1 | 1 | 1.000 | 0.729 | 0.979 | gate 4/4; AUROC 0.864; slope 1.02; NB 0.067 | 455 s | 17 % | $0.02 | no gap |  |
| icu | gpt-6-luna | 4c | 1.000 | 1 | 1 | 1 | 1.000 | 0.734 | 0.986 | gate 4/4; AUROC 0.867; slope 1.06; NB 0.068 | 312 s | 12 % | $0.03 | no gap |  |
| vessel | gpt-6-luna | vessel | 0.250 | 1 | 1 | 1 | 0.250 | 0.810 | 0.967 | 2/8; Dice 0.810; clDice 0.832 | 2783 s | 77 % | $0.10 | gap |  |

Specialist on the same hidden cases:
- reg: 4/6, mean TRE 3.03 mm;
- spleen: 3/6, Dice 0.939;
- hc18: 83/83, MAE 2.05 mm;
- ECG: all 3 gate parts (MI sensitivity 0.744);
- ICU: all 4 parts;
- vessel: 6/8, Dice 0.837, clDice 0.855.

## Per task and model: gap shown in k of n

n counts graded attempts only. "Not run" lists slots lost to the rate limit with no graded relaunch.

| Task | Model | Rewards | Mean | Range | Gap shown in | Session used | API cost | Not run |
|---|---|---|---|---|---|---|---|---|
| reg | claude-fable-5-2 | 0.333, 0.500, 0.500 | 0.444 | 0.333–0.500 | 0 of 3 | 35 %, 38 %, 37 % | $3.15 | – |
| spleen | claude-fable-5-2 | 0.167, 0.333, 0.667 | 0.389 | 0.167–0.667 | 0 of 3 | 69 %, 59 %, 60 % | $5.45 | – |
| hc18 | claude-fable-5-2 | 0.928, 0.892, 0.807 | 0.876 | 0.807–0.928 | 3 of 3 | 27 %, 28 %, 37 % | $3.05 | – |
| ecg | claude-fable-5-2 | 0.000, 1.000, 1.000 | 0.667 | 0.000–1.000 | 1 of 3 | 56 %, 61 %, 43 % | $2.47 | – |
| icu | claude-fable-5-2 | 1.000, 1.000, 1.000 | 1.000 | 1.000–1.000 | 0 of 3 | 4 %, 4 %, 3 % | $1.43 | – |
| vessel | claude-fable-5-2 | 0.625 | 0.625 | 0.625–0.625 | 0 of 1 | 76 % | $1.29 | – |
| reg | gpt-6-astra | – | – | – | 0 of 0 | – | $0.00 | 4a, 4b, 4c |
| spleen | gpt-6-astra | 0.333, 0.333, 0.167 | 0.278 | 0.167–0.333 | 0 of 3 | 85 %, 97 %, 95 % | $35.06 | – |
| hc18 | gpt-6-astra | – | – | – | 0 of 0 | – | $0.00 | 4a, 4b, 4c |
| ecg | gpt-6-astra | 1.000, 1.000, 1.000 | 1.000 | 1.000–1.000 | 0 of 3 | 80 %, 85 %, 96 % | $12.69 | – |
| icu | gpt-6-astra | 1.000, 1.000 | 1.000 | 1.000–1.000 | 0 of 2 | 35 %, 66 % | $12.55 | 4c |
| vessel | gpt-6-astra | – | – | – | 0 of 0 | – | $0.00 | vessel |
| reg | gpt-6.1-sol | 0.833 | 0.833 | 0.833–0.833 | 0 of 1 | 54 % | $1.41 | 4b, 4c |
| spleen | gpt-6.1-sol | 0.000, 0.333, 0.167 | 0.167 | 0.000–0.333 | 2 of 3 | 96 %, 87 %, 90 % | $4.79 | – |
| hc18 | gpt-6.1-sol | – | – | – | 0 of 0 | – | $0.00 | 4a, 4b, 4c |
| ecg | gpt-6.1-sol | 1.000, 1.000 | 1.000 | 1.000–1.000 | 0 of 2 | 80 %, 39 % | $1.13 | 4a |
| icu | gpt-6.1-sol | 1.000, 1.000 | 1.000 | 1.000–1.000 | 0 of 2 | 41 %, 30 % | $1.26 | 4b |
| vessel | gpt-6.1-sol | 0.750 | 0.750 | 0.750–0.750 | 0 of 1 | 99 % | $1.72 | – |
| reg | gpt-6-luna | 0.167, 0.167, 0.000 | 0.111 | 0.000–0.167 | 3 of 3 | 42 %, 19 %, 49 % | $0.25 | – |
| spleen | gpt-6-luna | 0.000, 0.000, 0.000 | 0.000 | 0.000–0.000 | 3 of 3 | 38 %, 100 %, 82 % | $0.15 | – |
| hc18 | gpt-6-luna | 0.843, 0.807, 0.578 | 0.743 | 0.578–0.843 | 3 of 3 | 60 %, 34 %, 54 % | $0.32 | – |
| ecg | gpt-6-luna | 0.000, 0.000, 0.000 | 0.000 | 0.000–0.000 | 3 of 3 | 15 %, 61 %, 27 % | $0.06 | – |
| icu | gpt-6-luna | 1.000, 1.000, 1.000 | 1.000 | 1.000–1.000 | 0 of 3 | 12 %, 17 %, 12 % | $0.07 | – |
| vessel | gpt-6-luna | 0.250 | 0.250 | 0.250–0.250 | 1 of 1 | 77 % | $0.10 | – |

## Comparison with Opus 5.5 and Sonnet 5.5

- The Opus and Sonnet clinical values are the three pooled attempts in [`hosted-agents3.json`](hosted-agents3.json).
- Their vessel values are the single attempts in [`seg_vessel.md`](seg_vessel.md).
- Each cell shows mean reward and "gap shown in k of n".
- **The Codex models ran in a different harness** (Codex CLI 0.167.0 at its default effort, not Claude Code). Their
  columns are side-by-side observations, not a like-for-like model comparison.
- Astra and Sol also carry the rate-limit confound described below.

| Task | Opus 5.5 | Sonnet 5.5 | Fable 5.2 | Astra | Sol | Luna |
|---|---|---|---|---|---|---|
| reg | 0.333; gap 1 of 3 | 0.056; gap 3 of 3 | 0.444; gap 0 of 3 | – (3 not run) | 0.833; gap 0 of 1 (2 not run) | 0.111; gap 3 of 3 |
| spleen | 0.222; gap 1 of 3 | 0.111; gap 1 of 3 | 0.389; gap 0 of 3 | 0.278; gap 0 of 3 | 0.167; gap 2 of 3 | 0.000; gap 3 of 3 |
| hc18 | 0.651; gap 3 of 3 | 0.839; gap 3 of 3 | 0.876; gap 3 of 3 | – (3 not run) | – (3 not run) | 0.743; gap 3 of 3 |
| ecg | 0.667; gap 1 of 3 | 1.000; gap 0 of 3 | 0.667; gap 1 of 3 | 1.000; gap 0 of 3 | 1.000; gap 0 of 2 (1 not run) | 0.000; gap 3 of 3 |
| icu | 1.000; gap 0 of 3 | 1.000; gap 0 of 3 | 1.000; gap 0 of 3 | 1.000; gap 0 of 2 (1 not run) | 1.000; gap 0 of 2 (1 not run) | 1.000; gap 0 of 3 |
| vessel | 0.625; gap 0 of 1 | 0.500; gap 0 of 1 | 0.625; gap 0 of 1 | – (1 not run) | 0.750; gap 0 of 1 | 0.250; gap 1 of 1 |

**Reading.**
- **Fetal head is still the stable gap.** Every graded fetal head attempt of every model shows it: Fable 3/3, Luna 3/3,
  and earlier Opus 3/3 and Sonnet 3/3. Astra and Sol have no graded fetal head attempt in the snapshot, because the
  rate limit stopped every one.
- **Fable is the strongest Claude model on registration and spleen.** No attempt shows a gap there. It still passes
  only 1, 2 and 4 of 6 spleen cases.
- **Luna fails on the per-case tasks.** It shows a gap in every attempt on registration, spleen, fetal head and vessel.
  It also misses the ECG MI operating point in 3 of 3 attempts.
- **Astra and Sol match or beat the Claude models where graded.**
  - ECG and ICU pass every attempt.
  - Sol's single graded registration attempt passes 5 of 6 cases.
  - Sol's vessel attempt passes 6 of 8 images, against 5 for Fable and Opus.
  - Spleen is mixed: Sol shows a gap in 2 of 3 attempts.

## Rate-limit confound

These Astra and Sol tasks finished, but their traces contain OpenAI rate-limit retries. Each retry episode stalls the
agent for up to about 10 s and costs it session time. They are reported as they are and marked "ran under rate
limiting".

| Model | Task | Slot | Rate-limit events in trace | Reward | Session used |
|---|---|---|---|---|---|
| gpt-6-astra | ecg_ptbxl | 4a | 8 | 1.000 | 80 % |
| gpt-6-astra | ecg_ptbxl | 4b | 15 | 1.000 | 85 % |
| gpt-6-astra | ecg_ptbxl | 4c | 6 | 1.000 | 96 % |
| gpt-6-astra | risk_icu | 4a | 26 | 1.000 | 35 % |
| gpt-6-astra | risk_icu | 4b | 11 | 1.000 | 66 % |
| gpt-6-astra | seg_spleen | 4c | 3 | 0.167 | 95 % |
| gpt-6.1-sol | ecg_ptbxl | 4b | 1 | 1.000 | 80 % |
| gpt-6.1-sol | ecg_ptbxl | 4c | 27 | 1.000 | 39 % |
| gpt-6.1-sol | risk_icu | 4a | 12 | 1.000 | 41 % |
| gpt-6.1-sol | risk_icu | 4c | 1 | 1.000 | 30 % |
| gpt-6.1-sol | seg_vessel | vessel | 9 | 0.750 | 99 % |

Astra/Sol tasks that finished with **no** rate-limit retries in the trace: gpt-6-astra seg_spleen 4a, gpt-6.1-sol reg_resect 4a, gpt-6.1-sol seg_spleen 4a, gpt-6-astra seg_spleen 4b, gpt-6.1-sol seg_spleen 4b, gpt-6.1-sol seg_spleen 4c.

## Trace notes

All 16 Fable traces and every Codex trace were read: `exp/suite-hosted-models4/<dir>/trace-<task>.txt`, with
summaries in `trace-<task>.json`. Codex traces show the agent's progress messages. Fable's thinking is omitted by the
API, so its traces contain only a few text messages.

**Web use.**
- *Fable.* The `init` event offers no WebFetch or WebSearch, and every trace has 0 web requests. The one `ToolSearch`
  call (vessel) loaded `Monitor`.
- *Codex.* Every trace has 0 `web_search` items, and no command reached for the network.
  - The only network errors are Codex's own model-catalog refresh ("failed to refresh available models:
    Connection failed"), which the allowlist blocks.
  - This web check was made on the first Astra trace and the first completed Luna trace before any Codex result was
    read.

**Claude Fable 5.2**
- **Early stopping below the bar, with false time pressure (fetal head).**
  - 4a stopped at 27 % of the session with a cross-validated 89.5 % against the 90 % bar: "I ran out of session time
    before diagnosing this."
  - 4c stopped at 37 % with 76 %: "I ran out of session time before I could improve it further."
  - 4b stopped at 28 % with 88 % ("falls just short of the 90 % bar") and made no time claim.
  - On the hidden set: 77, 74 and 67 of 83 images (the specialist passes 83).
- **Registration** (35–38 % of the session).
  - Each attempt reported its own shortfall and stopped: 4a "two of four cases meet the 2 mm target"; 4b "does not
    reliably meet the 2 mm target … Expect a partial score on the hidden cases".
  - Hidden: 2, 3 and 3 of 6, with no gap shown each time.
- **Spleen** (59–69 %). It flagged the uncertainty itself: "I have no honest estimate that hidden scans will clear the
  Dice ≥ 0.94 bar" (4b). Hidden: 1, 2 and 4 of 6.
- **Vessel** (76 %). Ended with 14 minutes left: "I did not retrain on all 20 images because there was no time left to
  validate it." Hidden: 5/8.
- **ECG 4a.** It passed every gate part on its own fold (MI sensitivity 75.5 %) but scored 0.693 on the hidden set,
  against a 0.70 bar. This is the same near-threshold miss as Opus R3.
- **ICU.** Finished in 80–119 s and passes every gate part.

**gpt-6-astra (Codex)**
- **Long sessions.** The completed tasks used most of the session: spleen 85–97 %, ECG 80–96 %, ICU 35–66 %. Astra
  tracked the clock explicitly: "The current pace still leaves time for refinement training and all eight end-to-end
  tests before the session limit" (4c spleen).
- **No early stopping below its own bar.** Every completed attempt reported passing its development gates before
  ending.
- **Spleen: over-optimistic validation.**
  - 4c reported "Two-case development holdout Dice: 0.968 / 0.943" and "All 8 development cases passed … clinical
    thresholds".
  - Hidden: 1/6, Dice 0.775.
- **Failure mode: the rate limit** (prereg change 7).
  - Nine tasks died with `turn.failed` 13–38 % into the session: vessel; reg and hc18 in all three runs; 4c ICU.
  - The vessel relaunch `cf0f7587` ran alone for 32 minutes (28 progress messages, 0 rate-limit events). It ended
    when the OpenAI quota ran out: `turn.failed`, "Quota exceeded. Check your plan and billing details."

**gpt-6.1-sol (Codex)**
- **Long sessions.**
  - Spleen used 87–96 % of the session and vessel 99 %. The vessel attempt changed plan near the end: "I'm dropping
    that candidate and using the remaining time to fit the validated compact-model recipe on all 20 images."
  - ECG and ICU used 30–80 %, passing every gate.
- **Spleen: training-case accuracy given as evidence.**
  - 4c said "Final-model mean Dice was 0.970 on training cases"; 4b reported held-out Dice 0.960 and 0.957.
  - Hidden: 0, 2 and 1 of 6, a gap in 2 of 3 attempts.
- **Failure mode: the rate limit.**
  - Eight tasks died 7–32 % into the session: reg and hc18 in all three runs; 4a ECG; 4b ICU.
  - Two relaunches started before the 05:45 cut-off:
    - 4a registration (`f6147eb4`) finished and is graded;
    - 4a fetal head (`39ab4e63`) died on the exhausted quota at 05:46:53.

**gpt-6-luna (Codex)**
- **Early stopping below its own measured bar, without claiming time pressure.**
  - 4c hc18 stopped at 54 % of the session: "This does not meet the 90% target".
  - 4a hc18 (60 %): "slightly below the 90% target".
  - 4a reg (42 %): "one case remains above the 2 mm target".
  - 4c reg (49 %): "two remain above the 2 mm target".
- **ECG: an optimistic single-fold estimate.**
  - On its held-out fold 8, it reported MI sensitivity 76 %, 72.4 % and 75.1 %.
  - Hidden: 0.681, 0.610 and 0.630, all below the 0.70 bar.
- **Spleen.**
  - 4c reported training-case results ("These are training-case results.").
  - 4b hit the 3,600 s session limit and was stopped (Valkyrie `TIMEOUT`), with hidden Dice 0.515.
  - All three attempts passed 0/6.
- **Cost.** Luna is the cheapest model by far, $0.01–0.13 per task.

## Cost

List-price API cost of the attempts above:
- Fable $16.85. The round-4 Anthropic stop was $80.
- OpenAI, completed tasks only: Astra $60.29, Sol $10.31,
  Luna $0.95.

Codex reports token usage only when a turn completes. Rate-limited tasks that died, and Luna 4b spleen (stopped at the
session limit), therefore add unmeasured OpenAI spend. Modal cost is not shown by Valkyrie.

## Pending at snapshot

- None.

Rate-limited attempts with no graded result (not scored; prereg changes 7, 7a and 7b):

- gpt-6-astra reg_resect 4a: rate-limited in the original run; not run (budget hold) (`22f34a74-…`).
- gpt-6-astra measure_hc18 4a: rate-limited in the original run; not run (budget hold) (`22f34a74-…`).
- gpt-6.1-sol measure_hc18 4a: rate-limited in the original run; relaunched but failed: OpenAI quota exhausted (`39ab4e63-…`).
- gpt-6.1-sol ecg_ptbxl 4a: rate-limited in the original run; not run (schedule) (`53a8d2c5-…`).
- gpt-6-astra reg_resect 4b: rate-limited in the original run; not run (budget hold) (`57cfd94d-…`).
- gpt-6-astra measure_hc18 4b: rate-limited in the original run; not run (budget hold) (`57cfd94d-…`).
- gpt-6.1-sol reg_resect 4b: rate-limited in the original run; not run (schedule) (`04a63778-…`).
- gpt-6.1-sol measure_hc18 4b: rate-limited in the original run; not run (schedule) (`04a63778-…`).
- gpt-6.1-sol risk_icu 4b: rate-limited in the original run; not run (schedule) (`04a63778-…`).
- gpt-6-astra reg_resect 4c: rate-limited in the original run; not run (budget hold) (`bdc5d418-…`).
- gpt-6-astra measure_hc18 4c: rate-limited in the original run; not run (budget hold) (`bdc5d418-…`).
- gpt-6-astra risk_icu 4c: rate-limited in the original run; not run (budget hold) (`bdc5d418-…`).
- gpt-6.1-sol reg_resect 4c: rate-limited in the original run; not run (schedule) (`e1f27d93-…`).
- gpt-6.1-sol measure_hc18 4c: rate-limited in the original run; not run (schedule) (`e1f27d93-…`).
- gpt-6-astra seg_vessel vessel: rate-limited in the original run; relaunched but failed: OpenAI quota exhausted (`cf0f7587-…`).
