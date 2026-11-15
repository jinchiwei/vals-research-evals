"""Verify the HC18 training set: sizes, pixel sizes, annotation format, HC reproduction.

Usage: python -I data_check.py DATA_ROOT OUT_JSON
DATA_ROOT holds raw/ (Zenodo files) and extracted/training_set/.
Writes per-image recomputation to DATA_ROOT/derived/hc_recomputed.csv (stays out of Git)
and aggregate facts to OUT_JSON.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_hc18.geometry import hc_from_outline  # noqa: E402


def main(root: Path, out_json: Path) -> None:
    tdir = root / "extracted" / "training_set"
    rows = list(csv.DictReader(open(root / "raw" / "training_set_pixel_size_and_HC.csv")))
    test_rows = list(csv.DictReader(open(root / "raw" / "test_set_pixel_size.csv")))
    keys = list(rows[0].keys())
    sizes, modes, ann_vals, recs = Counter(), Counter(), Counter(), []
    for r in rows:
        fn = r["filename"]
        px = float(r["pixel size(mm)"])
        hc = float(r["head circumference (mm)"])
        img = Image.open(tdir / fn)
        ann = Image.open(tdir / fn.replace(".png", "_Annotation.png"))
        sizes[img.size] += 1
        modes[(img.mode, ann.mode)] += 1
        a = np.asarray(ann)
        if a.ndim == 3:
            a = a[..., 0]
        ann_vals.update(np.unique(a).tolist())
        hc_re = hc_from_outline(a > 0, px)
        m = re.match(r"(\d+)_(\d*)HC\.png", fn)
        recs.append(dict(filename=fn, group=m.group(1), pixel_size_mm=px, hc_mm=hc,
                         hc_recomputed_mm=hc_re, diff_mm=hc_re - hc,
                         width=img.size[0], height=img.size[1]))
    d = np.array([x["diff_mm"] for x in recs])
    hcs = np.array([x["hc_mm"] for x in recs])
    pxs = np.array([x["pixel_size_mm"] for x in recs])
    groups = Counter(x["group"] for x in recs)
    (root / "derived").mkdir(exist_ok=True)
    with open(root / "derived" / "hc_recomputed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
        w.writeheader()
        w.writerows(recs)
    q = lambda v, p: float(np.percentile(v, p))  # noqa: E731
    facts = {
        "n_training_images": len(rows),
        "n_test_images": len(test_rows),
        "csv_columns": keys,
        "test_csv_columns": list(test_rows[0].keys()),
        "test_set_has_hc_reference": any("circumference" in k for k in test_rows[0]),
        "image_sizes": {f"{k[0]}x{k[1]}": v for k, v in sizes.items()},
        "image_modes": {f"{k[0]}/{k[1]}": v for k, v in modes.items()},
        "annotation_pixel_values": sorted(ann_vals),
        "pixel_size_mm": {"min": float(pxs.min()), "median": float(np.median(pxs)), "max": float(pxs.max())},
        "hc_mm": {"min": float(hcs.min()), "p33.3": q(hcs, 100 / 3), "median": float(np.median(hcs)),
                  "p66.7": q(hcs, 200 / 3), "max": float(hcs.max())},
        "hc_band_counts_approx_trimester": {
            "lt100mm": int((hcs < 100).sum()), "100to260mm": int(((hcs >= 100) & (hcs < 260)).sum()),
            "ge260mm": int((hcs >= 260).sum())},
        "groups": {"n_prefixes": len(groups), "images_per_prefix": dict(Counter(groups.values()))},
        "recompute_diff_mm": {"mean": float(d.mean()), "mean_abs": float(np.abs(d).mean()),
                               "p95_abs": q(np.abs(d), 95), "max_abs": float(np.abs(d).max()),
                               "rel_mean_abs_pct": float(np.mean(np.abs(d) / hcs) * 100)},
    }
    out_json.write_text(json.dumps(facts, indent=2))
    print(json.dumps(facts, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
