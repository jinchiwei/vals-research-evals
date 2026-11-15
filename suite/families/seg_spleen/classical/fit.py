"""Fit the classical reference on DEVELOPMENT cases only.

  python -I classical/fit.py STAGED_DEV_DIR [--jobs 6]

Writes classical/pipeline/prior.npy and params.json, and classical/fit_log.json with
the grid and per-case development Dice. Hidden cases are never read here.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pipeline"))
sys.path.insert(0, str(HERE.parent))
import segment  # noqa: E402
import grader  # noqa: E402

BINS = 64
PRIOR_SIGMA_BINS = 1.5
# Reduced grid (time budget on 2026-11-14; the first 2x2x3x2 grid was stopped after one
# combination scored dev Dice 0.24).
GRID = {"erode_mm": [5.0, 8.0], "prior_floor": [0.25],
        "win": [(40, 40)], "score": ["sum", "meanlog"]}
FIXED = {"min_core_ml": 5.0, "grow_iters": 6}


def load(case_dir):
    im = nib.load(str(case_dir / "image.nii.gz"))
    img = np.asanyarray(im.dataobj).astype(np.float32)
    lab = np.asanyarray(nib.load(str(case_dir / "label.nii.gz")).dataobj) > 0
    return img, im.affine, lab


def case_prior_hist(case_dir):
    img, aff, lab = load(case_dir)
    body = segment.body_mask(img)
    u, v = segment.body_coords(body)
    proj = lab.any(axis=2)
    h = np.zeros((BINS, BINS))
    iu, iv = (u * BINS).astype(int), (v * BINS).astype(int)
    xs, ys = np.nonzero(proj)
    np.add.at(h, (iu[xs], iv[ys]), 1.0)
    sm = ndimage.median_filter(img, size=(3, 3, 1))
    return (h > 0).astype(float), np.percentile(sm[lab], [2, 98])


def eval_case(args):
    case_dir, prior, params = args
    img, aff, lab = load(case_dir)
    pred = segment.segment(img, aff, prior, params)
    return grader.dice(lab, pred), float(pred.sum()) , float(lab.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dev_dir", type=Path)
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    cases = sorted(p for p in a.dev_dir.iterdir() if (p / "label.nii.gz").is_file())
    assert all(c.name.startswith("dev_") for c in cases), "fit only on development cases"
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(case_prior_hist, cases))
    prior = ndimage.gaussian_filter(np.mean([r[0] for r in res], axis=0), PRIOR_SIGMA_BINS)
    prior /= prior.max()
    hu = np.array([r[1] for r in res])
    base = {"hu_lo": float(np.floor(hu[:, 0].min() - 10)), "hu_hi": float(np.ceil(hu[:, 1].max() + 10)),
            **FIXED}
    combos = []
    for e, f, (wb, wa), sc in itertools.product(GRID["erode_mm"], GRID["prior_floor"], GRID["win"],
                                                GRID["score"]):
        combos.append({**base, "erode_mm": e, "prior_floor": f, "win_below": wb, "win_above": wa,
                       "score": sc})
    log = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for params in combos:
            r = list(ex.map(eval_case, [(c, prior, params) for c in cases]))
            d = [x[0] for x in r]
            log.append({"params": params, "dev_dice": d, "mean": float(np.mean(d))})
            print(json.dumps({k: params[k] for k in ("erode_mm", "prior_floor", "win_below", "win_above", "score")}),
                  round(float(np.mean(d)), 4), [round(x, 3) for x in d], flush=True)
    best = max(log, key=lambda x: x["mean"])
    (HERE / "pipeline" / "params.json").write_text(json.dumps(best["params"], indent=1))
    np.save(HERE / "pipeline" / "prior.npy", prior.astype(np.float32))
    (HERE / "fit_log.json").write_text(json.dumps({"cases": [c.name for c in cases], "grid": log,
                                                   "best": best}, indent=1))
    print("best", best["params"], best["mean"])


if __name__ == "__main__":
    main()
