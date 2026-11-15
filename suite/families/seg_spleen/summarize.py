"""Aggregate evaluate_pipeline.py results into tables and the grader's specialist summary.

  python -I summarize.py RESULTS_DIR   (e.g. /home/jkwei/data/vals-suite/seg_spleen/specialist)

Writes RESULTS_DIR/summary.json and, if ts_gpu_full_hidden.json exists,
suite/families/seg_spleen/specialist/summary_hidden.json (aggregate only; no masks).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def agg(rows):
    ok = [r for r in rows if r.get("valid")]
    f = lambda k: [r[k] for r in ok if r.get(k) is not None]  # noqa: E731
    d = [r.get("dice", 0.0) for r in rows]
    return {
        "n": len(rows),
        "mean_dice": float(np.mean(d)), "min_dice": float(np.min(d)), "median_dice": float(np.median(d)),
        "mean_nsd_2mm": float(np.mean(f("nsd_2mm"))) if ok else None,
        "mean_hd95_mm": float(np.mean(f("hd95_mm"))) if f("hd95_mm") else None,
        "median_hd95_mm": float(np.median(f("hd95_mm"))) if f("hd95_mm") else None,
        "mean_abs_volume_rel_error": float(np.mean(np.abs(f("volume_rel_error")))) if ok else None,
        "max_abs_volume_rel_error": float(np.max(np.abs(f("volume_rel_error")))) if ok else None,
        "mean_abs_volume_error_ml": float(np.mean(np.abs(f("volume_error_ml")))) if ok else None,
        "acceptable_fraction": float(np.mean([bool(r.get("acceptable")) for r in rows])),
        "wall_sec_median": float(np.median([r["wall_sec"] for r in rows])),
        "wall_sec_max": float(np.max([r["wall_sec"] for r in rows])),
    }


def main():
    d = Path(sys.argv[1])
    out = {}
    for p in sorted(d.glob("*.json")):
        if p.name == "summary.json":
            continue
        res = json.loads(p.read_text())
        out[res["label"]] = {"aggregate": agg(res["cases"]), "threads": res.get("threads"),
                             "env": res.get("env"), "cases": res["cases"]}
        a = out[res["label"]]["aggregate"]
        print(f"{res['label']:28s} n={a['n']} dice={a['mean_dice']:.3f} (min {a['min_dice']:.3f}) "
              f"nsd2={a['mean_nsd_2mm'] or 0:.3f} hd95={a['mean_hd95_mm'] or float('nan'):.1f} "
              f"|dV|={a['mean_abs_volume_rel_error'] or float('nan'):.3f} ok={a['acceptable_fraction']:.2f} "
              f"t_med={a['wall_sec_median']:.0f}s t_max={a['wall_sec_max']:.0f}s")
    (d / "summary.json").write_text(json.dumps(out, indent=1))
    if "ts_gpu_full_hidden" in out:
        a = out["ts_gpu_full_hidden"]["aggregate"]
        spec = {"tool": "TotalSegmentator 2.18.0, task total, --roi_subset spleen, full (1.5 mm) model",
                "device_for_masks": "GPU (RTX 3060)", **a}
        cpu = out.get("ts_cpu4_full_hidden", {}).get("aggregate")
        if cpu:
            spec["cpu4_full_wall_sec_median"] = cpu["wall_sec_median"]
        fast = out.get("ts_cpu4_fast_hidden", {}).get("aggregate")
        if fast:
            spec["cpu4_fast_wall_sec_median"] = fast["wall_sec_median"]
        (HERE / "specialist" / "summary_hidden.json").write_text(json.dumps(spec, indent=1))


if __name__ == "__main__":
    main()
