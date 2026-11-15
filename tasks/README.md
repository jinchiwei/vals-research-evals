# Tasks (Harbor format)

Every task that was run on Valkyrie, one folder per task, grouped by the Valkyrie dataset it was
pushed as. Each folder is the exported Harbor task **without its data**:

| Path in each task | What it is |
|---|---|
| `instruction.md` | What the agent is told: the clinical task, output format, units, limits, session length |
| `task.toml` | Harbor config: timeouts, resources, network (agent: model API only; verifier: no network) |
| `environment/Dockerfile` | The agent's image (scientific Python in `/opt/benchmark-venv`, no pretrained weights) |
| `solution/` | Reference solution (the oracle) used to check each dataset on Valkyrie before any agent ran |
| `tests/` | The verifier: `test.sh`, `grade.py`, the grading library in `tests/lib/`, and `task_config.json` (case IDs, limits) |

Left out, on purpose:
- `environment/data/`: the development cases the agent sees (public data; see below to rebuild).
- `tests/hidden/`: hidden cases and their reference answers. Publishing them would leak the benchmark.
- `tests/specialist/`: the specialist's stored outputs on the hidden cases.

| Dataset on Valkyrie | Task | Role | Family document |
|---|---|---|---|
| `suite/clinical-v1@2` | `reg-resect-build-0001` | scored | [reg_resect](../docs/research/suite/reg_resect.md) |
| `suite/clinical-v1@2` | `seg-spleen-build-0001` | scored | [seg_spleen](../docs/research/suite/seg_spleen.md) |
| `suite/clinical-v1@2` | `measure-hc18-0001` | scored | [measure_hc18](../docs/research/suite/measure_hc18.md) |
| `suite/clinical-v1@2` | `ecg-ptbxl-superdiag-0001` | control | [ecg_ptbxl](../docs/research/suite/ecg_ptbxl.md) |
| `suite/clinical-v1@2` | `risk-icu-mortality-0001` | control | [risk_icu](../docs/research/suite/risk_icu.md) |
| `suite/vessel-v1@1` | `seg-vessel-build-0001` | scored | [seg_vessel](../docs/research/suite/seg_vessel.md) |
| `suite/causal-v1@1` | `causal-satt-0001` | control | [causal_ate](../docs/research/suite/causal_ate.md) |
| `suite/report-label-v1@1` | `label-ptbxl-reports-0001` | excluded from scoring (worked example) | [label_ptbxl_reports](../docs/research/suite/label_ptbxl_reports.md) |
| `suite/hc18-keepworking-v1@1` | `measure-hc18-0001` | instruction test K (one added paragraph) | [hosted-keepworking1](../docs/research/suite/hosted-keepworking1.md) |
| `suite/hc18-clockcheck-v1@1` | `measure-hc18-0001` | instruction test K2 (K plus a clock check) | [hosted-clockcheck1](../docs/research/suite/hosted-clockcheck1.md) |

The OpenAI-network twins used for the Codex runs (`suite/clinical-openai-v1@1`,
`suite/vessel-openai-v1@1`) are identical to `suite/clinical-v1@2` and `suite/vessel-v1@1` except for
`allowed_hosts` in `task.toml` (`api.openai.com` instead of `api.anthropic.com`).

## Rebuilding the full tasks with data

The task generators live in `suite/families/<family>/`, with the shared exporter in `suite/core/`.
Download each dataset as its family document describes (all public, licences in the main README),
then run `scripts/export_suite_tasks.py` (the five clinical tasks) or the family's own export step.
This folder is regenerated from the exports by `scripts/publish_task_definitions.py`.
