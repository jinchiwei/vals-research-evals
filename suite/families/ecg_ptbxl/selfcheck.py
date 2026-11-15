"""Grader self-check: build reference pipelines and grade each on the real hidden set with grade.py.

    conda run -n vals-suite-ecg_ptbxl python suite/families/ecg_ptbxl/selfcheck.py \
        --root /home/jkwei/data/vals-suite/ecg_ptbxl [--only oracle,constant,...]

Pipelines (all go through the grader's own clock and strict parser):
  specialist     trained xresnet1d-style CNN (work/specialist_pipeline)
  simple         hand features + gradient boosting (work/simple_pipeline)
  oracle         hidden labels as 0/1 probabilities (cheats via a self-check-only env var)
  constant       development-set prevalence for every record
  overconfident  specialist ranking, logits multiplied by 5 (good ranking, bad calibration)
  too_slow       specialist outputs, but sleeps past the time budget first
  invalid_nan    specialist outputs with one NaN
"""
import argparse
import importlib.util
import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
_g = importlib.util.spec_from_file_location("ecg_grade", HERE / "grade.py")
G = importlib.util.module_from_spec(_g)
_g.loader.exec_module(G)

FAKE = r'''
import csv, math, os, shutil, sys, time
from pathlib import Path
mode, inp, outp = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
C = ["NORM", "MI", "STTC", "CD", "HYP"]
ids = [r["record_id"] for r in csv.DictReader(open(inp / "meta.csv"))]
def write(rows):
    outp.mkdir(parents=True, exist_ok=True)
    with open(outp / "predictions.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["record_id"] + C)
        for rid in ids: w.writerow([rid] + rows[rid])
def stored():
    return {r["record_id"]: [float(r[c]) for c in C] for r in csv.DictReader(open(os.environ["ECG_SELFCHECK_PROBS"]))}
if mode == "oracle":
    ref = {r["record_id"]: [float(r[c]) for c in C] for r in csv.DictReader(open(os.environ["ECG_SELFCHECK_REFERENCE"]))}
    write(ref)
elif mode == "constant":
    lab = list(csv.DictReader(open(os.environ["ECG_SELFCHECK_DEV_LABELS"])))
    prev = [sum(int(r[c]) for r in lab) / len(lab) for c in C]
    write({rid: prev for rid in ids})
elif mode == "overconfident":
    def sharp(p):
        p = min(max(p, 1e-6), 1 - 1e-6); z = 5 * math.log(p / (1 - p)); return 1 / (1 + math.exp(-max(min(z, 50), -50)))
    write({k: [sharp(v) for v in vs] for k, vs in stored().items()})
elif mode == "too_slow":
    time.sleep(float(os.environ.get("ECG_SELFCHECK_SLEEP", "620")))
    write(stored())
elif mode == "invalid_nan":
    s = stored(); s[ids[0]][1] = float("nan"); write(s)
'''


def make_fake(dirpath, mode):
    shutil.rmtree(dirpath, ignore_errors=True)
    dirpath.mkdir(parents=True)
    (dirpath / "fake.py").write_text(FAKE)
    (dirpath / "run.sh").write_text(f'#!/usr/bin/env bash\nset -euo pipefail\nexec python -I "$(dirname "$0")/fake.py" {mode} "$1" "$2"\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--only", default="specialist,simple,oracle,constant,overconfident,invalid_nan,too_slow")
    ap.add_argument("--n-boot", type=int, default=1000)
    a = ap.parse_args()
    work = a.root / "work"
    hidden = work / "hidden"
    sc = work / "selfcheck"
    probs = sc / "specialist" / "eval" / "out" / "predictions.csv"
    os.environ.update(ECG_SELFCHECK_REFERENCE=str(hidden / "reference.csv"),
                      ECG_SELFCHECK_DEV_LABELS=str(work / "dev" / "labels.csv"), ECG_SELFCHECK_PROBS=str(probs))
    spec_json = work / "specialist.json"
    summary_path = sc / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in a.only.split(","):
        pipe = {"specialist": work / "specialist_pipeline", "simple": work / "simple_pipeline"}.get(name)
        if pipe is None:
            pipe = sc / "pipelines" / name
            make_fake(pipe, name)
        reward, metrics = G.grade(pipe, hidden, sc / name, spec_json if name != "specialist" else None, n_boot=a.n_boot)
        if name == "specialist":
            s = metrics["scores"]
            spec_json.write_text(json.dumps({"macro_auroc": s["macro_auroc"], "mi_sensitivity_at_spec": s["mi_sensitivity_at_spec"],
                                             "macro_ece": s["macro_ece"], "subgroup_gap": s["subgroup_gap"],
                                             "per_ecg_s": metrics["per_ecg_s"], "elapsed_s": metrics["run"]["elapsed_s"]}, indent=1))
            reward["vs_specialist"] = 1.0
        s = metrics.get("scores", {})
        summary[name] = {"reward": reward, "elapsed_s": metrics["run"]["elapsed_s"], "per_ecg_s": metrics["per_ecg_s"],
                         "budget_s": metrics["time_budget_s"], "invalid_reason": metrics.get("invalid_reason"),
                         **{k: s.get(k) for k in ("macro_auroc", "mi_sensitivity_at_spec", "macro_ece", "macro_brier",
                                                  "subgroup_gap", "worst_subgroup", "gate", "ci95")}}
        summary_path.write_text(json.dumps(summary, indent=1, default=float))
        print(name, json.dumps(summary[name]["reward"]), flush=True)


if __name__ == "__main__":
    main()
