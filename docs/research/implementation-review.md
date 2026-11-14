# Runner/exporter review and acceptance checks

Final review status, 2026-11-14: **all identified implementation fixes have been applied and the acceptance tests pass.** The final local suite ran 60 tests: 59 passed and one numerical test was skipped for its local dependency; that numerical test was included in FAC's separately passing 10/10 audit/baseline suite. Sixteen tasks passed final SDK packaging checks. Root/container verifier execution and hosted Valkyrie execution remain pending. Preserve frozen runs and historical manifests; apply future source changes only between versioned runs.

All 12 new local model attempts passed, including 10 frozen attempts and two exploratory endpoint attempts. Strict replay under the final resource limits passed 10/10 frozen programs and 40/40 fixtures. See the [pilot report](../../results/20261114-repair-pilots/REPORT.md), [strict replay record](../../results/20261114-repair-pilots/strict-replay.json), [16-task package validation](../../results/20261114-repair-suite-v2-packaging/validation.json), and [FAC verification](../../pcnsl/results/20261114-hosted-release/baseline-validation.json). No frontier failure is established.

The historical findings and initial red-test record below are retained to explain the corrections. They are not outstanding implementation defects. The review regressions use mocks and temporary files, with no model/API calls or credential reads.

## Scope and current good evidence

The runner persists private cases and public prompts, records requested/observed model IDs, and replays submissions against hidden inputs. The exporter keeps fixtures and oracle outside the Docker build's public workspace. Controls distinguish valid and flawed programs, reject visible-answer hardcoding, and check non-root hidden-file separation. The final evidence above replaces the intermediate 39-test/12-package counts. These checks do not establish execution of the root/container path or hosted Valkyrie.

The initial independent review reproduced a replay-isolation failure being mislabeled as a semantic candidate using a mocked subprocess. The implementation now probes the verifier runtime, propagates bubblewrap infrastructure failures, detects source drift, distinguishes resource/invalid-submission/execution/mismatch outcomes, discloses aligned replay limits, and protects frozen oracle exports. The direct regression checks below now pass.

## 1. Replay timeouts: resource exhaustion, not scientific failure

**Historical defect, resolved:** `evaluate_program` recorded a fixture `replay_timeout`, but the original result path used only the Boolean replay outcome. A completed agent response could become `candidate_semantic_failure` despite exceeding the replay budget. The corrected path classifies replay timeout/resource-limit outcomes separately, with infrastructure precedence.

**Implemented rule:** Structured replay outcomes distinguish resource limits, invalid submissions, execution failures and output mismatch, with infrastructure errors overriding the candidate result. A timeout is evidence of performance at a particular budget, not automatically a scientific reasoning error. Per-fixture reasons remain inspectable; do not infer a specific resource cause from every nonzero exit.

**Acceptance:** `test_replay_timeout_is_resource_limit_not_semantic_failure` drives the real replay handler with a successful mocked runtime probe followed by `TimeoutExpired`, then drives `run_one` without launching a model. Infrastructure and genuine output-mismatch controls must retain their distinct categories.

## 2. Invalid submitted files versus broken verifier infrastructure

**Historical defect, resolved:** Submission-owned invalid files and size violations were recorded in the same infrastructure-error field as missing private fixtures or isolation failures.

**Implemented rule:** A dedicated submission-error path records explicit submission-contract violations under `submission_error`; missing private fixtures and runtime/isolation problems remain infrastructure errors. The regression controls verify the distinction. Do not classify arbitrary exceptions as submission errors merely because a submission was present.

The accepted implementation retains reward zero and normal verifier exit for infrastructure failures, with the distinction in `results.json`. The result aggregator must inspect that artifact and exclude/review outcomes with `infrastructure_error`; no platform-native infrastructure flag is claimed. Reward alone is not the scientific failure count. Verify artifact retrieval in the actual hosted output path before launch readiness is claimed.

**Acceptance:** The new test uses a harmless symlink to another file in its own temporary workspace; it must produce a submission error, not infrastructure error. A second test removes only the temporary export's private fixture file and must remain an infrastructure error. Neither test executes an attack or accesses host secrets.

## 3. Resource contracts aligned and disclosed

**Historical mismatch:** The original local replay allowed 20 seconds and 2 MB JSON output without explicit CPU/address-space limits. Exported verification used stricter limits. Final local replay and exported verification now disclose 8 CPU seconds, 12 wall-clock seconds, 512 MiB address space, a 2 MB file-write ceiling and 1 MB accepted JSON output. Workspace restrictions are stated in the versioned task contract. Agent wall time remains a separate configuration: historical local pilots used 600 seconds and the exported task allows 900 seconds.

**Options considered during review:**

- Align both paths around a shared, versioned limit specification and enforce/disclose it in both; or
- Retain separate configurations, disclose their exact values before the run, and report the results as distinct local/hosted experiments. Do not claim they are identical replications.

The aligned limits were applied to a separate strict replay: all 10 frozen submitted programs passed all 40 fixtures. Strict JSON rejects nonfinite constants and duplicate keys, and workspace entry limits are enforced/disclosed. Historical pilots retain their original 20-second/no-explicit-CPU-cap description. Final package v2 records the updated contract; historical manifests were not rewritten.

Public instructions now disclose replay limits. The passing regression derives CPU and memory limits from the exported verifier with mocked `setrlimit` and checks the instruction exposes those values without changing the test process's resource limits. Keep this disclosure consistent in future versions; a model-written alternative within the documented contract should not be rejected by an undisclosed constraint.

**Acceptance:** `test_exported_public_instruction_discloses_enforced_cpu_and_memory`; then independently rerun a reference and a valid submitted repair in both intended runtimes. Slow reference code is a task-design defect, not a frontier failure.

## 4. Export the frozen oracle, not today's reconstruction

**Historical defect, resolved:** The exporter preserved passed fixtures but reconstructed the solution from the current generator, allowing an archived case to acquire a different-version oracle.

**Implemented API:** `export_case(..., oracle_source=...)` accepts captured nonempty reference code without invoking the current generator. If omitted, the supplied case must match the current factory's same-variant case before export; drift is rejected. Current fresh-case callers remain compatible. An oracle SHA-256 accompanies the solution. The explicit-source caller remains responsible for executing that oracle against its frozen fixtures: a digest records identity, not compatibility.

**Acceptance:** `test_frozen_oracle_does_not_depend_on_current_generator` provides captured reference code while mocking the current generator to fail. The export must preserve that source and the original hidden fixtures. `test_implicit_oracle_rejects_archived_case_after_generator_drift` changes the current factory's protocol revision and requires an explicit rejection when the caller supplies the old case without its captured oracle. It is not enough to regenerate another passing case with the same numerical seed.

## Boundaries the implementation cannot claim yet

- Root/container execution remains untested. Privilege dropping for submitted replay is useful, but the grader/runtime remains trusted. Verify actual task-image content, mount timing, credentials, writable paths and agent privileges in the intended provider. Tests of the non-root fallback are not proof of root-path isolation.
- Public protocol documents specify the endpoint, geometry and statistical procedures. These tasks assess faithful implementation and repair across connected evidence; they do not demonstrate unprompted methodological discovery.
- Exact JSON outputs are graded; `findings.md`, publication prose and general clinical judgement are not presently adjudicated. Do not report them as measured dimensions.
- Seed/counterfactual replay gives within-family coverage, not independent held-out task-family evidence. Several fixture passes from one submitted program are not independent agent attempts.
- No existing all-pass model result becomes a failure because a harness concern was found. Keep earlier outcomes and explicitly version any regrading or exclusion.

## Regression checks and resolved historical record

```bash
python3 -m unittest discover -s tests -p 'test_repair_review.py' -v
```

These acceptance tests now pass after the implementation fixes. They use mocked model/subprocess interfaces and temporary task exports; no model calls, Docker service, accounts, global changes or paid work are needed. The historical failures were resolved rather than suppressed with `expectedFailure` annotations. Future source changes require fresh validation between versioned runs.

### Initial regression run — historical, now resolved

Executed the command above before applying live-source fixes: **8 tests, 3 passing, 4 assertion failures, 1 API error**. Passing controls were runtime-probe infrastructure classification, actual output-mismatch classification, and missing-private-fixture infrastructure classification. The failures reproduced replay-timeout misclassification, invalid-submission misclassification, missing public CPU/memory disclosure, and silent generator drift. The API error reflected the then-absent `oracle_source` keyword. This was an intentionally red acceptance run, subsequently resolved by the implemented fixes; no unexpected model invocation or runtime dependency was encountered.
