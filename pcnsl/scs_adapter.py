"""Read the existing SCS pipeline; write only into an explicitly supplied private output directory."""
import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import Dataset, dump, public_spatial_metric, run, validate_dataset


ROOT = Path("/working/rauschecker1/jkw/projects/cnsl")
REVIEW = ROOT / "dev/genet/exp/20261025_amr_review"
REGIONS = ["Frontal", "Parietal", "Occipital", "Temporal", "AnteriorTemporal",
           "MiddleTemporal", "PosteriorTemporal", "Parietal_Occipital",
           "CorpusCallosum", "CorpusCallosum_Rostrum"]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def load_internal():
    common_path = REVIEW / "multiple_testing/common.py"
    loader_path = ROOT / "dev/genet/exp/20260325_allfeatures_loo/generate_figures.py"
    common = module(common_path, "pcnsl_existing_common")
    loader = module(loader_path, "pcnsl_existing_loader")
    # Existing code is read-only; suppress incidental loader output, never emit source rows.
    with contextlib.redirect_stdout(io.StringIO()):
        frame, _ = loader.load_data()
        rows, _, _, labels = common.load_cohort("strict40")
    used = pd.read_csv(REVIEW / "multiple_testing/cohort_used.csv", dtype={"accessionnumber": str})
    used = used.sort_values("row_index")
    if not np.array_equal(used.row_index.to_numpy(), np.arange(len(frame))):
        raise ValueError("Cohort cache row indices do not align with feature loader")
    if not np.array_equal(used.accessionnumber.astype(str).to_numpy(), frame.accessionnumber.astype(str).to_numpy()):
        raise ValueError("Cohort cache accession order differs from feature loader")
    selected = frame.iloc[rows].copy()
    groups = used.iloc[rows].patient_code.to_numpy()
    if len(selected) != 40 or len(np.unique(groups)) != 40:
        raise ValueError("Expected strict40: 40 distinct patients and one scan each")
    normalized_sex = selected.sex.astype("string").str.strip().str.lower()
    selected["sex_male"] = normalized_sex.map({"male": 1.0, "female": 0.0}).astype(float)
    spatial = ["FLAIR_percentage_volume_in_" + region for region in REGIONS]
    if loader.select_features(frame, "spatial_only") != ["age_at_diagnosis"] + spatial:
        raise ValueError("Canonical spatial feature list changed; re-audit mapping")
    # Keep numeric imaging columns, including constants and sparse features. No cohort-wide
    # variance/missingness threshold is learned from held-out rows. Imputation is fold-local.
    excluded = {"accessionnumber", "id", "label", "age_at_diagnosis", "sex_male"}
    imaging = [c for c in frame.columns if c not in excluded
               and pd.api.types.is_numeric_dtype(frame[c])
               and not any(pattern in c for pattern in loader.EXCLUDE_PATTERNS)]
    names = ["age_at_diagnosis", "sex_male"] + imaging
    X = selected[names].to_numpy(dtype=float)
    views = {
        "demographics": [0, 1],
        "spatial": [0] + [names.index(c) for c in spatial],
        "spatial_demographics": [0, 1] + [names.index(c) for c in spatial],
        "all": list(range(len(names))),
    }
    data = Dataset([f"case-{i+1:03d}" for i in range(len(selected))],
                   groups, X, names, labels, views)
    validate_dataset(data)
    dictionary = REVIEW / "public_overlap/public_meta/github_UCSF-PCNSL/history_51a8a71b/data_dictionary_imaging.csv"
    with dictionary.open() as f:
        definitions = list(csv.DictReader(f))
    # Require region support in the public dictionary's descriptions or metric names.
    text = "\n".join(r["file type"] + " " + r["description"] for r in definitions)
    if "percentage_volume_in_{Region}" not in text:
        raise ValueError("Public percentage-volume metric family missing")
    metric_names = set()
    for region in REGIONS:
        if region not in text:
            raise ValueError(f"Public dictionary does not document region {region}")
        metric_names.add("percentage_volume_in_" + region)
    compatibility = []
    for column in spatial:
        metric = public_spatial_metric(column, metric_names)
        if metric is None:
            raise ValueError(f"No exact public mapping for {column}")
        compatibility.append({"feature": column, "public_metric": metric,
            "public_file": "FLAIR SummaryLesions CSV", "status": "schema-compatible; values/version unverified"})
    compatibility += [
        {"feature": "age_at_diagnosis", "public_source": "BirthDate and DiagnosisDate",
         "status": "derivable per public_overlap report; dates must not enter agent inputs"},
        {"feature": "sex_male", "public_source": "Sex",
         "status": "schema-compatible; unknown sex retained as missing"},
    ]
    provenance = {
        "cohort": "strict40", "n_patients": len(selected), "n_scans": len(selected),
        "original_cohort": {"scans": len(frame), "patients": int(used.patient_code.nunique())},
        "label_definition": "Existing cohort audit pair_<GENE> paired-tumor-sample binary labels",
        "label_limit": "VUS and pathogenicity policy inherited from existing audit; not reconciled to public mutations CSV",
        "status": "INTERNAL_ONLY_NOT_PUBLIC_RELEASE_VERIFIED",
        "public_export_allowed": False,
        "public_patient_membership_verified": False,
        "public_label_values_verified": False,
        "public_feature_value_equivalence_verified": False,
        "public_compatible_task_feature_count": len(views["spatial_demographics"]),
        "full_numeric_feature_count": len(names),
        "full_features_note": "All numeric candidates after canonical exclusions; constants/sparse features retained to avoid global filtering. Not identical to historic 227-feature filtered cache.",
        "compatibility": compatibility,
        "public_access": "https://imagingdatasets.ucsf.edu/dataset/4 (controlled access)",
        "public_overlap_evidence": "Existing report confirms at least five overlaps, not full cohort identity; public release must not be treated as independent validation.",
        "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            common_path, loader_path, dictionary, REVIEW / "multiple_testing/cohort_used.csv",
            REVIEW / "cohort/cohort_audit_PHI.csv", loader.RADIOMICS, loader.DEMOGRAPHICS,
        ]},
    }
    return data, provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    data, provenance = load_internal()
    print(json.dumps({k: provenance[k] for k in ["cohort", "n_patients", "n_scans",
        "full_numeric_feature_count", "public_compatible_task_feature_count", "status"]}), flush=True)
    report = run(data, args.out)
    dump(args.out / "provenance.json", provenance)
    dump(args.out / "feature_schema.json", {"features": data.feature_names,
         "views": {name: [data.feature_names[i] for i in indices] for name, indices in data.views.items()}})
    print(f"Complete: {len(report['summary'])} model/target summaries; subject-level artifacts remain local", flush=True)


if __name__ == "__main__":
    main()
