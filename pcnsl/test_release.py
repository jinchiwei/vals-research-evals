import tempfile
import unittest
from pathlib import Path

import numpy as np

import benchmark as b
from test_benchmark import fixture
import release_match as r


class ReleaseTests(unittest.TestCase):
    def test_release_age_preserves_missing_and_corrects_two_digit_birth_century(self):
        self.assertEqual(r.release_date("1/1/66").year, 1966)
        self.assertEqual(r.age_at_diagnosis("1/1/2000", "1/1/2004"), 4.0)
        self.assertTrue(np.isnan(r.age_at_diagnosis("", "1/1/2004")))
        with self.assertRaises(ValueError):
            r.age_at_diagnosis("1/1/2090", "1/1/2004")

    def test_summary_reads_required_metrics_by_name_not_row_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.csv"
            path.write_text("Label,Value\nother,99\npercentage_volume_in_Parietal,20\npercentage_volume_in_Frontal,30\n")
            result = r.read_summary(path, ["percentage_volume_in_Frontal", "percentage_volume_in_Parietal"])
            np.testing.assert_array_equal(result, [30, 20])

    def test_summary_rejects_missing_duplicate_and_nonfinite_required_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.csv"
            for body in ["Label,Value\nwrong,1\n", "Label,Value\nmetric,1\nmetric,2\n",
                         "Label,Value\nmetric,nan\n"]:
                path.write_text(body)
                with self.assertRaises(ValueError):
                    r.read_summary(path, ["metric"])

    def test_gene_token_and_strict_reported_pathogenic_policy(self):
        records = [
            {"gene": "IRF4", "variantclassification": "Uncertain Significance", "reportedalteration": "True", "geneticorigin": "Detected"},
            {"gene": "PRKDC", "variantclassification": "Pathogenic", "reportedalteration": "False", "geneticorigin": "Detected"},
            {"gene": "CD79B", "variantclassification": "Likely Pathogenic", "reportedalteration": "True", "geneticorigin": "Detected"},
            {"gene": "TP53", "variantclassification": "Pathogenic", "reportedalteration": "True", "geneticorigin": "Not Detected"},
            {"gene": "MYD88;BTG1", "variantclassification": "Pathogenic", "reportedalteration": "True", "geneticorigin": "Somatic"},
        ]
        self.assertEqual(r.gene_label(records, "IRF4", "legacy_any_listed"), 1)
        self.assertEqual(r.gene_label(records, "IRF", "legacy_any_listed"), 0)
        self.assertEqual(r.gene_label(records, "IRF4", "reported_pathogenic"), 0)
        self.assertEqual(r.gene_label(records, "PRKDC", "reported_pathogenic"), 0)
        self.assertEqual(r.gene_label(records, "CD79B", "reported_pathogenic"), 1)
        self.assertEqual(r.gene_label(records, "TP53", "reported_pathogenic"), 0)
        self.assertEqual(r.gene_label(records, "BTG1", "reported_pathogenic"), 1)
        with self.assertRaises(ValueError):
            r.gene_label([], "IRF4", "legacy_any_listed")
        with self.assertRaises(ValueError):
            r.gene_label(records, "IRF4", "undefined_policy")

    def test_feature_comparison_flags_mismatch_without_replacing_values(self):
        box = np.array([[1., 2.], [3., 4.]])
        internal = np.array([[1., 2.], [3., 4.2]])
        result = r.compare_features(box, internal, ["a", "b"])
        self.assertEqual(result["matching_values"], 3)
        self.assertEqual(result["rows_with_difference"], 1)
        self.assertAlmostEqual(result["per_feature"]["b"]["max_absolute_difference"], 0.2)
        np.testing.assert_array_equal(box, [[1., 2.], [3., 4.]])

    def test_configured_baselines_and_actual_fold_counts(self):
        d = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            result = b.run(d, Path(tmp) / "run", seeds=(11,), baselines={
                "age_sex_logreg": ("demographics", "logreg"),
                "spatial_age_sex_logreg": ("spatial_demographics", "logreg"),
            })
            self.assertEqual(len(result["summary"]), 2)
            self.assertEqual(result["fold_counts"], {"GENE": 5})
            self.assertEqual(result["tasks_exported"], 5)
            self.assertEqual(result["seeds"], [11])
            with self.assertRaises(ValueError):
                b.run(d, Path(tmp) / "run")

    def test_rare_target_uses_supported_fold_count(self):
        d = fixture()
        d.labels["GENE"] = np.repeat([1, 1] + [0] * 8, 2)
        self.assertEqual(len(b.make_folds(d, "GENE", 11)), 2)

    def test_patient_stratification_keeps_both_classes_in_every_fold(self):
        d = fixture()
        d.labels["GENE"] = np.repeat([1, 1] + [0] * 8, 2)
        datasets = [d]
        for positives in (2, 3, 4):
            datasets.append(b.Dataset([f"synthetic-{i}" for i in range(33)],
                np.arange(33), np.arange(99, dtype=float).reshape(33, 3),
                d.feature_names, {"GENE": np.random.default_rng(42).permutation(
                    np.array([1] * positives + [0] * (33 - positives)))}, d.views))
        for data in datasets:
            for seed in range(20):
                for train, test in b.make_folds(data, "GENE", seed):
                    self.assertEqual(set(data.labels["GENE"][train]), {0, 1})
                    self.assertEqual(set(data.labels["GENE"][test]), {0, 1})
                    self.assertFalse(set(data.groups[train]) & set(data.groups[test]))


if __name__ == "__main__":
    unittest.main()
