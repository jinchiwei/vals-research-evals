"""48-hour summary features for the specialist gradient-boosted comparator (grader-side only).

Not shown to the agent. Cleaning rules (fixed from the challenge documentation and set-A
inspection, not from hidden outcomes):
- descriptors: -1 means missing (Age, Gender, Height, ICUType, Weight);
- Height outside 100-250 cm, Weight outside 20-300 kg -> missing;
- pH values above 14 are treated as entered x100 (e.g. 735 -> 7.35) when in 650-800, else missing;
- Temp below 25 C -> missing; any negative value of a physiological quantity -> missing;
- 0 for HR, blood pressures, Weight, Temp -> missing (device dropouts);
- MechVent is an indicator (present = 1).
"""
from __future__ import annotations

import math
import os
import sys
from typing import Dict, List

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from records import TIME_SERIES, read_record  # noqa: E402

ZERO_INVALID = {"HR", "DiasABP", "SysABP", "MAP", "NIDiasABP", "NISysABP", "NIMAP", "Weight", "Temp", "pH"}
SERIES = [s for s in TIME_SERIES if s != "MechVent"]
STATS = ("first", "last", "min", "max", "mean", "std", "count", "last24_mean", "slope")


def clean_value(name: str, v: float) -> float:
    if v < 0:
        return math.nan
    if v == 0 and name in ZERO_INVALID:
        return math.nan
    if name == "pH":
        if 650 <= v <= 800:
            return v / 100.0
        if not 6.5 <= v <= 8.0:
            return math.nan
    if name == "Temp" and v < 25:
        return math.nan
    if name == "Weight" and not 20 <= v <= 300:
        return math.nan
    return v


def record_features(rec) -> Dict[str, float]:
    f: Dict[str, float] = {}
    d = rec.descriptors
    f["age"] = d.get("Age", math.nan)
    f["female"] = 1.0 if d.get("Gender") == 0 else (0.0 if d.get("Gender") == 1 else math.nan)
    h = d.get("Height", math.nan)
    f["height"] = h if h == h and 100 <= h <= 250 else math.nan
    w0 = d.get("Weight", math.nan)
    f["weight0"] = w0 if w0 == w0 and 20 <= w0 <= 300 else math.nan
    icu = d.get("ICUType", math.nan)
    for k in (1, 2, 3, 4):
        f[f"icu{k}"] = 1.0 if icu == k else 0.0
    mv = rec.series.get("MechVent", [])
    f["mechvent_any"] = 1.0 if mv else 0.0
    f["mechvent_first_h"] = mv[0][0] / 60.0 if mv else math.nan
    total_obs = 0
    for name in SERIES:
        pts = [(t, clean_value(name, v)) for t, v in rec.series.get(name, [])]
        pts = [(t, v) for t, v in pts if v == v]
        total_obs += len(pts)
        if name == "Urine":
            vals = np.array([v for _, v in pts])
            f["Urine_total"] = float(vals.sum()) if len(vals) else math.nan
            f["Urine_count"] = float(len(vals))
            f["Urine_last24_total"] = float(sum(v for t, v in pts if t >= 1440)) if pts else math.nan
            continue
        if not pts:
            for s in STATS:
                f[f"{name}_{s}"] = 0.0 if s == "count" else math.nan
            continue
        t = np.array([p[0] for p in pts], float) / 60.0
        v = np.array([p[1] for p in pts], float)
        f[f"{name}_first"] = v[0]
        f[f"{name}_last"] = v[-1]
        f[f"{name}_min"] = v.min()
        f[f"{name}_max"] = v.max()
        f[f"{name}_mean"] = v.mean()
        f[f"{name}_std"] = v.std() if len(v) > 1 else math.nan
        f[f"{name}_count"] = float(len(v))
        late = v[t >= 24]
        f[f"{name}_last24_mean"] = late.mean() if len(late) else math.nan
        f[f"{name}_slope"] = float(np.polyfit(t, v, 1)[0]) if len(v) > 2 and np.ptp(t) > 0 else math.nan
    f["total_obs"] = float(total_obs)
    return f


def feature_matrix(paths: List[str]):
    rows, ids = [], []
    for path in paths:
        rec = read_record(path)
        rows.append(record_features(rec))
        ids.append(rec.record_id)
    names = sorted(rows[0])
    X = np.array([[r.get(n, math.nan) for n in names] for r in rows], float)
    return ids, names, X
