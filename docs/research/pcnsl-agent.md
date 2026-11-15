# `pcnsl_claude`: a single-attempt Claude Code harness for the PCNSL tasks

Status: local code and unit tests only. **No image has been built. Nothing has been pushed to Valkyrie, and no hosted, oracle or model run has happened.** No model or provider calls, installs or patient data were used to write this.

Files: `agents/pcnsl_claude/{contract.yaml,run_agent.py,image/Dockerfile}`, `tests/test_pcnsl_agent.py`.

## Why not the registry `claude_code-v1.0.0` agent

Its setup installs Claude Code to `~/.local/bin` and symlinks it into `/usr/local/bin`, with an apt fallback. That breaks the rule that every tool lives in a project environment. It was not run.

This harness runs the same Claude Code CLI, which keeps the "frontier agent in its native harness" justification. The differences:
- The CLI is prebuilt into the task image under `/opt/agent-env`, and nothing is installed when a task runs.
- Each task gets exactly one attempt, with a hard spending cap.
- The CLI's own exit status and usage are recorded.

## What runs

| Stage | Command | Does |
|---|---|---|
| `install_cmd` (`install_egress: []`) | `/opt/benchmark-venv/bin/python -I run_agent.py check` | Verifies only. It fails if any of these hold: `/opt/agent-env/bin/claude` is missing or resolves outside `/opt/agent-env`; a `claude` exists in `/usr/local/bin`, `/usr/bin`, `/bin` or `~/.local/bin` (including `/root/.local/bin`); the wrapper's Python is not `/opt/benchmark-venv`; `claude --version` is not the pinned version. It downloads nothing. |
| `run_cmd` | `run_agent.py run "{problem_statement_path}" --task-id … --model … --effort … --max-budget-usd … --timeout-sec …` | Starts the CLI once with `subprocess.Popen` (an argv list, so no shell), with the prompt on stdin. |

CLI argv (no secrets):

```
claude --print --output-format stream-json --verbose --model <id> --effort high \
  --max-budget-usd 5 --permission-mode bypassPermissions --bare --no-session-persistence \
  --strict-mcp-config --disallowed-tools WebFetch WebSearch
```

- **Model:** `anthropic/<id>` becomes `<id>`. Non-Anthropic or malformed ids are refused before anything starts.
- **Bounds:**
  - effort defaults to `high`;
  - budget defaults to 5 USD and the wrapper refuses values above 5;
  - `timeout_sec` defaults to 1740, refuses values above 1800, and kills the whole process group (SIGTERM, then SIGKILL after 10 s). That leaves about 60 s inside the task's 1800 s `agent_timeout` to write `run.json`.
- **Single attempt:**
  - an `attempt.lock` created with `O_EXCL` refuses a second start in the same sandbox (exit 3), and the wrapper itself never retries;
  - `install_cmd` is retried by Valkyrie (up to 3 more times, then once more in a new sandbox), which is harmless because it only checks the image;
  - whether the platform reruns `run_cmd` in a **new** sandbox depends on run and retry settings, so do not use `valkyrie run retry` for scored runs.
- **Secrets:**
  - `ANTHROPIC_API_KEY` comes from the Valkyrie secret, enters the child only through an environment allowlist, and never appears in argv, `run.json` or logs (tested);
  - the CLI's HOME and `CLAUDE_CONFIG_DIR` are a new empty temporary directory outside `final_output`, so CLI config state is never carried.
- **Logs** (`final_output: /logs/pcnsl-claude`):
  - `stream.jsonl` (the full transcript) and `stderr.log`;
  - `run.json` with the exit code, status (`exited` / `failed` / `timeout` / `rejected`), `timed_out`, elapsed time, argv, and the CLI's own `result` event fields (`subtype`, `is_error`, `num_turns`, `total_cost_usd`, `usage`, `modelUsage`, `session_id`). It is `null` when the CLI emitted none; the wrapper never invents one.
  - `run.json` is also an optional `output_artifact`.
  - On a nonzero exit the wrapper writes one `AgentError: …` / `AgentTimeout: …` line to `VALKYRIE_ERROR_PATH`, with no model output.
- **Turns:** `--max-turns` is **not** in the installed CLI's `--help` (2.1.325), so 30 turns is **not enforced**. `run.json` records `max_turns: null` and the real `num_turns`, and spending is bounded by budget and time instead.

## Image recipe (`agents/pcnsl_claude/image/Dockerfile`)

**Build:** `docker build -f agents/pcnsl_claude/image/Dockerfile -t pcnsl-agent-base agents/pcnsl_claude`

**Agent environment** (`/opt/agent-env`):
- The Node binary and npm are copied from a `node` stage (multistage).
- `@anthropic-ai/claude-code@2.1.325` is installed with `npm install --prefix /opt/agent-env --save-exact`: no `-g`, no apt, and the npm cache is deleted.
- `bin/claude` symlinks to `../node_modules/.bin/claude`.

**Task environment** (`/opt/benchmark-venv`): a venv with `numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 scikit-learn==1.5.2 nibabel==5.3.2`.
- `PATH` puts it first, and `PIP_NO_INDEX=1` is set.
- No TabPFN, checkpoints or model weights are included. Add TabPFN only in a derived image, and only after its licence and checkpoint redistribution terms are verified.

**Build-time check:** the build runs the same `run_agent.py check` as `install_cmd`, plus an import check, and fails if either fails.

**Using it:** pass the pushed image by digest to `prediction_export task --base-image IMAGE@sha256:…`. That path adds no install step and already rejects a system-Python `python3`.

**Unresolved before use:**
- `node:22.12.0-bookworm-slim` and `python:3.12.8-slim-bookworm` are mutable tags. Pin both to digests and record the built image digest.
- It is not verified that npm publishes `2.1.325`, or that its package layout matches the symlink. The build-time `--version` check fails loudly if either is wrong.
- The Python pins have not been installed together in this image, and the `nibabel` pin is untested here.
- No hashed lock files exist for npm or pip.

## Network and isolation

The agent CLI runs inside the task sandbox, so the agent stage needs the model API host.
- The task default stays `no-network`.
- A hosted Claude run must be exported with `--agent-allowed-host api.anthropic.com`, and only that host.
- The verifier stays `no-network`.
- `WebFetch` and `WebSearch` are disallowed.
- `allow_provider_tools: false` removes provider-side tools, and the docs say an allowlist removes them anyway.
- An allowlist limited to the API host means Bash or Python inside the sandbox cannot reach the public dataset or the hidden labels.

**Unproven:**
- whether Modal enforces hostname allowlists;
- whether `api.anthropic.com` alone is enough for the CLI (the wrapper sets `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING` and `DISABLE_AUTOUPDATER`);
- whether a shared CDN widens the allowlist.

Both must be proven on the hosted provider before any score is reported.

**No shared memory across tasks:**
- one sandbox per task;
- `--bare` (no CLAUDE.md discovery, auto-memory, hooks or plugins);
- `--no-session-persistence`;
- a fresh HOME per run.

**Data handling:** `stream.jsonl` holds whatever task rows the agent printed. Treat every run's carried output as patient-level data, under the same sharing decision as the task folder. Never commit it here.

## Facts vs assumptions

**Checked locally:**
- The contract parses with the pinned Valkyrie SDK `AgentContract.from_directory` (valkyrie-sdk 0.34.0). `validate_kwargs` fills effort `high`, budget `5.0` and timeout `1740`, and rejects other effort values.
- The SDK bundler packs exactly `contract.yaml`, `run_agent.py` and `image/Dockerfile`.
- The local `claude --help` (native build 2.1.325, read-only) lists `--print`, `--output-format stream-json`, `--effort`, `--max-budget-usd`, `--bare`, `--no-session-persistence`, `--strict-mcp-config`, `--disallowed-tools` and `--permission-mode bypassPermissions`. It does not list `--max-turns`.
- 16 unit tests pass with `.venv-valkyrie/bin/python -m unittest tests.test_pcnsl_agent`. Under plain `python3`, 15 run and the SDK contract test skips. The tests replace only the CLI process with a fake executable and exercise the real wrapper, covering:
  - the runtime check rejecting a missing executable, an executable resolving outside `/opt/agent-env`, a global install alongside, a version mismatch and system Python;
  - forwarding of model, effort and budget, with the prompt sent verbatim on stdin (shell metacharacters are not executed);
  - the nonzero exit code recorded and returned, with no retry;
  - a second attempt refused;
  - the timeout killing the process and being recorded, with no invented result;
  - a missing key, over-cap budget or timeout, and non-Anthropic models all refused before the CLI starts;
  - the key absent from argv and every log file;
  - the rendered contract `run_cmd` driving the wrapper end to end.

**Read from source or assumed, not observed:**
- The Tracker fills placeholders with shell-escaping (`sandbox.render_run_cmd`, source commit `1fe5c33`); the test uses plain substitution, which is equivalent for these values.
- `IS_SANDBOX=1` lets `bypassPermissions` run as root.
- `--bare` keeps the normal coding tool set.
- The stream-json `result` event field names (taken from the CLI's documented output; the fake emits them).
- Hosted allowlist enforcement.
- The npm package version and layout.

Any of these could fail on the first hosted smoke run, and that run is the next step.
