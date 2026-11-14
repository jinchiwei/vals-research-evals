# PCNSL Frontier Research Evaluation Suite Implementation Plan

> **For agentic workers:** Use independent literature and implementation workers with separate file ownership. The user explicitly authorized implementation, experiments, subagents and an autoresearch workflow; proceed without a second launch confirmation.

**Goal:** Design a literature-grounded suite, obtain the hosted PCNSL release on FAC DS6, implement and test stronger executable research tasks, run bounded frontier pilots, and produce a reviewed deck with honest evidence labels.

**Architecture:** Keep the immutable hosted archive and all subject-level artifacts on FAC. Version code, schemas, scientific design, source citations and aggregate results in this private repository. Use synthetic counterfactual repair tasks for controlled pilot experiments until the release is inspected and model-facing extracts are explicitly sanitized. Reuse the existing isolated tool-agent harness and Harbor/Valkyrie task contract.

**Tech Stack:** Python, existing Claude CLI login and bubblewrap, FAC CPU data processing, GitHub private repository, user's autoresearch and build-pptx skills.

**Spec:** User request in this session: a comprehensive frontier-level failure-mode benchmark suite, literature review, slide deck, experimentation; hosted 16 GB PCNSL archive on FAC DS6. Public PCNSL release only for new real-data tasks, not internal research labels/features.

## Global Constraints

- Hosted archive goes under `/mnt/fac/CX500002_DS6/jkw/data/ucsf-pcnsl/`; signed URLs never enter Git or reports.
- No SCS-to-teal connection. No unrelated users' data/processes or original research modifications.
- Do not equate poor mutation predictability with an agent failure. Use executable ground truth, valid controls, fixed scoring, and adequate tool budgets.
- Record dataset hashes, model identifiers, prompts, seeds, source hashes, failures and rejected candidates. Infrastructure failures are not model failures.
- Freeze each evaluation version before held-out testing. Do not tune prompts/gold on held-out outcomes. No probability flipping.
- Deck author: Claude Opus 5.5, high effort, using Jin's build-pptx skill; no invented results or unsupported novelty claims.
- Human Git identity only; never add AI commit attribution. Raw logs, secrets and patient-level data remain untracked.
- This environment has no ScheduleWakeup tool. Run the research loop during the active session with durable state/STOP files; do not claim an unattended model scheduler is installed.

## Review Focus

1. Hosted v1.0 vs newer Box release preparation: no assumed identity or subject-number joins across versions.
2. Label absence, VUS, Not Detected, paired specimen dates and genomic ascertainment: define endpoints before fitting.
3. Hidden tests accidentally reading agent answers or mounting gold: execute independent verifier with filesystem separation.
4. Passing artifacts that hardcode visible cohort outcomes: test submitted functions on undisclosed generated cohorts and paired controls.
5. Scientific uncertainty and licensing claims: distinguish measured facts, authored counterfactuals, proposed extensions and unresolved checks.

## Tasks

- [x] Acquire archive on FAC DS6; verify SHA-256, byte count, ZIP CRC and safe extraction; inspect aggregate data inventory and release differences.
- [x] Review primary PCNSL/radiogenomics and frontier-agent evaluation literature; maintain source evidence tables and explicit novelty limits.
- [x] Specify 20+ failure modes across data/provenance, imaging, genomics, statistics, reproducibility and scientific reporting, with executable contracts and valid controls.
- [x] Implement three stronger repair-task families; prove reference and deliberately flawed controls behave as expected on independent hidden fixtures.
- [x] Run development pilots under capped time/usage budgets; classify semantic versus infrastructure failures; pivot only on development data.
- [x] Freeze a version and run held-out fixtures/agent trials; replay agent artifacts in network-isolated verification.
- [x] Build/validate Harbor/Valkyrie export for implemented tasks; report hosted execution separately.
- [x] Have Claude Opus 5.5 high author the branded deck from final evidence using build-pptx; verify figures and slides.
- [x] Save findings, limitations, next experiments and aggregate artifacts; commit/push reviewed files to the private repository.

## Bounded Research Loop

Initial axes: task family (endpoint/cohort repair, leakage/inference repair, imaging geometry/unit audit), valid/invalid paired variant, development seed vs frozen held-out seed, baseline vs repair agent. Prototype trials use the existing authenticated Claude frontier CLI. A second frontier backend is included only if available and independently isolated; otherwise record that coverage gap. Cap the initial round at 12 live tasks, $5 configured maximum usage estimate per task and 10 minutes per task; no model/provider account or billing changes.

Every iteration writes a hypothesis, input/source fingerprint, protocol, result, failure classification and keep/reject decision. Stop on the explicit STOP file, exhausted bounded queue, repeated infrastructure failures, or completion of the requested evidence package. Do not manufacture a failure if the agents succeed.

## Final evidence

The bounded round produced 12/12 passing local model attempts (10 frozen, two exploratory), with no demonstrated frontier failure. Strict replay passed 40/40 fixtures. The actual hosted archive and 63-patient fixed baseline are verified. Sixteen task packages pass the official SDK checks. Claude authored and visually reviewed the 25-slide deck with Jin's builder. Hosted Valkyrie and the root/provider verifier path remain deferred pending event access.
