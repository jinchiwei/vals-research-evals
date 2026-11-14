import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_repair_pilot import evaluate_program, classify_trial


class RepairRunnerTests(unittest.TestCase):
    def test_hidden_inputs_require_generalization_and_expected_is_not_mounted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            secret = root / "gold.json"
            secret.write_text("do not mount")
            program = "import json,sys,pathlib\nx=json.load(open(sys.argv[1]))\njson.dump({'value': x['value']*2, 'gold_visible': pathlib.Path(" + repr(str(secret)) + ").exists()},open(sys.argv[2],'w'))\n"
            (workspace / "analysis.py").write_text(program)
            hidden = [{"input": {"value": n}, "expected": {"value": n*2, "gold_visible": False}} for n in (3, 7)]
            result = evaluate_program(workspace, hidden, lambda a, b: a == b)
            self.assertTrue(result["passed"])
            (workspace / "analysis.py").write_text("import json,sys\njson.dump({'value':6,'gold_visible':False},open(sys.argv[2],'w'))\n")
            result = evaluate_program(workspace, hidden, lambda a, b: a == b)
            self.assertFalse(result["passed"])
            self.assertEqual(result["passed_fixtures"], 1)

    def test_symlink_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "analysis.py").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                evaluate_program(workspace, [], lambda a, b: a == b)

    def test_errors_and_timeouts_are_not_semantic_failure_claims(self):
        self.assertEqual(classify_trial("timeout", True, False), "resource_limit")
        self.assertEqual(classify_trial("runtime_error", False, False), "infrastructure_error")
        self.assertEqual(classify_trial("completed", True, False), "candidate_semantic_failure")
        self.assertEqual(classify_trial("completed", True, True), "pass")


if __name__ == "__main__":
    unittest.main()
