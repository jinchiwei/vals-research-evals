# Hosted oracle run 1: five scored families on Valkyrie (v2 exports)

Written 2026-11-14 by a Claude Code worker acting as platform operator (model: Claude Opus 5.5,
`claude-opus-5-5`). Authorised by the project lead: two fixes from `hosted-smoke.md`, a push of the five
scored families, and one oracle run on each. No model was run, no agent was installed, no provider,
secret or dataset was changed or deleted, nothing was published to GitHub, and no Git commit was made.
Evidence is in `exp/suite-hosted-oracle1/` (git-ignored). A scan of every fetched file for `sk-ant` found nothing.

## Summary

| Item | Result |
|---|---|
| Fix 1: benchmark Python on PATH | Done in `suite/core/export.py`. 7 new tests pass; full `tests/suite` gives 198 passed, 1 skipped. The new build-time check ran in all five Modal image builds and passed. |
| Fix 2: no-web agent | `agents/claude_code_noweb/` (`claude_code_noweb-v1.0.0`). It validates with the SDK. An offline CLI check shows that WebFetch and WebSearch are no longer offered. **Not installed.** |
| Dataset | **`suite/clinical-v1@1`**, tags `latest`, `oracle1`, digest `c755684595ed`, 5 tasks |
| Oracle run | `8ca063d3-ff52-4bd0-883f-4fc815e6e31a`, label `hosted-oracle1`. 5 of 5 tasks finished with no errors, and **all five rewards equal `oracle_expected_reward`**. Final score 48.51. |
| Network | The agent-phase allowlist **is enforced**. pypi.org, files.pythonhosted.org and example.com fail with `ENETUNREACH`; api.anthropic.com connects. DNS for public names still resolves. |

## Fix 1: `/opt/benchmark-venv/bin` first on PATH, interpreter named by absolute path

### Cause

The registry agent runs `bash -lc`. Debian's `/etc/profile` (in `python:3.12-slim`) resets `PATH` for
login shells, which drops the Dockerfile's `ENV PATH`. The old instruction said "`python3` on PATH =
`/opt/benchmark-venv`", which was false in that shell.

### Change (`exp/suite-hosted-oracle1/export.py.diff`)

- **New helpers.** `profile_snippet()`, `python_env_rule()`, `VENV_PYTHON`, `PROFILE_SCRIPT` and
  `PATH_CHECK_SHELLS`.
- **Dockerfile.** After the venv import check, the Dockerfile now adds:
  ```
  RUN echo 'export PATH="/opt/benchmark-venv/bin:$PATH" VIRTUAL_ENV=/opt/benchmark-venv' > /etc/profile.d/00-benchmark-venv.sh && chmod 0644 /etc/profile.d/00-benchmark-venv.sh
  RUN for s in 'bash -lc' 'bash -c' 'sh -lc' 'sh -c' 'env -i bash -lc' 'env -i sh -lc'; do p="$($s 'command -v python3')"; [ "$p" = /opt/benchmark-venv/bin/python3 ] || { echo "$s resolves python3 to $p" >&2; exit 1; }; done
  ```
  The build fails closed unless every one of those shells resolves the venv `python3`, with or without the
  image ENV. `ENV PATH` is unchanged, there is still exactly one pip line (the pilot runner parses it), and
  the data layer is unchanged.
- **instruction.md** (both per-case and cohort):

  > Use only the image's Python environment, `/opt/benchmark-venv/bin/python3` (packages: …). Call it by
  > this absolute path in `run.sh`; it is also first on `PATH` (login and non-login shells) here and in the
  > grader.

- **Verifier: unchanged.** `tests/test.sh` still runs `/opt/benchmark-venv/bin/python -I -B`. The runner
  still sets `PATH` explicitly (`runner.DEFAULT_PATH`), and the grader runs no login shell.

### Tests

New file `tests/suite/test_export_python_path.py` with 7 tests:

- the Dockerfile lines and their order;
- an emulated Debian `/etc/profile` (it resets PATH, then sources `profile.d`) under bash and dash: the
  snippet wins with and without the image ENV, and without the snippet the venv is lost;
- the build-check loop parses under `sh` and exits 1 with a message when the wrong interpreter is found;
- both instruction modes name the absolute path and no longer contain the old wording;
- `test.sh` and `DEFAULT_PATH` are unchanged.

Run with `~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite -q`: **198 passed, 1 skipped**
(the existing openpyxl skip).

**Hosted evidence.** All five images built on Modal with the check in place. A failing check would have
failed the build.

**Not yet observed.** The registry agent's own shell resolving `python3` to the venv. That needs an agent run.

### Re-export to `dist/suite-tasks-v2/<family>/<task-id>/` (`dist/suite-tasks/` untouched)

Each family's own `build_spec` was run with work folders in the session scratchpad. The script is a
13-line driver calling `export_task`, run with the `vals-suite` env.

- **Data read.** It reads the staged data under `/home/jkwei/data/vals-suite/<family>/`. Nothing there was
  written.
- **reg_resect specialist.** It was given the v1 export's stored `tests/specialist/` (outputs and
  runtimes), so the specialist was not re-run.

`diff -rq` of v1 against v2 shows only these differences:

| Family | Differences, v1 vs v2 |
|---|---|
| All five | `environment/Dockerfile`, `instruction.md` |
| ecg_ptbxl | Also `tests/lib/suite/families/ecg_ptbxl/build_task.py`. The source file gained a "SUPERSEDED" docstring note after the v1 export. It is a legacy builder the grader does not import. |

Every data, reference, specialist, grader and solution-pipeline file is byte-identical.

### Operator addition to `solution/solve.sh` (v2 only, not in the exporter)

A print-only egress probe block was appended to each v2 `solve.sh`. Its source is
`hosted-oracle1 egress probe` in `dist/suite-tasks-v2/*/*/solution/solve.sh`. It:

- runs under `timeout 90 … || echo` so it never fails the oracle, and writes nothing;
- reports the names of any proxy environment variables, then DNS, TCP :443 and HTTPS HEAD results for
  pypi.org, files.pythonhosted.org, example.com and api.anthropic.com.

Agents never see `solution/`. To ship the oracle without the probe, re-export.

### Checks on v2

| Check | Result |
|---|---|
| `check_no_leak` | All five pass |
| solution/ file hashes present in environment/ | none |
| `tests`, `solution`, `hidden` or `specialist` paths under environment/ | none |
| Licence and attribution files in environment/data | reg `LICENSE-DATA.md` (CC BY 4.0, RESECT citation); spleen `LICENSE-CC-BY-SA-4.0.txt` plus `ATTRIBUTION.md`; hc18 `LICENSE-DATA.md` (CC BY 4.0); ecg `LICENSE-DATA.md` (CC BY 4.0, PTB-XL citation); icu `LICENSE-DATA.md` (ODC-By 1.0, citations). **None was missing; none added.** |
| `exp/suite-platform-probe/check_taskconfig.py` | All `problems []`, separate verifier, agent allowlist `['api.anthropic.com']`, verifier no-network |
| `scripts/validate_exports.py` | "Validated and packed 5 tasks" (`v2-validation.json`) |
| Local `tests/grade.py` on `solution/pipeline` (family env, `--sandbox-root none`) | reg 0.6667, spleen 0.0, hc18 0.7590, ecg 0.0, icu 1.0. All equal the manifest. Wall times: 96, 156, 36, 13 and 54 s. |

## Fix 2: `agents/claude_code_noweb/` (prepared, not installed)

### What it is

This is the stock bundle (installed copy `exp/suite-hosted-smoke/agent-download/claude_code-v1.0.0`,
registry commit `3e47c50`) with only these changes (`exp/suite-hosted-oracle1/agent-noweb/stock-vs-noweb.diff`):

- **`collect_outputs.py`.**
  - `WebFetch` and `WebSearch` are removed from `--allowedTools`.
  - `--disallowedTools "WebFetch WebSearch"` is added.
  - `summary.json` records `"agent": "claude_code_noweb-v1.0.0"`.
- **`contract.yaml`.** `name: claude_code_noweb-v1.0.0`, and the `run_cmd` bundle path becomes
  `/bundle/claude_code_noweb-v1.0.0/`. The bundle root is the agent name, so a different `--name` at push
  would break `run_cmd`.
- **`README.md`.** A note at the top explaining the variant.

`setup.sh`, the model handling, the outputs and `agent_output_example/` are identical to the stock bundle.

### SDK validation (`.venv-valkyrie`, SDK 0.34.0; `agent-noweb/sdk-validation.txt`)

- `AgentContract.from_directory` passes.
- Every contract field except `name` equals the stock contract, including `allow_provider_tools false`,
  `egress_allowlist []`, no secrets and the same `defaults`.
- `run_cmd` differs only in the bundle path.
- `validate_kwargs(model=anthropic/claude-sonnet-5-5)` passes.
- `get_agent_zip_stream` packs 9 files under `claude_code_noweb-v1.0.0/`.
- The allowed tools are exactly the stock list minus the two web tools.

### Offline CLI check (`agent-noweb/offline-cli-toolset.txt`)

**Setup.** The local Claude Code 2.1.325 was started with each bundle's argv. It had a dummy key, a fresh
HOME, and `ANTHROPIC_BASE_URL=http://127.0.0.1:9`, so no request left the machine.

**Result.** The `init` event lists the tools offered:

| Bundle | Web tools offered |
|---|---|
| stock | WebFetch and WebSearch |
| noweb | neither; the other 26 tools are unchanged |

**Caveat.** The hosted `setup.sh` installs the latest Claude Code (unpinned), so the hosted version may differ.

### What installing would require (lead's decision; none was done)

There are three routes. All create an agent in the organisation's Tracker library.

1. **`valkyrie agent push agents/claude_code_noweb`** (no `--name`). It uploads the local folder through
   Tracker and creates or replaces the alias `claude_code_noweb-v1.0.0`. No GitHub is involved. This is the
   simplest route.
2. **`valkyrie run start --agent ./agents/claude_code_noweb …`.**
   - The CLI first pushes the folder under the contract name with `overwrite=False`, then starts the run.
     Source: `valkyrie/cli/run/start.py::_publish_local_agent`.
   - So it is an install plus a model run in one command, and it refuses if the name already exists.
3. **`valkyrie agent install <GitHub URL>`.** This needs the folder in a GitHub repository. Whether
   Tracker can read a private repository is unverified.

**Afterwards.**
- Verify with `valkyrie agent download claude_code_noweb-v1.0.0 -o <dir>` and `cmp` against `agents/claude_code_noweb/`.
- Run with `--agent claude_code_noweb-v1.0.0 --model anthropic/<id> -s ANTHROPIC_API_KEY anthropic-api-key`.
- Confirm in the trace that the `init` tools have no WebFetch or WebSearch, and that
  `server_tool_use.web_search_requests` is 0.

## Push

```
$ .venv-valkyrie/bin/valkyrie dataset push suite/clinical-v1 dist/suite-tasks-v2 --tag oracle1 --concurrency 2
✓ Created benchmark suite
✓ Created dataset suite/clinical-v1
✓ Uploaded seg-spleen-build-0001 (259,475,047 bytes)
✓ Uploaded reg-resect-build-0001 (509,426,721 bytes)
✓ Uploaded measure-hc18-0001 (30,157,789 bytes)
✓ Uploaded ecg-ptbxl-superdiag-0001 (155,147,749 bytes)
✓ Uploaded risk-icu-mortality-0001 (17,529,984 bytes)
✓ Published suite/clinical-v1@1: 5 task(s), 5 uploaded. Tags: latest, oracle1.
```

- **Totals.** 971,737,290 bytes in 8 min 19 s from teal.
- **Version.** `1  c755684595ed  5  latest, oracle1  2026-11-14 19:32:37 EST`.
- **Upload limit.** The 509 MB reg_resect upload was accepted, so the per-task limit is at least that.

## Oracle run

```
$ .venv-valkyrie/bin/valkyrie run start --agent oracle --dataset suite/clinical-v1@oracle1 --provider modal --concurrency 2 -l hosted-oracle1
│ Run ID:           8ca063d3-ff52-4bd0-883f-4fc815e6e31a
│ Dataset version:  suite/clinical-v1@1
│ Spend:            development · default · new_benchmark_generation
```

Fetched with:
- `run tasks`, `run task --format json` (per task), `run logs` (text and jsonl);
- `run fetch --format json`, `run results --path`, `run errors`, `run artifacts`, `run status`.

These are all in `exp/suite-hosted-oracle1/oracle/`, and `oracle-summary.json` collects them.

### Results

All five tasks ran in verifier mode `separate`, with verifier exit 0 and no task error. Times are in seconds.

| Task | reward | ran | valid | within_time | clin_acc | quality | vs_specialist | Expected | Match | Build | Agent | Eval | Wall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reg-resect-build-0001 | 0.6667 | 1 | 1 | 1 | 0.6667 | 0.3313 | 1.0 | 0.6667 | yes | 25.1 | 0.24 | 116.2 | 363 |
| seg-spleen-build-0001 | 0.0 | 1 | 1 | 1 | 0.0 | 0.4095 | 0.4362 | 0.0 | yes | 89.2 | 0.25 | 211.6 | 711 |
| measure-hc18-0001 | 0.7590 | 1 | 1 | 1 | 0.7590 | 0.4369 | 0.6092 | 0.759 | yes | 48.9 | 0.20 | 87.4 | 170 |
| ecg-ptbxl-superdiag-0001 | 0.0 | 1 | 1 | 1 | 0.0 | 0.9730 | 0.9903 | 0.0 | yes | 63.9 | 0.28 | 61.1 | 165 |
| risk-icu-mortality-0001 | 1.0 | 1 | 1 | 1 | 1.0 | 0.7451 | 0.9999 | 1.0 | yes | 78.5 | 0.22 | 151.2 | 437 |

Column notes:
- **Build** is `sandbox_build_duration` (the first build of each image).
- **Eval** is `evaluation_run_duration`, which includes start-up of the separate verifier sandbox.
- **Wall** runs from the task's start to its finish and includes queueing at concurrency 2.
- **Image size** is not reported anywhere in the CLI output.

### Headline values from the metrics summary

The metrics summary is the line the grader prints to verifier stdout; `metrics.json` itself is not among
the carried artifacts.

| Task | Gate | Pipeline time (median, s) | Runtime ratio vs specialist | Grading (s) |
|---|---|---|---|---|
| reg | – | 12.1 per case | 0.69 | 70.3 |
| spleen | – | 28.8 per case | 0.49 | 168.8 |
| ecg | `mi_operating_point` true, `calibration` **false**, `subgroup_gap` true; gate_fraction 0.667; specialist 1.0 | 3.1 for the cohort | 0.84 | 9.8 |
| icu | all four parts true; gate_fraction 1.0 | 12.7 | 0.56 | 17.2 |
| hc18 | – | not available | not available | not available |

For hc18, the platform cut the stored `verifier_output` at about 16 kB inside the per-case failure list, so
the summary line is not visible. Its rewards are in the table above.

### Comparison with the local run

- **Rewards.** All seven keys equal the local v2 grading for reg, spleen, hc18 and ecg.
- **risk_icu quality** was 0.74505 hosted against 0.74512 locally. It is a small numeric difference in
  the cohort metric between machines, and the reward and every gate part are the same.
- **Pipeline timing.** Pipeline times on Modal (4 CPU) were well inside every limit. For example, ICU took
  12.7 s of its 300 s limit, against 141 s on the loaded teal earlier.

### Run totals

- **Score.** `final_score` 48.51, which is the mean `reward` × 100.
- **Duration.** From 00:32:54Z to 00:45:17Z UTC, 12.4 min.
- **Artifacts.**
  - One `workspace/output.tar.gz` per task: 4.2 kB (reg), 7.5 kB (spleen), 2.4 kB (hc18), 4.9 MB (ecg) and
    1.6 MB (icu).
  - Plus `suite.json`.
- **Platform.** Executor `git-06cbc4f8bcb4-136bf000429fbfee`, protocol 7, spend type `development`.

## Network enforcement (settled for the agent phase)

All five oracle agent-phase sandboxes, configured with `[agent] network_mode = "allowlist"` and
`allowed_hosts = ["api.anthropic.com"]`, logged the same result:

```
EGRESS_PROBE proxy_env_set []
EGRESS_PROBE pypi.org {'dns': '151.101.x.223', 'tcp443': 'ERR OSError: [Errno 101] Network is unreachable', 'https': 'ERR URLError: …Network is unreachable'}
EGRESS_PROBE files.pythonhosted.org {… same …}
EGRESS_PROBE example.com {… same …}
EGRESS_PROBE api.anthropic.com {'dns': '160.79.104.10', 'tcp443': 'ok', 'https': 404, 'server': 'cloudflare'}
```

**Blocked.** Public hosts are blocked at the network layer (immediate `ENETUNREACH`, no proxy variables
set), so pip, curl and Python cannot reach PyPI or the web.

**Allowed.** The model API is reachable.

**Remaining channels.**
- **DNS.** Public names still resolve inside the sandbox. DNS lookups are a possible low-bandwidth side
  channel, though not a way to download packages or data.
- **Server-side web tools.** WebSearch and WebFetch remain reachable through api.anthropic.com for the
  stock agent. Fix 2 addresses this.

**Not tested here.**
- The verifier's `no-network` mode: the probe ran only in the agent phase.
- Whether another host that shares an IP with api.anthropic.com would be reachable.

## Cost

| Item | Cost |
|---|---|
| Model API | $0. No model was run. |
| Modal | **Not reported by Valkyrie**: `run fetch`, `run results`, `run task` and `run status` have no cost field. The `task_breakdown` credit fields are all null, and the spend type is `development`. |

Visible sandbox time in `sandbox_run_duration` summed to about 667 s across the five tasks, plus about
306 s of first image builds. The Modal dashboard is needed for actual cost. No estimate is given here.

## What remains unverified, and what blocks agent runs on the five tasks

1. **No-web agent not installed.** The lead must choose one of the three routes above. Until then the only
   installed agent is the stock `claude_code-v1.0.0`, which offers WebSearch and WebFetch.
2. **Fix 1 has not been seen from inside an agent run.** The build check proves that `bash -lc` resolves
   the venv in the image. The first agent run should confirm that the agent's Bash tool sees
   `/opt/benchmark-venv/bin/python3`.
3. **No spending cap in the stock or no-web agent.** Neither bundle has a turn or budget limit. Use
   `--concurrency 1`, rely on the task `[agent] timeout_sec` (1800–3600 s), and watch costs per trace.
4. **Verifier no-network, CPU and RAM actually granted, and image sizes** are still not visible.
5. **hc18 verifier stdout is truncated** by the platform. If the full `metrics.json` is wanted for hosted
   runs, it would have to be carried or printed more compactly. That is an exporter change, not made here.

Nothing found here blocks agent runs. The tasks build, grade and reproduce the expected oracle rewards on Modal.
