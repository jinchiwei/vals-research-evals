"""Independent hand-computable checks for synthetic repair-task contracts."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


def endpoint_fixture():
    return {
        "protocol": {"gene": "IRF4", "as_of_day": 100, "lookback_days": 30,
                     "gene_aliases": {"MUM1": "IRF4"}},
        "participants": [
            {"participant_id": "A", "age": 60, "confirmed_pcnsl": True, "therapy_day": 20},
            {"participant_id": "B", "age": 50, "confirmed_pcnsl": True, "therapy_day": 20},
            {"participant_id": "C", "age": 40, "confirmed_pcnsl": True, "therapy_day": 20},
            {"participant_id": "D", "age": 17, "confirmed_pcnsl": True, "therapy_day": 20},
            {"participant_id": "E", "age": 45, "confirmed_pcnsl": True, "therapy_day": 10},
        ],
        "specimens": [
            {"sample_id": "s" + p, "participant_id": p, "day": 10,
             "type": "tumor", "assay_status": "passed"} for p in "ABCDE"
        ] + [{"sample_id": "sA-late", "participant_id": "A", "day": 30,
              "type": "tumor", "assay_status": "passed"}],
        "scans": [
            {"scan_id": "i" + p, "participant_id": p, "day": 9 if p != "E" else 10,
             "qc_pass": True, "sequences": ["FLAIR", "T1POST"]} for p in "ABCDE"
        ] + [{"scan_id": "iA-later", "participant_id": "A", "day": 12,
              "qc_pass": True, "sequences": ["FLAIR", "T1POST"]}],
        "reports": [
            {"report_id": "rA0", "sample_id": "sA", "revision": 0, "issued_day": 15,
             "status": "final", "genes_tested": ["IRF4"], "variants": [
                 {"gene": "IRF4", "classification": "Pathogenic", "reported": True, "detection": "Detected"}]},
            {"report_id": "rA1", "sample_id": "sA", "revision": 1, "issued_day": 16,
             "status": "final", "genes_tested": ["IRF4"], "variants": [
                 {"gene": "IRF4", "classification": "Uncertain Significance", "reported": True, "detection": "Detected"}]},
            {"report_id": "rA2", "sample_id": "sA", "revision": 2, "issued_day": 101,
             "status": "final", "genes_tested": ["IRF4"], "variants": [
                 {"gene": "IRF4", "classification": "Pathogenic", "reported": True, "detection": "Detected"}]},
            {"report_id": "rB", "sample_id": "sB", "revision": 0, "issued_day": 15,
             "status": "final", "genes_tested": ["MUM1"], "variants": [
                 {"gene": "MYD88; MUM1", "classification": "Likely Pathogenic", "reported": "true", "detection": "Detected"}]},
            {"report_id": "rC", "sample_id": "sC", "revision": 0, "issued_day": 15,
             "status": "final", "genes_tested": ["MYD88"], "variants": []},
            {"report_id": "rE", "sample_id": "sE", "revision": 0, "issued_day": 15,
             "status": "final", "genes_tested": ["IRF4"], "variants": []},
        ],
    }


def claims_fixture():
    rows = [{"row_id": str(i), "participant_id": p, "visit_day": 0, "label": y,
             "probability": prob} for i, (p, y, prob) in enumerate([
                 ("A", 0, .1), ("B", 0, .2), ("C", 1, .8), ("D", 1, .9)])]
    run = {"run_id": "r1", "probability_for_class": 1, "freeze_day": 1,
           "selection_split": "development", "fit_subjects": ["other"],
           "transform_fit_subjects": ["other"], "selection_subjects": ["other"],
           "predictions": rows, "null_auroc": [.5] * 99}
    inverse = copy.deepcopy(run)
    inverse["run_id"] = "r2"
    inverse["predictions"] = [dict(r, probability=1 - r["probability"]) for r in rows]
    return {"plan": {"alpha": .05, "evaluation_lock_day": 2,
                     "hypotheses": [{"hypothesis_id": "H1", "run_id": "r1"},
                                    {"hypothesis_id": "H2", "run_id": "r2"},
                                    {"hypothesis_id": "H3", "run_id": "missing"}]},
            "runs": [run, inverse]}


def geometry_fixture():
    return {"scans": [{
        "scan_id": "A",
        "mask": {"values": [[[1]], [[2]]], "frame": "LPS",
                 "affine": [[2, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 1]]},
        "adc": {"values": [[[400]], [[800]]], "frame": "LPS",
                "affine": [[2, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 1]],
                "scale": 2, "offset": 100, "unit": "1e-6 mm2/s"}},
        {"scan_id": "B",
         "mask": {"values": [[[1]]], "frame": "RAS",
                  "affine": [[0, -2, 0, 0], [3, 0, 1, 0], [0, 0, 4, 0], [0, 0, 0, 1]]},
         "adc": {"values": [[[.001]]], "frame": "RAS",
                 "affine": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                 "scale": 1, "offset": 0, "unit": "mm2/s"}}],
        "pairs": [{"pair_id": "AB", "baseline": "A", "followup": "B"}]}


class RepairTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec("repair_evals"), "repair task package must exist")
        import repair_evals
        return repair_evals

    def test_endpoint_pairing_corrections_missing_assay_and_treatment(self):
        result = self.api().reference(endpoint_fixture(), "endpoint")
        self.assertEqual(result, {
            "cohort": [
                {"participant_id": "A", "sample_id": "sA", "report_id": "rA1", "scan_id": "iA", "label": 0},
                {"participant_id": "B", "sample_id": "sB", "report_id": "rB", "scan_id": "iB", "label": 1}],
            "excluded": [
                {"participant_id": "C", "reason": "gene_not_assayed"},
                {"participant_id": "D", "reason": "ineligible_participant"},
                {"participant_id": "E", "reason": "no_eligible_scan"}],
            "counts": {"eligible": 2, "positive": 1, "negative": 1, "excluded": 3}})

    def test_endpoint_reported_false_and_not_detected_are_not_positives(self):
        data = endpoint_fixture()
        report = next(r for r in data["reports"] if r["report_id"] == "rB")
        for field, value in [("reported", "false"), ("detection", "Not Detected")]:
            changed = copy.deepcopy(data)
            record = next(r for r in changed["reports"] if r["report_id"] == "rB")
            record["variants"][0][field] = value
            self.assertEqual(self.api().reference(changed, "endpoint")["cohort"][1]["label"], 0)

    def test_claims_fixed_direction_and_full_holm_family(self):
        result = self.api().reference(claims_fixture(), "claims")
        self.assertEqual(result["discoveries"], ["H1"])
        first, reverse, missing = result["hypotheses"]
        self.assertEqual(first["auroc"], 1)
        self.assertAlmostEqual(first["brier"], .025)
        self.assertAlmostEqual(first["p_value"], .01)
        self.assertAlmostEqual(first["holm_p"], .03)
        self.assertEqual(reverse["auroc"], 0)
        self.assertEqual(reverse["p_value"], 1)
        self.assertEqual(missing["reason"], "missing_run")
        self.assertEqual(missing["p_value"], 1)
        self.assertEqual(result["family_size"], 3)

    def test_claims_patient_dedup_and_leakage_withhold_confirmation(self):
        data = claims_fixture()
        data["runs"][0]["predictions"].append({"row_id": "later", "participant_id": "A", "visit_day": 9, "label": 0, "probability": .99})
        result = self.api().reference(data, "claims")
        self.assertEqual(result["hypotheses"][0]["n_patients"], 4)
        self.assertEqual(result["hypotheses"][0]["auroc"], 1)
        data["runs"][0]["transform_fit_subjects"].append("C")
        result = self.api().reference(data, "claims")
        self.assertEqual(result["hypotheses"][0]["reason"], "patient_overlap")
        self.assertEqual(result["discoveries"], [])

    def test_claims_explicit_class_zero_probability_is_converted(self):
        data = claims_fixture()
        data["runs"][1]["probability_for_class"] = 0
        result = self.api().reference(data, "claims")
        self.assertEqual(result["hypotheses"][1]["auroc"], 1)
        self.assertEqual(result["discoveries"], ["H1", "H2"])

    def test_geometry_determinant_frame_and_calibration(self):
        result = self.api().reference(geometry_fixture(), "geometry")
        first, second = result["scans"]
        self.assertEqual(first["lesion_volume_mm3"], 48)
        self.assertEqual(first["centroid_ras_mm"], [-1, 0, 0])
        self.assertEqual(first["left_volume_mm3"], 24)
        self.assertEqual(first["midline_volume_mm3"], 24)
        self.assertAlmostEqual(first["mean_adc_mm2_s"], .0013)
        self.assertEqual(first["adc_coverage"], 1)
        self.assertEqual(second["lesion_volume_mm3"], 24)
        self.assertEqual(result["changes"][0]["volume_change_pct"], -50)
        self.assertAlmostEqual(result["changes"][0]["adc_change_mm2_s"], -.0003)

    def test_geometry_world_resampling_and_partial_coverage(self):
        data = geometry_fixture()
        data["scans"][0]["adc"]["affine"][0][3] = 2
        result = self.api().reference(data, "geometry")
        self.assertEqual(result["scans"][0]["adc_coverage"], .5)
        self.assertAlmostEqual(result["scans"][0]["mean_adc_mm2_s"], .0009)
        self.assertIsNone(result["changes"][0]["adc_change_mm2_s"])

    def test_compare_rejects_extra_fields_nonfinite_wrong_type_and_evidence(self):
        compare = self.api().compare
        expected = {"rows": [{"id": "A", "value": .2, "eligible": True}]}
        self.assertTrue(compare(expected, copy.deepcopy(expected))["passed"])
        for bad in [None, {"rows": []}, {"rows": [{"id": "B", "value": .2, "eligible": True}]},
                    {"rows": [{"id": "A", "value": float("nan"), "eligible": True}]},
                    {"rows": [{"id": "A", "value": .2, "eligible": 1}]},
                    dict(expected, fabricated_evidence="validated")]:
            self.assertFalse(compare(expected, bad)["passed"])

    def test_hidden_fixtures_do_not_leak_and_defeat_visible_answer_hardcoding(self):
        api = self.api()
        for family in ("endpoint", "claims", "geometry"):
            case = api.make_case(family, 11)
            self.assertGreaterEqual(len(case["hidden"]), 3)
            self.assertEqual(set(case["files"]), {"analysis.py", "input.json", "protocol.md", "schema.md"})
            self.assertNotIn("repair_evals", case["files"]["analysis.py"])
            visible = api.reference(json.loads(case["files"]["input.json"]), family)
            self.assertTrue(any(not api.compare(h["expected"], visible)["passed"] for h in case["hidden"]))
            for hidden in case["hidden"]:
                self.assertTrue(api.compare(hidden["expected"], api.reference(hidden["input"], family))["passed"])

    def test_valid_controls_generalize_and_flawed_controls_fail(self):
        api = self.api()
        for family in ("endpoint", "claims", "geometry"):
            for variant in ("valid", "flawed"):
                case = api.make_case(family, 11, variant)
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    for name, text in case["files"].items():
                        (root / name).write_text(text)
                    results = []
                    for i, hidden in enumerate(case["hidden"]):
                        (root / "challenge.json").write_text(json.dumps(hidden["input"]))
                        done = subprocess.run(["python3", str(root / "analysis.py"), str(root / "challenge.json"), str(root / "output.json")], capture_output=True, text=True, timeout=10)
                        self.assertEqual(done.returncode, 0, done.stderr)
                        result = json.loads((root / "output.json").read_text())
                        results.append(api.compare(hidden["expected"], result)["passed"])
                self.assertEqual(all(results), variant == "valid", (family, variant, results))

    def test_invalid_family_or_variant_is_rejected(self):
        api = self.api()
        for family, variant in [("unknown", "flawed"), ("endpoint", "unknown")]:
            with self.assertRaises(ValueError):
                api.make_case(family, 11, variant)


if __name__ == "__main__":
    unittest.main()
