"""Fit the specialist gradient-boosted comparator on set A only and package it as a pipeline.

- Model: scikit-learn HistGradientBoostingClassifier on 48-hour summary features (features.py).
- Hyper-parameters: small grid chosen by 5-fold stratified cross-validation on set A (log loss).
- Calibration: CalibratedClassifierCV(method="isotonic", cv=5) on set A with the chosen settings.
- Output: a self-contained pipeline folder (run.sh, predict.py, features.py, records.py, model.pkl)
  that follows the agent contract, so the grader times it the same way.

Usage: python -I fit_gbm.py DEV_RECORDS DEV_OUTCOMES_CSV OUT_PIPELINE_DIR REPORT_JSON
"""
from __future__ import annotations

import csv
import json
import os
import pickle
import shutil
import sys
import time

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILY = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, FAMILY)
from features import feature_matrix  # noqa: E402
from records import list_records  # noqa: E402

SEED = 20261114
GRID = [
    {"learning_rate": lr, "max_leaf_nodes": leaves, "min_samples_leaf": 40, "l2_regularization": 1.0,
     "max_iter": 400, "early_stopping": True, "validation_fraction": 0.15, "n_iter_no_change": 30}
    for lr in (0.03, 0.06) for leaves in (8, 16)
]

PREDICT = '''"""Score every record in INPUT_DIR; write OUTPUT_DIR/predictions.csv (RecordID,risk)."""
import csv, os, pickle, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import feature_matrix
from records import list_records
import numpy as np

def main(inp, out, transform=None):
    with open(os.path.join(HERE, "model.pkl"), "rb") as h:
        bundle = pickle.load(h)
    ids, names, X = feature_matrix(list_records(inp))
    assert names == bundle["names"], "feature mismatch"
    p = bundle["model"].predict_proba(X)[:, 1]
    mode = os.environ.get("RISK_ICU_TRANSFORM", transform or "")
    if mode == "overconfident":  # failure pipeline: same ranking, logits x3
        q = np.clip(p, 1e-4, 1 - 1e-4); lo = np.log(q / (1 - q)) * 3.0; p = 1 / (1 + np.exp(-lo))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "predictions.csv"), "w", newline="") as h:
        w = csv.writer(h); w.writerow(["RecordID", "risk"])
        for i, v in zip(ids, p):
            w.writerow([i, f"{float(v):.6f}"])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
'''

RUN = '''#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I "$HERE/predict.py" "$1" "$2"
'''


def main(dev_records, dev_outcomes, out_dir, report_path):
    t0 = time.time()
    with open(dev_outcomes, newline="") as h:
        y_map = {int(r["RecordID"]): int(r["in_hospital_death"]) for r in csv.DictReader(h)}
    ids, names, X = feature_matrix(list_records(dev_records))
    y = np.array([y_map[i] for i in ids])
    t_feat = time.time() - t0
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    results = []
    for params in GRID:
        p = cross_val_predict(HistGradientBoostingClassifier(random_state=SEED, **params), X, y, cv=cv,
                              method="predict_proba")[:, 1]
        results.append({"params": params, "cv_auroc": roc_auc_score(y, p), "cv_logloss": log_loss(y, p)})
    best = min(results, key=lambda r: r["cv_logloss"])
    base = HistGradientBoostingClassifier(random_state=SEED, **best["params"])
    cal = CalibratedClassifierCV(base, method="isotonic", cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    # Honest internal estimate of the calibrated model: nested CV prediction.
    p_cal = cross_val_predict(cal, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED + 1),
                              method="predict_proba")[:, 1]
    cal.fit(X, y)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "model.pkl"), "wb") as h:
        pickle.dump({"model": cal, "names": names}, h)
    shutil.copyfile(os.path.join(HERE, "features.py"), os.path.join(out_dir, "features.py"))
    shutil.copyfile(os.path.join(FAMILY, "records.py"), os.path.join(out_dir, "records.py"))
    with open(os.path.join(out_dir, "predict.py"), "w") as h:
        h.write(PREDICT)
    with open(os.path.join(out_dir, "run.sh"), "w") as h:
        h.write(RUN)
    os.chmod(os.path.join(out_dir, "run.sh"), 0o755)
    report = {"n_dev": len(y), "deaths_dev": int(y.sum()), "n_features": len(names), "grid": results,
              "chosen": best["params"], "nested_cv_calibrated_auroc": roc_auc_score(y, p_cal),
              "nested_cv_calibrated_logloss": log_loss(y, p_cal), "feature_seconds": round(t_feat, 1),
              "total_fit_seconds": round(time.time() - t0, 1)}
    with open(report_path, "w") as h:
        json.dump(report, h, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "grid"}, indent=1))
    for r in results:
        print(r["params"]["learning_rate"], r["params"]["max_leaf_nodes"], round(r["cv_auroc"], 4), round(r["cv_logloss"], 4))


if __name__ == "__main__":
    main(*sys.argv[1:5])
