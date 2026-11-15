# codex_noweb-v1.0.0

The stock registry agent `codex-v1.0.0` (vals-ai/public-agent-registry@3e47c50, `examples/codex-v1.0.0`) with web
search turned off, for the vals healthcare suite (round 4). Differences from the stock bundle:

- Web search off. Codex 0.167.0 defaults `web_search` to `cached`, and with `--sandbox danger-full-access` (the stock
  flag) it resolves to `live`. Its web search is an OpenAI hosted tool reached through `api.openai.com`, so the task
  allowlist cannot block it. `collect_outputs.py` passes `-c web_search="disabled"` and `setup.sh` also writes
  `web_search = "disabled"` to `~/.codex/config.toml`.
- `setup.sh` pins `@openai/codex@0.167.0`, the version the stock "published at least 7 days ago" rule resolved to on
  2026-11-15.
- The contract `choices` add `gpt-6-astra`, `gpt-6.1-sol` and `gpt-6-luna` (slugs from Codex 0.167.0's
  `models-manager/models.json`).
- The contract `name`, the `run_cmd` and `uv sync` bundle paths and the `summary.json` agent name are
  `codex_noweb-v1.0.0` (the bundle root is the agent name, so push it without `--name`).

Everything else (model handling, reasoning-effort default, outputs, cost computation) is the stock agent. The stock
README follows.

---

# Codex-v1.0.0

Codex agent contract for Valkyrie. The wrapper installs the OpenAI Codex CLI, runs `codex exec --json` against the task prompt, and collects the streamed output into standard `/logs` artifacts.

## Configuration

- Secret: `OPENAI_API_KEY`
- Default model: `gpt-5.3-codex`
- Final output: `/logs`

Supported model choices are defined in `contract.yaml`.

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/jf/agent-checkpoint/examples/codex-v1.0.0
```

Download the agent, visit the [documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md) on **contract.yaml** if you would like to make any modifications.

```bash
valkyrie agent download codex-v1.0.0
```

Upload the agent after changes are made

```bash
valkyrie agent push codex-v1.0.0
```

Run a benchmark using codex as the agent, specify `--model <MODEL>` to change the underlying model that powers codex. Append to the contract or change it to allow any codex compatible model when running codex.

```bash
valkyrie run start --benchmark swebench --agent codex-v1.0.0 -s OPENAI_API_KEY <CLOUD_KEYNAME> --concurrency 10 --slice :10
```

## Output Files

The run writes:

- `summary.json`
- `metrics_total.json`
- `final_message.txt`
- `trajectory.jsonl`
- `raw_output.txt`

See [agent_output_example](agent_output_example/) for a sample output directory.
