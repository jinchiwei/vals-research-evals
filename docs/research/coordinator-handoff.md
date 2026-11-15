# Handoff to Neo Claude (teal t2), 2026-11-14

Repo: `/mnt/c/Users/jwei/arcadia/repos/vals-research-evals`, private `jinchiwei/vals-research-evals`, branch main, last committed HEAD `7811c8f`. **This round's code/results/docs are uncommitted and mostly untracked.** No commit/push was attempted while workers owned files. Preserve human Git identity `jinchiwei <mrjinch@gmail.com>`; no AI attribution trailers.

## Current direction

Jin directly steered this chat toward segmentation and quantitative brain-imaging tasks, with genetics optional. Your broader healthcare-suite coordination request is received. Fold the existing `pcnsl/` modules into `suite/` through adapters; don't duplicate the measurement/label logic. Current scope explanation: `docs/research/imaging-suite-scope.md`. Exact official prompt: `docs/research/hackathon-prompt.md`. Jin must personally write the opening README overview paragraph.

Familiar metrics are appropriate; the evaluated system must be the frontier **agent completing a task**, not merely a specialist model we run ourselves. A supplied-tool reproduction task and independent segmentation generalization are different claims. The current genetic experiments do not demonstrate a robust frontier-specific predictive gap.

## Workers and ownership

| Worker | Status / scope |
|---|---|
| teal `t1b`, name `prediction-harbor`, Opus 5.5 high | **Done, awaiting Neo.** Owns `pcnsl/prediction_export.py`, `prediction_aggregate.py`, `prediction_permutation.py`, `imaging_eval.py`, their tests, corresponding research docs and integration review. Latest imaging unit-inheritance fix complete; reported to both coordinators. |
| teal `t1c`, name `pcnsl-harness`, Opus 5.5 high | **Done, awaiting Neo.** Owns `agents/pcnsl_claude/`, `tests/test_pcnsl_agent.py`, `docs/research/pcnsl-agent.md`. See bounded harness below. |
| SCS `t8`, Neuronetwork Claude, self-reported Opus 5.5 | Versa discovery/client complete; segmentation report complete. IRF4 report exists; root requested two factual corrections, pending final acknowledgment. Read/report location below. No new model calls requested. |
| Codex `prediction_data` subagent | **Done, ownership released to Neo.** Extractor, data/geometry/unit audits, aggregate artifacts. It sent final handoff directly to t2. No jobs remain. |
| Neo's earlier implementation | `prediction_eval.py`, its tests and protocol complete. That earlier session identified itself as Fable 5.2, not Opus; keep model provenance honest. Root subsequently fixed feature naming to preserve all 439 legitimate descriptors. |

Use `hc send t1b ...` / `hc send t1c ...` here. For SCS use **teal-initiated** `ssh scs 'hc send t8 ...'`. Do not establish a new SCS→teal connection. The two local workers were created with parent t18; don't assume they survive closing that terminal, although all assigned artifacts are now written.

## Completed scientific evidence

- Hosted public archive verified: 16,659,458,958 bytes, SHA256 `4a45cbad0eee0cd7a3e6827c866f4041aeafb641a85ba6bed6304e3ce311138f`; 150 imaging patients, 64 with genomic records. FAC DS6 root below.
- Extractor: 64 unique genomic patients, **439 features** (438 imaging + sex), ten genes meeting ≥5 per class. No age: date-shift semantics unverified. `pcnsl/results/20261114-prediction-data/` contains catalog and provenance. No texture matrices invented; released radiomics are shape/first-order.
- Conventional fixed 5-fold controls, all ten eligible genes, all features and sex-only: FAC job **3067848 completed 0:0**. Results `pcnsl/results/20261114-prediction-baselines/`.
- Real TabPFN v2.5 cached checkpoint, package 8.0.2, CPU two threads, offline: SCS `vals-tabpfn-v1` / `t1n` completed exit 0. Five-fold full-feature AUROC: **MYD88 .420, CD79B .386**. Matched LR: **.562, .347**. `pcnsl/results/20261114-tabpfn-pilot/` records exact checkpoint hash/version and fold metrics.
- Direct prediction: **four** real Versa requests, SCS `vals-prediction-v1` / `t1m` completed exit 0. Fixed fold 0, 13 test patients, all 439 features. GPT-5.2 high AUROC **MYD88 .567, CD79B .361**. Opus 5.5 high failed the frozen response-format rule on both; an aggregate-only post-hoc diagnostic found one valid JSON block each, giving **.400/.403**. Keep strict failures and diagnostic scores distinct. No agent tools in these requests. `pcnsl/results/20261114-versa-pilot/`.
- The same fold's TabPFN AUROC is MYD88 .433 / CD79B .639; compare like-for-like, not single-fold vs pooled scores. Tiny-fold rankings are unstable.
- Fixed LR label-permutation null: FAC job **3067976 completed 0:0**, 199 permutations/gene. Higher-AUROC p: **MYD88 .27, CD79B .94**; lower-Brier p: **.395, .985**. `pcnsl/results/20261114-permutation/result.aggregate.json`. This calibrates LR only, not TabPFN/LLMs/agents. Two genes × two metrics, unadjusted.
- Old **12/12 synthetic code-repair passes** remain separate historical controls. They are not mutation-prediction or imaging-agent results.

## Imaging data and scorer: important real findings

- FAC job **3068002 completed 0:0**: 150 patients, 1,200 images, 300 masks; all 1,200 mask/image geometry pairings match. All 300 masks finite nonnegative integer labels, no empty masks; 157 binary, 143 multi-instance.
- **All mask headers have unknown spatial units.** Paired ADC images have mm spatial units and matching grids. Use the new `imaging_eval.load_mask_with_reference(mask, same_space_ADC)` to inherit units explicitly with provenance. Never assume mask units silently.
- ADC dictionary says **raw units**; all audited ADC scaling is slope 1/intercept 0. Spatial mm and header scaling do not prove ADC mm²/s. Report image-native ADC measurements.
- Count distinct positive supplied labels separately from 26-connected components. They need not agree.
- `pcnsl/imaging_eval.py`: Dice, volume/error in mL, lenient any-overlap lesion detection with stated limitations, components, distinct labels, ADC-native mean/median/p5, strict measurement grader, NIfTI validation and reference-unit inheritance. **Scorer prototype only; no real imaging-agent run or specialist segmentation inference yet.**
- Three development patients frozen before imaging-agent results, seed 20261114. Private manifest on FAC: `/mnt/fac/CX500002_DS6/jkw/vals-research-evals/imaging-data-20261114/development-manifest.private.json`, SHA256 `824b40597664f4f776e1977020dda0b08b1334bfb71a426574be9d7b12f32042`. Keep it there. Aggregate audit: `pcnsl/results/20261114-imaging-data/`, details `docs/research/imaging-task-data-audit.md`.
- Public PyALFE source identifies candidate tools: Dataset500_FLAIR fold 4 (FLAIR); Dataset503_Enhancement fold 0 (T1 + T1Post), checkpoint_final.pth. Exact release-generating weights, annotation/edit protocol and training overlap remain unverified. Use public/Jin-owned sources only; do not inspect other users' caches.

## IRF4 reconciliation (do not lose this)

SCS report: `/home/jiwei/arcadia/repos/vals-prediction-versa/IRF4-ENDPOINT.md`.
The original internal code labeled any listed IRF4 gene row positive; its extract lacked reported/classification/origin fields, and upstream filtering is undocumented. Public counts: **9 any-listed**, **5 reported**, **2 reported pathogenic/likely pathogenic**. Root's stricter endpoint was a different target and was not an exact reproduction of Jin's original task. Original strict40 also paired a tumor sample to the scan; public patient overlap is not established.

Root requested corrections before importing that report: (a) 9 any-listed minus 5 reported means **4 only-unreported**, not the report's erroneous 7; 7 is the overlapping count with any unreported row. (b) a uniform test-type string does not establish one assay per patient. Await Neuronetwork's corrected version. Retain sex-only controls: Jin's October vault review found strong sex association and no gene surviving multiple-testing correction. Do not silently broaden labels or equate any variant with a pathogenic/somatic alteration.

## Hard Valkyrie facts: proven vs read/unknown

| Item | Evidence / status |
|---|---|
| CLI environment | **Observed installed** in repo `.venv-valkyrie`, CLI 2026.11.12.2, SDK 0.34.0. No global Valkyrie install by this work. |
| Organization | User supplied `hackathon-neuronetwork-b91c517178`. Membership not verified. |
| Login | **Executed** `.venv-valkyrie/bin/valkyrie org list`; returned `Run valkyrie login`. No completed login here. |
| Credits/secrets | User earlier said not yet, prepare meanwhile. No organizer credits, Modal credits, hosted provider secrets or balances verified. Versa is separate UCSF access and was successfully used. |
| Hosted/local Valkyrie runs | **Zero.** No oracle run, no hosted frontier run, no Docker image build. No Docker/Podman daemon available in inspected teal environment. |
| Task/agent packaging | **Executed successfully** SDK task validation/packing, pinned Tracker TaskConfig parsing, synthetic grader tests, agent contract validation/bundling. These prove packaging, not execution. |
| Resource limits | Our task requests: 2 CPU, 4096 MB RAM, 4096 MB storage, agent 1800 s, verifier 120 s. **Requested, not provider-verified limits.** GPU support, availability, quotas and maximum CPU/RAM/time unknown. |
| Upload/image size | **Read in pinned source** `services/tracker/src/tracker/config.py`: default task-upload max 4,294,967,296 bytes; agent-upload max 1,073,741,824 bytes. Hosted overrides unknown. These are upload archive limits, **not a verified Docker image-size limit**. |
| Network | No-network / allowlist settings validate in source/schema. **Modal enforcement and exact harness host list untested.** Public data can be looked up if internet is open; do not score an unrestricted task. |
| Hidden verifier | Pinned source `1fe5c33...` supports separate verifier sandbox, tests uploaded only there, carry `/workspace/output`. SDK/schema tested; **hosted isolation unproven**. Marker-based fail-closed checks are only heuristics. Oracle first. |
| Cost | No measured Valkyrie/Modal cost per run. Versa token usage recorded, not actual invoices. Published lab pricing is not a verified current bill. |

`docs/research/prediction-harbor.md` and `prediction-integration-review.md` provide exact source paths/limitations. Genetic task exporter and OOF aggregator are implemented. Imaging Harbor packaging is **not implemented yet**.

## Environment-only Claude harness

`agents/pcnsl_claude/` is prepared and SDK-validated, **unbuilt/unrun**. Stock registry setup performs user/system installation, so don't run it unchanged. Our image recipe places Python dependencies in `/opt/benchmark-venv` and Node/Claude in `/opt/agent-env`; install step only checks prebuilt runtime. CLI 2.1.325, high effort, reported budget cap USD5, one attempt/no retries, process timeout 1740 s; no persisted session or external MCP, WebFetch/WebSearch disallowed. **No max-turns flag exists in inspected CLI, so 30 turns is not enforced.** Provider hard billing ceiling is not proven. Mutable FROM tags need digests; npm layout, root sandbox flag and actual API allowlist need smoke testing. Logs can contain patient data.

## Data boundaries

- Current operating rule and repo AGENTS.md: patient rows/images, original identifiers, dates/free text, private crosswalks, row-containing prompts, model-response prose, per-patient predictions and real task folders stay on FAC/SCS. Git/teal get code, schemas, aggregate metrics and hashes.
- **Observed exception within the authorized model experiment:** sanitized numeric public-release rows were sent from SCS to the existing UCSF Versa endpoints. This does not establish permission/readiness for arbitrary hosted task images or new third-party endpoints.
- No PCNSL image/row was uploaded to Valkyrie, Modal, GitHub or a public artifact store. **Do not assume PCNSL can now be embedded in a hosted image.** Resolve this boundary with Jin before an actual hosted patient-data transfer; prepare concrete sanitized artifacts/terms first.
- Official AWS registry lists CC BY 4.0. The actual archive has no bundled license/README; exact acquisition terms and image sanitization/redistribution readiness have not been fully verified. License attribution is separate from patient-metadata checks. DICOM/sidecar JSONs contain identifiers/dates; do not include them. NIfTI text/extensions need scrubbing before any model-facing export.
- Automatic approval review rejected exporting even regex-redacted response prose from SCS, citing this boundary. Root **did not bypass it**: only schema-valid-block counts and aggregate diagnostic scores were computed on SCS and returned. Raw prose stays there.

## Paths, verification, next actions

- FAC archive root: `/mnt/fac/CX500002_DS6/jkw/data/ucsf-pcnsl/hosted-v1.0-20261114/extracted`.
- Private numeric dataset FAC: `/mnt/fac/CX500002_DS6/jkw/vals-research-evals/prediction-data-20261114/dataset.private.json`.
- SCS work root: `/home/jiwei/arcadia/repos/vals-prediction-versa/`; private dataset `private-pilot-v1/dataset.private.json`, frozen calls `run-v1/private/`, offline TabPFN `tabpfn-v1/`; never bulk-copy these folders to teal.
- SCS verified model runtime: `/data/rauschecker1/jkw/envs/autofeeder/bin/python`; TabPFN runtime `/data/rauschecker1/jkw/envs/cph/bin/python -I -S`, with runner inserting only its own conda site-packages to avoid unrelated startup hooks. Checkpoint path/settings in `docs/research/versa-discovery.md`.
- Last root integrated test run: **193 tests, OK, 1 skip** with `PYTHONPATH=/tmp/vals-prediction-deps python3.12 -m unittest discover -s tests -q` outside nested sandbox. Later unit-inheritance tests increased count; worker: imaging 21 pass/1 nibabel skip, custom harness 16/16 via `.venv-valkyrie`. The temporary dependency directory predates Jin's new rule; **any new install must use an actual virtualenv/conda environment**. FAC already has nibabel for real loader verification.
- No remote experiment still running. Data worker has finished copying aggregates; t1b/t1c are available to Neo. SCS only owes IRF4 report corrections.
- Suggested immediate next: verify imaging loaders on the frozen real development cases; choose clear measurement/segmentation task contracts and a specialist-tool baseline; implement imaging Harbor packaging; settle data-hosting boundary and verify login/provider/oracle/egress before scored hosted runs. Don't expand genetic API calls on weak evidence.
- Deck: historical `results/pcnsl-frontier-deck/PCNSL_FRONTIER.pptx` is **not updated for these real results or the expanded suite**. All deck authoring must be Claude, using `/home/jkwei/arcadia/superstack/skills/build-pptx/SKILL.md`; use Opus 5.5 high where possible. Wait until scope/results stabilize.
- Preserve existing experiment artifacts and failures. Review/stage intentional files after all ownership is released, test affected modules, then commit/push with human-only attribution. Root is handing off rather than starting further work, per the request to conserve Codex usage.
