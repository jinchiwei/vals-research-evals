# Platform brief: Valkyrie and Harbor for timed medical-imaging tasks

Written 2026-11-14 by a Claude Code worker (model: Claude Opus 5.5, `claude-opus-5-5`).
Nothing was uploaded, launched, installed, logged in or configured. The only files written are this
brief and scratch files under `exp/suite-platform-probe/`.

## Evidence base and tags

Every platform claim carries one of three tags.

- **PROVEN**: seen in a command output on teal or in a result file in this repository. The file is cited.
- **DOCUMENTED**: stated in official documentation or implemented in official source. The URL or the
  pinned source path is cited. Source behaviour is what the code at that commit does. The hosted
  Tracker may run a different version, so DOCUMENTED is not the same as observed on the hosted service.
- **UNKNOWN**: not established by anything I could read or run.

Sources read:

| Source | Version |
|---|---|
| Valkyrie source and docs (`vals-ai/valkyrie`), local checkout `/tmp/valkyrie-inspect-20261114` | commit `1fe5c33d8c625540b1ea4f71e5ec159c1d813b48` (2026-11-14) |
| Sandbox providers used by Tracker (`vals-ai/create-benchmark-service`), cloned to scratch | tag `v0.74.0`, commit `f781507280b6791a28b7af3e88fbdaf727c37597`. Tracker pins this tag in `services/tracker/pyproject.toml`. |
| Registry agents (`vals-ai/public-agent-registry`) | commit `3e47c5065e26f02631c43c6e37d79dee06a20824` |
| Harbor docs source (`harbor-framework/harbor`, `docs-mintlify/tasks/*.mdx`) | commit `ec6aeab7fe0eb51df52b4e72c524daf5ea9cc5f4` |
| Live docs | https://docs.harborframework.com and https://docs.valkyrie.vals.ai. Both loaded today; the pages I fetched matched the source. |
| Installed CLI | `.venv-valkyrie`: `valkyrie-cli 2026.11.12.2`, `valkyrie-sdk 0.34.0` (`pip list`) |

Short names used below:

- `VK` = `https://github.com/vals-ai/valkyrie/blob/1fe5c33d8c625540b1ea4f71e5ec159c1d813b48`.
  Tracker dataset code lives under `VK/services/tracker/src/tracker/services/datasets/`.
- `CBS` = `https://github.com/vals-ai/create-benchmark-service/blob/v0.74.0/src/benchmark_service/sandbox/`.

**Valkyrie is not the Harbor framework.** Valkyrie's Tracker reads Harbor task folders with its own
parser (`VK/.../datasets/config.py`, `TaskConfig`) and runs them with its own executor. Where Harbor's
docs and Valkyrie's code differ, Valkyrie's code is what governs our runs. Each difference is flagged
below.

---

## 1. Harbor task format, as Valkyrie runs it

### 1.1 Required files

A dataset folder holds one sub-folder per task. The folder name is the task ID. Each task contains:

```
<task-id>/
  task.toml          required
  instruction.md     required (the agent's prompt)
  tests/test.sh      required (the verifier entry point)
  environment/       Dockerfile (or docker-compose.yaml); optional if task.toml sets docker_image
  solution/solve.sh  optional; required for the oracle agent
```

Optional files in the dataset's parent folder:

- `metric.py`: a dataset-level score from the task rewards, at most 256 KB.
- `dataset.toml`: pins the tasks and their digests.

Tags:

- DOCUMENTED: https://docs.valkyrie.vals.ai/benchmarks/datasets; https://docs.harborframework.com/tasks/overview.
- PROVEN that the SDK checker enforces `task.toml`, `instruction.md` and `tests/test.sh`. It also
  rejects symlinks and special files, and names containing `:` or `\`. The checker is
  `valkyrie/sdk/task_archive.py::task_problems` in `.venv-valkyrie`. My skeleton task in
  `exp/suite-platform-probe/template-tasks/` passes it with no problems
  (`exp/suite-platform-probe/taskconfig-check.txt`).

### 1.2 `task.toml` fields that matter for us

Source: `VK/.../datasets/config.py`. Harbor reference: https://docs.harborframework.com/tasks/configuration.

| Field | Default in Valkyrie | Meaning / caveat |
|---|---|---|
| `schema_version` | `"1.3"` (Harbor docs: `"1.4"`) | Both parse. |
| `artifacts = [...]` (top level, before any `[section]`) | `[]` | Paths copied out of the agent sandbox. In separate-verifier mode these are the **only** agent files the verifier sees. Max 20 entries. Each entry may be a string or `{source, destination, exclude}`. |
| `[agent] timeout_sec` | none, meaning no generation limit | **Always set it.** On Modal, a task without it can run until the 24 h sandbox limit. |
| `[agent] network_mode` / `allowed_hosts` | inherits `[environment]` | Network during the agent's run (see 1.6). |
| `[agent] user` | container default (root) | |
| `[verifier] timeout_sec` | 600 | Wall limit on `tests/test.sh`. |
| `[verifier] environment_mode` | shared, unless `[verifier.environment]` is present | `"separate"` gives a fresh sandbox. |
| `[verifier] network_mode` | inherits | Use `"no-network"`. |
| `[verifier] env`, `user` | `{}`, root | |
| `[verifier.environment]` | none | Same schema as `[environment]`. Sets verifier CPU, RAM and GPU. Declaring it implies separate mode. |
| `[environment] cpus` | **1** if omitted | `retrieve_task.py::sandbox_resources` |
| `[environment] memory_mb` | **1024** if omitted (`DEFAULT_MEMORY_GB = 1`) | Too small for 3D imaging. Always set it. |
| `[environment] storage_mb` | 15 GB if omitted | **Ignored by the Modal provider.** `CBS/modal.py::create_sandbox` does not pass disk. |
| `[environment] gpus`, `gpu_types` | 0, none | See 2.4. On Modal, `gpu_types` is required when `gpus > 0`. |
| `[environment] network_mode` | none, which is treated as `"*"` (public) | Also accepts the old `allow_internet = true/false`. |
| `[environment] docker_image` | none | A prebuilt public image, pulled with Modal `Image.from_registry`. |
| `[environment] build_timeout_sec` | 600 | The build may take this long **plus** a 360 s sandbox-create timeout (`CBS/types.py::provider_timeout`, `VK/.../tracker/sandbox.py::SANDBOX_CREATE_TIMEOUT`). |
| `[environment] workdir` | Dockerfile `WORKDIR`, else `/workspace` | The agent's cwd. The instruction is placed at `<workdir>/instruction.md`. |
| `[environment] env` | `{}` | Plain environment variables. `${SECRET}` and `${SECRET#FIELD}` read organisation secrets (datasets doc). |
| `[solution] env` | `{}` | Variables for the oracle. |
| `[metadata]` | free-form | Not interpreted. |
| `[[steps]]`, `multi_step_reward_strategy` | none | Multi-step tasks. Not needed by us. |

The TOML template in section 4 parses with the pinned Tracker `TaskConfig`. That result is PROVEN
(`exp/suite-platform-probe/taskconfig-check.txt`): `is_separate True`, the agent allowlist is
`['api.anthropic.com']`, verifier `no-network`, and the GPU variant parses as `gpus 1 ['L4','T4']`.

### 1.3 Image build and build context

DOCUMENTED (`retrieve_task.py::sandbox_source`; `CBS/modal.py::_resolve_image`):

- **Image choice.** The agent image comes from `environment/Dockerfile`. On Modal it is built with
  `Image.from_dockerfile(dockerfile, context_dir=<environment/>)`. The build context is therefore
  only `environment/`, and `tests/` and `solution/` are never in it. If `docker_image` is set, that
  image is pulled instead.
- **Network during the build.** The build runs on Modal's image builder, not in the agent stage.
  The task's network policy does not apply to it, so `pip install` in a `RUN` step works. That this
  builder has internet is an inference from Modal's normal behaviour; the existing repair tasks rely
  on the same thing.
- **Docker-in-the-sandbox.** Modal sandboxes run under gVisor, with GPU sandboxes forced to gVisor.
  Docker inside the task is not usable on local Docker and should not be planned for.
- **Size limits.** Per-task archive upload: at most 4 GiB (`DATASET_TASK_UPLOAD_MAX_BYTES` default,
  `VK/services/tracker/src/tracker/config.py`). The hosted value is UNKNOWN. Modal image-size
  limits are UNKNOWN; Modal's resources page gives none.

### 1.4 Where the agent works and where outputs go

- **Working directory.** The agent runs in `workdir`. The registry Claude Code agent runs `claude -p`
  with `cwd = Path.cwd()` (`public-agent-registry/examples/claude_code-v1.0.0/collect_outputs.py`).
  DOCUMENTED.
- **What the verifier receives.**
  - In **separate** mode, only the paths listed under `artifacts` reach the verifier sandbox, plus a
    non-empty `/logs/artifacts`.
  - Each artifact is tarred in the agent sandbox, sanitised and unpacked at the **same path** in the
    verifier.
  - Limits: 512 MiB compressed and 20 000 files per artifact (`artifacts.py`). An artifact over the
    limit raises `SeparateVerifierError`, which is an **infrastructure error, not a zero score**. The
    instruction must state the size limit.
  - DOCUMENTED (source).
- **What Valkyrie keeps for download.**
  - The agent contract's `final_output` and `output_artifacts`: at most 250 MiB each and 250 MiB in
    total (`VK/.../tracker/types.py::MAX_OUTPUT_ARTIFACT_BYTES`; `sandbox.py`).
  - The registry Claude agent sets `final_output: /logs`, so its trajectory under `/logs` is kept.
    Task `artifacts` are also kept and listed by `valkyrie run artifacts`.

### 1.5 How the verifier runs

DOCUMENTED (`grading.py`, `separate_verifier.py`; https://docs.harborframework.com/tasks/separate-verifier).

- **Shared mode (default).** After the agent finishes, `tests/` is uploaded to `/tests` in the
  **agent's own sandbox** and `bash /tests/test.sh` runs there. The agent's files and any processes
  it left behind are present. Do not use this mode for hidden references.
- **Separate mode** (`environment_mode = "separate"`) creates a **fresh sandbox**. Its image is chosen
  in this order:
  1. `[verifier.environment].docker_image`;
  2. `tests/docker-compose.yaml`;
  3. `tests/Dockerfile`, built with `tests/` as its context; the image must already contain
     `/tests/test.sh`, and tests are not uploaded;
  4. otherwise, a fresh build of the agent's `environment/Dockerfile`, with `tests/` uploaded to
     `/tests`.

  The verifier never inherits the agent's filesystem, only the carried artifacts. Resources come from
  `[verifier.environment]` if present, else from `[environment]` (`sandbox_resources(environment,
  fallback)`).
- **Verifier network.** `network_mode = "no-network"` creates the verifier with
  `block_network=True`.
- **Command.** The verifier runs `bash -c '/tests/test.sh > /logs/verifier/test-stdout.txt 2>&1'` in
  the verifier workdir, under `[verifier] timeout_sec`. Before it starts, `/logs/verifier` is emptied
  and set to mode 755, owned by root. `/logs/agent` and `/logs/artifacts` are set to mode 777.
- **What it can see.** It sees everything in `/tests`, the carried artifacts, and the image. Valkyrie
  keeps only the reward map, the exit code and the last **20 000 characters** of verifier stdout
  (`SAVED_OUTPUT_CHARS`). Other files under `/logs/verifier` are not known to be kept: UNKNOWN. Print
  the per-case summary to stdout.
- **Where `solution/` goes.** It never reaches the verifier. The oracle uploads it to `/solution` in
  the agent sandbox (1.7).

### 1.6 Network modes

`no-network`, `allowlist` (with `allowed_hosts`) and `public`. They can be set per stage:
`[environment]` sets the baseline, and `[agent]` and `[verifier]` override it. Valkyrie's `stage_egress`
maps them as follows: no-network becomes `[]`, allowlist becomes a host list, public becomes `"*"`, and
an unset mode becomes **allow-all**. DOCUMENTED.

- **The repair tasks are open.** All existing repair tasks under `dist/` set no `network_mode`
  (e.g. `dist/repair-suite-v2/integrated-25be5ac4e3/task.toml`). Their agents would therefore run with
  public internet. PROVEN (file) together with DOCUMENTED (source).
- **The prediction exporter is closed.** `pcnsl/prediction_export.py` sets `no-network` or
  `allowlist`. PROVEN (file).

### 1.7 Oracle

`valkyrie run start --agent oracle --dataset ...` runs:

```
DEBIAN_FRONTEND=noninteractive bash /solution/solve.sh; echo "solve.sh exited with $?"
```

It runs in the **agent sandbox**, under the agent's timeout and network policy, with `/solution`
uploaded. Grading then proceeds normally. No model key is needed. A failing `solve.sh` does not fail
the outer command, so judge the oracle by its reward, not its exit status. DOCUMENTED:
`VK/.../datasets/oracle.py`; https://docs.harborframework.com/tasks/solution.

### 1.8 Rewards

DOCUMENTED (`grading.py`, `rewards.py`, `scoring.py`).

- **Reward files.** `/logs/verifier/reward.json` takes precedence over `/logs/verifier/reward.txt`.
  `reward.json` must be a **flat object of finite numbers**. Booleans, nested objects, NaN and inf are
  rejected and make the task an infrastructure error.
- **No reward file.** If the verifier writes neither file, the task is a `VerifierResultError`
  (an infrastructure error), even when the exit code is 0.
- **Aggregation across tasks.**
  - Each key is averaged over tasks. **A key missing from a task counts as 0.0.**
  - The headline score is the mean of `reward` × 100, and only when that mean lies in [0, 1].
  - Every task must therefore write **the same key set**, and every key must be oriented so that 0 is
    the failure value.
  - Never emit raw HD95 in mm or raw seconds as reward keys: a missing value would average in as
    "0 mm" or "0 s", which is perfect.
- **Custom aggregation.** A `metric.py` in the dataset root can replace the mean.

---

## 2. Valkyrie specifics

### 2.1 Login and organisation on teal: PROVEN not logged in

Run today with `.venv-valkyrie/bin/valkyrie` (output: `exp/suite-platform-probe/whoami-etc.txt`):

```
=== whoami         Error: You are not logged in. Run `valkyrie login`.
=== org list       Error: Organizations are managed with your login. Run `valkyrie login`.
=== agent list     Error: You are not logged in. Run `valkyrie login`.
=== provider list  Error: You are not logged in. Run `valkyrie login`.
=== run list       Error: You are not logged in. Run `valkyrie login`.
=== secret list    Error: You are not logged in. Run `valkyrie login`.
```

- **Other evidence.** `~/.config/valkyrie` does not exist. `results/20261114-repair-suite-v2-packaging/preflight.json`
  records every credential variable absent, `"hosted_execution": "not_attempted"`, and no
  docker/podman/uv.
- **Version flag.** `valkyrie --version` does not exist (`No such option '--version'`). The version
  comes from `pip list`.
- **Organisation.** The assigned organisation, `hackathon-neuronetwork-b91c517178`, is in
  `docs/research/hackathon-prompt.md`. Whether this login can act for it is UNKNOWN.
- **Default Tracker.** `https://benchmark-tracker-prod.vals.ai` (`valkyrie/sdk/config.py`).

### 2.2 Hosted runs: PROVEN that none is recorded here

- **Validation files.** Every validation file says `"hosted_run": false`:
  - `results/20261113-valkyrie-validation/validation.json`;
  - `results/20261113-valkyrie-v2-validation/validation.json`;
  - `results/20261114-repair-suite-v1-packaging/validation.json`;
  - `results/20261114-repair-suite-v2-packaging/validation.json`.
- **README.** "Hosted Valkyrie has not run." (`README.md`, line 125).
- **Run IDs.** The UUIDs found under `results/` and `exp/` come from local agent traces, not from
  Valkyrie runs.
- **Other machines.** Whether a teammate or the Codex session has run something on another machine
  is UNKNOWN. The team shares runs, so `valkyrie run list` after login would answer it.

### 2.3 Agents

- **Out-of-the-box agents.** Claude Code, Codex and mini-SWE-agent are available. DOCUMENTED in the
  hackathon prompt.
- **Installed in the organisation.** UNKNOWN, because `agent list` needs login. The prompt says a
  teammate's installed agent is usable by everyone.
- **Registry `claude_code-v1.0.0`** (DOCUMENTED, contract and `setup.sh`):
  - Its `install_cmd` runs `bash setup.sh`. If curl or python3 are missing it installs them with
    `apt-get`, runs `curl https://claude.ai/install.sh | bash`, and symlinks
    `~/.local/bin/claude` to `/usr/local/bin/claude`.
  - It runs `claude -p --verbose --output-format stream-json --allowedTools "Bash Edit Write Read ...
    WebFetch ... WebSearch"`, with model `anthropic/<id>` stripped to `<id>`.
  - It has no max-turns or budget flag.
  - It does **not** declare `egress_allowlist`.
- **Registry `codex-v1.0.0`** (DOCUMENTED):
  - It installs Node via nodesource, runs `npm i -g @openai/codex`, and writes the key into
    `~/.codex/auth.json`.
  - Its model choices are `gpt-5.3-codex`, `gpt-5.4`, `gpt-5.2-codex`, `gpt-5.2`,
    `gpt-5.1-codex-max` and `gpt-5.1-codex-mini`.
- **Conflict with the project rule.** These global installs happen **inside the task sandbox at
  agent-install time**. They conflict with this project's environment-only rule, as already noted in
  `docs/research/harness-worker-brief.md`.
- **Custom bundle.** The custom bundle `agents/pcnsl_claude/` sets `install_egress: []` and expects
  a prebuilt runtime in the image. PROVEN (file). It has not been pushed or tested on Valkyrie.
- **Install-time network.** Install runs under the contract's `install_egress`, which defaults to
  `"*"`, not under the task's agent policy. A no-network task can therefore still install the
  registry agent. DOCUMENTED: https://docs.valkyrie.vals.ai/agents/agent-contract#install-egress.
- **Install limits.** 10 minutes, with 3 retries and then one more sandbox.

### 2.4 Modal sandbox limits

| Item | Value | Tag and source |
|---|---|---|
| Max sandbox lifetime | 24 h on Modal. The Valkyrie task wall limit is 166 h, so Modal caps it. | DOCUMENTED: https://docs.valkyrie.vals.ai/get-started/sandbox-providers; `CBS/modal.py::_MAX_LIFETIME_SECONDS` |
| CPU | `cpu=(vcpu, vcpu)`, i.e. request equals limit, so it is **hard-throttled**. That is good for timing. Whether Modal counts `cpu` in physical cores or vCPUs is UNKNOWN; Modal prices per physical core, equal to 2 vCPU. | DOCUMENTED: `CBS/modal.py` lines 541-546; https://modal.com/docs/guide/resources |
| RAM | `memory = memory_mb/1024 GB × 1024` MiB, passed as an int. Modal treats an int as a **request, not a hard limit**, and sandboxes may burst above it. Our memory budget is therefore not enforced unless the grader enforces it. | DOCUMENTED (source + Modal docs) |
| Disk | `storage_mb` is not passed. Modal's default per-container write quota is 512 GiB. | DOCUMENTED (source + Modal docs) |
| GPU | Supported: set `gpus = N` and `gpu_types = [...]`. Modal **requires** `gpu_types` when `gpus > 0`. Only the **first** listed type with a Modal name is requested; the rest are not fallbacks. Valid Modal names: T4, L4, A10, L40S, A100, A100-40GB, A100-80GB, H100, H100!, H200, B200, B200+, B300, RTX-PRO-6000. GPU sandboxes run under gVisor. | DOCUMENTED: `CBS/gpu.py`, `CBS/modal.py` 528-534 |
| GPU in the separate verifier | Taken from `[verifier.environment]` if declared, which has **no GPU fallback** to `[environment]`. Without that block, the verifier inherits `[environment]`, GPU included. | DOCUMENTED: `retrieve_task.py::sandbox_resources` |
| GPU availability for *our* Modal workspace | Modal Starter plan: 10 concurrent GPUs, 100 containers, $30/month of credits. The hackathon credit tier is UNKNOWN. | DOCUMENTED: https://modal.com/pricing; UNKNOWN for us |
| Build time limit | `build_timeout_sec` (default 600) + 360 s | DOCUMENTED |
| Image size limit | — | UNKNOWN |
| Default resources if omitted | 1 vCPU, 1 GB RAM | DOCUMENTED: `retrieve_task.py` |

### 2.5 Disabling public internet while allowing the model API

DOCUMENTED, not yet observed.

**Configuration.** Set the agent stage to an allowlist and close the other stages:

```toml
[environment]
network_mode = "no-network"   # baseline: setup and anything not overridden

[agent]
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com"]   # Codex: ["api.openai.com"]

[verifier]
network_mode = "no-network"
```

**How Modal enforces it** (`CBS/modal.py::modify_egress_rules`; `VK/.../tracker/sandbox.py::apply_egress_policy`):

- An exact hostname is **resolved to IPv4 /32 addresses**, both in the sandbox and on the Tracker.
- Those addresses go into Modal's `outbound_cidr_allowlist`. Wildcards (`*.example.com`) go into
  Modal's experimental domain allowlist. IPv6 is unsupported.

**How the run allowlist is assembled** (`VK/.../tracker/egress.py::combine_run_egress_policies`):

- If the task sets a list, the agent contract's legacy `egress_allowlist` hosts are **added** to it.
- The registry Claude and Codex contracts set none. The task's `allowed_hosts` is therefore the only
  way the agent reaches the model.
- With `[agent] network_mode = "no-network"`, the registry agents **cannot reach the model and the
  run fails**. The task does not silently run open.

**Weaknesses** (inference, not tested):

- If the API host's IPs change during a long run, calls may fail.
- Claude Code's non-essential telemetry hosts will be blocked. Setting
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` in `[environment.env]` should quiet that; it is
  untested here.
- Hosts behind a shared CDN broaden the allowlist (agent-contract doc).
- Provider-side tools such as hosted web search are stripped whenever the run is allowlisted
  (agent-contract doc, `allow_provider_tools`).

**Whether the hosted Tracker plus our Modal workspace honours this end to end is UNKNOWN until the
first run.** Check it in the first pilot: the agent must be able to call the model, and
`curl https://pypi.org` from inside the task must fail.

### 2.6 Dataset push: size and privacy

- **How push works.** `valkyrie dataset push BENCH/DATASET FOLDER [--tag T] [--concurrency 4]`
  creates the benchmark and dataset if missing. It uploads **only tasks the dataset does not already
  store**; an unchanged folder makes no new version. Every version also gets `latest`. Versions are
  immutable. DOCUMENTED: CLI help in `exp/suite-platform-probe/cli-help.txt`;
  https://docs.valkyrie.vals.ai/benchmarks/datasets.
- **Size.** At most 4 GiB per task archive by default (`DATASET_TASK_UPLOAD_MAX_BYTES`). The hosted
  setting is UNKNOWN. `.harborignore` inside `tests/` and `solution/` excludes local files from upload.
- **Privacy.**
  - Benchmarks are unique per organisation (`benchmark_definition` has `org_id`, with a unique index
    on `(org_id, name)` in `VK/.../tracker/database/models.py`).
  - I found no public or visibility flag. The prompt says "Everyone on your team sees the same runs,
    datasets and task logs."
  - Datasets are therefore **organisation-scoped, not public**. That is DOCUMENTED.
  - Vals AI operators and the owner of the Modal workspace can still access the stored archives and
    the sandboxes. This is not a data-governance guarantee.
  - Public imaging data is fine. Patient-level UCSF data must not be pushed (AGENTS.md).

### 2.7 Cost drivers

DOCUMENTED, with the magnitudes inferred:

- **Model tokens.** Billed to the API key mapped with `-s`. This is usually the largest cost: an
  agentic Claude Code session of 30-45 minutes can cost several dollars. The registry agent has
  **no budget or turn cap**.
- **Modal sandbox time.** Each task uses one agent sandbox for the whole agent run, one
  separate-verifier sandbox (a second sandbox, possibly a second image build), and image builds.
  Modal bills sandboxes at max(request, actual). List rates: about $0.047 per physical core-hour,
  $0.008 per GiB-hour, T4 about $0.59/h, L4 about $0.80/h, A100-80GB about $2.50/h.
  (https://modal.com/pricing; whether sandbox rates differ from these list rates is UNKNOWN.)
- **Multipliers.** `--count`, retries, and `run resume`.

The Tracker reads Modal usage per run (`VK/.../tracker/modal_cost.py`). Whether the CLI shows it is
UNKNOWN.

### 2.8 Traces and per-task logs

DOCUMENTED (CLI help captured in `exp/suite-platform-probe/cli-help.txt`;
https://docs.valkyrie.vals.ai/runs/monitor; https://docs.valkyrie.vals.ai/runs/results-and-outputs).

| Need | Command |
|---|---|
| Run summary and errors | `run fetch RUN_ID`, `run errors RUN_ID`, `run tasks RUN_ID --status ERROR` |
| One task's grade, exit reason and time breakdown | `run task RUN_ID TASK_ID --format json`. Fields: `generation_elapsed_seconds`, `agent_run_duration`, `sandbox_build_duration`, `evaluation_run_duration`, `agent_caused_exit_reason`. |
| Logs | `run logs RUN_ID [--task-id T] [--format jsonl] [--follow]` |
| Agent outputs and trajectories | `run outputs RUN_ID --output-dir DIR`. The registry Claude agent keeps `/logs` as `agent_output.tar.gz`. |
| One file or folder | `run artifacts RUN_ID --format json`, `run output RUN_ID TASK_ID -o DIR`, `run task-artifacts RUN_ID TASK_ID` (temporary links) |
| Scores | `run results RUN_ID --path FILE` |
| Live view | `valkyrie tui`; `run start ... --connect` |

### 2.9 Concurrency

- **Per run.** `--concurrency` defaults to 5 and can be changed live with `run update` or `run shed`.
  `--count` up to 10 starts independent runs, each with its own concurrency. DOCUMENTED.
- **Per organisation.** An optional active-run cap exists (`VK/.../services/runs/limits.py`). Its
  hosted value is UNKNOWN.
- **Effective ceiling.** Modal Starter allows 10 GPUs and 100 containers. Each task can hold two
  sandboxes (agent and verifier). Model-provider rate limits apply on top.
- **Queue.** `valkyrie queue status` shows the queue. DOCUMENTED.

---

## 3. Runtime measurement the agent cannot fake

### 3.1 What the platform gives us

- **Agent time only.** Valkyrie measures the agent's generation time and the grader's duration
  (`run task`). It does **not** time the agent's final pipeline. `agent_run_duration` measures the
  whole agentic session.
- **No trusted timing channel.** Anything the agent writes, such as a `timing.json` or log
  timestamps, is agent-controlled and can be fabricated or edited.
- **The verifier is the only trusted executor.** It runs code we control, in a sandbox the agent
  never touched, with fixed CPUs, no network and a hard timeout. That combination is DOCUMENTED in 1.5.

### 3.2 Recommended design: the verifier re-runs a submitted entry point on hidden cases

**Agent contract** (stated in `instruction.md`):

1. The agent develops on **visible cases** in `/workspace/data/visible/`, with their reference
   labels.
2. It must leave a self-contained pipeline in `/workspace/output/pipeline/`, with entry point
   `run.sh INPUT_DIR OUTPUT_DIR`. The entry point processes one case folder and writes a fixed file
   contract, e.g. `OUTPUT_DIR/mask.nii.gz` and `OUTPUT_DIR/measurements.csv`.
3. Only `/workspace/output` is carried. The pipeline may use only the image's Python environment
   (`/opt/benchmark-venv`) and files under `/workspace/output/pipeline`: no network, no pip, and
   nothing it put elsewhere in the agent sandbox.
4. Its own predictions on visible cases may go in `/workspace/output/visible_predictions/` for
   diagnostics. They are not scored.

**Verifier procedure** (separate mode, `no-network`, `[verifier.environment]` with the same image
and fixed CPU/RAM). `grade.py` runs as root and:

1. **Fail-closed check.** Refuse to score (exit 2, no reward, so it shows as an infrastructure error)
   if `/solution` or `/bundle` exists. This is the existing heuristic from
   `docs/research/prediction-harbor.md`.
2. **Protect the references.** `chmod -R go-rwx /tests`. The references, and the specialist
   baseline outputs, stay root-only.
3. **Stage inputs.** Copy only the hidden **inputs** to `/eval/in/<case>/`, world-readable. Create
   `/eval/out/<case>/`, owned by uid 65534. Copy the pipeline to `/eval/pipeline/`, root-owned and
   read-only.
4. **Run each case.** For each case, on a monotonic clock, launch:
   ```
   setpriv --reuid=65534 --regid=65534 --clear-groups -- \
     timeout -k 5 LIMIT bash /eval/pipeline/run.sh /eval/in/<case> /eval/out/<case>
   ```
   - Use a minimal environment: `PATH=/opt/benchmark-venv/bin:/usr/bin:/bin`,
     `HOME=/eval/home/<case>`, thread caps `OMP_NUM_THREADS=N` etc., and a new session.
   - Optionally cap memory with `prlimit --as` (Modal does not hard-cap RAM).
   - Afterwards, `pkill -KILL -u 65534`, so no background process survives into scoring.
   - Record wall time, exit code, and whether the timeout fired.
5. **Optional warm-up.** Run one untimed visible case first, so import and page-cache costs do not
   land on hidden case 1. Document whichever choice is made.
6. **Optional baseline normaliser.** Run the **specialist baseline pipeline** (shipped in `tests/`)
   on the same cases, in the same sandbox, the same way. Report `runtime_ratio = agent / baseline`.
   This removes most machine-to-machine variance between Modal hosts.
7. **Score.** Compute clinical metrics against the hidden references with our own code: Dice and
   HD95 for masks, landmark/TRE or Dice-after-warp for registration, Brier/AUROC for probabilities,
   absolute error for measurement tables.
8. **Write the reward.** Write `reward.json` with a **fixed key set**, all oriented 0 = bad, plus a
   compact per-case JSON line on stdout. For example:
   - `reward`: mean over hidden cases of `quality_i × [ran_ok_i and time_i ≤ LIMIT]`;
   - `valid_submission` (0/1);
   - `dice_mean`;
   - `hd95_score = mean exp(-hd95_mm / 20)`;
   - `cases_within_time` (fraction);
   - `runtime_score = min(1, baseline_s / agent_s)`.

   Raw seconds and mm go to stdout and to `metadata`-style lines, not to reward keys (see 1.8).

**Why it cannot be faked:**

- The hidden inputs first exist after the agent has finished.
- The clock and the timeout are in grader code.
- The pipeline runs as an unprivileged user that cannot read `/tests` or write `/logs/verifier`
  (root-owned, mode 755 per `grading.py`).
- There is no network, so nothing can be fetched or exfiltrated.

### 3.3 Weaknesses and mitigations

| Weakness | Mitigation |
|---|---|
| Hidden references live in the same verifier sandbox as untrusted code. A root-run submission could read them. | Never run the submission as root. `chmod 700 /tests` first. Run under `setpriv` as uid 65534. The `setpriv` (util-linux) and `timeout` (coreutils) binaries should exist in `python:3.12-slim`; that is inferred, not checked. The build step should assert both. |
| Timing noise. gVisor syscall overhead and neighbour load on Modal hosts. CPU is hard-limited, but I/O and caches vary. | Use a generous per-case `LIMIT` of about 3-5× the baseline. Score runtime relative to the baseline run in the same sandbox. Report the median, not the minimum. Run several hidden cases. |
| The pipeline depends on things outside `/workspace/output`, such as pip-installed packages, `/tmp` weights or caches. | The instruction states the contract. The verifier image is a fresh build, so such pipelines simply fail. That is a fair failure, and the oracle run proves the contract is satisfiable. |
| Large outputs or pipelines (for example, model weights) exceed the 512 MiB artifact limit, which gives an infrastructure error, not a 0. | State the limit. Use `exclude` globs on the artifact. Keep the verifier's own size check below the limit. |
| `verifier.timeout_sec` must cover every case × `LIMIT` plus the baseline and scoring. A verifier timeout without a reward file is an infrastructure error. | Budget: `timeout_sec ≥ n_cases × LIMIT × 2 + 300`. Write a provisional zero `reward.json` at the start and overwrite it at the end, so a hang still scores 0. Better still, enforce a grader-side global deadline. |
| The verifier sandbox is a second build of the agent image. If the build is not reproducible (unpinned packages), the environments differ. | Pin every package version, or use a digest-pinned `docker_image`. |
| GPU pipelines need a GPU verifier, which doubles GPU cost. | Prefer CPU tasks. If a GPU is needed, declare the same `gpus`/`gpu_types` under `[verifier.environment]`. |
| The agent can hard-code a lookup if the hidden cases are public data it memorised. | Use cases the agent cannot identify: re-sampled or cropped, with re-drawn IDs and stripped headers. Treat publicly famous cases as a known contamination risk. |

The rejected alternative is to trust a timing file the agent writes. It is trivially fakeable, and
even an honest file times the wrong machine. Use it only as a diagnostic.

---

## 4. Recommended reusable template

### 4.1 Layout

Folder names must pass `validate_task_id`; the existing exporter style is `family-<hash>`.

```
<family>-<hash>/
  task.toml
  instruction.md                 task, file contract, metrics, runtime rule, size limit, "no network"
  environment/
    Dockerfile
    data/visible/<case>/...      inputs + reference labels the agent may study
    data/README.md               provenance, licence, voxel spacing, label map
  tests/
    test.sh                      exec /opt/benchmark-venv/bin/python -I /tests/grade.py
    grade.py                     stdlib + numpy/SimpleITK; the procedure in 3.2
    hidden/<case>/input/...      hidden inputs (verifier only)
    hidden/<case>/reference/...  hidden references (verifier only)
    baseline/run.sh + code       specialist baseline (verifier only)
    baseline_expected.json       baseline metrics computed offline, for the README comparison
  solution/
    solve.sh                     oracle: copy tests-independent reference pipeline into /workspace/output/pipeline
    pipeline/run.sh + code       reference (e.g. classical SimpleITK) pipeline
```

`solution/` must not read `/tests`. The oracle runs in the agent sandbox, where `/tests` does not
exist in separate mode. The oracle therefore proves that a correct pipeline can be built from
agent-visible material alone.

### 4.2 `task.toml` (parses with the pinned Tracker; see 1.2)

```toml
schema_version = "1.4"
# Only this folder reaches the verifier.
artifacts = [{ source = "/workspace/output", exclude = ["*.tmp", "__pycache__"] }]

[metadata]
category = "medical-imaging"
family = "segmentation"             # or registration / probability / measurement
dataset = "PUBLIC_SOURCE_NAME"
runtime_budget_sec_per_case = 60

[agent]
timeout_sec = 2700.0                # 45 min of agent work
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com"]   # Codex runs: ["api.openai.com"]

[verifier]
timeout_sec = 1800.0                # >= n_hidden * LIMIT * 2 + 300
environment_mode = "separate"
network_mode = "no-network"

[verifier.environment]              # fixed, explicit timing machine; still uses environment/Dockerfile
cpus = 4
memory_mb = 16384

[environment]
cpus = 4
memory_mb = 16384
storage_mb = 20480                  # ignored on Modal, kept for other providers
workdir = "/workspace"
build_timeout_sec = 1500.0
network_mode = "no-network"         # baseline for setup; agent override above
env = { CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1", PIP_NO_INDEX = "1" }
# GPU variant (only if truly needed; also add the same two lines under [verifier.environment]):
# gpus = 1
# gpu_types = ["L4"]
```

The skeleton copy of this file is
`exp/suite-platform-probe/template-tasks/imaging-template-0001/task.toml`. It includes the `env`
line, and it parses with the pinned Tracker `TaskConfig`. PROVEN: the last line of
`exp/suite-platform-probe/taskconfig-check.txt` shows `environment.env` populated. Keep the `env`
key under `[environment]`: a TOML table key placed after `[verifier]` silently becomes
`verifier.env`, which I hit once while testing.

### 4.3 Dockerfile: imaging tools without internet at run time

This follows the pattern in `pcnsl/prediction_export.py::_dockerfile`. Everything goes into one
virtualenv at build time. There are no system-Python or user-level installs and no apt. The image is
not built or tested yet, because there is no Docker on teal.

```dockerfile
FROM python:3.12-slim                      # pin by digest once known: python:3.12-slim@sha256:...
RUN python3 -m venv /opt/benchmark-venv \
 && /opt/benchmark-venv/bin/python -m pip install --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 nibabel==5.3.2 SimpleITK==2.4.0 scikit-image==0.24.0 \
      pandas==2.2.3 scikit-learn==1.5.2
#   optional: antspyx==0.5.4 (large wheel, slow build); torch CPU wheel + a small checkpoint COPY'd from
#   environment/models/ only if its licence allows redistribution.
ENV PATH=/opt/benchmark-venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=4
RUN python3 -c "import sys; assert sys.prefix=='/opt/benchmark-venv', sys.prefix; \
import numpy, scipy, nibabel, SimpleITK, skimage" \
 && command -v setpriv && command -v timeout && command -v prlimit
WORKDIR /workspace
COPY data/ /workspace/data/
RUN mkdir -p /workspace/output
```

- **Version pins.** The pins shown are illustrative. Confirm that each version has a cp312
  manylinux wheel before the first build. A failed pin shows up as `SandboxImageBuildError`, with the
  last 2000 characters of the build log kept.
- **Python for the agent.** The registry Claude agent needs `python3` and `curl` on PATH. The venv
  provides `python3`. `curl` is absent from slim, so `setup.sh` would `apt-get install curl` at
  install time. The cleaner path is the project's own `agents/pcnsl_claude` bundle with a prebuilt
  runtime image (`agents/pcnsl_claude/image/Dockerfile`), so that nothing installs at task time.
- **Build cost and caching.** Each task has its own `environment/data`, so each task builds its own
  image. Every Docker layer is a separate build step, so the pip layer may be cached across tasks.
  Whether Modal's `from_dockerfile` cache shares the identical pip layer between tasks is UNKNOWN.
  Expect a few minutes of build per task on a cold cache; keep `build_timeout_sec` generous.

### 4.4 Keeping hidden references out of the agent's reach

- **What the agent's world contains.** Hidden inputs, references and baseline code live **only
  under `tests/`**. The agent image's build context is `environment/` alone. In separate mode,
  `tests/` exists only in the fresh verifier sandbox.
- **Larger hidden sets.** Either keep them in `tests/` (uploaded at grading time), or add a
  `tests/Dockerfile` whose context is `tests/`. The latter bakes the references into a verifier-only
  image, but that image must then repeat the same pinned pip install and contain `/tests/test.sh`.
  Start with the first option, because it is simpler.
- **What the oracle sees.** `solution/` reaches only the oracle's agent sandbox.
- **Visible cases.** They must not be the hidden cases, and they must not be trivially linkable to
  them: no shared subject IDs or headers. Strip identifying NIfTI header text and re-draw case IDs.
- **Byte-identity test.** Reuse the exporter test from `pcnsl/prediction_export.py`: agent-visible
  bytes must be byte-identical when the hidden references are changed. Compute a per-file SHA-256
  manifest tagged with its audience (`task_manifest`).

### 4.5 Grader output

`grade.py` writes `/logs/verifier/reward.json` **once at the start** with every key set to 0 and
`valid_submission` set to 0. It **overwrites** the file at the end. A crash or timeout then still
yields a score of 0 rather than an infrastructure error. For a deliberate infrastructure failure
(the fail-closed `/solution` check), it exits non-zero **before** writing anything.

Example reward:

```json
{"reward": 0.71, "valid_submission": 1, "dice_mean": 0.78, "hd95_score": 0.64,
 "cases_within_time": 1.0, "runtime_score": 0.83}
```

On stdout it prints one compact JSON object per case, with case ID, Dice, HD95 in mm, seconds,
exit code and timed-out flag, plus a summary line. All of it must fit in 20 000 characters. The
baseline comparison for the README uses `tests/baseline_expected.json`, or the baseline run in the
verifier, and goes in the stdout summary, not the reward.

### 4.6 Local validation before any upload

These scripts already exist. All are read-only towards the platform.

1. **Unit tests** for the exporter and the grader, run with a local project environment. Test
   `grade.py` against fixtures: a perfect mask, an empty mask, a wrong-shape mask, NaN, a timeout,
   a pipeline that tries to read `/tests`, a pipeline that leaves a background process, and an
   oversize output.
2. **Packaging check:**
   `.venv-valkyrie/bin/python scripts/validate_exports.py dist/<suite> results/<suite>-packaging`.
   It runs SDK `task_problems`, does a deterministic `pack_task`, and records a SHA-256 per task.
3. **Readiness report:** `.venv-valkyrie/bin/python scripts/valkyrie_preflight.py --tasks dist/<suite>`.
   It reports versions, Docker presence and credential presence only.
4. **Tracker parser check.** Parse every `task.toml` with the pinned Tracker `TaskConfig`, loaded by
   path from `/tmp/valkyrie-inspect-20261114/.../datasets/config.py`; it needs only pydantic, which
   is in `.venv-valkyrie`. Assert `verifier.is_separate`, the agent allowlist, verifier `no-network`
   and the artifact source. The script is
   `.venv-valkyrie/bin/python -I exp/suite-platform-probe/check_taskconfig.py TASKS_DIR`. It is
   read-only and prints the SDK problems and the parsed fields per task. Copy it into `scripts/`
   when the suite exporter lands.
5. **Dry-run the grader without Docker.** Run `solution/pipeline` and `tests/grade.py` in a
   project-local virtualenv with the same pins, with paths remapped by environment variables. This
   proves the metric code and the oracle reward, but not the sandbox isolation.
6. **Not available here:** a local Tracker with the Docker provider. There is no Docker on teal, and
   the Docker provider forces open egress anyway (`execute.py`: "Local Docker execution requires
   unrestricted egress for every stage"). The first real isolation test is the hosted oracle run.

---

## 5. Cheapest path to one successful hosted run

Each step costs nothing or very little until step 6. Run them in order; stop and fix at the first
failure.

1. **Log in and inspect** (only the lead or an authorised session should do this). Run
   `valkyrie login --no-browser`, then `valkyrie org use hackathon-neuronetwork-b91c517178`, then
   `whoami`, `provider list`, `secret list`, `agent list` and `run list`. This answers most of the
   UNKNOWNs in section 2 at no cost.
2. **Provider.** If `provider list` shows no Modal, store the team's Modal token as a JSON secret
   (`valkyrie secret set modal-credentials < modal.json`). Then run
   `valkyrie provider set modal modal-credentials` and `valkyrie provider default modal`. Without a
   default, runs go to **Daytona**.
3. **Model key.** Run `valkyrie secret set anthropic-api-key`, interactively. Confirm which model IDs
   the credits cover.
4. **Build one tiny imaging task.** Use 2 visible and 2 hidden small 2D or downsampled cases, CPU
   only, `cpus = 2`, `memory_mb = 4096`. Validate it locally (4.6). Push it to a scratch dataset:
   `valkyrie dataset push imaging-suite/smoke ./dist/imaging-smoke --tag smoke1`.
5. **Oracle** on that task:
   `valkyrie run start --agent oracle --dataset imaging-suite/smoke@smoke1 --provider modal --concurrency 1 --connect`.
   Check `run task ... --format json` for a reward equal to the expected oracle value, and confirm
   that the verifier ran in separate mode. Use `run logs` and the stdout summary.

   It also proves the image build, the artifact carry, `setpriv` isolation and the reward keys. It
   uses only sandbox minutes.
6. **One frontier run, one task:**
   `valkyrie run start --agent claude_code-v1.0.0 --dataset imaging-suite/smoke@smoke1 --provider modal --model anthropic/MODEL_ID -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 1 --connect`.
   Install the agent first if `agent list` lacks it. This verifies the allowlist end to end.

   Also confirm that public egress is really blocked. Use a deliberate probe task whose `solve.sh`
   runs `curl https://pypi.org` and `curl https://api.anthropic.com`, writes both exit codes into its
   output, and is graded on them. Run that probe with the oracle, which is cheap.
7. **Save the evidence.** Run `run results`, `run outputs`, `run logs --format jsonl` and
   `run task --format json` for the run. Then scale: more tasks, the Codex agent, `--count` for
   repeats.

### Most likely failures

1. **Daytona instead of Modal.** No default provider, or the hackathon organisation has no Modal
   provider configured, sends runs to Daytona.
2. **The agent cannot reach the model.** `no-network` on the agent stage, or a missing
   `allowed_hosts`.
3. **The allowlist is not honoured** by the hosted executor or by Modal's experimental policy call,
   so the agent runs open. Detect this with the probe task in step 6.
4. **Out of memory.** The default 1 GB RAM when `memory_mb` is omitted. 3D NIfTI pipelines exceed it
   quickly, and the result may be OOM kills (`OS_KILLED`) or a silently slow, swapping pipeline.
5. **Image build failures or timeouts.** Bad pins, slow ANTsPy or torch wheels, the
   `build_timeout_sec` + 360 s ceiling, or the image built twice per task (agent and verifier).
6. **Infrastructure errors instead of zero scores.** No reward file after a verifier timeout or
   crash, a non-numeric reward key, an artifact over 512 MiB, or the fail-closed `/solution` check
   firing.
7. **Inconsistent reward keys** across tasks, which corrupt the averages (missing key = 0.0).
8. **The registry agent's `setup.sh` fails or does things we do not want.** It needs apt to install
   curl, and it does user- and global-level installs that conflict with the project rule. The custom
   `pcnsl_claude` bundle avoids this, but it is untested and needs its runtime baked into the task
   image.
9. **No turn or budget cap** in the registry Claude agent, so cost can run away. Keep
   `--concurrency 1` and `[agent] timeout_sec` tight for pilots.
10. **Hosted Tracker version drift.** The hosted Tracker may predate features read here: separate
    verifier, artifact carry, `exclude`. The oracle run is the check.

## Open questions only the lead or a logged-in session can answer

- Can this login act for `hackathon-neuronetwork-b91c517178`? Is Modal already configured there, and
  is it the default?
- Which secrets and agents already exist in the organisation? Have any runs been made by teammates?
- Which Anthropic and OpenAI model IDs do the hackathon credits cover?
- What are the Modal credit amount and plan (GPU concurrency), and is GPU allowed at all?
- Are there an organisation run cap and a hosted `DATASET_TASK_UPLOAD_MAX_BYTES`?
- Does the hosted Tracker's version support separate verifiers and allowlisted agent egress on
  Modal? Answer this by experiment (steps 5-6).
- Does the hosted Tracker keep files under `/logs/verifier` beyond `reward.json` and stdout?
