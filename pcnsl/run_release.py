"""SCS-only matched Box-candidate experiment. No network calls or patient output."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark import Dataset, dump, make_folds, run, validate_dataset
from release_match import age_at_diagnosis, compare_features, gene_label, read_summary, release_date
from scs_adapter import REGIONS, REVIEW, load_internal


BASELINES = {
    "prevalence": ("demographics", None),
    "age_sex_logreg": ("demographics", "logreg"),
    "spatial_age_logreg": ("spatial", "logreg"),
    "spatial_age_sex_logreg": ("spatial_demographics", "logreg"),
    "spatial_random_forest": ("spatial_demographics", "random_forest"),
}
DEFINITIONS = {
    "legacy_any_listed": "1 means the gene appears in any mutation-table row for the paired tumor sample. This includes variants of uncertain significance and unclassified or unreported alterations; it does NOT mean a pathogenic mutation is present. 0 means no gene row is listed for a sample with mutation records.",
    "reported_pathogenic": "1 means at least one gene row has reportedalteration=True, classification Pathogenic or Likely Pathogenic, and geneticorigin is not 'Not Detected'. 0 means no qualifying row among this sample's mutation records. This is a reported-alteration endpoint, not proof of biological wild type or somatic origin.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame["subject_key"] = frame.patientdurablekey.str.zfill(4)
    return frame


def prepare(source):
    metadata = json.loads((source / "aggregate_manifest.json").read_text())["files"]
    for name, item in metadata.items():
        if sha(source / name) != item["sha256"]:
            raise ValueError("Metadata hash mismatch")
    feature_hashes = json.loads((source / "feature_manifest.json").read_text())
    if len(feature_hashes) != 33:
        raise ValueError("Expected 33 downloaded feature files")
    for name, expected in feature_hashes.items():
        if sha(source / "features" / name) != expected:
            raise ValueError("Feature hash mismatch")

    internal, provenance = load_internal()
    cohort = pd.read_csv(REVIEW / "multiple_testing/cohort_used.csv")
    strict = cohort.loc[cohort.in_strict40.astype(str).str.lower().isin(["true", "1"])].sort_values("row_index")
    if len(strict) != 40 or not np.array_equal(strict.patient_code.to_numpy(), internal.groups):
        raise ValueError("Strict cohort ordering no longer matches the existing adapter")
    row_to_position = {int(row): i for i, row in enumerate(strict.row_index)}
    crosswalk = pd.read_csv(source / "scan_label_comparison_PHI.csv", dtype={"public_sub": str})
    mask = crosswalk.same_scan.astype(str).str.lower().eq("true") & crosswalk.same_sample_date.astype(str).str.lower().eq("true")
    matched = crosswalk.loc[mask].sort_values("public_sub").reset_index(drop=True)
    if len(matched) != 33 or matched.public_sub.nunique() != 33 or matched.row_index.nunique() != 33:
        raise ValueError("Exact scan/sample cohort changed")
    positions = np.array([row_to_position[int(row)] for row in matched.row_index])
    demographics = table(source / "demographics.csv").set_index("subject_key", verify_integrity=True)
    dates = table(source / "biopsy_and_diagnosis_dates.csv").set_index("subject_key", verify_integrity=True)
    mutations = table(source / "ucsf500_mutations.csv")
    metrics = ["percentage_volume_in_" + name for name in REGIONS]
    names = ["age_at_diagnosis", "sex_male"] + ["FLAIR_" + name for name in metrics]
    labels = {policy: {gene: [] for gene in internal.labels} for policy in DEFINITIONS}
    values, used_paths = [], []
    for subject in matched.public_sub:
        key = subject.removeprefix("sub-").zfill(4)
        demo, visit = demographics.loc[key], dates.loc[key]
        sub, ses = "sub-" + key, "ses-" + visit.accessions.zfill(4)
        relative = f"{sub}/{ses}/statistics/lesions_SummaryLesions/{sub}_{ses}_FLAIR_SummaryLesions.csv"
        if relative not in feature_hashes:
            raise ValueError("Required feature file is absent from verified manifest")
        used_paths.append(relative)
        sex = {"male": 1., "female": 0.}.get(demo.Sex.strip().lower(), float("nan"))
        values.append(np.r_[age_at_diagnosis(demo.BirthDate, visit.DiagnosisDate), sex,
                            read_summary(source / "features" / relative, metrics)])
        records = mutations.loc[mutations.subject_key.eq(key)].to_dict("records")
        sample_dates = {release_date(r["tumorcollecteddate"]) for r in records}
        if len(sample_dates) != 1 or None in sample_dates:
            raise ValueError("Expected a single observed tumor sample date")
        for policy in labels:
            for gene in internal.labels:
                labels[policy][gene].append(gene_label(records, gene, policy))
    if set(used_paths) != set(feature_hashes):
        raise ValueError("Feature downloads and selected cohort do not match exactly")
    labels = {p: {g: np.array(y, dtype=int) for g, y in targets.items()} for p, targets in labels.items()}
    for gene, y in labels["legacy_any_listed"].items():
        if not np.array_equal(y, internal.labels[gene][positions]):
            raise ValueError("Legacy gene labels differ from paired internal labels")
    X = np.array(values)
    internal_X = internal.X[positions][:, [internal.feature_names.index(n) for n in names]]
    views = {"demographics": [0, 1], "spatial": [0] + list(range(2, 12)),
             "spatial_demographics": list(range(12)), "all": list(range(12))}
    ids = [f"case-{i+1:03d}" for i in range(33)]
    def dataset(matrix, policy, targets):
        result = Dataset(ids, internal.groups[positions], matrix, names, targets, views, DEFINITIONS[policy])
        validate_dataset(result)
        return result
    box = dataset(X, "legacy_any_listed", labels["legacy_any_listed"])
    control = dataset(internal_X, "legacy_any_listed", labels["legacy_any_listed"])
    strict_labels, exclusions = {}, {}
    for gene, y in labels["reported_pathogenic"].items():
        if min(int(y.sum()), len(y) - int(y.sum())) < 2:
            exclusions[gene] = {"positive": int(y.sum()), "reason": "Fewer than two independent patients in one class"}
        else:
            strict_labels[gene] = y
    reported = dataset(X, "reported_pathogenic", strict_labels) if strict_labels else None
    for gene in box.labels:
        for seed in (11, 23, 37):
            for a, b in zip(make_folds(box, gene, seed), make_folds(control, gene, seed)):
                if not all(np.array_equal(x, y) for x, y in zip(a, b)):
                    raise ValueError("Box and internal comparison folds differ")
    report = {
        "status": "BOX_RELEASE_CANDIDATE_LOCAL_DEVELOPMENT_ONLY",
        "source": "scs2box:pcnsl_radiomics/dataset_manuscript/",
        "published_archive_identity_verified": False, "public_export_allowed": False,
        "n_patients": 33, "exact_scan_and_sample_matches": 33,
        "patient_overlap_before_sample_date_filter": 35,
        "excluded_for_sample_date_mismatch": 2,
        "legacy_label_comparisons": 33 * len(internal.labels), "legacy_label_disagreements": 0,
        "feature_agreement": compare_features(X, internal_X, names),
        "spatial_feature_agreement": compare_features(X[:, 2:], internal_X[:, 2:], names[2:]),
        "label_definitions": DEFINITIONS,
        "positive_counts": {p: {g: int(y.sum()) for g, y in targets.items()} for p, targets in labels.items()},
        "reported_pathogenic_exclusions": exclusions,
        "metadata_hashes_verified": len(metadata), "feature_hashes_verified": len(feature_hashes),
        "same_folds_for_box_and_internal_legacy": True,
        "source_sha256": {name: item["sha256"] for name, item in metadata.items()},
        "feature_manifest_sha256": sha(source / "feature_manifest.json"),
        "crosswalk_sha256": sha(source / "scan_label_comparison_PHI.csv"),
        "internal_source_sha256": provenance["source_sha256"],
        "code_sha256": {name: sha(Path(__file__).parent / name) for name in
                        ["benchmark.py", "scs_adapter.py", "release_match.py", "run_release.py"]},
        "limitations": ["These patients were historically studied; this is not independent validation.",
            "A Box release-preparation folder is not verified identical to the official published archive.",
            "An unlisted qualifying variant is a table-derived negative, not proof of biological wild type.",
            "Sparse targets and correlated folds make estimates unstable; no multiplicity correction or frontier trial performed."],
    }
    matched["case_id"] = ids
    return box, control, reported, report, matched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("release_candidate"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.out.exists():
        raise ValueError("Use a new output directory")
    box, control, reported, report, crosswalk = prepare(args.source)
    args.out.mkdir(parents=True, mode=0o700)
    dump(args.out / "comparison.json", report)
    crosswalk.to_csv(args.out / "crosswalk_PHI.csv", index=False)
    dump(args.out / "feature_schema.json", {"features": box.feature_names,
         "views": {k: [box.feature_names[i] for i in v] for k, v in box.views.items()}})
    print(json.dumps({k: report[k] for k in ["n_patients", "legacy_label_disagreements", "feature_agreement", "positive_counts"]}), flush=True)
    for name, data in [("box_legacy", box), ("internal_matched_legacy", control), ("box_reported_pathogenic", reported)]:
        if data is None:
            continue
        print("Starting " + name, flush=True)
        result = run(data, args.out / name, baselines=BASELINES)
        result["input_source"] = "internal matched research features" if name.startswith("internal") else "Box release candidate features"
        result["status"] = report["status"]
        dump(args.out / name / "aggregate_results.json", result)
    dump(args.out / "completed.json", {"complete": True, "n_patients": 33})
    print("Complete; patient-level artifacts remain on SCS", flush=True)


if __name__ == "__main__":
    main()
