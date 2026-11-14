"""Replay frozen submitted programs under the final limits; never call a model."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repair_evals import compare
from scripts.run_repair_pilot import evaluate_program
from scripts.summarize_repair_results import RUNS


def main():
    rows = []
    for name in RUNS:
        if name == "pilot-dev-v1":
            continue  # No immutable case snapshot for the exploratory run.
        run = ROOT / "exp/20261114_pcnsl-frontier-suite" / name
        summary = json.loads((run / "summary.json").read_text())
        for original in summary["results"]:
            trial = run / (original["id"] + "-" + original["backend"])
            case_path = trial / "case_private.json"
            case = json.loads(case_path.read_text())
            replay = evaluate_program(trial / "workspace", case["hidden"], compare)
            rows.append({"run": name, "id": original["id"], "backend": original["backend"],
                         "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
                         "original_classification": original["classification"], "replay": replay})
    result = {"model_calls": 0, "hosted_valkyrie_run": False, "attempts": len(rows),
              "passed": sum(r["replay"]["passed"] for r in rows),
              "fixture_replays": sum(r["replay"]["total_fixtures"] for r in rows),
              "limits": {"wall_seconds": 12, "cpu_seconds": 8, "memory_mib": 512,
                         "accepted_json_bytes": 1_000_000, "file_write_bytes": 2_000_000},
              "runner_sha256": hashlib.sha256((ROOT / "scripts/run_repair_pilot.py").read_bytes()).hexdigest(),
              "rows": rows}
    target = ROOT / "results/20261114-repair-pilots/strict-replay.json"
    with target.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({k: result[k] for k in ["attempts", "passed", "fixture_replays", "model_calls"]}))
    if result["passed"] != result["attempts"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
