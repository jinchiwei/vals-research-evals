"""Publish aggregate evidence from the bounded local repair pilots; no raw traces."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "pilot-dev-v1": "Exploratory endpoint development; generator changed during execution",
    "pilot-dev-v2": "Frozen claims/geometry development",
    "pilot-integrated-dev-v1": "Frozen integrated development",
    "pilot-integrated-valid-v1": "Frozen integrated clean control",
    "pilot-integrated-heldout-v1": "Frozen integrated held-out seed 101",
}


def main():
    out = ROOT / "results/20261114-repair-pilots"
    out.mkdir(exist_ok=True)
    attempts, missing = [], []
    for name, description in RUNS.items():
        source = ROOT / "exp/20261114_pcnsl-frontier-suite" / name / "summary.json"
        if not source.exists():
            missing.append(name)
            continue
        result = json.loads(source.read_text())
        result["run_description"] = description
        result["snapshot_status"] = ("Exploratory only: no immutable case snapshot; generator changed mid-run."
                                     if name == "pilot-dev-v1" else "Private case and source snapshots retained.")
        (out / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        for row in result["results"]:
            attempts.append({"run": name, "description": description,
                             "frozen": name != "pilot-dev-v1", **row})
    frozen = [r for r in attempts if r["frozen"]]
    passed = sum(r["classification"] == "pass" for r in attempts)
    frozen_passed = sum(r["classification"] == "pass" for r in frozen)
    finished = not missing and len(attempts) == 12
    summary = {
        "schema_version": 1, "hosted_valkyrie_run": False,
        "data": "synthetic counterfactual fixtures only; no patient records sent to models",
        "attempt_count": len(attempts), "passed_attempts": passed,
        "frozen_attempt_count": len(frozen), "frozen_passed_attempts": frozen_passed,
        "frozen_fixture_replays": sum(r["replay"]["total_fixtures"] for r in frozen),
        "missing_runs": missing, "bounded_round_complete": finished,
        "demonstrated_frontier_failure": False,
        "decision": "Retain passing tasks as controls; no demonstrated frontier gap."
                    if passed == len(attempts) else "Inspect candidate failures before scientific attribution.",
        "claude_cli_usage_estimate_usd": round(sum(r.get("usage_estimate_usd") or 0 for r in attempts), 6),
        "usage_note": "CLI estimates are not billing statements; Codex uses the existing ChatGPT login.",
        "attempts": attempts,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# PCNSL repair pilots: evidence and decision", "",
        f"**{passed}/{len(attempts)} local agent attempts passed.** "
        f"Of these, {frozen_passed}/{len(frozen)} have frozen private case/source snapshots. "
        "No frontier-model failure has been demonstrated in this round.", "",
        "These are local isolated CLI experiments, **not Valkyrie runs**. "
        "Both backends were configured at high effort: response-confirmed `claude-opus-5-5`, "
        "and request-pinned `gpt-6-astra` (the Codex CLI did not emit a response model identifier).", "",
        "| Experiment | Model | Outcome | Hidden fixtures | Seconds |",
        "|---|---|---|---|---|"]
    for row in attempts:
        replay = row["replay"]
        label = row["family"] + (" / clean" if row["variant"] == "valid" else " / flawed")
        if "heldout" in row["run"]:
            label += " / held-out 101"
        if not row["frozen"]:
            label += " / exploratory"
        lines.append(f"| {label} | {row['backend']} | {row['classification']} | "
                     f"{replay['passed_fixtures']}/{replay['total_fixtures']} | {row['elapsed_seconds']} |")
    lines += ["", "## Interpretation", "",
        "The initial hypothesis was that executable repository repair would expose errors hidden by "
        "simple answer scoring. Both models repaired the separate endpoint, inference and geometry tasks. "
        "We then combined endpoint construction, selected scans, transitive patient identities, model-artifact "
        "ancestry, regenerated permutation nulls, multiplicity correction and manuscript reconciliation. "
        "The integrated development trial also passed, so the frozen version proceeded to a valid control "
        "and a new seed without further task or prompt tuning.", "",
        "The protocol supplies the scientific rules. The measured capability is faithful implementation "
        "and repair across connected evidence, not autonomous methodological discovery. `findings.md` and "
        "general clinical judgement are not graded. A valid control is scored on preserved behavior; "
        "textual edits alone are not a regression.", "",
        "**Keep the harness and passing controls; do not pitch this version as an established frontier-failure "
        "benchmark.** The next candidate should require expert-adjudicated research decisions from genuine "
        "evidence, with a clear task contract but less procedural scaffolding. Freeze that as a new development "
        "version. Do not turn these held-out results into tuning data and retain the held-out label.", "",
        "## Evidence boundaries", "",
        "- Four hidden fixtures are reruns of one submitted program, not four independent agent attempts. "
        "They contain new cohorts and an order counterfactual within the same task family.",
        "- The two endpoint attempts are exploratory: their generator changed while the run was active. "
        "They are excluded from the frozen denominator rather than silently reconstructed.",
        "- Model budget was 600 seconds per attempt; Claude's configured usage-estimate cap was $5. "
        "Historical local replay used 20 seconds per fixture, a 2 MB output limit and no explicit CPU/address-space cap. "
        "Subsequent stricter replay is reported separately; it does not rewrite these manifests.",
        "- Infrastructure, budget exhaustion and invalid submissions require separate classification. "
        "A zero reward alone is not a scientific reasoning failure. See the implementation review.",
        "- Data acquisition/audit and fixed real-data baselines are separate experiments. These model inputs "
        "are wholly synthetic and do not validate clinical utility or mutation predictability.",
        "- Root/container verifier execution and actual hosted Valkyrie execution remain pending. "
        "Local SDK packaging is not platform execution.", "",
        "## Reproduction", "",
        "Aggregate manifests and results accompany this report. Private source/case snapshots, raw traces "
        "and submitted workspaces remain under `exp/20261114_pcnsl-frontier-suite/` on teal. "
        "`scripts/run_repair_pilot.py` creates a new immutable run directory and detects source drift. "
        "`scripts/summarize_repair_results.py` regenerates this report without new model calls.", ""]
    if missing:
        lines += ["**Pending:** " + ", ".join(missing), ""]
    (out / "REPORT.md").write_text("\n".join(lines))
    if finished:
        (out / "FINALIZED").write_text("Bounded model round complete; see REPORT.md and summary.json.\n")
    print(json.dumps({k: summary[k] for k in ["attempt_count", "passed_attempts", "frozen_attempt_count", "bounded_round_complete"]}))


if __name__ == "__main__":
    main()
