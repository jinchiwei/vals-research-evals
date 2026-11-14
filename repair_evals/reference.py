"""Verifier-side algorithms. Never mount this module in an agent workspace."""
import math
import re


def endpoint(data):
    protocol = data["protocol"]
    aliases = {k.strip().upper(): v.strip().upper() for k, v in protocol["gene_aliases"].items()}
    def genes(text):
        return {aliases.get(token, token) for token in re.split(r"[;,|/\s]+", text.strip().upper()) if token}
    target = next(iter(genes(protocol["gene"])))
    cohort, excluded = [], []
    for patient in sorted(data["participants"], key=lambda p: p["participant_id"]):
        pid = patient["participant_id"]
        if patient["age"] < 18 or patient["confirmed_pcnsl"] is not True:
            excluded.append({"participant_id": pid, "reason": "ineligible_participant"})
            continue
        samples = [s for s in data["specimens"] if s["participant_id"] == pid
                   and s["type"] == "tumor" and s["assay_status"] == "passed"
                   and s["day"] <= protocol["as_of_day"]]
        if not samples:
            excluded.append({"participant_id": pid, "reason": "no_index_specimen"})
            continue
        sample = min(samples, key=lambda s: (s["day"], s["sample_id"]))
        reports = [r for r in data["reports"] if r["sample_id"] == sample["sample_id"]
                   and r["status"] == "final" and r["issued_day"] <= protocol["as_of_day"]]
        if not reports:
            excluded.append({"participant_id": pid, "reason": "no_final_report"})
            continue
        report = max(reports, key=lambda r: (r["revision"], r["issued_day"], r["report_id"]))
        tested = set().union(*(genes(g) for g in report["genes_tested"]))
        if target not in tested:
            excluded.append({"participant_id": pid, "reason": "gene_not_assayed"})
            continue
        scans = [s for s in data["scans"] if s["participant_id"] == pid and s["qc_pass"] is True
                 and {"FLAIR", "T1POST"} <= set(s["sequences"])
                 and sample["day"] - protocol["lookback_days"] <= s["day"] <= sample["day"]
                 and (patient["therapy_day"] is None or s["day"] < patient["therapy_day"])]
        if not scans:
            excluded.append({"participant_id": pid, "reason": "no_eligible_scan"})
            continue
        scan = min(scans, key=lambda s: (-s["day"], s["scan_id"]))
        positive = any(target in genes(v["gene"])
                       and v["classification"].strip().casefold() in {"pathogenic", "likely pathogenic"}
                       and (v["reported"] is True or isinstance(v["reported"], str) and v["reported"].strip().casefold() == "true")
                       and v["detection"].strip().casefold() == "detected" for v in report["variants"])
        cohort.append({"participant_id": pid, "sample_id": sample["sample_id"], "report_id": report["report_id"],
                       "scan_id": scan["scan_id"], "label": int(positive)})
    positives = sum(row["label"] for row in cohort)
    return {"cohort": cohort, "excluded": excluded,
            "counts": {"eligible": len(cohort), "positive": positives,
                       "negative": len(cohort) - positives, "excluded": len(excluded)}}


def _auc(rows):
    positive = [r[1] for r in rows if r[0] == 1]
    negative = [r[1] for r in rows if r[0] == 0]
    return sum(1 if p > n else .5 if p == n else 0 for p in positive for n in negative) / (len(positive) * len(negative))


def claims(data):
    plan = data["plan"]
    runs = {r["run_id"]: r for r in data["runs"]}
    rows = []
    for hypothesis in sorted(plan["hypotheses"], key=lambda h: h["hypothesis_id"]):
        item = {"hypothesis_id": hypothesis["hypothesis_id"], "run_id": hypothesis["run_id"],
                "eligible": False, "reason": None, "n_patients": 0, "auroc": None,
                "brier": None, "p_value": 1., "holm_p": 1., "reject": False}
        run = runs.get(hypothesis["run_id"])
        if run is None:
            item["reason"] = "missing_run"
            rows.append(item)
            continue
        chosen = {}
        for prediction in sorted(run["predictions"], key=lambda r: (r["visit_day"], r["row_id"])):
            chosen.setdefault(prediction["participant_id"], prediction)
        item["n_patients"] = len(chosen)
        participants = set(chosen)
        used = set(run["fit_subjects"] + run["transform_fit_subjects"] + run["selection_subjects"])
        if run["freeze_day"] > plan["evaluation_lock_day"] or run["selection_split"] != "development":
            item["reason"] = "evaluation_selection"
        elif participants & used:
            item["reason"] = "patient_overlap"
        elif any(len({r["label"] for r in run["predictions"] if r["participant_id"] == pid}) != 1 for pid in chosen):
            item["reason"] = "conflicting_labels"
        elif {r["label"] for r in chosen.values()} != {0, 1}:
            item["reason"] = "single_class"
        elif run["probability_for_class"] not in (0, 1) or any(
                not isinstance(r["probability"], (float, int)) or isinstance(r["probability"], bool)
                or not math.isfinite(r["probability"]) or not 0 <= r["probability"] <= 1 for r in chosen.values()):
            item["reason"] = "invalid_probability"
        elif not run["null_auroc"] or any(not math.isfinite(v) or not 0 <= v <= 1 for v in run["null_auroc"]):
            item["reason"] = "missing_null"
        else:
            values = [(r["label"], r["probability"] if run["probability_for_class"] == 1 else 1 - r["probability"])
                      for r in chosen.values()]
            auc = _auc(values)
            item.update(eligible=True, reason="eligible", auroc=auc,
                        brier=sum((y - p) ** 2 for y, p in values) / len(values),
                        p_value=(1 + sum(v >= auc for v in run["null_auroc"])) / (len(run["null_auroc"]) + 1))
        rows.append(item)
    previous = 0.
    for rank, item in enumerate(sorted(rows, key=lambda r: (r["p_value"], r["hypothesis_id"]))):
        previous = max(previous, min(1., (len(rows) - rank) * item["p_value"]))
        item["holm_p"] = previous
        item["reject"] = item["eligible"] and previous <= plan["alpha"]
    return {"family_size": len(rows), "hypotheses": rows,
            "discoveries": [r["hypothesis_id"] for r in rows if r["reject"]]}


def _det3(a):
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))


def _to_ras(affine, frame):
    return [[v * (-1 if frame == "LPS" and i < 2 else 1) for v in row] for i, row in enumerate(affine)]


def _world(a, x):
    return [sum(a[i][j] * x[j] for j in range(3)) + a[i][3] for i in range(3)]


def _voxel(a, world):
    matrix = [row[:3] for row in a[:3]]
    right = [world[i] - a[i][3] for i in range(3)]
    determinant = _det3(matrix)
    result = []
    for column in range(3):
        replaced = [row[:] for row in matrix]
        for i in range(3):
            replaced[i][column] = right[i]
        result.append(_det3(replaced) / determinant)
    return result


def geometry(data):
    measured = []
    for scan in sorted(data["scans"], key=lambda s: s["scan_id"]):
        mask, adc = scan["mask"], scan["adc"]
        ma, aa = _to_ras(mask["affine"], mask["frame"]), _to_ras(adc["affine"], adc["frame"])
        volume = abs(_det3(ma))
        coords = [(x, y, z) for x, plane in enumerate(mask["values"])
                  for y, line in enumerate(plane) for z, value in enumerate(line) if value != 0]
        worlds = [_world(ma, xyz) for xyz in coords]
        values = []
        factors = {"mm2/s": 1., "1e-6 mm2/s": 1e-6, "um2/ms": 1e-3}
        for point in worlds:
            x, y, z = [math.floor(v + .5) for v in _voxel(aa, point)]
            array = adc["values"]
            if 0 <= x < len(array) and 0 <= y < len(array[x]) and 0 <= z < len(array[x][y]):
                value = array[x][y][z]
                if value is not None:
                    values.append((value * adc["scale"] + adc["offset"]) * factors[adc["unit"]])
        n = len(worlds)
        measured.append({"scan_id": scan["scan_id"], "lesion_volume_mm3": n * volume,
                         "centroid_ras_mm": [sum(p[i] for p in worlds) / n for i in range(3)] if n else None,
                         "left_volume_mm3": sum(p[0] < -1e-9 for p in worlds) * volume,
                         "right_volume_mm3": sum(p[0] > 1e-9 for p in worlds) * volume,
                         "midline_volume_mm3": sum(abs(p[0]) <= 1e-9 for p in worlds) * volume,
                         "mean_adc_mm2_s": sum(values) / len(values) if values else None,
                         "adc_coverage": len(values) / n if n else None})
    by_id = {m["scan_id"]: m for m in measured}
    changes = []
    for pair in sorted(data["pairs"], key=lambda p: p["pair_id"]):
        a, b = by_id[pair["baseline"]], by_id[pair["followup"]]
        changes.append({"pair_id": pair["pair_id"],
                        "volume_change_pct": (b["lesion_volume_mm3"] / a["lesion_volume_mm3"] - 1) * 100 if a["lesion_volume_mm3"] else None,
                        "adc_change_mm2_s": b["mean_adc_mm2_s"] - a["mean_adc_mm2_s"]
                        if a["adc_coverage"] == b["adc_coverage"] == 1 else None})
    return {"scans": measured, "changes": changes}


def reference(case_input, family):
    functions = {"endpoint": endpoint, "claims": claims, "geometry": geometry}
    if family not in functions:
        raise ValueError("Unknown repair-task family")
    return functions[family](case_input)
