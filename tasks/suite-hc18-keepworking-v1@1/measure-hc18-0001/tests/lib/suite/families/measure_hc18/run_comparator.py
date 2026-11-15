"""Run a specialist comparator on hidden cases through the grader (same clock and limit as agents).

Usage: python -I run_comparator.py DATA_ROOT NAME
Per-case outputs and runtimes -> DATA_ROOT/comparators/<NAME>/ (outside Git; the exporter ships them
under tests/ for the verifier). Aggregate only -> split/comparators.json.
"""
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_hc18 import grader  # noqa: E402

HERE = Path(__file__).resolve().parent
root, name = Path(sys.argv[1]), sys.argv[2]
hid = root / "staged" / "hidden"
out = root / "comparators" / name
res = grader.grade(HERE / "pipelines" / name, hid / "inputs", hid / "references.csv", out)
shutil.rmtree(out / "work", ignore_errors=True)
m = res["metrics"]
preds = {p["case_id"]: {"hc_mm": p["pred"], "seconds": p["seconds"]} for p in m["per_case"]}
(out / "outputs.json").write_text(json.dumps(preds, indent=1))
aggp = HERE / "split" / "comparators.json"
agg = json.loads(aggp.read_text()) if aggp.exists() else {}
agg[name] = {"reward": res["reward"], "overall": {k: v for k, v in m["overall"].items()},
             "by_stratum": {k: {"mae_mm": v["mae_mm"], "frac_within_tol": v["frac_within_tol"], "n": v["n"]}
                            for k, v in m["by_stratum"].items()},
             "by_hc_band": {k: {"mae_mm": v["mae_mm"], "frac_within_tol": v["frac_within_tol"], "n": v["n"]}
                            for k, v in m["by_hc_band"].items()},
             "worst_subgroup": {k: m["worst_subgroup"][k] for k in ("stratum", "mae_mm", "frac_within_tol")},
             "runtime_s": m["runtime_s"]}
aggp.write_text(json.dumps(agg, indent=1) + "\n")
choice = json.loads((HERE / "split" / "specialist_choice.json").read_text())["specialist"]
if name == choice:
    (root / "comparators" / "specialist_metrics.json").write_text(json.dumps(
        {"name": name, "quality": res["reward"]["quality"], "overall": m["overall"],
         "runtime_s": m["runtime_s"]}, indent=1))
