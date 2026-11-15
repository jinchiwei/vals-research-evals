# Versa client: status report (partial, 2026-11-14)

Written by the Claude session "neuronetwork" on scs (model: Claude Opus 5.5, `claude-opus-5-5`).
No commits, no pushes. No patient data was used. No worker was spawned.

## 1. Live calls already made (do not repeat)

| # | What | Model ID sent | Result |
|---|---|---|---|
| 0 | Catalog listing `GET {endpoint}/openai/deployments` | none, no model invoked | **HTTP 405 "Method is not allowed"**; the gateway does not expose a listing |
| 1 | health, `output_config.effort="high"` | `us.anthropic.claude-opus-5-5` | OK; reported `claude-opus-5-5`; stop `end_turn`; 18 in / 4 out tokens; 31.9 s |
| 2 | health | `us.anthropic.claude-sonnet-5-5` | OK; reported `claude-sonnet-5-5`; 18 / 4 tokens; 1.6 s |
| 3 | health | `us.anthropic.claude-haiku-5-5` | OK; reported `claude-haiku-5-5`; 18 / 4 tokens; 3.8 s |
| 4 | health | `gpt-5.2-2025-12-11` | OK; reported `gpt-5.2-2025-12-11`; stop `stop`; 11 / 4 tokens; 24.1 s |

- **Model calls used:** 4 of the 4 allowed.
- **Prompt for every call:** the synthetic text "Reply with exactly: OK", with `max_output_tokens=1024` and `max_retries=0`.

**Verified working, live, on 2026-11-14:**

- **Anthropic route:** `us.anthropic.claude-opus-5-5`, with `effort: high` accepted.
- **Anthropic route:** `us.anthropic.claude-sonnet-5-5`.
- **Anthropic route:** `us.anthropic.claude-haiku-5-5`.
- **OpenAI route:** `gpt-5.2-2025-12-11`.

For a two-deployment pilot I'd use `us.anthropic.claude-opus-5-5` (effort high) and `gpt-5.2-2025-12-11`. Those are the strongest verified model on each route.

**Not verified this session:** every other ID in `versa_client.py` (`ANTHROPIC_MODELS`, `OPENAI_MODELS`). That list is copied from the lab's shared file (`/data/rauschecker2/jkw/aria/dev/src/utils/versa_models.py`) and was not tested live.

**Deployment limits**
- **Rate limits and quotas:** not discoverable; the gateway returned no rate-limit headers that we read, and the listing endpoint is blocked (405).
- **Latency:** 1.6–32 s for a 4-token answer. The Opus 5.5 call took 32 s at high effort even for "OK". The client timeout defaults to 180 s; I'd raise it to 600 s for long payloads at 8,192 output tokens.
- **Prices published to us** (USD per 1k tokens, from the shared file):

| Model | Input | Output |
|---|---|---|
| Opus 5.5 | 0.0044 | 0.022 |
| Sonnet 5.5 | 0.0022 | 0.011 |
| Haiku 5.5 | 0.00011 | 0.00055 |

  GPT-5.2's price is not in the file.
- **Network:** Versa answers only from the UCSF network. Both scs and FAC are on it; FAC goes through its proxy, so the `https_proxy` variables must be set, as they are in a login shell.

## 2. Client

- **File:** `versa_client.py`. Standard library plus `anthropic` and `openai` (and `httpx` for the catalog call).
- **Tested environment:** `/data/rauschecker1/jkw/envs/autofeeder/bin/python` on scs (anthropic 0.115.1, openai 2.44.0).
- **Offline tests:** `tests/test_versa_client.py`, 14 tests, all passing, no network:

  ```bash
  /data/rauschecker1/jkw/envs/autofeeder/bin/python -m pytest -q tests
  ```

**Adapter for DirectLLMArm**

```python
from versa_client import load_env_file, make_llm_callable
load_env_file("~/.config/versa/credentials")   # AWS key pair (VERSA_AWS_* mapped to AWS_*)
load_env_file("~/versa_key.env")               # VERSA_API_KEY + endpoint for the OpenAI route
log = []                                       # one sanitized result dict per call (text, usage, latency, stop_reason)
llm = make_llm_callable("us.anthropic.claude-opus-5-5", effort="high",
                        max_output_tokens=8192, timeout_s=600, max_retries=0, log=log)
text = llm(payload_text)                       # raises VersaCallError on refusal / empty / API error
```

What the adapter guarantees:
- `max_retries=0` is the default, so one call is one billed request.
- Output is capped at the `max_output_tokens` you pass (8,192 here), with a hard ceiling of 32,000.
- Returned text is cut at `max_chars`. The default is 200,000 characters, and `log[-1]["truncated"]` is set when that happens; your plan to reject truncated responses should check that flag.
- The Anthropic route also reports `stop_reason == "max_tokens"` when output hit the cap.

**Logging:** `log` holds response text. Keep it in private run output only; never copy it into an aggregate report.

**Credentials:** read only from environment variables. `load_env_file` returns variable names, never values. Error text is scrubbed of credential values, `api-key` / `Authorization` / bearer headers, AWS key IDs and any 32+-character token-like string.

**Command line:**

```bash
cd /home/jiwei/arcadia/repos/vals-prediction-versa
PY=/data/rauschecker1/jkw/envs/autofeeder/bin/python
$PY versa_client.py models
$PY versa_client.py --env-file ~/.config/versa/credentials health --model us.anthropic.claude-haiku-5-5   # 1 billed call
$PY versa_client.py --env-file ~/versa_key.env call --model gpt-5.2-2025-12-11 --prompt-file p.txt --json
```

`--env-file` takes one file, so a single command line loads only one. The CLI route needs `AWS_*` for Claude models and `VERSA_API_KEY` for GPT models. Calling from Python with two `load_env_file` calls, as above, covers both routes.

**On FAC:** none of the FAC environments I checked has `anthropic` or `openai`. Copy the folder over and use any Python environment that has both packages; I have not installed anything. The credentials file exists on FAC too: scs's `50-versa-claude.sh` notes it uses the same key pair as FAC.

## 3. TabPFN (metadata only; nothing installed or run)

### Use this (scs, offline-capable)

**Environment:** `/data/rauschecker1/jkw/envs/cph`, `tabpfn 8.0.2`.

**Cached weights:** these checkpoints are already on disk, so nothing needs downloading.

- The cache folder is `$XDG_CACHE_HOME/tabpfn`, which on scs is `/data/rauschecker2/jkw/home-offload/xdg-cache/tabpfn`. That folder holds:
  - `tabpfn-v2.5-classifier-v2.5_default.ckpt`, 42,935,499 bytes, dated 2026-06-17.
  - `tabpfn-v2-classifier-finetuned-zk73skhh.ckpt`, the TabPFN v2 classifier default.
  - `tabpfn-v2.5-regressor-v2.5_default.ckpt`.
- An identical-size v2.5 classifier also sits in `~/.cache/tabpfn`.

**Pitfall:** this TabPFN version (8.0.2) defaults to **v3** (`settings.model_version = V3`). No v3 checkpoint is cached, so a plain `TabPFNClassifier()` would try a licence-gated download from Prior Labs / Hugging Face. Always pass `model_path` explicitly.

**Telemetry:** the package pings Prior Labs. A bare `import tabpfn` probe in this environment hung for over 5 minutes, and I stopped it. Telemetry is the likely cause; I did not confirm it. Set `TABPFN_DISABLE_TELEMETRY=1`.

**Invocation (not yet smoke-tested; do a one-row fit first):**

```bash
export TABPFN_DISABLE_TELEMETRY=1
export TABPFN_MODEL_CACHE_DIR=/data/rauschecker2/jkw/home-offload/xdg-cache/tabpfn
/data/rauschecker1/jkw/envs/cph/bin/python -I your_script.py   # prints a stray "cases with unprocessed exams: 525" line at startup; ignore it
```

```python
from tabpfn import TabPFNClassifier
clf = TabPFNClassifier(
    model_path="/data/rauschecker2/jkw/home-offload/xdg-cache/tabpfn/tabpfn-v2.5-classifier-v2.5_default.ckpt",
    device="cuda",          # or "cpu"; 64 rows x 439 features is small
    random_state=0)
```

**Not checked:**
- the v2.5 weight licence terms;
- whether the cached file loads under 8.0.2 without a licence check (the download-only licence path in `browser_auth.py` is not obviously triggered for a local `model_path`).

The smoke fit answers both.

### Earlier notes

**scs, usable now:**
- **Environment:** `/data/rauschecker1/jkw/envs/cph`.
- **Versions:** `tabpfn 8.0.2`, Python 3.12.8, torch 2.10.0, scikit-learn 1.8.0.
- **Use:** `/data/rauschecker1/jkw/envs/cph/bin/python -I -c "from tabpfn import TabPFNClassifier"`.
- **Superseded:** the cache and default-version questions are answered under "Use this" above. `~/versa_key.env` defines a `TABPFN_TOKEN`, a sign that a token was needed before.
- **Startup quirk:** this environment's Python prints the line "cases with unprocessed exams: 525" at startup even with `-I`, so ignore that line when parsing output.

**Precedent:**
- The PCNSL pipeline used TabPFN (a 6.4.1 local package in the earlier AGF work).
- The PCNSL tabular foundation-model sweep (`cnsl/dev/genet/exp/20261025_amr_review/tabfm_sweep/code/models.py`) ran in `/data/rauschecker1/jkw/envs/tabfm`. That environment has TabFM, TabICL, TabDPT, Mitra and LimiX-2, but no TabPFN.

**FAC:** no `tabpfn` package in any environment under `/mnt/fac/CX500002_DS6/jkw/envs/` (archive_bench, llm, neuronetwork, nn, nnvfm, nnviz, praria). No TabPFN checkpoint was found there either.

## 4. Segmentation (scope note only)

The PCNSL pipeline's masks came from **pyALFE's nnU-Net models**:
- environment `/data/rauschecker1/jkw/envs/pyalfe`;
- automatic masks dated 2025-08-12;
- one rater edited them afterwards.

**Training-overlap caveat:** pyALFE was developed in this lab on UCSF clinical MRI. Its training set may include patients in the UCSF PCNSL cohort, and so may overlap the public hosted release. I did not verify either way.

I did not locate the model weight files this session.

## 5. Data handling

- No patient data, prompt payload or patient-linked response was used, copied or logged by this work.
- This report contains only synthetic health-check outputs and metadata.
