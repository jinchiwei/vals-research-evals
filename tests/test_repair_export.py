"""Executable export checks: no model calls, Docker, or hosted service required."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from repair_evals import make_case, reference

ROOT = Path(__file__).resolve().parents[1]


class RepairExportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('repair_evals.export'),
                             'repair exporter must exist')
        from repair_evals.export import export_case
        self.export_case = export_case
        self.tmp = tempfile.TemporaryDirectory(prefix='repair-export-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def grade(self, task, code=None, env=None):
        workspace = self.base / ('workspace-' + task.name)
        shutil.copytree(task / 'environment' / 'workspace', workspace)
        if code is not None:
            (workspace / 'analysis.py').write_text(code)
        logs = self.base / ('logs-' + task.name)
        result = subprocess.run([sys.executable, '-I', str(task / 'tests' / 'grade.py'),
                                 '--workspace', str(workspace), '--logs', str(logs)],
                                capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (logs / 'reward.txt').read_text().strip(), json.loads((logs / 'results.json').read_text())

    def test_valid_controls_pass_and_flawed_controls_fail_every_family(self):
        # Catches packaging a wrong oracle or failing to execute hidden inputs.
        for family in ('endpoint', 'claims', 'geometry'):
            for variant, reward in [('valid', '1'), ('flawed', '0')]:
                with self.subTest(family=family, variant=variant):
                    task = self.export_case(make_case(family, 11, variant), self.base)
                    actual, result = self.grade(task)
                    self.assertEqual(actual, reward, result)
                    self.assertEqual(result['infrastructure_error'], None, result)
                    self.assertEqual(len(result['fixtures']), 4)

    def test_visible_case_hardcoding_does_not_pass(self):
        case = make_case('endpoint', 101)
        task = self.export_case(case, self.base)
        answer = reference(json.loads(case['files']['input.json']), 'endpoint')
        code = 'import sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_text(' + repr(json.dumps(answer)) + ')\n'
        reward, result = self.grade(task, code)
        self.assertEqual(reward, '0', result)

    def test_submitted_program_cannot_read_gold_or_oracle(self):
        case = make_case('geometry', 11, 'valid')
        task = self.export_case(case, self.base)
        # A valid solver deliberately exits if any private path is readable.
        paths = [str(task / 'tests' / 'fixtures.json'), str(task / 'solution' / 'analysis.py'),
                 '/tests/fixtures.json', '/solution/analysis.py']
        probe = 'from pathlib import Path\nfor p in ' + repr(paths) + ':\n'
        probe += '    try:\n        Path(p).read_bytes()\n    except (OSError, PermissionError):\n        continue\n    raise SystemExit(44)\n'
        reward, result = self.grade(task, probe + case['files']['analysis.py'])
        self.assertEqual(reward, '1', result)

    def test_missing_isolation_fails_closed(self):
        if os.geteuid() == 0:
            self.skipTest('This checks the non-root fallback')
        task = self.export_case(make_case('endpoint', 11, 'valid'), self.base)
        env = dict(os.environ, PATH='/definitely/missing')
        reward, result = self.grade(task, env=env)
        self.assertEqual(reward, '0')
        self.assertIsNotNone(result['infrastructure_error'])

    def test_malformed_output_and_output_symlink_are_rejected(self):
        # Catches unchecked output loading or allowing non-JSON success signals.
        programs = [
            "import sys\nopen(sys.argv[2], 'w').write('NaN')\n",
            "import sys,os\nos.symlink(sys.argv[1], sys.argv[2])\n",
            "import sys\nopen(sys.argv[2], 'w').write('{\"x\":1,\"x\":2}')\n",
        ]
        for seed, code in enumerate(programs):
            with self.subTest(seed=seed):
                task = self.export_case(make_case('endpoint', seed), self.base)
                reward, result = self.grade(task, code)
                self.assertEqual(reward, '0')
                self.assertIsNone(result['infrastructure_error'])
                self.assertTrue(all(r['execution_error'] for r in result['fixtures']))

    def test_oracle_script_installs_a_passing_solution(self):
        # Catches an unusable solve.sh path or installing the flawed submission.
        from prototype_evals.pilot import sandbox_command
        task = self.export_case(make_case('claims', 101), self.base)
        workspace = self.base / 'oracle-workspace'
        shutil.copytree(task / 'environment' / 'workspace', workspace)
        home = self.base / 'oracle-home'
        home.mkdir()
        cmd = sandbox_command(workspace, home, [])
        cmd += ['--ro-bind', str(task / 'solution'), '/solution',
                '/bin/sh', '/solution/solve.sh']
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        reward, result = self.grade(task, (workspace / 'analysis.py').read_text())
        self.assertEqual(reward, '1', result)

    def test_export_public_payload_excludes_hidden_data_and_oracle(self):
        case = make_case('claims', 101)
        task = self.export_case(case, self.base)
        public = task / 'environment' / 'workspace'
        self.assertEqual({p.name for p in public.iterdir()}, set(case['files']))
        for name, content in case['files'].items():
            self.assertEqual((public / name).read_text(), content)
        self.assertEqual(json.loads((task / 'tests' / 'fixtures.json').read_text()), case['hidden'])
        self.assertEqual((task / 'solution' / 'analysis.py').read_text(),
                         make_case('claims', 101, 'valid')['files']['analysis.py'])
        with self.assertRaises(FileExistsError):
            self.export_case(case, self.base)

    def test_path_traversal_is_rejected_before_writing(self):
        case = make_case('endpoint', 11)
        case['files']['../../escape.txt'] = 'bad'
        with self.assertRaises(ValueError):
            self.export_case(case, self.base)
        self.assertFalse((self.base / 'escape.txt').exists())

    def test_cli_and_official_sdk_packaging(self):
        sdk_python = ROOT / '.venv-valkyrie' / 'bin' / 'python'
        if not sdk_python.exists():
            self.skipTest('Optional valkyrie SDK environment not installed')
        out = self.base / 'tasks'
        subprocess.run([sys.executable, '-m', 'repair_evals.export', '--out', str(out),
                        '--seeds', '11', '101', '--families', 'endpoint', 'geometry',
                        '--variants', 'flawed', 'valid'], cwd=ROOT, check=True,
                       capture_output=True, text=True)
        result = subprocess.run([str(sdk_python), 'scripts/validate_exports.py', str(out),
                                 str(self.base / 'archives')], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.base / 'archives').glob('*.zip'))), 8)


if __name__ == '__main__':
    unittest.main()
