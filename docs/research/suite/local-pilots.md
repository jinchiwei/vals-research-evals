# Local suite pilots: one agent attempt in bubblewrap, graded by the task's own verifier

Written 2026-11-14 by a Claude Code worker (model: Claude Opus 5.5, `claude-opus-5-5`). This is a
**local stand-in for a hosted Valkyrie run**, used while hosted access is unavailable. Every result
it writes says so (`run.json: evidence`).

Files: `scripts/run_suite_pilot.py` (CLI), `suite/pilot/{pilot,sandbox,runtime,relay}.py`,
`tests/suite/test_pilot_runner.py`.

## Launching a pilot

1. Export the family's task with `suite/core/export.py` (see `suite/README.md`) into an **absolute** path, e.g.
   `os.path.abspath('dist/suite-<family>')` (see Known pitfalls).
2. Run one model once:

```bash
cd /mnt/c/Users/jwei/arcadia/repos/vals-research-evals
~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py run dist/suite-<family>/<task-id> \
  --run-name 20261115-<family> --model claude-opus-5-5 --effort high --time-limit 2700 --budget 5
~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py summarize exp/suite-pilots/20261115-<family>
```

`--model` can be repeated (models run one after another, each once). Results go to
`exp/suite-pilots/<run-name>/<task-id>/<model>/`. `exp/` is in `.gitignore`, so traces,
workspaces and metrics are not tracked. A model directory that already exists is never
overwritten. A `STOP` file in `exp/suite-pilots/` or in the run directory stops the runner from
starting, kills a running agent (status `stopped`) and skips grading.

Supported tasks: those exported by `suite/core/export.py` (`tests/task_config.json` with schema
`suite-task-config/1`, `tests/grade.py` → `suite.core.grading`). A family with its own grader CLI is
refused with a clear error rather than graded wrongly.

Backends: Claude Code (`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`). A Codex backend
(`--backend codex`) exists but refuses to run without `--allow-codex`; it has not been run.

## What one run does

1. **Runtime.** It reads the pip pins from the task's own `environment/Dockerfile` and uses or creates
   the conda env `vals-suite-rt-<family>`: python 3.12 + pip, conda-forge with nodefaults, everything
   else via pip, like `suite/environment.yml`. A marker in the env records the pins' hash, and every
   pin is checked with `pip list`. If the Dockerfile has no pins, the runner falls back to
   `suite/requirements.txt` without pytest. The env is bound at `/opt/benchmark-venv` in both
   sandboxes, so the agent, its pipeline and the image path all match the hosted image. The grader
   runs with the same env's interpreter, at its host path.
2. **Agent sandbox** (bubblewrap): see the next section. The prompt is `instruction.md` on stdin. It
   is also placed at `/workspace/instruction.md`, as the platform does.
3. **Claude Code flags:**
   - `--print --output-format stream-json --verbose --model M --effort E --max-budget-usd B`
   - `--permission-mode bypassPermissions --no-session-persistence --strict-mcp-config --disallowed-tools WebFetch WebSearch`
   - `--safe-mode` with the local subscription login. `--bare` refuses OAuth: its auth is API key only.
   - `--bare` with `--auth api-key` (key passed in the environment, never in argv). With `--bare` the
     CLI reported only the tools `Bash, Edit, Read`. That is a smaller tool set, so do not mix the two
     modes in one comparison.
   - `--max-turns` does not exist in 2.1.325, so turns are recorded but not capped.
4. **One attempt.** There are no retries. The run is stopped at `--time-limit` (SIGTERM, then
   SIGKILL to the process group after 10 s).
5. **What is kept:**
   - the trace (`trace.jsonl`) and `agent-stderr.txt`;
   - the agent's `/workspace/output`, which is what the platform carries to the verifier;
   - a listing of everything else in `/workspace`.

   Afterwards the kept files are scanned for the login tokens (or API key), and any match is
   replaced by `[REDACTED-CREDENTIAL]`. The count is recorded.
6. **Grading.**
   - It runs `<rt-env>/bin/python -I -B <task>/tests/grade.py --tests <task>/tests --pipeline <shim> --logs … --work … --sandbox-root none`.
     That is the task's own verifier, unmodified, run outside the agent sandbox.
   - `<shim>` is a copy of the agent's pipeline under `agent/` plus a generated `run.sh`. The shim
     makes the grader's per-case `bash run.sh IN OUT` run the agent's `run.sh` inside the pipeline
     sandbox, at the hosted paths `/eval/pipeline`, `/eval/in/<case>`, `/eval/out/<case>` and
     `/eval/home/<case>`.
   - Timing, the time limit, kills, the size caps and the reward come from `suite/core` unchanged.
   - If the agent left no regular `run.sh` (or left special files), the original path is passed and
     the grader scores it exactly as hosted would (zeros, `not_run`).
   - The grader's work directory, which holds copies of the hidden inputs, is deleted afterwards.
7. **Outputs** in the model directory:
   - `reward.json` and `metrics.json`, the verifier's own files;
   - `grading/verifier-stdout.txt` and `grading/pipeline_logs/`;
   - `run.json`: task, family, tier, the agent-side and grader hashes, model requested and reported
     (from API response messages and `modelUsage`, not from the CLI's init line), effort, limits,
     the runtime env and its pins, the agent status, exit code and wall time, cost, turns, the
     tools used, the egress log and the sandbox properties.

## Isolation actually achieved

**Agent sandbox** (`bwrap`, unprivileged user namespace):
- The root is empty. Read-only binds: `/usr` (with `/bin`, `/lib`, `/lib64` and `/sbin` as
  usr-merged symlinks), `/etc`, the runtime at `/opt/benchmark-venv`, and the CLI binary at
  `/opt/agent/claude`.
- Fresh, writable `HOME=/home/agent`. With OAuth, the only file in it from the host is
  `~/.claude/.credentials.json`, bound read-only, plus a generated `.claude.json` holding
  onboarding and trust flags and the `oauthAccount` metadata.
- Writable `/workspace`, with `environment/data` bound read-only at `/workspace/data`. Private
  `/tmp`, `/proc` and `/dev`.
- New PID, IPC, UTS and cgroup namespaces.
- Not mounted: the repository, `tests/` and `solution/` of the task, `/home/jkwei` (including
  `/home/jkwei/data`), `/mnt/c`, and other projects.
- The tests try each of these from inside and get `ENOENT`.

**Agent network.** The default is `--egress proxy`:
- The sandbox gets its own network namespace with loopback only. Direct connections fail ("network unreachable").
- A small relay inside it (`relay.py`, started by system `python3`) forwards `127.0.0.1:18080` over a
  bind-mounted unix socket to a CONNECT proxy in the runner process.
- That proxy tunnels only to the task's `allowed_hosts` (`api.anthropic.com`) on port 443 and returns
  403 for anything else. Each attempt is logged in `run.json → agent.egress`.
- `HTTPS_PROXY` points the CLI at the relay. Tools that ignore the proxy variables simply have no network.
- This uses bubblewrap and the standard library only; nothing was installed system-wide.

Limits of the agent network setup:
- It is a hostname allowlist at the CONNECT layer. Anything reachable through `api.anthropic.com:443` is reachable.
- `--egress open` shares the host network instead. Use it only if the proxy breaks the CLI, and
  record that general internet was reachable (`run.json → network_note`).

**Pipeline sandbox** (grading, `bwrap --unshare-all`):
- No network at all: a new network namespace, so connections to the internet and the API both fail (tested).
- New user, PID and IPC namespaces.
- Read-only: `/usr`, `/etc` and the runtime; the pipeline at `/eval/pipeline`; its own case input
  only; the agent's `/workspace/output` and the public `/workspace/data`. The hosted verifier image
  contains both of the last two.
- Writable: its own output and home.
- Not mounted: `tests/` (hidden references, other cases, specialist outputs), the repository and user files (tested).

**Not achieved vs hosted:**
- **No uid switch.** As non-root, the pipeline cannot drop to uid 65534. It runs as the invoking uid
  inside a user namespace, and isolation is by mount namespace instead.
- **No CPU or RAM caps** on the agent or the pipeline (the hosted task declares cpus and memory_mb).
  Per-case wall time is measured on this shared 16-core machine and includes the few tens of
  milliseconds bubblewrap takes to start.
- **Bigger toolset.** The host `/usr` has far more tools than `python:3.12-slim` (git, compilers, curl).
- **Different filesystem.** The agent runs on a Linux tmp directory (ext4), not a container overlay.

## Known pitfalls

- **Export with an absolute output path.** `export_task(spec, 'dist/...')` with a relative path
  leaves `tests/specialist/<case>/` **empty**, without any error. `run_specialist` passes a
  relative output path to `runner.run_pipeline`, which runs the specialist with `cwd` set to a
  temporary home, so its files land elsewhere. The grader then scores the specialist 0, and
  `vs_specialist` becomes meaningless. Use `os.path.abspath(...)`. The `suite/README.md` example
  uses a relative path. The bug is in `suite/core/export.py` (not owned by this runner).
- **Login token.** The sandbox gets the host login read-only and has no route to the OAuth refresh
  host. The runner therefore refuses to start if the access token expires before
  `time limit + 5 min`. A refresh inside the sandbox could rotate the host's refresh token. The
  host's own Claude Code session refreshes the token when it next needs it; wait for that.
- **Sandbox failures.** If the pipeline sandbox fails to start (a log line beginning `bwrap:`),
  `run.json → grading.infrastructure_error` is true. The zeros in that run are not the agent's
  score. The summary table shows `infra_error`.

## Smoke run, 2026-11-14 (toy task, synthetic, no medical data)

Settings: `claude-opus-5-5`, effort high, 900 s limit, 3 USD cap, egress proxy, OAuth login
(`--safe-mode`). Directory: `exp/suite-pilots/20261114-toy-smoke/toy-sphere-volume-0001/claude-opus-5-5/`.

**Run:**
- Exit 0, status `completed`, `subtype success`.
- Agent wall time 30.6 s, 5 turns, 4 Bash calls, cost 0.159 USD.
- Model reported by the API: `claude-opus-5-5`.
- Egress: one CONNECT, to `api.anthropic.com:443`. Nothing was denied and no credential strings were found in the kept files.
- Tools offered under `--safe-mode` were the full default set, including Task, Workflow, Cron* and
  Write. Under `--bare` only Bash, Edit and Read were offered.

**Rewards:** all seven keys are 1.0. On each of the 3 hidden cases: Dice 1.0, 0.27 s, inside the sandbox.

**What it revealed:**
- That export was made with a relative path, so its specialist value is 0. That is the export
  bug above, not a property of the agent.
- Regrading the same pipeline against an absolute-path export of the same seeds (grading only,
  no model call) gives all 1.0 again, with specialist quality 0.982 and specialist clinically
  acceptable 1.0.
- The trace showed no sandbox or instruction problem. The agent read `/workspace/data`, used
  `python3` from `/opt/benchmark-venv`, checked its pipeline on the development cases and wrote
  diagnostics to `visible_predictions/`.
- The toy task is a plumbing check and is easy by design.

## Tests

```bash
~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite/test_pilot_runner.py -q
```

A fake agent script stands in for the CLI. The tests cover:
- hidden references, `tests/`, `solution/`, the repository, `$HOME`, `~/.claude.json`, `/home/jkwei/data` and `/mnt/c` are unreadable from the agent sandbox;
- direct egress fails and a non-allowlisted CONNECT gets 403;
- `/workspace/data` is read-only and `python3` resolves to `/opt/benchmark-venv/bin/python3`;
- a pipeline left by the fake agent (the toy oracle) gets exactly the reward of direct `grade.py` grading (all 1.0);
- an agent that leaves nothing scores all zeros;
- the pipeline sandbox has no network and cannot see the reference, `tests/` or the repository, sees only its own case under `/eval/in`, and runs at `/eval/pipeline` with cwd `/eval/home/<case>`;
- an existing run directory is not overwritten;
- the STOP file and the Codex guard work;
- the summary table is correct.
