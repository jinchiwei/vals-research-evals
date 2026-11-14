"""Review regressions: no model calls, credentials, Docker, or live-source edits.

These assert desired behavior for the pending review fixes. Until the fixes are
applied they intentionally fail; do not relabel them as passing or xfail them.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from repair_evals import make_case
from repair_evals import export as exporter
from scripts import run_repair_pilot as runner


class RepairReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="repair-review-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def completed_trial(self, replay):
        """Drive the actual result-classification path without launching a model."""
        case = make_case("endpoint", 11)

        def fake_execute(command, prompt, stdout, stderr, timeout):
            stdout.write(json.dumps({"type": "assistant", "message": {
                "model": "test-only-model", "content": []}}) + "\n")
            stdout.write(json.dumps({"type": "result", "is_error": False}) + "\n")
            return "completed", 0

        with patch.object(runner, "model_command", return_value=["never-executed"]), \
             patch.object(runner, "_execute", side_effect=fake_execute), \
             patch.object(runner, "evaluate_program", return_value=replay):
            return runner.run_one(case, self.base / "attempt", "claude", "test-only-model")

    def test_replay_timeout_is_resource_limit_not_semantic_failure(self):
        # The runtime probe succeeds; the submitted program then times out.
        workspace = self.base / "input"
        workspace.mkdir()
        (workspace / "analysis.py").write_text("pass\n")
        ready = SimpleNamespace(returncode=0, stdout="ready\n", stderr="")
        with patch.object(runner.subprocess, "run", side_effect=[
            ready, subprocess.TimeoutExpired(["fixture-program"], timeout=20)
        ]):
            replay = runner.evaluate_program(
                workspace, [{"input": {}, "expected": {}}], lambda want, got: want == got)
        self.assertFalse(replay["passed"])
        self.assertEqual(replay["checks"][0]["error"], "replay_timeout")
        result = self.completed_trial(replay)
        self.assertEqual(result["classification"], "resource_limit")

    def test_runtime_probe_failure_remains_infrastructure_error(self):
        workspace = self.base / "input"
        workspace.mkdir()
        (workspace / "analysis.py").write_text("pass\n")
        failure = SimpleNamespace(returncode=1, stdout="", stderr="bwrap: namespace unavailable")
        with patch.object(runner.subprocess, "run", return_value=failure):
            replay = runner.evaluate_program(
                workspace, [{"input": {}, "expected": {}}], lambda want, got: want == got)
        result = self.completed_trial(replay)
        self.assertEqual(result["classification"], "infrastructure_error")

    def test_actual_output_mismatch_remains_a_candidate_semantic_failure(self):
        result = self.completed_trial({
            "passed": False, "passed_fixtures": 0, "total_fixtures": 1,
            "checks": [{"fixture": 0, "passed": False, "error": "output_mismatch"}],
        })
        self.assertEqual(result["classification"], "candidate_semantic_failure")

    def invoke_exported_grader(self, task, workspace):
        logs = self.base / "logs"
        completed = subprocess.run([
            sys.executable, "-I", str(task / "tests/grade.py"),
            "--workspace", str(workspace), "--logs", str(logs),
        ], capture_output=True, text=True, timeout=20)
        # Either successful grading or explicit infrastructure exit is allowed;
        # detailed outcomes, not shell returncode alone, distinguish the cases.
        self.assertTrue((logs / "results.json").is_file(), completed.stderr)
        return (logs / "reward.txt").read_text().strip(), json.loads((logs / "results.json").read_text())

    def test_exported_invalid_submission_is_not_infrastructure_failure(self):
        task = exporter.export_case(make_case("endpoint", 11), self.base / "tasks")
        workspace = self.base / "workspace"
        workspace.mkdir()
        (workspace / "analysis.py").write_text("pass\n")
        # A local link entirely inside this temporary workspace; no sandbox
        # escape, patient files, host secrets, or hostile payload is involved.
        (workspace / "linked.py").symlink_to("analysis.py")
        reward, result = self.invoke_exported_grader(task, workspace)
        self.assertEqual(reward, "0")
        self.assertIsNone(result.get("infrastructure_error"), result)
        self.assertTrue(result.get("submission_error"), result)

    def test_missing_private_fixtures_remains_infrastructure_failure(self):
        task = exporter.export_case(make_case("endpoint", 11), self.base / "tasks")
        (task / "tests/fixtures.json").unlink()
        workspace = self.base / "workspace"
        workspace.mkdir()
        (workspace / "analysis.py").write_text("pass\n")
        reward, result = self.invoke_exported_grader(task, workspace)
        self.assertEqual(reward, "0")
        self.assertTrue(result.get("infrastructure_error"), result)
        self.assertFalse(result.get("submission_error"), result)

    def test_exported_public_instruction_discloses_enforced_cpu_and_memory(self):
        task = exporter.export_case(make_case("endpoint", 11), self.base / "tasks")
        spec = importlib.util.spec_from_file_location("review_exported_grade", task / "tests/grade.py")
        grade = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(grade)
        observed = {}
        with patch.object(grade.resource, "setrlimit", side_effect=lambda key, values: observed.update({key: values})):
            grade.child_limits(False)
        instruction = (task / "instruction.md").read_text()
        cpu_seconds = observed[grade.resource.RLIMIT_CPU][0]
        memory_mib = observed[grade.resource.RLIMIT_AS][0] // (1024 ** 2)
        self.assertIn(f"{cpu_seconds} CPU seconds", instruction)
        self.assertIn(f"{memory_mib} MiB", instruction)

    def test_frozen_oracle_does_not_depend_on_current_generator(self):
        case = make_case("endpoint", 11)
        frozen_oracle = make_case("endpoint", 11, "valid")["files"]["analysis.py"]
        # An archived case must be exportable with its captured oracle even if
        # the currently installed generator no longer reconstructs that version.
        with patch.object(exporter, "make_case", side_effect=RuntimeError("generator changed after freeze")):
            task = exporter.export_case(case, self.base / "tasks", oracle_source=frozen_oracle)
        self.assertEqual((task / "solution/analysis.py").read_text(), frozen_oracle)
        self.assertEqual(json.loads((task / "tests/fixtures.json").read_text()), case["hidden"])

    def test_implicit_oracle_rejects_archived_case_after_generator_drift(self):
        archived = make_case("endpoint", 11)
        original_factory = exporter.make_case

        def changed_factory(*args, **kwargs):
            current_case = original_factory(*args, **kwargs)
            current_case["files"]["protocol.md"] += "\nUpdated release protocol revision.\n"
            return current_case

        with patch.object(exporter, "make_case", side_effect=changed_factory):
            with self.assertRaisesRegex(ValueError, "(?i)(frozen|drift|case|generator|mismatch)"):
                exporter.export_case(archived, self.base / "tasks")


if __name__ == "__main__":
    unittest.main()
