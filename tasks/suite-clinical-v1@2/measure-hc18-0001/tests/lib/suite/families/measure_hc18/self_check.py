"""Grader self-check on the real hidden cases: oracle -> 1.0; pixels, constant, slow -> 0.

Usage: python -I self_check.py DATA_ROOT [pipeline ...]
The slow pipeline runs on the first 5 hidden cases only (83 x 10 s timeouts would take 14 minutes);
that is enough to show within_time = 0 and reward = 0.
Writes per-pipeline reward/metrics under DATA_ROOT/selfcheck/ and an aggregate (no per-case data)
to split/self_check.json in the repo.
"""
import csv, json, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_hc18 import grader  # noqa: E402

HERE = Path(__file__).resolve().parent


def main(root: Path, names):
    hid = root / "staged" / "hidden"
    refs = hid / "references.csv"
    spec = root / "comparators" / "specialist_metrics.json"
    agg = json.loads((HERE / "split" / "self_check.json").read_text()) if (HERE / "split" / "self_check.json").exists() else {}
    for name in names:
        pdir = HERE / "pipelines" / name
        inputs, rf = hid / "inputs", refs
        if name == "slow":
            sub = root / "selfcheck" / "slow_subset"
            if sub.exists():
                shutil.rmtree(sub)
            (sub / "inputs").mkdir(parents=True)
            rows = list(csv.DictReader(open(refs)))[:5]
            for r in rows:
                shutil.copytree(inputs / r["case_id"], sub / "inputs" / r["case_id"])
            with open(sub / "references.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            inputs, rf = sub / "inputs", sub / "references.csv"
        res = grader.grade(pdir, inputs, rf, root / "selfcheck" / name, spec if spec.exists() else None,
                           extra_env={"HC18_ORACLE_REFS": str(rf)})
        m = res["metrics"]
        agg[name] = {"reward": res["reward"], "n_cases": m["n_cases"], "mae_mm": m["overall"]["mae_mm"],
                     "n_invalid": m["n_invalid"], "median_runtime_s": m["runtime_s"]["median"],
                     "n_timed_out": m["runtime_s"]["n_timed_out"]}
    (HERE / "split" / "self_check.json").write_text(json.dumps(agg, indent=1) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:] or ["oracle", "pixels", "constant", "slow"])
