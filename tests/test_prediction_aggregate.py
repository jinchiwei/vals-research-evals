"""Aggregation of Harbor agent submissions into pooled out-of-fold metrics. Synthetic data only."""
import copy
import json
import math
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pcnsl import prediction_aggregate as pa
from pcnsl import prediction_eval as ev
from pcnsl import prediction_export as px

GENE = 'SYNTHA'
REPO = Path(__file__).resolve().parents[1]


def dataset():
    ds = ev.synthetic_dataset()
    # Real gene symbols have no underscore; the exporter enforces that.
    ds['labels'] = {name.replace('_', ''): v for name, v in ds['labels'].items()}
    return ds


def bundles(ds, gene=GENE):
    out = {}
    for k in range(ev.N_SPLITS):
        public, gold, crosswalk = px.build_eval_fold(ds, gene, k)
        out[k] = {'public': public, 'gold': gold, 'crosswalk': crosswalk}
    return out


def agent_probability(x):
    """A fixed, label-free rule standing in for an agent's model."""
    v = x[0] if x[0] is not None else 0.0
    return round(1 / (1 + math.exp(-v)), 6)


def submission(bundle, shuffle_seed=None, override=None):
    rows = [(r['row_id'], agent_probability(r['x'])) for r in bundle['public']['test']]
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(rows)
    lines = ['row_id,probability'] + [f'{i},{p}' for i, p in rows]
    text = '\n'.join(lines) + '\n'
    return override(text) if override else text


def expected_pooled(ds, gene=GENE):
    X = ev.canonical_matrix(ds['X'])
    y = ds['labels'][gene]
    p = [agent_probability(list(row)) for row in X]
    return ev.evaluate_probabilities(y, p)


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.ds = dataset()
        self.b = bundles(self.ds)
        self.subs = {k: submission(v) for k, v in self.b.items()}

    def run_agg(self, subs=None, b=None, **kw):
        kw.setdefault('bootstrap', 50)
        return pa.aggregate_submissions(self.ds, GENE, b or self.b, self.subs if subs is None else subs, **kw)

    def arm(self, report, name='agent'):
        return report['genes'][GENE]['arms'][name]

    def test_complete_folds_give_pooled_oof_matching_case_keyed_reference(self):
        report = self.run_agg()
        arm = self.arm(report)
        self.assertEqual(arm['status'], 'complete')
        self.assertEqual(arm['folds_completed'], 5)
        self.assertEqual(len(arm['per_fold']), 5)
        for metric, value in expected_pooled(self.ds).items():
            self.assertAlmostEqual(arm['pooled_oof'][metric], value, places=12)
        self.assertIn('bootstrap_95', arm)
        self.assertIn('conditional on the fitted folds', report['design']['bootstrap']['note'])
        self.assertEqual(report['agent_submissions']['folds_valid'], [0, 1, 2, 3, 4])

    def test_row_order_of_submissions_is_irrelevant(self):
        shuffled = {k: submission(v, shuffle_seed=k + 1) for k, v in self.b.items()}
        a, b = self.run_agg(), self.run_agg(subs=shuffled)
        self.assertEqual(self.arm(a)['pooled_oof'], self.arm(b)['pooled_oof'])
        self.assertEqual(self.arm(a)['per_fold'], self.arm(b)['per_fold'])

    def test_report_is_aggregate_only(self):
        text = json.dumps(self.run_agg(comparators=['training_prevalence']))
        for k, v in self.b.items():
            for row_id, case_id in v['crosswalk'].items():
                self.assertNotIn(row_id, text)
                self.assertNotIn(case_id, text)
        self.assertFalse(self.run_agg()['design']['patient_level_outputs'])

    def test_missing_fold_is_partial_without_pooled_oof(self):
        subs = dict(self.subs); subs[3] = None
        arm = self.arm(self.run_agg(subs=subs))
        self.assertEqual(arm['status'], 'partial')
        self.assertIsNone(arm['pooled_oof'])
        self.assertEqual([f['fold'] for f in arm['per_fold']], [0, 1, 2, 4])
        self.assertNotIn('bootstrap_95', arm)

    def test_invalid_fold_is_error_without_pooled_oof(self):
        subs = dict(self.subs)
        subs[1] = 'row_id,probability\n' + ''.join(f"{r['row_id']},nan\n" for r in self.b[1]['public']['test'])
        report = self.run_agg(subs=subs)
        arm = self.arm(report)
        self.assertEqual(arm['status'], 'error')
        self.assertIsNone(arm['pooled_oof'])
        self.assertEqual(report['agent_submissions']['folds_invalid'], [1])

    def test_predictions_from_another_fold_or_gene_task_are_invalid(self):
        subs = dict(self.subs); subs[0] = self.subs[1]
        self.assertEqual(self.arm(self.run_agg(subs=subs))['status'], 'error')
        other = bundles(self.ds, 'SYNTHB')
        subs = dict(self.subs); subs[2] = submission(other[2])
        self.assertEqual(self.arm(self.run_agg(subs=subs))['status'], 'error')

    def test_rejects_bundle_for_wrong_gene_or_fold(self):
        b = dict(self.b); b[0] = bundles(self.ds, 'SYNTHB')[0]
        with self.assertRaises(ValueError):
            self.run_agg(b=b)
        b = dict(self.b); b[0], b[1] = self.b[1], self.b[0]
        with self.assertRaises(ValueError):
            self.run_agg(b=b)
        b = dict(self.b); del b[4]
        with self.assertRaises(ValueError):
            self.run_agg(b=b)

    def test_rejects_crosswalk_mismatch_and_duplicate_cases(self):
        b = copy.deepcopy(self.b)
        cw = b[0]['crosswalk']
        test_id = b[0]['public']['test'][0]['row_id']
        train_id = b[0]['public']['train'][0]['row_id']
        cw[test_id], cw[train_id] = cw[train_id], cw[test_id]
        with self.assertRaises(ValueError):
            self.run_agg(b=b)
        b = copy.deepcopy(self.b)
        ids = [r['row_id'] for r in b[2]['public']['test']]
        b[2]['crosswalk'][ids[1]] = b[2]['crosswalk'][ids[0]]
        with self.assertRaisesRegex(ValueError, 'two rows to one case'):
            self.run_agg(b=b)
        b = copy.deepcopy(self.b)
        b[3]['crosswalk'].pop(next(iter(b[3]['crosswalk'])))
        with self.assertRaises(ValueError):
            self.run_agg(b=b)

    def test_rejects_self_consistent_bundle_built_on_a_different_split(self):
        folds = ev.make_folds(self.ds, GENE)
        public, gold, crosswalk = px.build_fold(self.ds, GENE, folds[1]['test'], seed=ev.DEFAULT_SEED, fold=0)
        b = dict(self.b); b[0] = {'public': public, 'gold': gold, 'crosswalk': crosswalk}
        with self.assertRaisesRegex(ValueError, 'canonical make_folds split'):
            self.run_agg(b=b)

    def test_rejects_gold_or_features_that_disagree_with_source(self):
        b = copy.deepcopy(self.b)
        key = next(iter(b[0]['gold']['labels']))
        b[0]['gold']['labels'][key] = 1 - b[0]['gold']['labels'][key]
        with self.assertRaises(ValueError):
            self.run_agg(b=b)
        b = copy.deepcopy(self.b)
        b[1]['public']['test'][0]['x'][0] = 99.0
        with self.assertRaises(ValueError):
            self.run_agg(b=b)

    def test_paired_comparators_share_folds_and_bootstrap(self):
        report = self.run_agg(comparators=['training_prevalence'])
        gene = report['genes'][GENE]
        self.assertEqual(gene['arms']['training_prevalence']['status'], 'complete')
        self.assertEqual(gene['arms']['agent']['split_fingerprint'],
                         gene['arms']['training_prevalence']['split_fingerprint'])
        diff = gene['paired_auroc_differences']['training_prevalence_minus_agent']
        self.assertIsNotNone(diff['bootstrap_95'])
        self.assertEqual(report['agent_submissions']['representation'], 'matches comparator inputs')

    def test_comparators_skipped_when_representation_differs(self):
        report = self.run_agg(comparators=['training_prevalence'], feature_group='spatial')
        self.assertNotIn('training_prevalence', report['genes'][GENE]['arms'])
        self.assertIn('not compared', report['agent_submissions']['representation'])
        self.assertEqual(self.arm(report)['status'], 'complete')


class CliTests(unittest.TestCase):
    def test_cli_writes_new_aggregate_file_and_never_overwrites(self):
        ds = dataset(); b = bundles(ds)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'dataset.json').write_text(json.dumps(ds))
            args = [sys.executable, '-m', 'pcnsl.prediction_aggregate', '--dataset', str(tmp / 'dataset.json'),
                    '--gene', GENE, '--private-dir', str(tmp / 'private'), '--out', str(tmp / 'report.json'),
                    '--bootstrap', '20']
            (tmp / 'private').mkdir()
            for k, v in b.items():
                stem = f'{GENE.lower()}-fold{k}'
                for part in ('public', 'gold', 'crosswalk'):
                    (tmp / 'private' / f'{stem}.{part}.json').write_text(json.dumps(v[part]))
                path = tmp / f'pred{k}.csv'
                path.write_text(submission(v))
                args += ['--submission', f'{k}={path}']
            run = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads((tmp / 'report.json').read_text())
            self.assertEqual(report['genes'][GENE]['arms']['agent']['status'], 'complete')
            before = (tmp / 'report.json').read_bytes()
            again = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=120)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual((tmp / 'report.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
