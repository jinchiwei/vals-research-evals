"""Pure parsing and comparison helpers for the Box release candidate."""
import csv
import re
from datetime import datetime

import numpy as np


def read_summary(path, required_metrics):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows or len(rows[0]) != 2:
        raise ValueError("Expected a two-column SummaryLesions table")
    header = [x.strip().lower() for x in rows[0]]
    if header[0] not in {"label", "metric", "", "unnamed: 0"} or header[1] not in {"value", "0"}:
        raise ValueError(f"Unrecognized SummaryLesions header: {header}")
    values = {}
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != 2:
            raise ValueError("Malformed SummaryLesions row")
        key = row[0].strip()
        if key not in required_metrics:
            continue
        if key in values:
            raise ValueError("Duplicate required metric")
        value = float(row[1])
        if not np.isfinite(value):
            raise ValueError("Nonfinite required metric")
        values[key] = value
    if set(values) != set(required_metrics):
        raise ValueError("Missing required SummaryLesions metric")
    return np.array([values[name] for name in required_metrics], dtype=float)


def gene_label(records, gene, policy):
    if not records:
        raise ValueError("No mutation records for this sample; do not infer a negative")
    if policy not in {"legacy_any_listed", "reported_pathogenic"}:
        raise ValueError("Unknown label policy")
    for row in records:
        tokens = re.split(r"[;,|/\s]+", str(row.get("gene", "")).strip().upper())
        if gene.upper() not in tokens:
            continue
        if policy == "legacy_any_listed":
            return 1
        classification = str(row.get("variantclassification", "")).strip().lower()
        reported = str(row.get("reportedalteration", "")).strip().lower() == "true"
        origin = str(row.get("geneticorigin", "")).strip().lower()
        if reported and classification in {"pathogenic", "likely pathogenic"} and origin != "not detected":
            return 1
    return 0


def compare_features(box, internal, names, atol=1e-6, rtol=1e-5):
    box, internal = np.asarray(box, float), np.asarray(internal, float)
    if box.shape != internal.shape or box.ndim != 2 or box.shape[1] != len(names):
        raise ValueError("Feature arrays and names must align")
    if np.isinf(box).any() or np.isinf(internal).any():
        raise ValueError("Infinite feature value")
    equal = np.isclose(box, internal, atol=atol, rtol=rtol, equal_nan=True)
    finite = np.isfinite(box) & np.isfinite(internal)
    differences = np.abs(box - internal)
    result = {
        "rows": len(box), "features": len(names), "absolute_tolerance": atol, "relative_tolerance": rtol,
        "matching_values": int((equal & finite).sum()),
        "both_missing_values": int((np.isnan(box) & np.isnan(internal)).sum()),
        "mismatched_values": int((~equal).sum()),
        "rows_with_difference": int((~equal).any(axis=1).sum()), "per_feature": {},
    }
    for j, name in enumerate(names):
        diff = differences[finite[:, j], j]
        result["per_feature"][name] = {
            "mismatched_values": int((~equal[:, j]).sum()),
            "max_absolute_difference": float(diff.max()) if len(diff) else None,
        }
    return result


def release_date(value):
    value = str(value).strip()
    if value.lower() in {"", "nan", "nat", "none"}:
        return None
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}", value):
        date = datetime.strptime(value, "%m/%d/%y")
        if date.year > 2026:
            date = date.replace(year=date.year - 100)
        return date
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError("Unrecognized release date format")


def age_at_diagnosis(birth, diagnosis):
    birth, diagnosis = release_date(birth), release_date(diagnosis)
    if birth is None or diagnosis is None:
        return float("nan")
    age = (diagnosis - birth).days / 365.25
    if not 0 <= age <= 120:
        raise ValueError("Implausible age; check date parsing")
    return age
