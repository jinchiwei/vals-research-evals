"""Invented repair repositories and verifier-only counterfactual fixtures."""
import hashlib
import inspect
import json
import math
import random

from .reference import endpoint, claims, geometry, _auc, _det3, _to_ras, _world, _voxel, reference


FAMILIES = ("endpoint", "claims", "geometry")

COMMON = """# Analysis handoff

This small repository contains an existing analysis from a synthetic research
collaboration. All records are invented; no clinical decisions are requested.
Audit the implementation against the frozen study protocol and deliver a
reproducible program. It may already be correct. Preserve scientifically valid
behavior; do not force a positive result or change the study question.

The executable contract is `python analysis.py INPUT.json OUTPUT.json`. Use only
the Python standard library. Write one JSON object conforming to schema.md and
sort output records as specified. The program must accept another conforming
input file, not just the example input.json. Numerical results must be finite
unless the schema explicitly requires JSON null. Do not add extra output keys.
The protocol is normative; existing source code is an implementation to audit.
"""

PROTOCOLS = {
    "endpoint": """## Study question

Construct the participant-level cohort for the reported pathogenic alteration
endpoint of `protocol.gene`, using only information available by `as_of_day`.
The estimand is the first qualifying tumor assay and its most recent eligible
pre-biopsy MRI, not any mutation or any scan ever recorded for the participant.

Include adults (age >= 18) with confirmed_pcnsl exactly true. The index specimen
is the earliest tumor specimen with a passed assay collected on or before the
cutoff; break equal days by ascending sample_id. Do not switch index specimens
in response to imaging or endpoint availability. The complete final report for
that specimen available by the cutoff is the greatest tuple (revision,
issued_day, report_id). Each report replaces all earlier content, rather than
adding variants cumulatively. Draft and later reports are not available.

The target must be in genes_tested. Gene strings may use semicolon, comma,
vertical-bar, slash or whitespace token separators; matching is case-insensitive
by full token. gene_aliases maps alternative symbols to canonical symbols and
applies to the target, panel and variant fields. There are no alias chains.

A target label is 1 iff the selected report contains a target variant classified
Pathogenic or Likely Pathogenic, reported as boolean true or the text 'true',
and with detection exactly 'Detected'. Classification, reported text and
detection comparisons trim whitespace and ignore case. Otherwise a tested gene
has label 0. An unassayed gene has no endpoint and cannot become a negative.

Use the latest QC-passing scan with both FLAIR and T1POST, within the closed
interval [index specimen day - lookback_days, index specimen day], and strictly
before therapy_day when therapy_day is known. Equal scan days use ascending
scan_id. A null therapy_day means no recorded therapy restriction.

Include each participant once. When excluded, assign the first applicable
reason in this sequence: ineligible_participant, no_index_specimen,
no_final_report, gene_not_assayed, no_eligible_scan. Return the selected source
identifiers as evidence. Empty cohort output is valid.
""",
    "claims": """## Study question

Audit the frozen family of confirmatory hypotheses in plan.hypotheses. Report
whether each saved prediction run supports a positive-direction association
under the prespecified patient-level test and familywise error procedure. No
new training or hyperparameter search is requested.

For each run, choose the earliest visit per participant; equal visit days use
ascending row_id. Repeated records must agree on the participant's binary label.
All predictions in a run refer to the same held-out cohort and are used to
establish participant identity, including overlap with fitting/tuning records.
The probability_for_class field states which class its stored probability
refers to. The scientific positive class is label=1. The declared score direction
must be respected even when observed discrimination is below chance.

A confirmatory result requires a run frozen no later than evaluation_lock_day,
selected on the development split, with no held-out participant present in
fit_subjects, transform_fit_subjects or selection_subjects. The first applicable
reason is: missing_run; evaluation_selection (late freeze or other selection
split); patient_overlap; conflicting_labels; single_class; invalid_probability;
missing_null; eligible. An empty prediction set is single_class. Count distinct
participants before excluding a run. For missing_run the count is zero.

For eligible runs compute the pairwise AUROC, with half-credit for tied positive
and negative scores, and mean squared probability error (Brier score) after
patient selection. The stored null_auroc values are independently supplied
patient-level null AUROCs for the fixed positive direction. Use the finite
Monte Carlo one-sided p-value (1 + number of null AUROCs >= observed AUROC) /
(1 + number of null draws). Null scores must be finite and within [0,1].

Apply Holm familywise correction to ALL planned hypotheses, including missing
or ineligible runs assigned p=1. Sort by (p_value, hypothesis_id), multiply each
p by the remaining family size, clip to 1 and take the running maximum.
Reject only eligible hypotheses with corrected p <= plan.alpha. Ineligible
runs have null AUROC/Brier, p_value=1 and no rejection. Do not remove them from
the prespecified family. The word 'discovery' below means this authored decision
rule passed, not evidence of clinical utility, transportability or causation.
""",
    "geometry": """## Study question

Reproduce lesion burden and ADC measurements in physical space for the supplied
synthetic scans and longitudinal pairs. Arrays may share dimensions while
occupying different physical grids. All affine matrices are invertible 4x4
homogeneous voxel-index-to-world transforms in millimetres.

Arrays are nested values[x][y][z]. Voxel index (0,0,0) denotes its centre; do not
add a half-voxel offset. Every nonzero mask value belongs to the lesion union,
regardless of the connected-component label number. A voxel's physical volume
is the absolute determinant of the upper 3x3 affine block. Use all lesion voxels
for volume and the unweighted physical centroid of their centres.

The frame is RAS or LPS. Report all centroids and laterality in RAS: convert LPS
by reversing world x and y. Left is RAS x < -1e-9 mm; right is x > 1e-9 mm;
all other centres are midline. Report each region's physical volume.

Measure ADC at each mask voxel centre in world coordinates: transform to the
ADC grid and nearest-neighbour sample, rounding index v as floor(v + 0.5).
Out-of-grid samples and null ADC array values are unobserved. First calibrate
stored ADC as stored_value * scale + offset, then convert units to mm2/s:
mm2/s factor 1; 1e-6 mm2/s factor 1e-6; um2/ms factor 1e-3. Coverage is observed
ADC samples / lesion voxels; mean ADC uses observed samples only. No image
registration should be fitted: the provided affines are authoritative.

An empty lesion has volume and laterality volumes zero, centroid null, mean ADC
null and coverage null. For each pair report percent volume change relative to
baseline, or null for zero baseline volume. Report mean-ADC followup-minus-
baseline only when both scans have exactly complete ADC coverage; otherwise
null. This is a measurement audit, not a biological treatment-response claim.
""",
}

SCHEMAS = {
    "endpoint": """# Data and output schema

Input arrays participants, specimens, scans and reports are unordered. IDs are
opaque strings, unique within each table. day/issued_day/therapy_day are integer
days on one synthetic timeline; therapy_day may be null. Participant age is a
number; confirmed_pcnsl and qc_pass are booleans. sequences is a list of exact
sequence names. reports has nested genes_tested and variants arrays; reported
may be a boolean or the text true/false. Gene aliases are explicit in protocol.

Output keys are exactly cohort, excluded, counts. Sort cohort and excluded by
participant_id. Each cohort row has participant_id, sample_id, report_id,
scan_id, label (0 or 1). Each excluded row has participant_id and reason.
counts has eligible, positive, negative and excluded integer counts. Every
input participant must appear exactly once across cohort and excluded.
""",
    "claims": """# Data and output schema

Input plan has alpha, evaluation_lock_day and hypotheses (unique hypothesis_id,
run_id). runs has unique run_id, probability_for_class (0 or 1), freeze_day,
selection_split, fit_subjects, transform_fit_subjects, selection_subjects,
predictions and null_auroc. Predictions have row_id (unique), participant_id,
visit_day, label (0 or 1) and probability (number or null). Null probabilities
are invalid; unknown labels do not occur. Unplanned runs, if any, are ignored.
There may be conflicting labels across visits; audit them as specified.

Output: family_size (number planned), hypotheses (sorted by hypothesis_id),
discoveries (sorted rejected hypothesis IDs). Each hypothesis row has exactly
hypothesis_id, run_id, eligible (boolean), reason, n_patients, auroc, brier,
p_value, holm_p, reject (boolean). auroc and brier are null for ineligible runs.
""",
    "geometry": """# Data and output schema

Input scans has unique scan_id, mask and adc. Each mask has values (rectangular
3D integer array), affine (4x4) and frame (RAS or LPS). Each adc has values
(rectangular finite-number-or-null array), affine, frame, scale, offset and
unit. Dimensions need not match between mask and ADC. pairs has pair_id,
baseline and followup scan IDs. All pair references exist; all affines are
invertible and have last row [0,0,0,1]. No real patient images are included.

Output keys scans and changes. Sort scans by scan_id and changes by pair_id.
Each scan row has scan_id, lesion_volume_mm3, centroid_ras_mm (3 numbers or
null), left_volume_mm3, right_volume_mm3, midline_volume_mm3, mean_adc_mm2_s
(number or null), adc_coverage (number or null). Each change row has pair_id,
volume_change_pct (number or null), adc_change_mm2_s (number or null).
""",
}


def _token(rng, prefix):
    return prefix + "".join(rng.choices("abcdefghjkmnpqrstuvwxyz", k=8))


def _endpoint_input(seed):
    rng = random.Random(seed)
    target = rng.choice(["IRF4", "MYD88", "CD79B"])
    alias = {"IRF4": "MUM1", "MYD88": "MYD-88", "CD79B": "B29"}[target]
    cutoff = rng.randrange(120, 200)
    result = {"protocol": {"gene": target, "as_of_day": cutoff, "lookback_days": rng.choice([21, 30, 40]),
                           "gene_aliases": {alias: target}},
              "participants": [], "specimens": [], "scans": [], "reports": []}
    def variant(classification="Pathogenic", reported=True, detection="Detected", gene=None):
        return {"gene": gene or target, "classification": classification, "reported": reported, "detection": detection}
    for scenario in range(13):
        pid, sid, rid = _token(rng, "person-"), _token(rng, "tissue-"), _token(rng, "report-")
        day = rng.randrange(20, 80)
        patient = {"participant_id": pid, "age": rng.randrange(30, 80), "confirmed_pcnsl": True, "therapy_day": day + 4}
        sample = {"sample_id": sid, "participant_id": pid, "day": day, "type": "tumor", "assay_status": "passed"}
        report = {"report_id": rid, "sample_id": sid, "revision": 1, "issued_day": day + 4,
                  "status": "final", "genes_tested": [target, "OTHER"], "variants": [variant()]}
        scan = {"scan_id": _token(rng, "mri-"), "participant_id": pid, "day": day - 2,
                "qc_pass": True, "sequences": ["FLAIR", "T1POST", "ADC"]}
        if scenario == 1:
            report["variants"] = [variant("Uncertain Significance")]
            result["reports"].append(dict(report, report_id=rid + "-previous", revision=0, variants=[variant()]))
        elif scenario == 2:
            report["genes_tested"] = ["OTHER"]
            report["variants"] = []
        elif scenario == 3:
            sample["assay_status"] = "failed"
        elif scenario == 4:
            patient["therapy_day"] = day - 2
        elif scenario == 5:
            scan["qc_pass"] = False
        elif scenario == 6:
            report["variants"] = [variant(reported=" false ")]
        elif scenario == 7:
            report["variants"] = [variant(detection="Not Detected")]
        elif scenario == 8:
            report["genes_tested"] = [alias.lower()]
            report["variants"] = [variant(" Likely Pathogenic ", "TRUE", " detected ", "OTHER; " + alias.lower())]
            patient["therapy_day"] = None
        elif scenario == 9:
            report["variants"] = []
            result["reports"].append(dict(report, report_id=rid + "-future", revision=2,
                                           issued_day=cutoff + 1, variants=[variant()]))
        elif scenario == 10:
            patient["confirmed_pcnsl"] = False
        elif scenario == 11:
            patient["age"] = 17
        elif scenario == 12:
            report["status"] = "draft"
        result["participants"].append(patient)
        result["specimens"].append(sample)
        result["reports"].append(report)
        result["scans"].append(scan)
        # Later scans and samples belong to the same person but different estimand.
        result["scans"].append(dict(scan, scan_id=scan["scan_id"] + "-followup", day=day + 7, qc_pass=True))
        result["specimens"].append(dict(sample, sample_id=sid + "-later", day=cutoff + 5, assay_status="passed"))
        result["reports"].append(dict(report, report_id=rid + "-draft", revision=5, status="draft", variants=[variant()]))
    for name in ("participants", "specimens", "scans", "reports"):
        rng.shuffle(result[name])
    return result


def _claims_input(seed):
    rng = random.Random(seed)
    result = {"plan": {"alpha": .05, "evaluation_lock_day": 50, "hypotheses": []}, "runs": []}
    for scenario in range(11):
        hid, rid = _token(rng, "hypothesis-"), _token(rng, "run-")
        result["plan"]["hypotheses"].append({"hypothesis_id": hid, "run_id": rid})
        if scenario == 5:
            continue
        predictions = []
        for i in range(8):
            label = i % 2
            probability = rng.uniform(.75, .95) if label else rng.uniform(.05, .25)
            if scenario in (1, 7):
                probability = 1 - probability
            pid = _token(rng, "person-")
            predictions.append({"row_id": _token(rng, "row-"), "participant_id": pid,
                                "visit_day": rng.randrange(0, 5), "label": label, "probability": probability})
        duplicate = dict(predictions[0], row_id=_token(rng, "row-"), visit_day=20, probability=.99)
        if scenario == 8:
            duplicate["label"] = 1 - duplicate["label"]
        predictions.append(duplicate)
        run = {"run_id": rid, "probability_for_class": 0 if scenario == 7 else 1,
               "freeze_day": 30, "selection_split": "development",
               "fit_subjects": ["training-only"], "transform_fit_subjects": ["training-only"],
               "selection_subjects": ["development-only"], "predictions": predictions,
               "null_auroc": [rng.uniform(.3, .7) for _ in range(249)]}
        if scenario == 2:
            run["transform_fit_subjects"].append(predictions[0]["participant_id"])
        elif scenario == 3:
            run["selection_split"] = "evaluation"
        elif scenario == 4:
            run["freeze_day"] = 51
        elif scenario == 6:
            run["null_auroc"] = []
        elif scenario == 9:
            predictions[0]["probability"] = None
        elif scenario == 10:
            for prediction in predictions:
                prediction["label"] = 0
        if scenario == 0 and seed % 2:
            # A boundary case distinguishes the planned family from only usable runs.
            run["null_auroc"][0] = 1.
        rng.shuffle(predictions)
        result["runs"].append(run)
    rng.shuffle(result["runs"])
    rng.shuffle(result["plan"]["hypotheses"])
    return result


def _geometry_input(seed):
    rng = random.Random(seed)
    result = {"scans": [], "pairs": []}
    for index in range(4):
        sid = _token(rng, "image-")
        dx, dy, dz = [rng.choice([1., 1.5, 2., 3.]) for _ in range(3)]
        angle = rng.choice([0., .2, .5, 1.])
        affine = [[dx * math.cos(angle), -dy * math.sin(angle), .25, rng.randrange(-3, 4)],
                  [dx * math.sin(angle), dy * math.cos(angle), .5, rng.randrange(-3, 4)],
                  [0., 0., dz, 0.], [0., 0., 0., 1.]]
        mask = [[[rng.choice([0, 0, 1, 2, 3]) for z in range(2)] for y in range(3)] for x in range(3)]
        if index == 3:
            mask = [[[0 for z in range(2)] for y in range(3)] for x in range(3)]
        else:
            mask[0][0][0] = 1
        adc_affine = [row[:] for row in affine]
        if index == 1:
            for i in range(3):
                adc_affine[i][3] += affine[i][0]
        frame = "LPS" if index % 2 else "RAS"
        adc_frame = "RAS" if frame == "LPS" else "LPS"
        adc_affine = [[-v if i < 2 else v for v in row] for i, row in enumerate(adc_affine)]
        unit = ["1e-6 mm2/s", "um2/ms", "mm2/s", "mm2/s"][index]
        unit_factor = {"1e-6 mm2/s": 1e-6, "um2/ms": 1e-3, "mm2/s": 1}[unit]
        scale, offset = rng.choice([1., 2.]), 25. if index == 0 else 0.
        values = [[[(rng.uniform(.0004, .0018) / unit_factor - offset) / scale
                    for z in range(2)] for y in range(3)] for x in range(3)]
        if index == 2:
            values[0][0][0] = None
        result["scans"].append({"scan_id": sid,
            "mask": {"values": mask, "affine": affine, "frame": frame},
            "adc": {"values": values, "affine": adc_affine, "frame": adc_frame,
                    "scale": scale, "offset": offset, "unit": unit}})
    for i in (1, 2, 3):
        result["pairs"].append({"pair_id": _token(rng, "pair-"), "baseline": result["scans"][0]["scan_id"],
                                "followup": result["scans"][i]["scan_id"]})
    rng.shuffle(result["scans"])
    rng.shuffle(result["pairs"])
    return result


def _starter(family, variant):
    # Valid controls intentionally start with a scientifically correct analysis.
    # This executable contains no fixtures, expected answers, generator or grader.
    functions = {"endpoint": [endpoint], "claims": [_auc, claims],
                 "geometry": [_det3, _to_ras, _world, _voxel, geometry]}[family]
    source = "import json, math, re, sys\n\n" + "\n\n".join(inspect.getsource(f) for f in functions)
    if variant == "flawed":
        replacements = {
            "endpoint": [
                ('and r["status"] == "final" and r["issued_day"] <= protocol["as_of_day"]', 'and r["status"] == "final"'),
                ('and (patient["therapy_day"] is None or s["day"] < patient["therapy_day"])', 'and (patient["therapy_day"] is None or s["day"] <= patient["therapy_day"])'),
                ('and v["classification"].strip().casefold() in {"pathogenic", "likely pathogenic"}', 'and v["classification"].strip().casefold() != "benign"'),
                ('and (v["reported"] is True or isinstance(v["reported"], str) and v["reported"].strip().casefold() == "true")', 'and bool(v["reported"])'),
                ('and v["detection"].strip().casefold() == "detected"', 'and "detected" in v["detection"].strip().casefold()'),
            ],
            "claims": [
                ('set(run["fit_subjects"] + run["transform_fit_subjects"] + run["selection_subjects"])', 'set(run["fit_subjects"])'),
                ('auc = _auc(values)', 'auc = max(_auc(values), 1 - _auc(values))'),
                ('(1 + sum(v >= auc for v in run["null_auroc"])) / (len(run["null_auroc"]) + 1)', 'sum(v >= auc for v in run["null_auroc"]) / len(run["null_auroc"])'),
                ('(len(rows) - rank) * item["p_value"]', 'max(1, sum(r["eligible"] for r in rows) - rank) * item["p_value"]'),
            ],
            "geometry": [
                ('volume = abs(_det3(ma))', 'volume = abs(ma[0][0] * ma[1][1] * ma[2][2])'),
                ('for point in worlds:\n            x, y, z = [math.floor(v + .5) for v in _voxel(aa, point)]', 'for xyz in coords:\n            x, y, z = xyz'),
                ('(value * adc["scale"] + adc["offset"]) * factors[adc["unit"]]', 'value * factors[adc["unit"]]'),
            ],
        }[family]
        for old, new in replacements:
            if source.count(old) != 1:
                raise RuntimeError("Starter source changed; re-audit injected control")
            source = source.replace(old, new)
    source += f'\nif __name__ == "__main__":\n    with open(sys.argv[1]) as handle:\n        data = json.load(handle)\n    with open(sys.argv[2], "w") as handle:\n        json.dump({family}(data), handle, indent=2, allow_nan=False)\n'
    return source


def make_case(family, seed, variant="flawed"):
    if family not in FAMILIES or variant not in {"flawed", "valid"}:
        raise ValueError("Unknown family or starter variant")
    generate = {"endpoint": _endpoint_input, "claims": _claims_input, "geometry": _geometry_input}[family]
    public_input = generate(seed)
    hidden = []
    for offset in (1001, 2003, 3007):
        inputs = generate(seed + offset)
        hidden.append({"input": inputs, "expected": reference(inputs, family)})
    shuffled = json.loads(json.dumps(public_input))
    for key, value in shuffled.items():
        if isinstance(value, list):
            value.reverse()
    hidden.append({"input": shuffled, "expected": reference(shuffled, family)})
    fingerprint = hashlib.sha256(json.dumps([family, seed, variant]).encode()).hexdigest()[:10]
    files = {"analysis.py": _starter(family, variant), "input.json": json.dumps(public_input, indent=2) + "\n",
             "protocol.md": COMMON + "\n" + PROTOCOLS[family], "schema.md": SCHEMAS[family]}
    return {"id": family + "-" + fingerprint, "family": family, "seed": seed, "variant": variant,
            "instruction": "Audit this research analysis against protocol.md and schema.md. Deliver a corrected or validated standalone analysis.py and run it on input.json to produce output.json. Preserve the frozen scientific question. Do not assume an error exists; justify any changes in a short NOTES.md. The analysis program must work on new inputs following the same documented schema.",
            "files": files, "hidden": hidden}
