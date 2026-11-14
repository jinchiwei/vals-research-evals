import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import benchmark as b


def fixture():
    return b.Dataset(
        ids=[f"case-{i:03}" for i in range(20)],
        groups=np.repeat(np.arange(10), 2),
        X=np.arange(60, dtype=float).reshape(20, 3),
        feature_names=["age", "sex", "flair_percentage_volume_in_Frontal"],
        labels={"GENE": np.repeat([0, 1] * 5, 2)},
        views={"demographics": [0, 1], "spatial": [0, 2],
               "spatial_demographics": [0, 1, 2], "all": [0, 1, 2]},
    )


class BenchmarkTests(unittest.TestCase):
    def test_patients_never_cross_folds_and_each_row_is_tested_once(self):
        d = fixture()
        folds = b.make_folds(d, "GENE", seed=11)
        seen = []
        for train, test in folds:
            self.assertFalse(set(d.groups[train]) & set(d.groups[test]))
            seen.extend(test)
        self.assertEqual(sorted(seen), list(range(20)))

    def test_missing_label_is_rejected_not_mapped_to_negative(self):
        d = fixture()
        d.labels["GENE"] = d.labels["GENE"].astype(float)
        d.labels["GENE"][0] = np.nan
        with self.assertRaisesRegex(ValueError, "binary"):
            b.validate_dataset(d)

    def test_conflicting_labels_for_repeated_patient_are_rejected(self):
        d = fixture()
        d.labels["GENE"][0] = 1
        with self.assertRaisesRegex(ValueError, "patient"):
            b.validate_dataset(d)

    def test_unknown_gene_and_duplicate_case_ids_are_rejected(self):
        d = fixture()
        with self.assertRaises(ValueError):
            b.make_folds(d, "ABSENT", 0)
        d.ids[1] = d.ids[0]
        with self.assertRaisesRegex(ValueError, "unique"):
            b.validate_dataset(d)

    def test_preprocessing_is_fit_only_on_training_data(self):
        model = b.make_model("logreg")
        train = np.array([[0.0], [2.0], [np.nan], [4.0]])
        model.fit(train, [0, 0, 1, 1])
        np.testing.assert_allclose(model.named_steps["impute"].statistics_, [2.0])
        np.testing.assert_allclose(model.named_steps["scale"].mean_, [2.0])
        model.predict_proba([[100000.0]])
        np.testing.assert_allclose(model.named_steps["scale"].mean_, [2.0])

    def test_auc_is_not_flipped_and_brier_uses_probabilities(self):
        result = b.score([0, 1], [0.9, 0.1])
        self.assertEqual(result["auroc"], 0.0)
        self.assertAlmostEqual(result["brier"], 0.81)

    def test_bad_probability_and_incomplete_submission_are_rejected(self):
        for p in ([0.1, np.nan], [0.1, 1.1], [0.1]):
            with self.assertRaises(ValueError):
                b.score([0, 1], p)
        gold = {"ids": ["a", "b"], "labels": [0, 1]}
        for submission in (
            [{"id": "a", "probability": 0.1}],
            [{"id": "a", "probability": 0.1}, {"id": "a", "probability": 0.9}],
            [{"id": "a", "probability": 0.1}, {"id": "c", "probability": 0.9}],
        ):
            with self.assertRaises(ValueError):
                b.grade_submission(gold, submission)
        result = b.grade_submission(gold, [
            {"id": "b", "probability": 0.9}, {"id": "a", "probability": 0.1}])
        self.assertAlmostEqual(result["brier"], 0.01)

    def test_task_input_has_no_test_labels_and_gold_is_separate(self):
        d = fixture()
        train, test = b.make_folds(d, "GENE", 11)[0]
        with tempfile.TemporaryDirectory() as tmp:
            b.export_task(d, "GENE", train, test, Path(tmp))
            inputs = json.loads((Path(tmp) / "agent" / "input.json").read_text())
            gold = json.loads((Path(tmp) / "private" / "gold.json").read_text())
            self.assertEqual(set(inputs), {"gene", "feature_names", "label_definition", "train", "test"})
            self.assertEqual(inputs["label_definition"], d.label_definition)
            self.assertIn(d.label_definition, (Path(tmp) / "agent" / "instruction.md").read_text())
            self.assertTrue(all(set(row) == {"id", "x"} for row in inputs["test"]))
            self.assertTrue(all(set(row) == {"id", "x", "label"} for row in inputs["train"]))
            self.assertEqual(gold["labels"], d.labels["GENE"][test].tolist())
            self.assertFalse(set(gold["ids"]) & {row["id"] for row in inputs["train"]})

    def test_public_schema_requires_exact_metric_and_sequence(self):
        metrics = {"percentage_volume_in_Frontal"}
        self.assertEqual(b.public_spatial_metric("FLAIR_percentage_volume_in_Frontal", metrics),
                         "percentage_volume_in_Frontal")
        self.assertIsNone(b.public_spatial_metric("FLAIR_percentage_volume_in_FrontalPole", metrics))
        self.assertIsNone(b.public_spatial_metric("unrelated_percentage_volume_in_Frontal", metrics))


if __name__ == "__main__":
    unittest.main()
