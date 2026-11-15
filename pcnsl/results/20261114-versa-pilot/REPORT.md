# Real direct-prediction pilot

Four requests completed on SCS through UCSF Versa: Opus 5.5 high and GPT-5.2 high, each on the fixed fold 0 of MYD88 and CD79B. Each fold has 13 patients; MYD88 has 10 qualifying positives, CD79B has 4. All arms saw the same canonical 439 features. No retries occurred. This is not an agent-with-tools run or a hosted Valkyrie result.

| Gene | Model | Strict result | AUROC | Brier |
|---|---|---|---:|---:|
| MYD88 | claude-opus-5-5 | response_format_error | — | — |
| MYD88 | gpt-5.2-2025-12-11 | scored | 0.567 | 0.176 |
| CD79B | claude-opus-5-5 | response_format_error | — | — |
| CD79B | gpt-5.2-2025-12-11 | scored | 0.361 | 0.227 |

The strict parser required a single probability object, optionally in one code fence, without extra material. An aggregate-only diagnostic subsequently found exactly one schema-valid JSON block in each Opus response. Extracting that block gives MYD88 AUROC 0.400 / Brier 0.188 and CD79B AUROC 0.403 / Brier 0.217. **Those are post-hoc diagnostic scores, not replacements for the frozen primary format failures.** No response prose or individual predictions were transferred from SCS.

Each Opus request used 170,429 input tokens; each GPT request used 164,740. The preflight heuristic underestimated numeric-table tokenization (approximately 100,625). Both routes accepted the requests; no truncation or context rejection was reported. Exact usage, returned model IDs, source hashes and response-format codes are recorded in summary.aggregate.json.

Compare against the same fold of the cached TabPFN report, not its pooled OOF score. These tiny-fold values have coarse resolution and do not establish model rankings or a frontier-specific biological prediction gap. The agent workflow remains a separate Harbor task with tools, hidden labels and isolated verification.
