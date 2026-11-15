"""SAPS-I comparator: logistic recalibration of the challenge-supplied SAPS-I score.

risk = 1 / (1 + exp(-(a + b * SAPS-I))), with a and b fitted by maximum likelihood on set A
(stays with SAPS-I recorded). Stays with SAPS-I missing (-1 in the outcomes file) get the set-A
mortality of SAPS-missing stays. The SAPS-I values were computed by the challenge organisers from
the same 48-hour records (Silva et al., CinC 2012); we read them from the outcomes file rather
than recomputing them, so no runtime is measured for this comparator.

Usage: python -I saps.py DEV_OUTCOMES_CSV HIDDEN_OUTCOMES_CSV OUT_PREDICTIONS_CSV OUT_JSON
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grade import _logistic_fit  # noqa: E402


def load(path):
    with open(path, newline="") as h:
        rows = list(csv.DictReader(h))
    return rows, np.array([int(r["saps1"]) for r in rows], float), np.array([int(r["in_hospital_death"]) for r in rows])


def fit(dev_path):
    _, s, y = load(dev_path)
    ok = s >= 0
    beta = _logistic_fit(np.column_stack([np.ones(ok.sum()), s[ok]]), y[ok])
    missing_rate = float(y[~ok].mean()) if (~ok).any() else float(y.mean())
    return {"intercept": float(beta[0]), "slope_per_point": float(beta[1]), "missing_risk": missing_rate,
            "n_fit": int(ok.sum()), "n_missing_dev": int((~ok).sum())}


def predict(model, saps):
    saps = np.asarray(saps, float)
    p = 1 / (1 + np.exp(-(model["intercept"] + model["slope_per_point"] * saps)))
    return np.where(saps >= 0, p, model["missing_risk"])


def main(dev, hidden, out_csv, out_json):
    model = fit(dev)
    rows, s, _ = load(hidden)
    p = predict(model, s)
    with open(out_csv, "w", newline="") as h:
        w = csv.writer(h)
        w.writerow(["RecordID", "risk"])
        for r, v in zip(rows, p):
            w.writerow([r["RecordID"], f"{v:.6f}"])
    model["n_missing_hidden"] = int((s < 0).sum())
    with open(out_json, "w") as h:
        json.dump(model, h, indent=1)
    print(json.dumps(model))


if __name__ == "__main__":
    main(*sys.argv[1:5])
