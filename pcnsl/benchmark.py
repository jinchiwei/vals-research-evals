"""Local-only radiogenomics development benchmark; no data transfer or model API calls."""
from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import re

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class Dataset:
    ids: list
    groups: np.ndarray
    X: np.ndarray
    feature_names: list
    labels: dict
    views: dict
    label_definition: str = "Paired-tumor-sample binary labels from the existing research audit; pathogenicity policy is not verified."


def validate_dataset(d):
    n = len(d.ids)
    if n == 0 or len(set(d.ids)) != n:
        raise ValueError("Case IDs must be nonempty and unique")
    if d.X.ndim != 2 or d.X.shape != (n, len(d.feature_names)) or len(d.groups) != n:
        raise ValueError("Feature, group and row dimensions must match")
    if len(set(d.feature_names)) != len(d.feature_names) or np.isinf(d.X).any():
        raise ValueError("Feature names must be unique and values must not be infinite")
    if not d.labels:
        raise ValueError("At least one target is required")
    for gene, y in d.labels.items():
        if np.asarray(y).shape != (n,) or not np.isin(y, [0, 1]).all():
            raise ValueError(f"{gene}: labels must be observed binary values, never missing")
        for group in np.unique(d.groups):
            if len(np.unique(y[d.groups == group])) != 1:
                raise ValueError(f"{gene}: conflicting labels for repeated patient")
    for cols in d.views.values():
        if not cols or len(set(cols)) != len(cols) or min(cols) < 0 or max(cols) >= d.X.shape[1]:
            raise ValueError("Invalid feature view")


def make_folds(d, gene, seed, n_splits=5):
    validate_dataset(d)
    if gene not in d.labels:
        raise ValueError("Unknown gene")
    y = d.labels[gene]
    patients, first = np.unique(d.groups, return_index=True)
    counts = np.bincount(y[first].astype(int), minlength=2)
    k = min(n_splits, int(counts.min()))
    if k < 2:
        raise ValueError("Too few independent patients in one class for cross-validation")
    # Split independent patients first, then expand to all their rows. Stratifying
    # rows with a grouped heuristic can leave rare-target folds with one class.
    patient_folds = StratifiedKFold(k, shuffle=True, random_state=seed).split(
        np.zeros((len(patients), 1)), y[first])
    folds = [(np.flatnonzero(np.isin(d.groups, patients[tr])),
              np.flatnonzero(np.isin(d.groups, patients[te]))) for tr, te in patient_folds]
    seen = []
    for tr, te in folds:
        if set(d.groups[tr]) & set(d.groups[te]):
            raise ValueError("Patient crossed evaluation folds")
        if len(np.unique(y[tr])) != 2 or len(np.unique(y[te])) != 2:
            raise ValueError("Both classes must be represented in each patient-stratified fold")
        seen.extend(te)
    if sorted(seen) != list(range(len(y))):
        raise ValueError("Every row must be tested exactly once")
    return folds


def make_model(kind):
    impute = SimpleImputer(strategy="median", keep_empty_features=True)
    if kind == "logreg":
        return Pipeline([
            ("impute", impute), ("scale", StandardScaler()),
            ("model", LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=42)),
        ])
    if kind == "random_forest":
        return Pipeline([
            ("impute", impute),
            ("model", RandomForestClassifier(n_estimators=100, max_depth=3,
                min_samples_leaf=3, class_weight="balanced", random_state=42, n_jobs=1)),
        ])
    raise ValueError("Unknown model")


def score(y, probability):
    y, p = np.asarray(y), np.asarray(probability, dtype=float)
    if y.ndim != 1 or len(y) == 0 or not np.isin(y, [0, 1]).all():
        raise ValueError("Gold labels must be observed binary values")
    if p.shape != y.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Supply exactly one finite probability in [0,1] per case")
    both = len(np.unique(y)) == 2
    return {
        "auroc": float(roc_auc_score(y, p)) if both else None,
        "average_precision": float(average_precision_score(y, p)) if both else None,
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.column_stack([1 - p, p]), labels=[0, 1])),
    }


def grade_submission(gold, submission):
    if not isinstance(submission, list):
        raise ValueError("Submission must be a list")
    expected = gold["ids"]
    actual = [row["id"] for row in submission]
    if len(set(expected)) != len(expected) or len(set(actual)) != len(actual) or set(actual) != set(expected):
        raise ValueError("Prediction IDs must match gold exactly, without duplicates")
    predictions = {row["id"]: row["probability"] for row in submission}
    return score(gold["labels"], [predictions[key] for key in expected])


def public_spatial_metric(column, public_metrics):
    if "flair" not in column.lower():
        return None
    # Require a full metric name, rather than accepting a shared prefix.
    for metric in sorted(public_metrics, key=len, reverse=True):
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(metric) + r"(?![A-Za-z0-9])", column):
            return metric
    return None


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def export_task(d, gene, train, test, out, view="spatial_demographics"):
    if set(d.groups[train]) & set(d.groups[test]):
        raise ValueError("Patient crossed task boundary")
    cols = d.views[view]
    def row(i, labeled):
        obj = {"id": d.ids[i], "x": [None if np.isnan(v) else float(v) for v in d.X[i, cols]]}
        if labeled:
            obj["label"] = int(d.labels[gene][i])
        return obj
    dump(out / "agent" / "input.json", {
        "gene": gene, "feature_names": [d.feature_names[i] for i in cols],
        "label_definition": d.label_definition,
        "train": [row(i, True) for i in train], "test": [row(i, False) for i in test],
    })
    dump(out / "private" / "gold.json", {
        "ids": [d.ids[i] for i in test], "labels": d.labels[gene][test].astype(int).tolist(),
    })
    (out / "agent" / "instruction.md").write_text(
        f"Build a predictor for the supplied {gene} endpoint using the training patients. "
        f"Label definition: {d.label_definition} "
        "Null feature values are missing, not zero. "
        "Submit submission.json as a JSON list of {id, probability}, exactly once per test case. "
        "Probability means P(label=1); do not invert predictions using test outcomes. "
        "Use training-only model selection and preprocessing. Include reproducible analysis.py. "
        "Compare against an age/sex-only model using training data. "
        "A scientifically valid negative result is acceptable; do not invent predictability.\n"
    )


BASELINES = {
    "prevalence": ("demographics", None),
    "age_sex_logreg": ("demographics", "logreg"),
    "spatial_age_logreg": ("spatial", "logreg"),
    "spatial_age_sex_logreg": ("spatial_demographics", "logreg"),
    "all_logreg": ("all", "logreg"),
    "all_random_forest": ("all", "random_forest"),
}


def run(d, out, seeds=(11, 23, 37), baselines=None):
    validate_dataset(d)
    baselines = BASELINES if baselines is None else baselines
    if not seeds or not baselines or any(view not in d.views for view, _ in baselines.values()):
        raise ValueError("Provide seeds and valid baseline feature views")
    out = Path(out)
    if out.exists():
        raise ValueError("Use a new output directory; previous runs are never overwritten")
    out.mkdir(parents=True, mode=0o700)
    results = []
    fold_counts = {}
    task_count = 0
    for gene, y in d.labels.items():
        for seed in seeds:
            folds = make_folds(d, gene, seed)
            fold_counts[gene] = len(folds)
            for model_name, (view, kind) in baselines.items():
                cols = d.views[view]
                predictions = np.full(len(y), np.nan)
                for fold, (train, test) in enumerate(folds):
                    if kind is None or len(np.unique(y[train])) < 2:
                        predictions[test] = y[train].mean()
                    else:
                        model = make_model(kind)
                        model.fit(d.X[train][:, cols], y[train])
                        predictions[test] = model.predict_proba(d.X[test][:, cols])[:, 1]
                    if seed == seeds[0] and model_name == "spatial_age_sex_logreg":
                        task = out / "tasks_local_only" / f"{gene.lower()}-fold-{fold}"
                        export_task(d, gene, train, test, task)
                        task_count += 1
                        sub = [{"id": d.ids[i], "probability": float(predictions[i])} for i in test]
                        dump(task / "reference" / "submission.json", sub)
                        gold = json.loads((task / "private" / "gold.json").read_text())
                        dump(task / "reference" / "score.json", grade_submission(gold, sub))
                metrics = score(y, predictions)
                results.append({"gene": gene, "seed": seed, "model": model_name,
                    "n": len(y), "positive": int(y.sum()), "features": len(cols), **metrics})
                dump(out / "private_predictions" / f"{gene}-{seed}-{model_name}.json", {
                    "ids": d.ids, "labels": y.astype(int).tolist(), "probabilities": predictions.tolist(),
                })
        print(f"Completed {gene}: {len(seeds)} repetitions, {len(baselines)} fixed baselines", flush=True)
    summaries = []
    for gene in d.labels:
        for model in baselines:
            rows = [r for r in results if r["gene"] == gene and r["model"] == model]
            summary = {k: rows[0][k] for k in ("gene", "model", "n", "positive", "features")}
            for metric in ("auroc", "average_precision", "brier", "log_loss"):
                values = [r[metric] for r in rows]
                summary[metric] = float(np.mean(values))
                summary[metric + "_range"] = [min(values), max(values)]
            summaries.append(summary)
    report = {
        "status": "internal-development-only; not public-release verified; no live frontier trial",
        "seeds": list(seeds), "n_patients": len(np.unique(d.groups)), "summary": summaries,
        "label_definition": d.label_definition,
        "fold_counts": fold_counts, "tasks_exported": task_count,
        "split_method": "StratifiedKFold on unique patients, expanded to all rows; both classes required in every train/test fold",
        "limitations": [
            "Historically analyzed cohort: these are development CV results, not new external validation.",
            "Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.",
            "No permutation tests or multiplicity correction in this quick prototype.",
            "Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.",
            "No automatic post-hoc probability flipping or winner-based gene selection.",
            "Agent input and private truth must be isolated before evaluating untrusted agents.",
        ],
    }
    dump(out / "aggregate_results.json", report)
    dump(out / "aggregate_runs.json", results)
    display_models = [m for m in baselines if m != "prevalence"]
    lines = ["# PCNSL tabular development prototype", "", report["status"], "",
        f"AUROC / Brier, averaged over {len(seeds)} fixed repetitions. Folds per target: {json.dumps(fold_counts)}. Fixed baselines, not frontier agents.", "",
        "| Gene | Positive / N | " + " | ".join(display_models) + " |",
        "|---|---:|" + "---:|" * len(display_models)]
    for gene in d.labels:
        rows = {r["model"]: r for r in summaries if r["gene"] == gene}
        cells = [f"{rows[m]['auroc']:.3f} / {rows[m]['brier']:.3f}" for m in display_models]
        lines.append(f"| {gene} | {int(d.labels[gene].sum())} / {len(d.ids)} | " + " | ".join(cells) + " |")
    lines += ["", *["- " + item for item in report["limitations"]]]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade a local task submission; no remote services")
    parser.add_argument("gold", type=Path)
    parser.add_argument("submission", type=Path)
    args = parser.parse_args()
    print(json.dumps(grade_submission(json.loads(args.gold.read_text()), json.loads(args.submission.read_text()))))
