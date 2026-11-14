"""Replay all private graders and check matched-cohort artifacts; print aggregates only."""
import argparse
import json
import os
from pathlib import Path

import numpy as np

from benchmark import dump, grade_submission, make_folds, score
from run_release import BASELINES, prepare, sha


def read(path):
    return json.loads(Path(path).read_text())


def verify(root, source):
    assert read(root / "completed.json")["complete"]
    comparison = read(root / "comparison.json")
    for name, digest in comparison["code_sha256"].items():
        assert sha(Path(__file__).parent / name) == digest, "Run code changed"
    box, control, reported, fresh, _ = prepare(source)
    assert fresh == comparison, "Inputs or matching provenance changed"
    checks = {}
    for name, data in [("box_legacy", box), ("internal_matched_legacy", control), ("box_reported_pathogenic", reported)]:
        if data is None:
            continue
        run = root / name
        aggregate = read(run / "aggregate_results.json")
        rows = read(run / "aggregate_runs.json")
        assert len(rows) == len(data.labels) * len(BASELINES) * 3
        assert len(aggregate["summary"]) == len(data.labels) * len(BASELINES)
        assert aggregate["label_definition"] == data.label_definition
        for gene, labels in data.labels.items():
            for seed in aggregate["seeds"]:
                for train, test in make_folds(data, gene, seed):
                    assert set(labels[train]) == {0, 1}, "One-class training fold"
                    assert set(labels[test]) == {0, 1}, "One-class test fold"
        for row in rows:
            prediction = read(run / "private_predictions" / f"{row['gene']}-{row['seed']}-{row['model']}.json")
            assert prediction["ids"] == data.ids
            assert prediction["labels"] == data.labels[row["gene"]].tolist()
            for metric, value in score(prediction["labels"], prediction["probabilities"]).items():
                assert np.isclose(value, row[metric], atol=1e-12, rtol=0)
        for summary in aggregate["summary"]:
            repeats = [r for r in rows if r["gene"] == summary["gene"] and r["model"] == summary["model"]]
            for metric in ("auroc", "average_precision", "brier", "log_loss"):
                assert np.isclose(np.mean([r[metric] for r in repeats]), summary[metric], atol=1e-12, rtol=0)
        task_count = 0
        for gene in data.labels:
            seen = []
            folds = make_folds(data, gene, 11)
            assert len(folds) == aggregate["fold_counts"][gene]
            for index, (train, test) in enumerate(folds):
                task = run / "tasks_local_only" / f"{gene.lower()}-fold-{index}"
                inputs, gold = read(task / "agent/input.json"), read(task / "private/gold.json")
                assert set(inputs) == {"gene", "feature_names", "label_definition", "train", "test"}
                assert inputs["label_definition"] == data.label_definition
                assert inputs["feature_names"] == data.feature_names
                assert [r["id"] for r in inputs["train"]] == [data.ids[i] for i in train]
                assert [r["id"] for r in inputs["test"]] == gold["ids"] == [data.ids[i] for i in test]
                assert all(set(r) == {"id", "x"} for r in inputs["test"])
                assert [r["label"] for r in inputs["train"]] == data.labels[gene][train].tolist()
                assert gold["labels"] == data.labels[gene][test].tolist()
                for role, indices in [("train", train), ("test", test)]:
                    matrix = np.array([[np.nan if x is None else x for x in r["x"]] for r in inputs[role]])
                    assert np.allclose(matrix, data.X[indices], rtol=0, atol=0, equal_nan=True)
                assert not set(data.groups[train]) & set(data.groups[test])
                replay = grade_submission(gold, read(task / "reference/submission.json"))
                assert replay == read(task / "reference/score.json")
                seen.extend(gold["ids"])
                task_count += 1
            assert sorted(seen) == sorted(data.ids)
        assert task_count == aggregate["tasks_exported"]
        assert len(list((run / "tasks_local_only").iterdir())) == task_count
        checks[name] = {"patient_count": len(data.ids), "targets": len(data.labels),
            "model_target_summaries": len(aggregate["summary"]), "prediction_files_replayed": len(rows),
            "tasks_verified": task_count, "fold_counts": aggregate["fold_counts"],
            "test_labels_absent_from_agent_inputs": True, "patients_never_cross_folds": True,
            "both_classes_in_all_train_and_test_folds": True,
            "each_patient_tested_once_per_target": True, "grader_replay_matches": True}
    assert os.stat(root).st_mode & 0o077 == 0
    assert all(os.stat(p).st_mode & 0o077 == 0 for p in root.rglob("*")), "Run artifacts must be owner-only"
    result = {"verified": True, "code_and_source_hashes_match": True,
              "run_artifacts_owner_only": True, "runs": checks,
              "published_archive_identity_verified": False, "live_frontier_trial_performed": False}
    dump(root / "verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--source", type=Path, default=Path("release_candidate"))
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(verify(args.run, args.source), indent=2))
