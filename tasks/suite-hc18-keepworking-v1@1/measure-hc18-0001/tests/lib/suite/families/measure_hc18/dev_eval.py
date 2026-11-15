"""Score a pipeline on development cases only (for tuning). Usage: dev_eval.py DATA_ROOT PIPELINE_NAME"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_hc18 import grader  # noqa: E402
root, name = Path(sys.argv[1]), sys.argv[2]
r = grader.grade(Path(__file__).resolve().parent / "pipelines" / name, root / "staged" / "visible",
                 root / "staged" / "visible" / "references.csv", root / "dev_eval" / name)
m = r["metrics"]
print({k: (v["mae_mm"], round(v["frac_within_tol"], 3)) for k, v in m["by_stratum"].items()})
print("mean signed", m["overall"]["mean_signed_err_mm"], "median abs", m["overall"]["median_abs_err_mm"])
