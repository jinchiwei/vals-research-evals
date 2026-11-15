"""Mutation-prediction harness tests: splits, held-out-label separation, parser.

Synthetic fixtures only. No patient rows, model APIs or network access.
Run with: python3 -m unittest tests.test_prediction_eval -v
"""
import importlib.util
import json
import math
import random
import unittest

HAVE_SKLEARN = importlib.util.find_spec("sklearn") is not None
SEED = 20261114


def api():
    assert importlib.util.find_spec("pcnsl.prediction_eval") is not None, \
        "pcnsl/prediction_eval.py must exist"
    from pcnsl import prediction_eval
    return prediction_eval


def fixture(n=64, n_features=6, seed=5, positives=None, secret_ids=True):
    """Synthetic dataset in the load_dataset() contract. Feature 0 carries signal."""
    rng = random.Random(seed)
    positives = positives or {"GENEA": 26, "GENEB": 9, "RARE": 3}
    ids = [f"SECRET_CASE_{i:03d}" if secret_ids else f"case-{i:03d}" for i in range(n)]
    labels = {}
    for gene, count in positives.items():
        chosen = set(rng.sample(range(n), count))
        labels[gene] = [int(i in chosen) for i in range(n)]
    X = []
    for i in range(n):
        row = [rng.gauss(0, 1) + 1.5 * labels["GENEA"][i]]
        row += [rng.gauss(0, 1) for _ in range(n_features - 1)]
        if i % 11 == 0:
            row[2] = None
        X.append(row)
    names = [f"feat_{j}" for j in range(n_features)]
    return {"case_ids": ids, "feature_names": names, "X": X, "labels": labels,
            "feature_groups": {"spatial": names[:3], "clinical": names[3:]},
            "metadata": {"source_kind": "synthetic fixture"}}


class SpyArm:
    """Records exactly what an arm is given; predicts a constant."""
    name = "spy"

    def __init__(self, name="spy"):
        self.name = name
        self.seen = []

    def availability(self):
        return {"available": True}

    def predict_fold(self, fold):
        self.seen.append(fold)
        return [0.5] * len(fold.test_X)


class SplitTests(unittest.TestCase):
    def test_five_disjoint_covering_folds_with_both_classes_everywhere(self):
        pe = api(); data = fixture()
        for gene in ["GENEA", "GENEB"]:
            folds = pe.make_splits(data["case_ids"], data["labels"][gene], gene=gene, seed=SEED)
            self.assertEqual(len(folds), 5)
            tested = [i for f in folds for i in f["test"]]
            self.assertEqual(sorted(tested), list(range(64)))
            for f in folds:
                self.assertFalse(set(f["train"]) & set(f["test"]))
                self.assertEqual(sorted(f["train"] + f["test"]), list(range(64)))
                y = data["labels"][gene]
                self.assertEqual({y[i] for i in f["test"]}, {0, 1})
                self.assertEqual({y[i] for i in f["train"]}, {0, 1})

    def test_stratification_balances_each_class_within_one(self):
        pe = api(); data = fixture(); y = data["labels"]["GENEA"]
        folds = pe.make_splits(data["case_ids"], y, gene="GENEA", seed=SEED)
        for cls in (0, 1):
            counts = [sum(1 for i in f["test"] if y[i] == cls) for f in folds]
            self.assertLessEqual(max(counts) - min(counts), 1)
        sizes = [len(f["test"]) for f in folds]
        self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_assignment_is_deterministic_and_independent_of_row_order(self):
        pe = api(); data = fixture(); y = data["labels"]["GENEA"]
        ids = data["case_ids"]
        first = pe.make_splits(ids, y, gene="GENEA", seed=SEED)
        again = pe.make_splits(ids, y, gene="GENEA", seed=SEED)
        self.assertEqual(first, again)
        by_case = {ids[i]: k for k, f in enumerate(first) for i in f["test"]}
        order = list(range(64)); random.Random(1).shuffle(order)
        shuffled = pe.make_splits([ids[i] for i in order], [y[i] for i in order], gene="GENEA", seed=SEED)
        moved = {ids[order[i]]: k for k, f in enumerate(shuffled) for i in f["test"]}
        self.assertEqual(by_case, moved)
        self.assertEqual(pe.split_fingerprint(ids, first),
                         pe.split_fingerprint([ids[i] for i in order], shuffled))

    def test_seed_and_gene_change_the_assignment(self):
        pe = api(); data = fixture(); y = data["labels"]["GENEA"]; ids = data["case_ids"]
        base = pe.make_splits(ids, y, gene="GENEA", seed=SEED)
        self.assertNotEqual(base, pe.make_splits(ids, y, gene="GENEA", seed=SEED + 1))
        self.assertNotEqual(pe.split_fingerprint(ids, base),
                            pe.split_fingerprint(ids, pe.make_splits(ids, y, gene="OTHER", seed=SEED)))

    def test_default_seed_is_the_prespecified_one(self):
        pe = api()
        self.assertEqual(pe.DEFAULT_SEED, 20261114)
        self.assertEqual(pe.N_SPLITS, 5)
        self.assertEqual(pe.MIN_CLASS_COUNT, 5)

    def test_rows_of_one_patient_never_span_train_and_test(self):
        pe = api()
        ids = [f"scan-{i}" for i in range(40)]
        groups = [f"patient-{i // 2}" for i in range(40)]
        y = [int(i // 2 < 8) for i in range(40)]
        folds = pe.make_splits(ids, y, gene="G", seed=SEED, groups=groups)
        for f in folds:
            self.assertFalse({groups[i] for i in f["train"]} & {groups[i] for i in f["test"]})
        with self.assertRaises(ValueError):
            pe.make_splits(ids, [i % 2 for i in range(40)], gene="G", seed=SEED, groups=groups)

    def test_rejects_too_few_patients_per_class_and_bad_inputs(self):
        pe = api()
        ids = [f"c{i}" for i in range(20)]
        with self.assertRaises(ValueError):
            pe.make_splits(ids, [1] * 4 + [0] * 16, gene="G", seed=SEED)
        with self.assertRaises(ValueError):
            pe.make_splits(ids, [2] + [0] * 19, gene="G", seed=SEED)
        with self.assertRaises(ValueError):
            pe.make_splits(["dup"] * 20, [1] * 10 + [0] * 10, gene="G", seed=SEED)

    def test_gene_eligibility_uses_class_counts_only(self):
        pe = api(); data = fixture()
        eligible, excluded = pe.eligible_genes(data["labels"], min_class_count=5)
        self.assertEqual(eligible, ["GENEA", "GENEB"])
        self.assertEqual(excluded["RARE"]["positive"], 3)
        self.assertEqual(excluded["RARE"]["no_qualifying_report"], 61)

    def test_every_arm_gets_identical_splits_and_features(self):
        pe = api(); data = fixture()
        a, b = SpyArm("a"), SpyArm("b")
        report = pe.run_evaluation(data, [a, b], bootstrap=0)
        self.assertEqual(len(a.seen), 10)
        for fa, fb in zip(a.seen, b.seen):
            self.assertEqual(fa, fb)
        for gene in report["genes"].values():
            prints = {arm["split_fingerprint"] for arm in gene["arms"].values()}
            self.assertEqual(len(prints), 1)
            self.assertEqual({arm["feature_fingerprint"] for arm in gene["arms"].values()},
                             {report["design"]["feature_fingerprint"]})


class LeakageTests(unittest.TestCase):
    def test_legitimate_radiomics_names_keep_their_meaning_for_frontier_models(self):
        names = [
            'FLAIR_individual_largest_average_dist_to_ventricles_(voxels)',
            'T1Post_individual_weighted_percentage_volume_in_CorpusCallosum_Splenium',
            'FLAIR_individual_largest_lesion_volume_in_Cortical Gray Matter',
        ]
        self.assertEqual(api().safe_feature_names(names), tuple(names))
        unsafe = ['Patient 12345678', '/mnt/private/patient', 'name\nsecret', '<PatientName>']
        self.assertTrue(all(a != b for a, b in zip(unsafe, api().safe_feature_names(unsafe))))

    def test_arms_never_receive_held_out_labels_or_original_case_ids(self):
        pe = api(); data = fixture()
        spy = SpyArm()
        pe.run_evaluation(data, [spy], bootstrap=0)
        for fold in spy.seen:
            fields = set(vars(fold)) if hasattr(fold, "__dict__") else set(fold._fields)
            self.assertFalse({f for f in fields if "test" in f and ("y" in f.split("_") or "label" in f)})
            self.assertEqual(len(fold.train_X), len(fold.train_y))
            self.assertEqual(len(fold.test_X), len(fold.test_ids))
            self.assertNotIn("SECRET_CASE", json.dumps([fold.train_ids, fold.test_ids]))

    def test_changing_held_out_labels_cannot_change_any_arm_input(self):
        """Fix the splits, then flip only test labels: arm inputs must be byte-identical."""
        pe = api(); data = fixture(); gene = "GENEA"
        folds = pe.make_splits(data["case_ids"], data["labels"][gene], gene=gene, seed=SEED)
        X = pe.canonical_matrix(data["X"])
        for k, split in enumerate(folds):
            original = pe.build_fold(data["case_ids"], data["feature_names"], X,
                                     data["labels"][gene], split, gene=gene, fold=k, seed=SEED)
            flipped_labels = list(data["labels"][gene])
            for i in split["test"]:
                flipped_labels[i] = 1 - flipped_labels[i]
            flipped = pe.build_fold(data["case_ids"], data["feature_names"], X,
                                    flipped_labels, split, gene=gene, fold=k, seed=SEED)
            self.assertEqual(original, flipped)
            self.assertEqual(json.dumps(pe.build_llm_payload(original), sort_keys=True),
                             json.dumps(pe.build_llm_payload(flipped), sort_keys=True))

    def test_test_row_order_does_not_encode_the_label(self):
        pe = api(); data = fixture(); gene = "GENEA"; y = data["labels"][gene]
        folds = pe.make_splits(data["case_ids"], y, gene=gene, seed=SEED)
        sorted_by_label = 0
        for k, split in enumerate(folds):
            fold, key = pe.build_fold(data["case_ids"], data["feature_names"], pe.canonical_matrix(data["X"]),
                                      y, split, gene=gene, fold=k, seed=SEED, return_key=True)
            hidden = [y[i] for i in key]
            self.assertEqual(sorted(key), sorted(split["test"]))
            sorted_by_label += hidden == sorted(hidden) or hidden == sorted(hidden, reverse=True)
        self.assertLess(sorted_by_label, 5)

    def test_train_only_preprocessing_ignores_test_rows(self):
        pe = api()
        train = [[1.0, None, 5.0], [3.0, None, 5.0], [5.0, 2.0, 5.0]]
        prep = pe.fit_preprocessor(train)
        self.assertEqual(prep["median"], [3.0, 2.0, 5.0])
        self.assertEqual(prep["scale"][2], 1.0)          # constant column is not divided by zero
        out = pe.apply_preprocessor(prep, [[1e9, None, None]])
        self.assertEqual(out[0][1], 0.0)                 # test missing value -> training median
        self.assertEqual(out[0][2], 0.0)
        self.assertGreater(out[0][0], 1e6)               # extreme test value did not rescale anything
        empty = pe.fit_preprocessor([[None, 1.0], [None, 2.0]])
        self.assertEqual(empty["all_missing"], [0])
        self.assertEqual(pe.apply_preprocessor(empty, [[7.0, 1.5]])[0][0], 0.0)

    def test_report_is_aggregate_only(self):
        pe = api(); data = fixture()
        report = pe.run_evaluation(data, [pe.TrainingPrevalenceArm()], bootstrap=50)
        text = json.dumps(report, allow_nan=False)
        self.assertNotIn("SECRET_CASE", text)
        self.assertNotIn("test-0", text)
        self.assertNotIn("predictions", text)
        self.assertNotIn("wild", text.lower())
        self.assertEqual(report["design"]["patient_level_outputs"], False)

    def test_llm_payload_is_sanitized_and_has_no_test_labels(self):
        pe = api(); data = fixture()
        data["feature_names"][1] = "MRN 12345678 <b>name</b>"
        gene = "GENEA"; y = data["labels"][gene]
        split = pe.make_splits(data["case_ids"], y, gene=gene, seed=SEED)[0]
        fold = pe.build_fold(data["case_ids"], data["feature_names"], pe.canonical_matrix(data["X"]),
                             y, split, gene=gene, fold=0, seed=SEED)
        payload = pe.build_llm_payload(fold)
        text = json.dumps(payload)
        self.assertNotIn("SECRET_CASE", text)
        self.assertNotIn("12345678", text)
        self.assertNotIn("<b>", text)
        self.assertNotIn("wild", text.lower())
        self.assertEqual(len(payload["train"]), len(split["train"]))
        self.assertEqual(len(payload["test"]), len(split["test"]))
        self.assertTrue(all(set(r) == {"case", "features", "label"} for r in payload["train"]))
        self.assertTrue(all(set(r) == {"case", "features"} for r in payload["test"]))
        self.assertTrue(all(r["label"] in (0, 1) for r in payload["train"]))
        self.assertEqual(payload["label_definition"]["0"], "no qualifying alteration reported")
        pe.assert_payload_sanitized(payload, data["case_ids"])
        payload["test"][0]["label"] = 1
        with self.assertRaises(ValueError):
            pe.assert_payload_sanitized(payload, data["case_ids"])

    def test_dataset_validation_rejects_non_numeric_and_misaligned_rows(self):
        pe = api()
        for mutate in (lambda d: d["X"][0].__setitem__(0, "1.5"),
                       lambda d: d["X"][0].__setitem__(0, float("nan")),
                       lambda d: d["X"][0].__setitem__(0, True),
                       lambda d: d["X"].pop(),
                       lambda d: d["labels"]["GENEA"].__setitem__(0, 2),
                       lambda d: d["case_ids"].__setitem__(1, d["case_ids"][0])):
            data = fixture(); mutate(data)
            with self.assertRaises(ValueError):
                pe.validate_dataset(data)

    @unittest.skipUnless(HAVE_SKLEARN, "scikit-learn not installed on this host")
    def test_logistic_regression_is_not_transductive(self):
        pe = api(); data = fixture(); gene = "GENEA"; y = data["labels"][gene]
        split = pe.make_splits(data["case_ids"], y, gene=gene, seed=SEED)[0]
        X = pe.canonical_matrix(data["X"])
        fold = pe.build_fold(data["case_ids"], data["feature_names"], X, y, split, gene=gene, fold=0, seed=SEED)
        arm = pe.LogisticRegressionArm()
        base = arm.predict_fold(fold)
        test_X = [list(r) for r in fold.test_X]
        for row in test_X[1:]:
            row[0] = 1e6
        changed = arm.predict_fold(fold._replace(test_X=tuple(tuple(r) for r in test_X)))
        self.assertAlmostEqual(base[0], changed[0], places=12)


class ParserTests(unittest.TestCase):
    IDS = ["test-001", "test-002", "test-003"]

    def good(self, values=(0.1, 0.5, 0.9)):
        return json.dumps({"predictions": [{"case": c, "probability": p} for c, p in zip(self.IDS, values)]})

    def test_accepts_exact_json_and_one_fenced_block(self):
        pe = api()
        self.assertEqual(pe.parse_probabilities(self.good(), self.IDS), [0.1, 0.5, 0.9])
        self.assertEqual(pe.parse_probabilities("```json\n" + self.good() + "\n```\n", self.IDS), [0.1, 0.5, 0.9])
        self.assertEqual(pe.parse_probabilities(self.good((0, 1, 1.0)), self.IDS), [0.0, 1.0, 1.0])

    def test_returns_probabilities_in_requested_order_not_response_order(self):
        pe = api()
        text = json.dumps({"predictions": [{"case": "test-003", "probability": 0.9},
                                           {"case": "test-001", "probability": 0.1},
                                           {"case": "test-002", "probability": 0.5}]})
        self.assertEqual(pe.parse_probabilities(text, self.IDS), [0.1, 0.5, 0.9])

    def test_rejects_everything_else_without_repair(self):
        pe = api()
        item = lambda c, p: {"case": c, "probability": p}
        full = [item(c, 0.5) for c in self.IDS]
        bad = {
            "empty": "",
            "prose before": "Here are my predictions:\n" + self.good(),
            "prose after": self.good() + "\nHope this helps.",
            "two objects": self.good() + self.good(),
            "two fences": "```json\n" + self.good() + "\n```\n```json\n" + self.good() + "\n```",
            "top-level list": json.dumps(full),
            "missing case": json.dumps({"predictions": full[:2]}),
            "extra case": json.dumps({"predictions": full + [item("test-004", 0.5)]}),
            "duplicate case": json.dumps({"predictions": full[:2] + [item("test-002", 0.4)]}),
            "unknown case": json.dumps({"predictions": full[:2] + [item("SECRET", 0.4)]}),
            "string probability": json.dumps({"predictions": full[:2] + [item("test-003", "0.4")]}),
            "boolean probability": json.dumps({"predictions": full[:2] + [item("test-003", True)]}),
            "null probability": json.dumps({"predictions": full[:2] + [item("test-003", None)]}),
            "above one": json.dumps({"predictions": full[:2] + [item("test-003", 1.0001)]}),
            "percentage": json.dumps({"predictions": full[:2] + [item("test-003", 42)]}),
            "negative": json.dumps({"predictions": full[:2] + [item("test-003", -0.01)]}),
            "NaN": '{"predictions":[{"case":"test-001","probability":NaN},{"case":"test-002","probability":0.5},{"case":"test-003","probability":0.5}]}',
            "Infinity": '{"predictions":[{"case":"test-001","probability":Infinity},{"case":"test-002","probability":0.5},{"case":"test-003","probability":0.5}]}',
            "overflow": '{"predictions":[{"case":"test-001","probability":1e999},{"case":"test-002","probability":0.5},{"case":"test-003","probability":0.5}]}',
            "duplicate key": '{"predictions":[{"case":"test-001","probability":0.9,"probability":0.1},{"case":"test-002","probability":0.5},{"case":"test-003","probability":0.5}]}',
            "extra item key": json.dumps({"predictions": full[:2] + [{"case": "test-003", "probability": 0.5, "label": 1}]}),
            "extra top key": json.dumps({"predictions": full, "notes": "x"}),
            "wrong key": json.dumps({"probabilities": full}),
            "mapping form": json.dumps({"predictions": {c: 0.5 for c in self.IDS}}),
            "class label instead": json.dumps({"predictions": [{"case": c, "probability": "positive"} for c in self.IDS]}),
            "not json": "0.1, 0.5, 0.9",
        }
        for name, text in bad.items():
            with self.subTest(name), self.assertRaises(pe.ParseFailure):
                pe.parse_probabilities(text, self.IDS)

    def test_parser_never_clips_or_rescales(self):
        pe = api()
        with self.assertRaises(pe.ParseFailure):
            pe.parse_probabilities(self.good((10, 50, 90)), self.IDS)
        with self.assertRaises(pe.ParseFailure):
            pe.parse_probabilities(self.good((0.1, 0.5, 1.2)), self.IDS)


class MetricTests(unittest.TestCase):
    def test_auroc_handles_ties_and_is_never_flipped(self):
        pe = api()
        self.assertEqual(pe.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)
        self.assertEqual(pe.auroc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]), 0.0)
        self.assertEqual(pe.auroc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]), 0.5)
        self.assertAlmostEqual(pe.auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]), 0.75)
        self.assertAlmostEqual(pe.auroc([0, 1, 1, 0], [0.5, 0.5, 0.9, 0.1]), 0.875)
        with self.assertRaises(ValueError):
            pe.auroc([1, 1, 1], [0.1, 0.2, 0.3])

    def test_average_precision_and_brier(self):
        pe = api()
        self.assertAlmostEqual(pe.average_precision([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]), 0.8333333333333333)
        self.assertAlmostEqual(pe.average_precision([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]), 0.5)
        self.assertEqual(pe.average_precision([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)
        self.assertAlmostEqual(pe.brier([0, 1], [0.2, 0.7]), (0.04 + 0.09) / 2)

    @unittest.skipUnless(HAVE_SKLEARN, "scikit-learn not installed on this host")
    def test_metrics_match_scikit_learn_on_random_scores_with_ties(self):
        from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
        pe = api(); rng = random.Random(3)
        for _ in range(25):
            y = [rng.randint(0, 1) for _ in range(40)]
            if len(set(y)) < 2:
                continue
            p = [round(rng.random(), 1) for _ in y]
            self.assertAlmostEqual(pe.auroc(y, p), roc_auc_score(y, p), places=12)
            self.assertAlmostEqual(pe.average_precision(y, p), average_precision_score(y, p), places=12)
            self.assertAlmostEqual(pe.brier(y, p), brier_score_loss(y, p), places=12)


class ArmTests(unittest.TestCase):
    def test_training_prevalence_uses_training_fold_only(self):
        pe = api(); data = fixture()
        report = pe.run_evaluation(data, [pe.TrainingPrevalenceArm()], bootstrap=0)
        self.assertEqual(report["design"]["seed"], 20261114)
        self.assertEqual(sorted(report["genes"]), ["GENEA", "GENEB"])
        self.assertIn("RARE", report["excluded_genes"])
        arm = report["genes"]["GENEA"]["arms"]["training_prevalence"]
        self.assertEqual(arm["status"], "complete")
        self.assertEqual(arm["folds_completed"], 5)
        self.assertTrue(0 <= arm["pooled_oof"]["brier"] <= 1)

    def test_inverted_scores_are_reported_below_half_not_flipped(self):
        pe = api(); data = fixture()

        class Inverted(SpyArm):
            def predict_fold(self, fold):
                return [1 / (1 + math.exp(row[0])) for row in fold.test_X]
        report = pe.run_evaluation(data, [Inverted("inverted")], bootstrap=0)
        self.assertLess(report["genes"]["GENEA"]["arms"]["inverted"]["pooled_oof"]["auroc"], 0.4)
        self.assertEqual(report["design"]["score_direction"], "fixed: higher probability = reported qualifying alteration; never flipped")

    def test_invalid_arm_output_is_an_error_not_a_repaired_score(self):
        pe = api(); data = fixture()
        for bad in ([1.5], [float("nan")], ["0.5"], []):
            class Bad(SpyArm):
                def predict_fold(self, fold, bad=bad):
                    return (bad * len(fold.test_X)) if bad else []
            arm = pe.run_evaluation(data, [Bad("bad")], bootstrap=0)["genes"]["GENEA"]["arms"]["bad"]
            self.assertEqual(arm["status"], "error")
            self.assertIsNone(arm["pooled_oof"])

    def test_missing_tabpfn_is_reported_unavailable_with_no_substitute(self):
        pe = api(); data = fixture()

        def no_tabpfn(name):
            raise ImportError("No module named 'tabpfn'")
        arms = [pe.TrainingPrevalenceArm(), pe.TabPFNArm(importer=no_tabpfn)]
        report = pe.run_evaluation(data, arms, bootstrap=0)
        tab = report["genes"]["GENEA"]["arms"]["tabpfn"]
        self.assertEqual(tab["status"], "unavailable")
        self.assertIsNone(tab["pooled_oof"])
        self.assertEqual(tab["folds_completed"], 0)
        self.assertIn("tabpfn", tab["reason"].lower())
        self.assertEqual(report["genes"]["GENEA"]["arms"]["training_prevalence"]["status"], "complete")

    def fake_tabpfn(self, fail_with=None, accepts_model_path=True):
        import types
        created = []

        class Classifier:
            def __init__(self, n_estimators="auto", device="auto", random_state=0, **extra):
                if extra and not accepts_model_path:
                    raise TypeError("unexpected")
                self.kwargs = {"device": device, "random_state": random_state, **extra}; created.append(self)

            def fit(self, X, y):
                if fail_with:
                    raise fail_with
                self.classes_ = [0, 1]; self.rate = float(sum(y)) / len(y); return self

            def predict_proba(self, X):
                import numpy as np
                return np.asarray([[1 - self.rate, self.rate]] * len(X))
        if accepts_model_path:
            def init(self, n_estimators="auto", model_path="auto", device="auto", random_state=0):
                self.kwargs = {"model_path": model_path, "device": device, "random_state": random_state}
                created.append(self)
            Classifier.__init__ = init
        module = types.SimpleNamespace(TabPFNClassifier=Classifier)

        def importer(name):
            return module if name == "tabpfn" else importlib.import_module(name)
        return importer, created

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy not installed on this host")
    def test_tabpfn_adapter_passes_checkpoint_and_seed_and_records_its_hash(self):
        import hashlib, tempfile
        from pathlib import Path
        pe = api(); data = fixture()
        importer, created = self.fake_tabpfn()
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "classifier.ckpt"; checkpoint.write_bytes(b"synthetic checkpoint bytes")
            arm = pe.TabPFNArm(model_path=checkpoint, device="cpu", importer=importer)
            result = pe.run_evaluation(data, [arm], genes=["GENEA"], bootstrap=0)["genes"]["GENEA"]["arms"]["tabpfn"]
            self.assertEqual(result["status"], "complete")
            self.assertEqual(created[0].kwargs, {"model_path": str(checkpoint), "device": "cpu", "random_state": 20261114})
            self.assertEqual(result["settings"]["checkpoint_sha256"], hashlib.sha256(b"synthetic checkpoint bytes").hexdigest())
            self.assertEqual(result["settings"]["checkpoint_file"], "classifier.ckpt")
            self.assertIs(result["settings"]["offline"], True)
            self.assertNotIn(tmp, json.dumps(result))

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy not installed on this host")
    def test_tabpfn_offline_requires_an_existing_supported_checkpoint(self):
        import tempfile
        from pathlib import Path
        pe = api()
        importer, _ = self.fake_tabpfn()
        self.assertFalse(pe.TabPFNArm(importer=importer).availability()["available"])
        self.assertIn("checkpoint", pe.TabPFNArm(importer=importer).availability()["reason"])
        self.assertFalse(pe.TabPFNArm(model_path="/nonexistent/x.ckpt", importer=importer).availability()["available"])
        old_api, _ = self.fake_tabpfn(accepts_model_path=False)
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "c.ckpt"; checkpoint.write_bytes(b"x")
            self.assertFalse(pe.TabPFNArm(model_path=checkpoint, importer=old_api).availability()["available"])
            self.assertTrue(pe.TabPFNArm(model_path=checkpoint, importer=importer).availability()["available"])
        self.assertTrue(pe.TabPFNArm(offline=False, importer=importer).availability()["available"])

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy not installed on this host")
    def test_tabpfn_failure_records_a_fixed_code_not_the_library_message(self):
        import tempfile
        from pathlib import Path
        pe = api(); data = fixture()
        importer, _ = self.fake_tabpfn(fail_with=RuntimeError("GET https://hub.example/secret?token=hf_SECRETTOKEN denied"))
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "c.ckpt"; checkpoint.write_bytes(b"x")
            report = pe.run_evaluation(data, [pe.TabPFNArm(model_path=checkpoint, importer=importer)], genes=["GENEA"], bootstrap=0)
        result = report["genes"]["GENEA"]["arms"]["tabpfn"]
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["pooled_oof"])
        self.assertEqual(result["failures"][0]["message"], "tabpfn_fit_failed:RuntimeError")
        self.assertNotIn("SECRETTOKEN", json.dumps(report))
        self.assertNotIn("hub.example", json.dumps(report))

    def test_llm_arm_without_a_client_is_unavailable(self):
        pe = api(); data = fixture()
        arm = pe.run_evaluation(data, [pe.DirectLLMArm(client=None)], bootstrap=0)["genes"]["GENEA"]["arms"]["direct_llm"]
        self.assertEqual(arm["status"], "unavailable")
        self.assertIsNone(arm["pooled_oof"])

    def test_llm_arm_scores_valid_responses_and_records_parse_failures(self):
        pe = api(); data = fixture()
        requests = []

        def scripted(payload_text):
            payload = json.loads(payload_text); requests.append(payload)
            mean = lambda rows: sum(r["features"][0] for r in rows) / len(rows)
            mid = (mean([r for r in payload["train"] if r["label"]]) + mean([r for r in payload["train"] if not r["label"]])) / 2
            return json.dumps({"predictions": [{"case": r["case"], "probability": round(1 / (1 + math.exp(mid - r["features"][0])), 4)}
                                               for r in payload["test"]]})
        report = pe.run_evaluation(data, [pe.DirectLLMArm(client=scripted, model_label="scripted-test-double")], bootstrap=0)
        arm = report["genes"]["GENEA"]["arms"]["direct_llm"]
        self.assertEqual(arm["status"], "complete")
        self.assertGreater(arm["pooled_oof"]["auroc"], 0.7)
        self.assertEqual(arm["model_label"], "scripted-test-double")
        self.assertEqual(len(requests), 10)
        self.assertNotIn("SECRET_CASE", json.dumps(requests))

        calls = {"n": 0}

        def flaky(payload_text):
            calls["n"] += 1
            return "I think the first one is positive." if calls["n"] == 2 else scripted(payload_text)
        arm = pe.run_evaluation(data, [pe.DirectLLMArm(client=flaky)], bootstrap=0)["genes"]["GENEA"]["arms"]["direct_llm"]
        self.assertEqual(arm["status"], "parse_failure")
        self.assertIsNone(arm["pooled_oof"])
        self.assertEqual(arm["folds_completed"], 4)
        self.assertEqual(arm["failures"][0]["fold"], 1)

    def test_prespecified_feature_groups_apply_to_every_arm(self):
        pe = api(); data = fixture()
        a, b = SpyArm("a"), SpyArm("b")
        report = pe.run_evaluation(data, [a, b], feature_groups=["spatial"], bootstrap=0)
        self.assertEqual(report["design"]["feature_count"], 3)
        self.assertTrue(all(len(f.feature_names) == 3 and len(f.test_X[0]) == 3 for f in a.seen + b.seen))
        with self.assertRaises(ValueError):
            pe.run_evaluation(data, [SpyArm()], feature_groups=["missing_group"], bootstrap=0)

    def test_bootstrap_intervals_and_paired_differences_are_reported(self):
        pe = api(); data = fixture()

        class Signal(SpyArm):
            def predict_fold(self, fold):
                return [1 / (1 + math.exp(-row[0])) for row in fold.test_X]
        report = pe.run_evaluation(data, [pe.TrainingPrevalenceArm(), Signal("signal")], bootstrap=200)
        gene = report["genes"]["GENEA"]
        low, high = gene["arms"]["signal"]["bootstrap_95"]["auroc"]
        self.assertLess(low, gene["arms"]["signal"]["pooled_oof"]["auroc"])
        self.assertGreater(high, gene["arms"]["signal"]["pooled_oof"]["auroc"])
        diff = gene["paired_auroc_differences"]["signal_minus_training_prevalence"]
        self.assertGreater(diff["difference"], 0.1)
        self.assertEqual(report, pe.run_evaluation(data, [pe.TrainingPrevalenceArm(), Signal("signal")], bootstrap=200))

    def test_llm_arm_can_run_a_prespecified_fold_subset_without_pooled_scores(self):
        pe = api(); data = fixture()
        seen = []

        def constant(payload_text):
            payload = json.loads(payload_text); seen.append(payload["target_gene"])
            return json.dumps({"predictions": [{"case": r["case"], "probability": 0.25} for r in payload["test"]]})
        report = pe.run_evaluation(data, [pe.TrainingPrevalenceArm(), pe.DirectLLMArm(client=constant, only_folds=[0])],
                                   genes=["GENEA"], bootstrap=0)
        arm = report["genes"]["GENEA"]["arms"]["direct_llm"]
        self.assertEqual(seen, ["GENEA"])
        self.assertEqual(arm["status"], "partial")
        self.assertEqual(arm["folds_requested"], [0])
        self.assertIsNone(arm["pooled_oof"])
        self.assertEqual([f["fold"] for f in arm["per_fold"]], [0])
        self.assertEqual(arm["per_fold"][0]["auroc"], 0.5)
        baseline = report["genes"]["GENEA"]["arms"]["training_prevalence"]
        self.assertEqual(len(baseline["per_fold"]), 5)
        self.assertEqual(baseline["per_fold"][0]["test_rows"], arm["per_fold"][0]["test_rows"])
        self.assertNotIn("direct_llm_minus_training_prevalence", report["genes"]["GENEA"]["paired_auroc_differences"])
        self.assertIn("GENEB", report["excluded_genes"])

    def test_oversized_request_is_refused_before_the_client_is_called(self):
        pe = api(); data = fixture()
        calls = []
        arm = pe.DirectLLMArm(client=lambda text: calls.append(text) or "{}", max_request_chars=500)
        result = pe.run_evaluation(data, [arm], bootstrap=0)["genes"]["GENEA"]["arms"]["direct_llm"]
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "request_too_large")
        self.assertIsNone(result["pooled_oof"])

    @unittest.skipUnless(HAVE_SKLEARN, "scikit-learn not installed on this host")
    def test_logistic_regression_baseline_finds_planted_signal(self):
        pe = api(); data = fixture()
        report = pe.run_evaluation(data, [pe.LogisticRegressionArm()], bootstrap=0)
        self.assertGreater(report["genes"]["GENEA"]["arms"]["logistic_regression"]["pooled_oof"]["auroc"], 0.7)


class IntegrationApiTests(unittest.TestCase):
    def test_make_folds_matches_what_the_runner_uses(self):
        pe = api(); data = fixture()
        folds = pe.make_folds(data, "GENEA")
        report = pe.run_evaluation(data, [pe.TrainingPrevalenceArm()], genes=["GENEA"], bootstrap=0)
        self.assertEqual(pe.split_fingerprint(data["case_ids"], folds),
                         report["genes"]["GENEA"]["arms"]["training_prevalence"]["split_fingerprint"])
        self.assertEqual(folds, pe.make_folds(data, "GENEA", n_splits=5, seed=20261114))

    def test_public_payload_round_trip_with_evaluator_key(self):
        pe = api(); data = fixture(); gene = "GENEA"; y = data["labels"][gene]
        fold = pe.make_folds(data, gene)[0]
        payload, key = pe.build_public_payload(data, gene, fold["train"], fold["test"], feature_group="clinical")
        self.assertEqual(payload["feature_names"], ["feat_3", "feat_4", "feat_5"])
        self.assertEqual(sorted(key), sorted(fold["test"]))
        self.assertEqual([r["features"] for r in payload["test"]],
                         [[float(f"{v:.6g}") for v in data["X"][i][3:]] for i in key])
        self.assertNotIn("SECRET_CASE", json.dumps(payload))
        response = json.dumps({"predictions": [{"case": r["case"], "probability": 0.5} for r in payload["test"]]})
        p = pe.parse_predictions(response, [r["case"] for r in payload["test"]])
        scores = pe.evaluate_probabilities([y[i] for i in key], p)
        self.assertEqual(scores["auroc"], 0.5)
        self.assertEqual(set(scores), {"auroc", "average_precision", "brier"})
        with self.assertRaises(ValueError):
            pe.build_public_payload(data, gene, fold["train"] + fold["test"][:1], fold["test"])
        with self.assertRaises(ValueError):
            pe.build_public_payload(data, gene, fold["train"], fold["test"], feature_group="not_a_group")

    def test_all_group_falls_back_to_every_column(self):
        pe = api(); data = fixture(); fold = pe.make_folds(data, "GENEA")[0]
        payload, _ = pe.build_public_payload(data, "GENEA", fold["train"], fold["test"])
        self.assertEqual(len(payload["feature_names"]), 6)
        data["feature_groups"]["all"] = data["feature_names"][:5]
        payload, _ = pe.build_public_payload(data, "GENEA", fold["train"], fold["test"], feature_group="all")
        self.assertEqual(len(payload["feature_names"]), 5)

    def test_evaluate_probabilities_rejects_invalid_values(self):
        pe = api()
        for bad in ([0.2, 1.2], [0.2, float("nan")], [0.2], ["0.2", 0.4]):
            with self.assertRaises(ValueError):
                pe.evaluate_probabilities([0, 1], bad)

    def test_run_baselines_reports_each_arm_and_a_clinical_control(self):
        pe = api(); data = fixture()

        def no_tabpfn(name):
            raise ImportError(name)
        original = pe.ARMS["tabpfn"]
        pe.ARMS["tabpfn"] = lambda: original(importer=no_tabpfn)
        try:
            report = pe.run_baselines(data, genes=["GENEA"], feature_group="clinical", bootstrap=0)
        finally:
            pe.ARMS["tabpfn"] = original
        arms = report["genes"]["GENEA"]["arms"]
        self.assertEqual(list(arms), ["training_prevalence", "logistic_regression", "tabpfn"])
        self.assertEqual(arms["tabpfn"]["status"], "unavailable")
        self.assertEqual(report["design"]["feature_groups"], ["clinical"])
        self.assertEqual(report["design"]["feature_count"], 3)
        self.assertEqual(arms["logistic_regression"]["status"], "complete" if HAVE_SKLEARN else "unavailable")

    def test_preflight_reports_sizes_and_sends_nothing(self):
        pe = api(); data = fixture()
        small = pe.payload_preflight(data, genes=["GENEA"], feature_group="clinical")
        full = pe.payload_preflight(data, genes=["GENEA"], max_request_chars=1000)
        self.assertEqual(len(full["folds"]), 5)
        self.assertGreater(full["largest_request_chars"], small["largest_request_chars"])
        self.assertIs(full["within_limit"], False)
        self.assertIsNone(small["within_limit"])
        fold = pe.make_folds(data, "GENEA")[0]
        payload, _ = pe.build_public_payload(data, "GENEA", fold["train"], fold["test"])
        self.assertEqual(full["folds"][0]["request_chars"], len(json.dumps(payload)))
        self.assertNotIn("SECRET_CASE", json.dumps(full))


if __name__ == "__main__":
    unittest.main()
