# Valkyrie: actual execution path and remaining prerequisites

Checked 2026-11-14 against official `vals-ai/valkyrie` source commit `1fe5c33d8c625540b1ea4f71e5ec159c1d813b48` and the installed CLI `2026.11.12.2` / SDK `0.34.0`. Official documentation pages were inaccessible to the web reader; the corresponding `.mdx` files and implementation were read from the public repository. No credentials were read, copied, uploaded, or validated. No account was created, infrastructure started, or paid task launched.

## Decision

**Prepare the hosted Valkyrie task package and launch sequence now; hosted execution remains pending access.** The user does not yet have organizer-provided Valkyrie, provider, or model access and explicitly requested preparation meanwhile. Do not repeatedly ask for login or claim package validation meets the execution requirement.

There is also a genuine no-Vals-account route: **local Tracker + Docker + local task folder + `oracle`**. This executes the reference solution through Valkyrie, including sandbox setup and grading. It does not require a model key or Modal account. However, this teal WSL currently has no `docker`, `podman`, or `uv` executable on the inspected PATH, no `/var/run/docker.sock`, and no checked Docker Desktop CLI integration path. Local Tracker therefore requires new infrastructure and is not the fastest currently available path. Nothing was installed or changed globally.

The installed SDK is an HTTP client for Tracker; its task archive helpers validate and package files. It is not a standalone in-process replacement for Tracker and sandbox execution. Likewise, `valkyrie tui --fake` displays sample runs, not an evaluation.

## What counts as execution

| Stage | Evidence | What it establishes |
|---|---|---|
| Task packaging | SDK validation and archive digest | Files satisfy packaging rules. |
| Local custom pilot | Our isolated runner's trace and replay | Agent behavior under our runner; not a Valkyrie run. |
| Valkyrie oracle | Tracker run ID, terminal task states, verifier rewards, logs, outputs | Actual Valkyrie orchestration and reference execution; not a frontier-model result. |
| Valkyrie frontier run | Same evidence plus exact agent/model/settings and trajectory | Actual benchmark execution against that frontier agent. |
| Hosted run | Above, from the configured hosted Tracker | Hosted platform execution; a local Tracker run must remain labeled local. |

For the demo, retain the run ID, immutable dataset version/digest, exact task IDs, agent version/digest, requested and returned model identifiers, budget/settings, reward and failure details, and output artifacts. Display authentic recorded failures, controls, and reference success. [Official run documentation](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/runs/start.mdx).

## Readiness check available now

From this repository:

```bash
.venv-valkyrie/bin/python scripts/valkyrie_preflight.py
.venv-valkyrie/bin/python scripts/valkyrie_preflight.py --tasks ./dist/workflow-v2
```

Use the final repair task directory instead of `workflow-v2` once exported. The script reports installed versions, Docker/Compose availability, credential **presence only**, and optional SDK task checks. It never reads session files, prints secrets, contacts hosted services, uploads anything, or starts jobs. Docker checks, if available, query the selected daemon read-only. A credential's presence does not prove it works; missing environment variables do not prove the organization lacks server-side secrets. The readiness report deliberately never says that an evaluation ran.

## Hosted route: prepared command sequence

These are instructions for when access exists, **not commands already executed**. Choose the actual organizer Tracker/organization if they provide one. Use the repo-local executable shown below; replace task folder, model, dataset tag, and run IDs with the recorded final values.

### 1. Authenticate and inspect shared configuration

```bash
.venv-valkyrie/bin/valkyrie login --no-browser
.venv-valkyrie/bin/valkyrie whoami
.venv-valkyrie/bin/valkyrie org list
.venv-valkyrie/bin/valkyrie provider list
```

If organizers supply a different Tracker, set `VALKYRIE_URL` for that service first. A headless access key uses `VALKYRIE_API_KEY`; it belongs to its issuing Tracker. Do not paste credentials into chat or a tracked file. An existing organization may already have provider/model credentials, so inspect before configuring duplicates. [Official authentication/configuration](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/get-started/configuration.mdx).

### 2. Connect a provider only if the organization lacks one

Hosted providers documented are **Modal and Daytona**. Docker is local-Tracker-only. For Modal, the organization stores a JSON secret with `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` and maps the provider to that secret. The command `valkyrie secret set modal-credentials` accepts the value at its prompt; then:

```bash
.venv-valkyrie/bin/valkyrie provider set modal modal-credentials
```

Use a private local input/prompt workflow for secret values. This preparation does not create or upload a credential file. Daytona instead requires its API key, API URL, and target region. [Official provider setup](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/get-started/sandbox-providers.mdx).

### 3. Publish the final task dataset

Example final destination `pcnsl/repair-eval`; the source folder below is a placeholder for the parent implementation's actual export:

```bash
.venv-valkyrie/bin/python scripts/validate_exports.py ./dist/repair-tasks ./results/repair-package-check
.venv-valkyrie/bin/valkyrie dataset push pcnsl/repair-eval ./dist/repair-tasks --tag hackathon-v1
.venv-valkyrie/bin/valkyrie dataset versions pcnsl/repair-eval
```

The push creates a versioned dataset; record the immutable revision/digest rather than relying on a moving `latest` tag. Hosted Tracker **rejects a local folder passed directly to `run start --dataset`**; push it first. Each task needs `task.toml`, `instruction.md`, `tests/test.sh`, its environment, and `solution/solve.sh` for the oracle. Only explicitly selected task artifacts belong in the upload, never the entire repo or raw 16 GB archive. [Official dataset instructions](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/benchmarks/datasets.mdx); [server enforcement](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/services/tracker/main.py).

### 4. Run the oracle first

```bash
.venv-valkyrie/bin/valkyrie run start --agent oracle \
  --dataset pcnsl/repair-eval@hackathon-v1 --provider modal \
  --slice 0:1 --concurrency 1 --connect
```

The reserved `oracle` agent runs the task's `solution/solve.sh`; it is implemented in the official [dataset oracle](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/services/tracker/src/tracker/services/datasets/oracle.py). Check verifier reward and generated artifacts, not just process completion: the current oracle command echoes the solve exit status, so a successful outer shell alone is not proof of reference correctness. This hosted smoke run still consumes sandbox resources even without a model call; it has not been launched.

### 5. Install and run a frontier agent

The official quickstart supplies a Claude Code registry agent:

```bash
.venv-valkyrie/bin/valkyrie agent install \
  https://github.com/vals-ai/public-agent-registry/tree/main/examples/claude_code-v1.0.0
.venv-valkyrie/bin/valkyrie secret set anthropic-api-key
```

The second command prompts for an **Anthropic API key**. The host Claude subscription/OAuth login is not automatically a sandbox credential. Do not copy Claude or Codex login files into bundles or assume subscription access can substitute for the documented key mapping. Confirm the actual selected registry contract and the available frontier model before running; a quickstart's model example is not evidence of today's strongest model.

```bash
.venv-valkyrie/bin/valkyrie run start --agent claude_code-v1.0.0 \
  --dataset pcnsl/repair-eval@hackathon-v1 --provider modal \
  --model anthropic/MODEL_ID \
  -s ANTHROPIC_API_KEY anthropic-api-key \
  --slice 0:1 --concurrency 1 --connect
```

`MODEL_ID` must be replaced. Reasoning settings require parameters declared in the installed agent contract; do not assume an arbitrary `-k effort high` works. The contract silently ignores undeclared kwargs. Start one task, then the matched control and held-out fixture after successful integration. [Official quickstart](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/README.md); [contract reference](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/agents/agent-contract.mdx).

### 6. Preserve platform evidence

```bash
.venv-valkyrie/bin/valkyrie run fetch RUN_ID
.venv-valkyrie/bin/valkyrie run errors RUN_ID
.venv-valkyrie/bin/valkyrie run logs RUN_ID --format jsonl
.venv-valkyrie/bin/valkyrie run results RUN_ID --path ./results/valkyrie-RUN_ID.json
```

Use distinct paths per run; retain unsuccessful attempts and distinguish infrastructure errors from model mistakes. Inspect final outputs as well as rewards. The CLI also supports TUI monitoring and fetching output artifacts; verify the installed `run --help` before choosing artifact-download commands.

## Optional local Tracker route

This is actual Valkyrie, but currently not executable on teal without installing/enabling Docker. It requires Docker with Compose, `uv`, Python 3.12 dependencies, an official source checkout, and enough disk/RAM for PostgreSQL, project service, task containers, and image builds. A local model-free oracle needs neither hosted Vals authentication nor a Modal/Daytona token. The service stack still needs locally generated bootstrap/runtime secrets; these are not external accounts.

Once an appropriate existing Docker host is available:

```bash
git clone https://github.com/vals-ai/valkyrie.git ./valkyrie-local
cd ./valkyrie-local
git checkout 1fe5c33d8c625540b1ea4f71e5ec159c1d813b48
make -C services/tracker install
export EXECUTOR_BOOTSTRAP_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
CBS_DOCKER_ENABLED=true make local-tracker
```

The source's default config uses `.local/data` and `.env`. For a Docker/oracle-only run, an empty private `.env` or an explicit config omitting external secrets avoids unrelated provider settings; verify the chosen config against the pinned version. Do not reuse production environment files. Keep the service bound to localhost. The Make target starts PostgreSQL/project service containers, migrations, executor control, and Tracker; it is not merely a Python CLI. If queued runs must survive restarts, retain a securely generated `EXECUTOR_PAYLOAD_LOCAL_KEY` as described officially.

From a second shell, with a valid task directory visible to Tracker:

```bash
VALKYRIE_URL=http://127.0.0.1:8000 \
  .venv-valkyrie/bin/valkyrie run start --agent oracle \
  --dataset ./dist/repair-tasks --provider docker \
  --slice 0:1 --concurrency 1 --connect
```

That shell command is run from **this eval repo**, not the Valkyrie source checkout. The CLI resolves the local dataset directory; Tracker must be able to read it. Source inspection confirms local-folder dataset support directly, so the task-folder route does not require deploying a separate custom benchmark HTTP service. A service-based benchmark is another supported route.

Docker-specific limitations: benchmark and agent stages must permit unrestricted `"*"` network access; stage-specific restrictions/allowlists are unsupported. Task containers cannot run Docker themselves. Therefore local Docker does not reproduce the earlier network-isolated pilot's security configuration. A local oracle's success remains valuable harness verification, but use a supported provider and explicit network policy for the intended evaluation. [Official local Tracker guide](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/self-hosting/local-tracker.mdx); [actual Make target](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/services/tracker/Makefile).

## Custom local agent support

Valkyrie accepts any agent with a CLI entry point and a `contract.yaml` declaring `install_cmd` and `run_cmd`; `run_cmd` must include `{problem_statement_path}`. It runs **inside the task sandbox**, with the agent bundle under `/bundle/NAME`, not as an arbitrary process on the host. `--agent ./my-agent` accepts a local bundle path, but it still needs Tracker/provider execution. [Official packaging guide](https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48/docs/agents/package-an-agent.mdx).

The current native Claude/Codex host logins therefore do not immediately give a credential-free Valkyrie frontier run. A custom bridge to host CLI credentials would be new infrastructure with isolation/auth implications, not a documented shortcut; do not implement it during this preparation. Use the official API-key agent or an organizer-supported agent/gateway when supplied. The reference oracle already provides a model-free framework test.

## Exact access prerequisites remaining

No immediate user action is requested while preparation continues. For the hosted frontier run, eventually obtain:

1. An active Valkyrie organization/account on the intended Tracker, with permission to publish datasets and start runs, or an appropriate headless access key.
2. A working sandbox provider configured for that organization: organizer-shared Modal/Daytona access is sufficient; a personal account is not necessarily required.
3. An allowed model credential or organizer-provided agent/gateway compatible with the selected contract, plus the actual permitted model ID and run budget.

For the alternative local oracle, only an available Docker/Compose runtime and local service setup are missing infrastructure prerequisites; no external model credential is required. Whether a local-only run is sufficient for the organizers' submission process is not established by the public repository. **Current status: packaging/preparation available; local Tracker execution not performed; hosted execution not performed.**
