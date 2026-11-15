# First hosted Valkyrie runs: toy smoke task (oracle and Claude Code)

Written 2026-11-14 by a Claude Code worker (model: Claude Opus 5.5, `claude-opus-5-5`), acting as
platform operator. Four steps were authorised; all four succeeded on the first attempt. There were no
relaunches and no changes to the task. The only platform state created is: benchmark `suite-scratch`,
dataset `suite-scratch/toy-smoke` version 1 (tags `latest`, `smoke1`), agent `claude_code-v1.0.0`, and two runs.
Nothing was deleted, no secret was read or changed, and no provider was changed.

Evidence files are under `exp/suite-hosted-smoke/` (git-ignored). No secret values appeared in any
command output or fetched file. A scan for `sk-ant-…` found nothing. The only matches were the
variable name `ANTHROPIC_API_KEY` (`apiKeySource`) and the secret's storage path
`valkyrie/tenants/<org-id>/modal-credentials`, which is a name, not a value.

## Summary

| Step | Result | Key evidence |
|---|---|---|
| 1. Push toy task | Done | `suite-scratch/toy-smoke@1`, 1 task, 623,281 bytes uploaded, digest `269a4572c144` |
| 2. Oracle run | Done, reward as expected | run `1ff5a572-99f5-4623-9062-397e992201ca`; all seven keys 1.0; verifier mode `separate` |
| 3. Install agent | Done | `claude_code-v1.0.0`; the installed bundle is byte-identical to registry commit `3e47c50` |
| 4. Claude Code run | Done | run `cea5e542-b160-4971-8119-0a9443d82663`; reward 1.0; 4 turns; 15.6 s of agent time; $0.0454 API cost (from the trace) |

## Preparation (local, no platform state)

`dist/suite-tasks/toy/toy-sphere-volume-0001` was a complete export, written 18:22 and populated
under `tests/specialist/<case>/` (3 cases plus `runtime.json`). I copied it twice:

- `exp/suite-hosted-smoke/orig/` is a pristine reference copy;
- `exp/suite-hosted-smoke/tasks/` is the copy that was pushed.

`diff -r` of the two copies is empty at the end, so **no task changes were made**. I did not export
the task myself and did not touch `suite/`.

```
$ .venv-valkyrie/bin/python -I exp/suite-platform-probe/check_taskconfig.py exp/suite-hosted-smoke/tasks
toy-sphere-volume-0001 problems [] separate True agent allowlist ['api.anthropic.com'] 2700.0 verifier no-network 435.0 env 2.0 4096 None None {'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'PIP_NO_INDEX': '1'} artifacts ['/workspace/output']
$ .venv-valkyrie/bin/python scripts/validate_exports.py exp/suite-hosted-smoke/tasks exp/suite-hosted-smoke/validation
Validated and packed 1 tasks; no uploads performed.      # archive_sha256 7c2e602b…3142
```

- **Transient failure.** The first `validate_exports.py` call failed with
  `OSError: [Errno 12] Cannot allocate memory` inside `pack_task`. teal had about 2.4 GB of memory
  available at the time. A retry, with nothing changed, passed.
- **Local grader dry run.** I ran the copy's `tests/grade.py` on `solution/pipeline` with
  `--sandbox-root none` and the vals-suite env. It gave all seven keys = 1.0.

## Step 1: push

```
$ .venv-valkyrie/bin/valkyrie dataset push suite-scratch/toy-smoke exp/suite-hosted-smoke/tasks --tag smoke1 --concurrency 1
✓ Created benchmark suite-scratch
✓ Created dataset suite-scratch/toy-smoke
✓ Uploaded toy-sphere-volume-0001 (623,281 bytes)
✓ Published suite-scratch/toy-smoke@1: 1 task(s), 1 uploaded. Tags: latest, smoke1.
$ .venv-valkyrie/bin/valkyrie dataset versions suite-scratch/toy-smoke
1        269a4572c144  1      latest, smoke1  2026-11-14 18:31:02 EST
```

- **Time.** 14.7 s of wall time.
- **Privacy.** Neither `dataset show` nor `dataset create` has a visibility or public field. The
  benchmark was created inside the active organisation (`hackathon-neuronetwork-b91c517178`).
  Organisation scoping is therefore what the CLI exposes. I did not verify from outside the
  organisation that it is invisible there.

## Step 2: oracle

```
$ .venv-valkyrie/bin/valkyrie run start --agent oracle --dataset suite-scratch/toy-smoke@smoke1 --provider modal --concurrency 1 -l hosted-smoke-oracle
│ Run ID:           1ff5a572-99f5-4623-9062-397e992201ca
│ Dataset version:  suite-scratch/toy-smoke@1
│ Spend:            development · default · new_benchmark_generation
$ valkyrie run logs 1ff5a572-…
23:33:29Z Running agent oracle
23:33:30Z solve.sh exited with 0
23:33:39Z Starting a separate verifier for toy-sphere-volume-0001
23:33:42Z Running the verifier for toy-sphere-volume-0001
23:33:45Z Verifier rewards …: {"clinically_acceptable": 1.0, "quality": 1.0, "ran": 1.0, "reward": 1.0, "valid": 1.0, "vs_specialist": 1.0, "within_time": 1.0}
```

From `run task … --format json` (`exp/suite-hosted-smoke/oracle/task.json`):

- **Rewards.** `reward_source /logs/verifier/reward.json`, `verifier_exit_code 0`,
  `verifier_environment_mode "separate"`. All seven keys are 1.0, which matches the expected oracle value.
- **Per-case verifier stdout.** Quality 1.0 and 0.44 s for each of the 3 hidden cases. The runtime
  ratio against the specialist was 1.19, but the specialist time was measured on the export host.
- **Time breakdown.**
  - `sandbox_build_duration` was 34.4 s. This was the first-ever build of the image, and it
    succeeded with no fixes.
  - `agent_run_duration` was 0.21 s.
  - `evaluation_run_duration` was 42.1 s. This includes creating the separate verifier sandbox.
  - `sandbox_run_duration` was 51.2 s.
- **Wall time.** The task ran from 23:32:20 to 23:34:15 (115 s). The run was marked finished at
  23:34:46, and its final score was 100.0.
- **Carried artifact.** `toy-sphere-volume-0001/artifacts/workspace/output.tar.gz` (1,267 B).
- **Logs.**
  - The CLI fetches them with `run logs`, `run task` and `run artifacts`.
  - Server side, they are in AWS us-east-1, log group
    `/valkyrie/benchmarks-prod/tenants/a76dcee0-65ac-412f-ba9b-29f0f416f170`, with 365-day retention,
    and in bucket `valkyrie-629807611108-prod-80646c7ee8e9f413`.
- **Platform details.** Executor `git-06cbc4f8bcb4-136bf000429fbfee`, protocol 7.
- **Resources granted.** Not visible. No field reports the CPU or RAM actually granted. The task
  requested 2 CPU and 4096 MB for both the agent and the verifier.
- **Cost.** No Modal or other cost is reported. `run results` and `run fetch` contain no cost field.

## Step 3: install the agent

```
$ .venv-valkyrie/bin/valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/examples/claude_code-v1.0.0
✓ Agent 'claude_code-v1.0.0' installed successfully!
$ valkyrie agent list
claude_code-v1.0.0  2026-11-14 18:38:39 EST
```

- **What the install did.** Install only registers the bundle with the Tracker; it runs nothing.
  `setup.sh` runs later, inside each task sandbox.
- **Verification.** `agent download` into `exp/suite-hosted-smoke/agent-download/` gave
  `contract.yaml`, `setup.sh` and `collect_outputs.py`. All three are byte-identical (`cmp`) to
  `public-agent-registry@3e47c5065e26f02631c43c6e37d79dee06a20824`.
- **Agent name.** Use `claude_code-v1.0.0`.

## Step 4: Claude Code on the toy task

### Model id

- **Registry agent.** The contract's `model` is a free string (default
  `anthropic/claude-sonnet-4-20250514`). `collect_outputs.py` strips `anthropic/` and sets
  `ANTHROPIC_MODEL`.
- **Anthropic API.** `claude-sonnet-5-5` is the current Sonnet. The list price is $2 per million
  input tokens and $10 per million output tokens, with cache reads at $0.10 (claude-api reference,
  cached 2026-11-03).
- **Valkyrie.** It accepted `anthropic/claude-sonnet-5-5` without complaint. The API responses
  report `"model": "claude-sonnet-5-5"`.

```
$ .venv-valkyrie/bin/valkyrie run start --agent claude_code-v1.0.0 --dataset suite-scratch/toy-smoke@smoke1 --provider modal \
    --model anthropic/claude-sonnet-5-5 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 1 -l hosted-smoke-claude-sonnet
│ Run ID:           cea5e542-b160-4971-8119-0a9443d82663
```

### Rewards and timing

**Run and task identifiers.**
- Run: `cea5e542-b160-4971-8119-0a9443d82663`.
- Task: `toy-sphere-volume-0001`, task row `1e5e42a1-817a-406d-a851-898c4673a9b3`.
- Oracle task row, for comparison: `238d1642-da63-443d-9a8c-f3bc3c6ab17c`.

**reward.json** (verifier mode `separate`, exit 0):

```json
{"reward": 1.0, "ran": 1.0, "valid": 1.0, "within_time": 1.0, "clinically_acceptable": 1.0,
 "quality": 0.9996921842083616, "vs_specialist": 1.0}
```

- **Per hidden case.** Quality was 0.9998, 0.9997 and 0.9996. Times were 0.51, 0.55 and 0.50 s.
- **Time breakdown.**
  - `sandbox_build_duration` was 0.48 s: the image built for the oracle run was reused.
  - `agent_run_duration` was 15.6 s.
  - `evaluation_run_duration` was 39.9 s.
  - `sandbox_run_duration` was 68.2 s.
- **Wall time.** The task ran from 23:39:18 to 23:40:51 (93 s). The run finished at 23:41:21.
- **Agent install inside the sandbox.**
  - `setup.sh` took about 4 s, from 23:39:48 to 23:39:51.6.
  - It installed Claude Code native build 2.1.325.
  - The log shows no apt step, so `curl` and `python3` were already found.

### Trace

The trace is in `exp/suite-hosted-smoke/agent-run/outputs/toy-sphere-volume-0001/agent_output/logs/`
(`trajectory.jsonl`, `summary.json`, `metrics_total.json`).

**Result event.** `success`, `num_turns` 4, `duration_ms` 15216, `duration_api_ms` 13360.

**Tokens and cost.** From `modelUsage` for `claude-sonnet-5-5`:

| Field | Value |
|---|---|
| inputTokens | 8 |
| cacheCreationInputTokens | 8,652 |
| cacheReadInputTokens | 72,594 |
| outputTokens | 1,649 |
| thinkingTokens | 0 |
| webSearchRequests | 0 |
| `total_cost_usd` (`costBasis: list`) | **$0.0453954** |

This dollar figure is Claude Code's own list-price calculation. It is not an Anthropic invoice, and
Valkyrie reports no cost of its own.

**What the agent did.** It made three Bash calls:

1. It read `/workspace/data`.
2. It wrote `pipeline/run.sh` and `seg.py` (Gaussian smoothing, then Otsu thresholding, then the
   largest connected component). The test failed with `ModuleNotFoundError: No module named 'numpy'`.
3. It found `/opt/benchmark-venv/bin/python3`, re-ran with that directory first on `PATH`, and got
   Dice 0.9996 and 0.9989 on the two development cases.

**Model API reachability.** Proven: four API turns succeeded from the sandbox.

**Anything else reachable?** Not tested by this run. The agent made no non-API network attempt:
- no `curl`, pip or http strings in the trajectory;
- zero WebSearch and WebFetch calls;
- no blocked attempt in the logs.

So the allowlist is **configured** (the task sets `[agent] allowlist ["api.anthropic.com"]`, and the
contract has `egress_allowlist []` and `allow_provider_tools false`), but its **enforcement was not
observed**.

**Tools offered.** The init event lists the full default Claude Code tool set, including `WebFetch`,
`WebSearch`, `Task` and `Workflow`, with `permissionMode default` and the registry's `--allowedTools`.

## Findings that matter for real tasks

1. **`python3` in the agent's shell is not the benchmark venv.**
   - The contract's `run_cmd` is `bash -lc '…'`. A login shell on Debian sources `/etc/profile`,
     which resets `PATH` and drops the Dockerfile's `ENV PATH=/opt/benchmark-venv/bin:$PATH`. This
     is an inference; what the trace shows is that bare `python3` had no numpy while
     `/opt/benchmark-venv/bin/python3` existed.
   - `instruction.md` says "`python3` on PATH = `/opt/benchmark-venv`". That is false inside the
     registry agent's shell.
   - The pipeline still scored, because the grader runs it with
     `pipeline_path /opt/benchmark-venv/bin:…`. A weaker model may waste turns or pip-install
     packages, which fails offline.
   - Fix it in the exporter, not by hand here. Either state the absolute interpreter path in
     `instruction.md`, or add a `/etc/profile.d/` snippet in the Dockerfile that puts
     `/opt/benchmark-venv/bin` first on `PATH`. Either change needs one hosted oracle and agent
     check.
2. **WebSearch is not blocked by an `api.anthropic.com` allowlist.** The registry agent allows
   `WebSearch`, which is an Anthropic server-side tool reached through `api.anthropic.com`.
   Valkyrie's `allow_provider_tools false` cannot strip a tool that the CLI itself declares. This is
   an inference, not observed: the agent made zero searches. For the no-internet rule, use a bundle
   that passes `--disallowedTools WebFetch WebSearch`, as the local pilots do, or check
   `server_tool_use.web_search_requests` in every trace.
3. **The registry agent has no turn or budget cap**, and its tool set includes `Task` and
   `Workflow`. Keep `--concurrency 1` and a tight `[agent] timeout_sec` for pilots.
4. **Image cache.** The oracle run built the image in 34 s, and the agent run reused it (0.5 s).
   The verifier's own sandbox start-up dominates evaluation time, at about 40 s per task.

## Platform unknowns from platform-brief.md now settled

| Unknown | Now |
|---|---|
| Login acts for the organisation; Modal configured and default | Yes. `whoami` shows the organisation; `provider list` shows `* modal → modal-credentials`; runs record `sandbox_provider: modal`. |
| Hosted Tracker supports the separate verifier | Yes. `verifier_environment_mode: "separate"` and the log line "Starting a separate verifier". |
| Artifact carry of `/workspace/output` | Works. The verifier graded the carried pipeline. |
| reward.json with 7 flat keys | Accepted. `reward_source /logs/verifier/reward.json`; the score is mean `reward` × 100. |
| First image build (`python:3.12-slim` and the pinned imaging stack) | Builds on Modal in 34 s and is cached for later runs. No size-limit problem at this size. The image-size limit itself is still unknown. |
| 623 KB task upload | Fine. The hosted per-task upload limit is still unknown. |
| Registry agent install in a no-network task | Works. `setup.sh` reached claude.ai at install time, consistent with install egress `*`. |
| Model id format | `anthropic/claude-sonnet-5-5` is accepted by Valkyrie and works with the registry agent. |
| Model API reachable under the agent allowlist | Yes. |
| Allowlist **blocks** other hosts | **Not settled.** No attempt was made. It needs the oracle egress probe from brief §5 step 6, which was not authorised here. |
| Verifier `no-network` enforced | Not settled. Nothing in the verifier tried the network. |
| Resources actually granted (CPU/RAM) | Not visible through the CLI. |
| GPU availability | Not tested (CPU-only task). |
| Costs | API dollars come from the agent trace only. **Modal cost is not reported anywhere** in `run fetch`, `run results`, `run task` or `run status`. |
| Files under `/logs/verifier` beyond reward and stdout | Not settled. `run artifacts` lists only the workspace artifact, `agent_output.tar.gz`, the agent zip and a run summary JSON. `metrics.json` was not listed. |

## Cost of these four steps

- **Model API: $0.0454** (Claude Code `total_cost_usd`, list basis, one run).
- **Modal: not reported.**
  - Estimate (labelled as such): about 5 sandbox-minutes at 2 CPU and 4 GiB, plus one 34 s image
    build. At Modal list rates (about $0.047 per physical-core-hour and $0.008 per GiB-hour) that is
    on the order of $0.01. The true figure needs the Modal dashboard.
  - Not obtainable from here: actual Modal billing, and whether the hackathon credits apply.
- **Platform fees:** none shown.

## What a real-data task run should do differently

- **Data.** Do not push UCSF patient data at all (AGENTS.md); push public or de-identified datasets
  only. Datasets are organisation-scoped, but Vals AI operators and the owner of the Modal workspace
  can read the archives.
- **Instruction and image.** Fix the `python3` and `PATH` mismatch (finding 1) in the exporter
  before the first real-family run. Then re-run that family's oracle once.
- **Network.** Before trusting no-internet claims, run the oracle egress probe: `solve.sh` curls
  `pypi.org` and `api.anthropic.com` and records both exit codes. Also use an agent bundle without
  WebSearch and WebFetch, or audit `server_tool_use`.
- **Time and memory.** Expect a cold image build per task (each task has its own `environment/data`
  layer) and about 40 s of verifier start-up per task. Set `memory_mb` explicitly for 3D data, and
  keep `build_timeout_sec` generous for large wheels.
- **Cost.** Record cost from each trace's `modelUsage`, and get Modal spend from the Modal dashboard,
  because Valkyrie does not report it.
- **Monitoring.** The `run tasks` text output uses upper-case statuses (`FINISHED`), which matters
  for polling scripts.
