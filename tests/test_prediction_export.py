"""Tests for the Harbor prediction-task exporter. Synthetic fixtures only.

Run: python3 -m unittest tests.test_prediction_export -v
SDK/tracker-schema checks run only when .venv-valkyrie (and the pinned
Valkyrie source checkout) exist; they are skipped, never faked, otherwise.
"""
import copy
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from pcnsl import prediction_export as pe

REPO = Path(__file__).resolve().parents[1]
SDK_PYTHON = REPO / '.venv-valkyrie' / 'bin' / 'python'
TRACKER_CONFIG = Path('/tmp/valkyrie-inspect-20261114/services/tracker/src/tracker/services/datasets/config.py')


def synthetic_dataset(n=20, seed=3):
    rng = random.Random(seed)
    names = ['flair_volume', 'adc_mean', 'age_years', 'ldh_ratio']
    X, labels = [], []
    for i in range(n):
        y = i % 2
        X.append([round(rng.gauss(10 + 3 * y, 2), 4), None if i % 7 == 0 else round(rng.random(), 4),
                  rng.randint(40, 80), round(rng.random() * 2, 3)])
        labels.append(y)
    return {'case_ids': ['case-%024x' % rng.getrandbits(96) for _ in range(n)],
            'feature_names': names, 'X': X,
            'labels': {'MYD88': labels, 'CD79B': [1 - v for v in labels]},
            'feature_groups': {'imaging': ['flair_volume', 'adc_mean'],
                               'clinical': ['age_years', 'ldh_ratio'],
                               'all_volumes': ['flair_volume']},
            'metadata': {'source_path': '/mnt/fac/raw/release-v1', 'extracted': '2026-11-14'}}


TEST_INDICES = [0, 1, 4, 7, 10]


def build(dataset=None, gene='MYD88', test_indices=TEST_INDICES, seed=11, fold=0):
    return pe.build_fold(dataset or synthetic_dataset(), gene, test_indices, seed=seed, fold=fold)


def all_files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}


def agent_visible(task):
    """Everything the agent can see: the Docker build context and the instruction."""
    files = {'instruction.md': (task / 'instruction.md').read_bytes()}
    for name, data in all_files(task / 'environment').items():
        files['environment/' + name] = data
    return files


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class MetricTests(unittest.TestCase):
    """Hand-computed fixtures; see comments for the arithmetic."""

    def test_perfect_ranking(self):
        y, p = [1, 0, 1, 0], [0.9, 0.1, 0.8, 0.3]
        self.assertEqual(pe.auroc(y, p), 1.0)
        self.assertEqual(pe.average_precision(y, p), 1.0)
        # (0.01 + 0.01 + 0.04 + 0.09) / 4
        self.assertAlmostEqual(pe.brier(y, p), 0.0375, places=12)

    def test_ties_and_imperfect_ranking(self):
        y, p = [1, 0, 1, 0, 0], [0.6, 0.6, 0.2, 0.4, 0.1]
        # pos 0.6: tie(0.5) + 1 + 1; pos 0.2: 0 + 0 + 1  -> 3.5 / 6
        self.assertAlmostEqual(pe.auroc(y, p), 3.5 / 6, places=12)
        # thresholds 0.6 (P=.5,R=.5), 0.4 (P=1/3,R=.5), 0.2 (P=.5,R=1), 0.1 (P=.4,R=1)
        # AP = .5*.5 + 0 + .5*.5 + 0
        self.assertAlmostEqual(pe.average_precision(y, p), 0.5, places=12)
        # (.16 + .36 + .64 + .16 + .01) / 5
        self.assertAlmostEqual(pe.brier(y, p), 0.266, places=12)

    def test_constant_prediction_is_chance(self):
        y, p = [1, 0, 0, 0], [0.25] * 4
        self.assertEqual(pe.auroc(y, p), 0.5)
        self.assertAlmostEqual(pe.average_precision(y, p), 0.25, places=12)
        self.assertAlmostEqual(pe.brier(y, p), 0.1875, places=12)

    def test_inverted_ranking_is_never_flipped(self):
        self.assertEqual(pe.auroc([1, 0], [0.2, 0.8]), 0.0)

    def test_single_class_is_undefined_not_guessed(self):
        with self.assertRaises(ValueError):
            pe.auroc([1, 1], [0.2, 0.8])
        with self.assertRaises(ValueError):
            pe.average_precision([0, 0], [0.2, 0.8])


class PredictionParsingTests(unittest.TestCase):
    IDS = ['t-a', 't-b', 't-c']

    def parse(self, text):
        return pe.parse_predictions(text, self.IDS)

    def test_accepts_exact_contract_in_any_row_order(self):
        got = self.parse('row_id,probability\nt-c,0.1\nt-a,1\nt-b,0\n')
        self.assertEqual(got, {'t-a': 1.0, 't-b': 0.0, 't-c': 0.1})

    def test_rejects_invalid_submissions_without_repair(self):
        bad = {
            'empty': '',
            'header': 'id,prob\nt-a,0.1\nt-b,0.2\nt-c,0.3\n',
            'missing id': 'row_id,probability\nt-a,0.1\nt-b,0.2\n',
            'extra id': 'row_id,probability\nt-a,0.1\nt-b,0.2\nt-c,0.3\nt-d,0.4\n',
            'duplicate': 'row_id,probability\nt-a,0.1\nt-a,0.2\nt-b,0.2\nt-c,0.3\n',
            'nan': 'row_id,probability\nt-a,nan\nt-b,0.2\nt-c,0.3\n',
            'inf': 'row_id,probability\nt-a,inf\nt-b,0.2\nt-c,0.3\n',
            'above one': 'row_id,probability\nt-a,1.0001\nt-b,0.2\nt-c,0.3\n',
            'negative': 'row_id,probability\nt-a,-0.01\nt-b,0.2\nt-c,0.3\n',
            'blank value': 'row_id,probability\nt-a,\nt-b,0.2\nt-c,0.3\n',
            'text value': 'row_id,probability\nt-a,high\nt-b,0.2\nt-c,0.3\n',
            'extra column': 'row_id,probability,x\nt-a,0.1,1\nt-b,0.2,1\nt-c,0.3,1\n',
            'blank row': 'row_id,probability\nt-a,0.1\n\nt-b,0.2\nt-c,0.3\n',
            'percent': 'row_id,probability\nt-a,10\nt-b,20\nt-c,30\n',
        }
        for label, text in bad.items():
            with self.subTest(label), self.assertRaises(pe.SubmissionError):
                self.parse(text)


class BuildFoldTests(unittest.TestCase):
    def test_partitions_rows_and_hides_test_labels(self):
        public, gold, crosswalk = build()
        self.assertEqual(len(public['train']), 15)
        self.assertEqual(len(public['test']), 5)
        self.assertTrue(all('label' in r for r in public['train']))
        self.assertTrue(all(set(r) == {'row_id', 'x'} for r in public['test']))
        self.assertEqual(set(gold['labels']), {r['row_id'] for r in public['test']})
        text = json.dumps(public)
        for case_id in synthetic_dataset()['case_ids']:
            self.assertNotIn(case_id, text)
        self.assertEqual(set(crosswalk), {r['row_id'] for r in public['train'] + public['test']})

    def test_public_payload_is_independent_of_held_out_labels(self):
        ds = synthetic_dataset()
        flipped = copy.deepcopy(ds)
        for i in TEST_INDICES:
            flipped['labels']['MYD88'][i] = 1 - flipped['labels']['MYD88'][i]
        self.assertEqual(build(ds)[0], build(flipped)[0])
        self.assertNotEqual(build(ds)[1], build(flipped)[1])

    def test_row_ids_are_fresh_per_task(self):
        a = {r['row_id'] for r in build(fold=0)[0]['test']}
        b = {r['row_id'] for r in build(gene='CD79B', fold=0)[0]['test']}
        self.assertFalse(a & b)

    def test_features_use_shared_canonical_rounding(self):
        from pcnsl import prediction_eval as ev
        ds = synthetic_dataset()
        ds['feature_names'][1] = 'lesion_volume_in_Cortical Gray Matter'
        ds['feature_groups']['imaging'][1] = 'lesion_volume_in_Cortical Gray Matter'
        ds['X'][2][0] = 1.234567891
        ds['X'][3][0] = 123456789
        public, _, crosswalk = build(ds)
        canon = ev.canonical_matrix(ds['X'])
        index = {c: i for i, c in enumerate(ds['case_ids'])}
        for row in public['train'] + public['test']:
            self.assertEqual(row['x'], list(canon[index[crosswalk[row['row_id']]]]))
        values = {v for r in public['train'] for v in r['x']}
        self.assertTrue({1.23457, 123457000.0} <= values)

    def test_fold_helper_uses_prediction_eval_folds(self):
        from pcnsl import prediction_eval as ev
        ds = synthetic_dataset()
        folds = ev.make_folds(ds, 'MYD88', seed=ev.DEFAULT_SEED, min_class_count=2)
        public, gold, crosswalk = pe.build_eval_fold(ds, 'MYD88', 2, min_class_count=2)
        self.assertEqual({crosswalk[k] for k in gold['labels']},
                         {ds['case_ids'][i] for i in folds[2]['test']})
        self.assertEqual(public['fold'], 2)

    def test_rejects_contract_violations(self):
        cases = {}
        d = synthetic_dataset(); d['X'][3][1] = 'high'; cases['string feature'] = d
        d = synthetic_dataset(); d['X'][3][1] = float('nan'); cases['nan feature'] = d
        d = synthetic_dataset(); d['X'][3][1] = True; cases['bool feature'] = d
        d = synthetic_dataset(); d['X'][3] = d['X'][3][:2]; cases['ragged row'] = d
        d = synthetic_dataset(); d['labels']['MYD88'][2] = 2; cases['non-binary label'] = d
        d = synthetic_dataset(); d['case_ids'][1] = d['case_ids'][0]; cases['duplicate case'] = d
        d = synthetic_dataset(); d['feature_groups']['imaging'].append('nope'); cases['unknown group member'] = d
        d = synthetic_dataset(); d['feature_names'][0] = 'scan_date'; cases['date feature'] = d
        d = synthetic_dataset(); d['feature_names'][0] = 'patient_id'; cases['id feature'] = d
        d = synthetic_dataset(); d['feature_names'][0] = '/data/raw/x'; cases['path feature'] = d
        for label, dataset in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                build(dataset)
        with self.assertRaises(ValueError):
            build(gene='TP53')
        with self.assertRaises(ValueError):  # single-class held-out fold
            build(test_indices=[1, 3, 5])
        with self.assertRaises(ValueError):
            build(test_indices=[0, 0, 1])


class ExportTests(TempDirCase):
    def export(self, **kw):
        public, gold, _ = build()
        return pe.export_task(public, gold, self.tmp / 'tasks', **kw)

    def test_gold_lives_only_in_verifier_tests(self):
        task = self.export()
        public, gold, _ = build()
        visible = agent_visible(task)
        gold_text = (task / 'tests' / 'gold.json').read_text()
        self.assertEqual(json.loads(gold_text)['labels'], gold['labels'])
        for name, data in visible.items():
            self.assertNotIn(b'gold', name.encode())
            self.assertNotIn(b'"labels"', data, name)
        test_csv = (task / 'environment' / 'data' / 'test.csv').read_text().splitlines()
        self.assertEqual(test_csv[0].split(',')[:2], ['row_id', 'flair_volume'])
        self.assertNotIn('label', test_csv[0])
        dockerfile = (task / 'environment' / 'Dockerfile').read_text()
        self.assertNotIn('tests', dockerfile)
        self.assertNotIn('solution', dockerfile)

    def test_agent_visible_bytes_do_not_depend_on_held_out_labels(self):
        ds = synthetic_dataset()
        flipped = copy.deepcopy(ds)
        for i in TEST_INDICES:
            flipped['labels']['MYD88'][i] = 1 - flipped['labels']['MYD88'][i]
        a = pe.export_task(*build(ds)[:2], self.tmp / 'a')
        b = pe.export_task(*build(flipped)[:2], self.tmp / 'b')
        self.assertEqual(agent_visible(a), agent_visible(b))
        self.assertNotEqual((a / 'tests' / 'gold.json').read_bytes(), (b / 'tests' / 'gold.json').read_bytes())

    def test_no_original_ids_dates_or_paths_in_task(self):
        task = self.export()
        blob = b''.join(all_files(task).values()).decode()
        for case_id in synthetic_dataset()['case_ids']:
            self.assertNotIn(case_id, blob)
        self.assertNotIn(str(self.tmp), blob)
        self.assertNotIn('/mnt/', blob)
        self.assertNotIn('2026-11-14', blob)

    def test_instruction_states_contract_without_solution_code(self):
        text = (self.export() / 'instruction.md').read_text()
        for needle in ('/workspace/data/train.csv', '/workspace/data/test.csv',
                       '/workspace/output/predictions.csv', 'row_id,probability', 'AUROC'):
            self.assertIn(needle, text)
        for forbidden in ('LogisticRegression', 'TabPFNClassifier', 'import sklearn', 'fit('):
            self.assertNotIn(forbidden, text)
        self.assertNotIn('TabPFN', text)  # not offered unless a checkpoint is declared

    def test_task_toml_isolates_verifier_and_carries_only_output(self):
        task = self.export(agent_allowed_hosts=['api.anthropic.com'])
        config = tomllib.loads((task / 'task.toml').read_text())
        self.assertEqual(config['verifier']['environment_mode'], 'separate')
        self.assertEqual(config['verifier']['network_mode'], 'no-network')
        self.assertEqual(config['artifacts'], ['/workspace/output'])
        self.assertEqual(config['agent']['network_mode'], 'allowlist')
        self.assertEqual(config['agent']['allowed_hosts'], ['api.anthropic.com'])

    def test_agent_network_fails_closed_unless_model_api_is_allowlisted(self):
        default = self.export()
        self.assertEqual(tomllib.loads((default / 'task.toml').read_text())['agent']['network_mode'], 'no-network')
        self.assertIn('no network access', (default / 'instruction.md').read_text())
        allowed = pe.export_task(*build()[:2], self.tmp / 'allowed', agent_allowed_hosts=['api.anthropic.com'])
        agent = tomllib.loads((allowed / 'task.toml').read_text())['agent']
        self.assertEqual((agent['network_mode'], agent['allowed_hosts']), ('allowlist', ['api.anthropic.com']))
        text = (allowed / 'instruction.md').read_text()
        self.assertIn('api.anthropic.com', text)
        self.assertNotIn('no network access', text)

    def test_default_image_installs_into_project_venv_not_system_python(self):
        dockerfile = (self.export() / 'environment' / 'Dockerfile').read_text()
        self.assertIn('python3 -m venv /opt/benchmark-venv', dockerfile)
        self.assertIn('/opt/benchmark-venv/bin/python -m pip install --no-cache-dir', dockerfile)
        self.assertIn('ENV PATH=/opt/benchmark-venv/bin:$PATH', dockerfile)
        install = next(l for l in dockerfile.splitlines() if 'pip install' in l)
        self.assertNotRegex(install, r'RUN (python3 -m )?pip install')
        self.assertLess(dockerfile.index('ENV PATH=/opt/benchmark-venv'), dockerfile.index('import numpy'))
        self.assertIn('sys.prefix', dockerfile)  # build fails if python3 resolves to system Python

    def test_custom_image_must_already_have_environment_on_path(self):
        dockerfile = (self.export(base_image='registry.example/pcnsl-tabpfn@sha256:' + 'b' * 64)
                      / 'environment' / 'Dockerfile').read_text()
        self.assertNotIn('pip install', dockerfile)
        self.assertNotIn('-m venv', dockerfile)
        self.assertIn('sys.prefix', dockerfile)

    def test_tabpfn_requires_prebuilt_image_and_fails_closed_at_build(self):
        with self.assertRaises(ValueError):
            self.export(tabpfn_checkpoint='/opt/tabpfn/model.ckpt')
        task = self.export(base_image='registry.example/pcnsl-tabpfn@sha256:' + 'a' * 64,
                           tabpfn_checkpoint='/opt/tabpfn/model.ckpt')
        dockerfile = (task / 'environment' / 'Dockerfile').read_text()
        self.assertIn('/opt/tabpfn/model.ckpt', dockerfile)
        self.assertIn('import tabpfn', dockerfile)
        self.assertNotIn('pip install', dockerfile)
        self.assertIn('TabPFN', (task / 'instruction.md').read_text())

    def test_never_overwrites_existing_task(self):
        task = self.export()
        before = all_files(task)
        with self.assertRaises(FileExistsError):
            self.export()
        self.assertEqual(all_files(task), before)
        self.assertEqual(sorted(p.name for p in (self.tmp / 'tasks').iterdir()), [task.name])

    def test_rejects_payload_that_skipped_canonical_rounding(self):
        public, gold, _ = build()
        public = copy.deepcopy(public)
        public['train'][0]['x'][0] = 1.234567891
        with self.assertRaises(ValueError):
            pe.export_task(public, gold, self.tmp / 'tasks')

    def test_rejects_mismatched_gold(self):
        public, gold, _ = build()
        gold = copy.deepcopy(gold)
        gold['labels'].popitem()
        with self.assertRaises(ValueError):
            pe.export_task(public, gold, self.tmp / 'tasks')
        self.assertFalse((self.tmp / 'tasks').exists() and any((self.tmp / 'tasks').iterdir()))


class VerifierTests(TempDirCase):
    """Run the exported grade.py exactly as shipped, against temp paths."""

    def setUp(self):
        super().setUp()
        self.public, self.gold, _ = build()
        self.task = pe.export_task(self.public, self.gold, self.tmp / 'tasks')
        self.out = self.tmp / 'output'
        self.out.mkdir()
        self.logs = self.tmp / 'logs'
        self.sandbox_root = self.tmp / 'sandbox'
        self.sandbox_root.mkdir()

    def grade(self, gold=None):
        return subprocess.run(
            [sys.executable, '-I', str(self.task / 'tests' / 'grade.py'),
             '--output-dir', str(self.out), '--gold', str(gold or self.task / 'tests' / 'gold.json'),
             '--logs', str(self.logs), '--sandbox-root', str(self.sandbox_root)],
            capture_output=True, text=True, timeout=60)

    def write(self, probs):
        lines = ['row_id,probability'] + [f'{k},{v}' for k, v in probs.items()]
        (self.out / 'predictions.csv').write_text('\n'.join(lines) + '\n')

    def rewards(self):
        return json.loads((self.logs / 'reward.json').read_text())

    def test_scores_valid_submission_with_reference_metrics(self):
        rng = random.Random(5)
        probs = {k: round(rng.random(), 3) for k in self.gold['labels']}
        self.write(probs)
        run = self.grade()
        self.assertEqual(run.returncode, 0, run.stderr)
        ids = sorted(self.gold['labels'])
        y = [self.gold['labels'][k] for k in ids]
        p = [probs[k] for k in ids]
        self.assertEqual(self.rewards(), {'reward': pe.auroc(y, p), 'valid_submission': 1.0})
        metrics = json.loads((self.logs / 'metrics.json').read_text())
        self.assertAlmostEqual(metrics['average_precision'], pe.average_precision(y, p), places=12)
        self.assertAlmostEqual(metrics['brier'], pe.brier(y, p), places=12)
        self.assertEqual(metrics['n_test'], 5)
        self.assertIn('"auroc"', run.stdout)

    def test_invalid_submission_scores_zero_and_is_flagged(self):
        ids = list(self.gold['labels'])
        variants = {
            'missing file': None,
            'nan': {k: ('nan' if i == 0 else 0.5) for i, k in enumerate(ids)},
            'missing row': {k: 0.5 for k in ids[1:]},
            'extra row': {**{k: 0.5 for k in ids}, 't-extra': 0.5},
        }
        for label, probs in variants.items():
            with self.subTest(label):
                for f in self.out.iterdir():
                    f.unlink()
                if probs is not None:
                    self.write(probs)
                run = self.grade()
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(self.rewards(), {'reward': 0.0, 'valid_submission': 0.0})
                metrics = json.loads((self.logs / 'metrics.json').read_text())
                self.assertIsNone(metrics['auroc'])
                self.assertTrue(metrics['submission_error'])

    def test_symlinked_prediction_file_is_rejected(self):
        target = self.tmp / 'elsewhere.csv'
        target.write_text('row_id,probability\n' + ''.join(f'{k},0.5\n' for k in self.gold['labels']))
        (self.out / 'predictions.csv').symlink_to(target)
        self.assertEqual(self.grade().returncode, 0)
        self.assertEqual(self.rewards()['valid_submission'], 0.0)

    def test_fails_closed_without_reward_when_verifier_shares_agent_sandbox(self):
        self.write({k: 0.5 for k in self.gold['labels']})
        for marker in ('solution', 'bundle'):
            with self.subTest(marker):
                (self.sandbox_root / marker).mkdir()
                run = self.grade()
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((self.logs / 'reward.json').exists())
                self.assertIn('separate', run.stdout + run.stderr)
                (self.sandbox_root / marker).rmdir()

    def test_missing_gold_is_infrastructure_error_not_score(self):
        self.write({k: 0.5 for k in self.gold['labels']})
        run = self.grade(gold=self.tmp / 'absent.json')
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.logs / 'reward.json').exists())

    def test_oracle_baseline_runs_offline_and_scores_chance(self):
        run = subprocess.run(
            [sys.executable, '-I', str(self.task / 'solution' / 'prevalence_baseline.py'),
             str(self.task / 'environment' / 'data'), str(self.out / 'predictions.csv')],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.grade().returncode, 0)
        self.assertEqual(self.rewards(), {'reward': 0.5, 'valid_submission': 1.0})
        solve = (self.task / 'solution' / 'solve.sh').read_text()
        self.assertNotIn('gold', solve)
        self.assertNotIn('/tests', solve)


@unittest.skipUnless(SDK_PYTHON.exists(), 'Valkyrie SDK venv not installed')
class SdkValidationTests(TempDirCase):
    def test_sdk_accepts_and_packs_exported_task(self):
        task = pe.export_task(*build()[:2], self.tmp / 'tasks')
        code = ('import sys, json; from pathlib import Path\n'
                'from valkyrie.sdk.task_archive import find_task_folders, task_problems, pack_task\n'
                'from valkyrie.sdk.task_content import task_files\n'
                'root = Path(sys.argv[1]); out = {}\n'
                'for name, folder in find_task_folders(root).items():\n'
                '    pack_task(folder, Path(sys.argv[2]) / (name + ".zip"))\n'
                '    out[name] = dict(problems=task_problems(folder),\n'
                '        files=[p.relative_to(folder).as_posix() for p in task_files(folder)])\n'
                'print(json.dumps(out))\n')
        run = subprocess.run([str(SDK_PYTHON), '-c', code, str(task.parent), str(self.tmp)],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)[task.name]
        self.assertEqual(report['problems'], [])
        self.assertIn('tests/gold.json', report['files'])
        self.assertIn('environment/data/test.csv', report['files'])

    @unittest.skipUnless(TRACKER_CONFIG.exists(), 'pinned Valkyrie tracker source not present')
    def test_tracker_schema_parses_separate_verifier_config(self):
        task = pe.export_task(*build()[:2], self.tmp / 'tasks', agent_allowed_hosts=['api.anthropic.com'])
        code = ('import importlib.util, sys, tomllib\n'
                'spec = importlib.util.spec_from_file_location("tracker_config", sys.argv[1])\n'
                'm = importlib.util.module_from_spec(spec); sys.modules["tracker_config"] = m\n'
                'spec.loader.exec_module(m)\n'
                'c = m.TaskConfig.model_validate(tomllib.loads(open(sys.argv[2]).read()))\n'
                'assert c.verifier.is_separate, "verifier not separate"\n'
                'assert [a.source for a in c.artifacts] == ["/workspace/output"], c.artifacts\n'
                'assert c.verifier.network_mode.value == "no-network"\n'
                'print("ok")\n')
        run = subprocess.run([str(SDK_PYTHON), '-c', code, str(TRACKER_CONFIG), str(task / 'task.toml')],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), 'ok')


if __name__ == '__main__':
    unittest.main()
