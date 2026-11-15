"""Label-permutation null for the fixed logistic-regression pipeline. Synthetic data, few permutations."""
import copy
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pcnsl import prediction_eval as ev
from pcnsl import prediction_permutation as pp

REPO = Path(__file__).resolve().parents[1]
HAVE_SKLEARN = all(importlib.util.find_spec(m) for m in ('numpy', 'sklearn'))
B = 19


class CentroidArm:
    """Stdlib stand-in for the fixed pipeline: train-only means, projection onto the class-mean difference."""
    name = 'logistic_regression'
    safe_error_messages = True
    calls = 0

    def availability(self):
        return {'available': True}

    def predict_fold(self, fold):
        CentroidArm.calls += 1
        cols = range(len(fold.feature_names))
        mean = [sum(r[j] for r in fold.train_X if r[j] is not None) /
                max(1, sum(r[j] is not None for r in fold.train_X)) for j in cols]
        fill = lambda r: [mean[j] if r[j] is None else r[j] for j in cols]
        pos = [fill(r) for r, t in zip(fold.train_X, fold.train_y) if t == 1]
        neg = [fill(r) for r, t in zip(fold.train_X, fold.train_y) if t == 0]
        w = [sum(r[j] for r in pos) / len(pos) - sum(r[j] for r in neg) / len(neg) for j in cols]
        out = []
        for r in fold.test_X:
            z = sum((a - m) * b for a, m, b in zip(fill(r), mean, w))
            out.append(1 / (1 + math.exp(-max(-30.0, min(30.0, z)))))
        return out


class InvertedArm(CentroidArm):
    def predict_fold(self, fold):
        return [1 - p for p in super().predict_fold(fold)]


class BrokenOnPermutationArm(CentroidArm):
    def __init__(self):
        self.n = 0

    def predict_fold(self, fold):
        self.n += 1
        if self.n > 5:          # observed run (5 folds) works; first permutation fails
            raise ev.ArmError('fit failed')
        return super().predict_fold(fold)


class UnavailableArm(CentroidArm):
    def availability(self):
        return {'available': False, 'reason': 'not installed'}


def dataset():
    ds = ev.synthetic_dataset()
    ds['labels'] = {k.replace('_', ''): v for k, v in ds['labels'].items() if k != 'SYNTH_RARE'}
    return ds


def run(ds=None, genes=('SYNTHA', 'SYNTHB'), arm=CentroidArm, **kw):
    kw.setdefault('permutations', B)
    return pp.permutation_null(ds or dataset(), genes=genes, arm_factory=arm, **kw)


class PValueTests(unittest.TestCase):
    def test_plus_one_p_values_count_ties_as_extreme(self):
        null = [0.5, 0.6, 0.6, 0.7]
        self.assertAlmostEqual(pp.plus_one_p(null, 0.6, higher=True), (1 + 3) / 5)
        self.assertAlmostEqual(pp.plus_one_p(null, 0.6, higher=False), (1 + 3) / 5)
        self.assertAlmostEqual(pp.plus_one_p(null, 0.8, higher=True), 1 / 5)
        self.assertAlmostEqual(pp.plus_one_p(null, 0.4, higher=True), 5 / 5)
        self.assertAlmostEqual(pp.plus_one_p(null, 0.4, higher=False), 1 / 5)


class PermutedLabelTests(unittest.TestCase):
    def test_permutations_preserve_counts_are_reproducible_and_vary(self):
        y = dataset()['labels']['SYNTHB']
        perms = [pp.permuted_labels(y, 'SYNTHB', 20261115, b) for b in range(B)]
        self.assertTrue(all(sum(p) == sum(y) and len(p) == len(y) for p in perms))
        self.assertEqual(perms, [pp.permuted_labels(y, 'SYNTHB', 20261115, b) for b in range(B)])
        self.assertGreater(len({tuple(p) for p in perms}), B - 2)
        self.assertNotEqual(perms[0], pp.permuted_labels(y, 'SYNTHB', 1, 0))
        self.assertNotEqual(perms[0], pp.permuted_labels(y, 'MYD88', 20261115, 0))


class NullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CentroidArm.calls = 0
        cls.report = run()
        cls.calls = CentroidArm.calls

    def gene(self, name):
        return self.report['genes'][name]

    def test_signal_gene_has_minimum_p_and_null_gene_does_not(self):
        a, b = self.gene('SYNTHA'), self.gene('SYNTHB')
        self.assertEqual(a['status'], 'complete')
        self.assertGreater(a['observed']['auroc'], 0.7)
        self.assertEqual(a['p_values']['auroc_higher'], 1 / (B + 1))
        self.assertEqual(a['p_values']['brier_lower'], 1 / (B + 1))
        self.assertGreater(b['p_values']['auroc_higher'], 0.1)

    def test_p_values_follow_from_reported_null_distribution(self):
        for g in ('SYNTHA', 'SYNTHB'):
            r = self.gene(g)
            null, obs = r['null']['auroc'], r['observed']['auroc']
            self.assertEqual(len(null), B)
            self.assertEqual(len(r['null']['brier']), B)
            self.assertAlmostEqual(r['p_values']['auroc_higher'], (1 + sum(v >= obs for v in null)) / (B + 1))
            self.assertAlmostEqual(r['p_values']['brier_lower'],
                                   (1 + sum(v <= r['observed']['brier'] for v in r['null']['brier'])) / (B + 1))
            self.assertEqual(r['permutations_completed'], B)

    def test_every_permutation_refits_and_recomputes_splits(self):
        self.assertEqual(self.calls, 2 * (B + 1) * ev.N_SPLITS)
        self.assertGreater(self.gene('SYNTHB')['distinct_null_split_fingerprints'], B // 2)

    def test_reproducible_and_seed_dependent(self):
        again = run()
        self.assertEqual(json.dumps(again['genes'], sort_keys=True), json.dumps(self.report['genes'], sort_keys=True))
        other = run(seed=7)
        self.assertNotEqual(other['genes']['SYNTHB']['null'], self.gene('SYNTHB')['null'])
        self.assertEqual(other['genes']['SYNTHB']['observed'], self.gene('SYNTHB')['observed'])

    def test_report_is_aggregate_only_with_provenance_and_caveats(self):
        text = json.dumps(self.report)
        for case in dataset()['case_ids']:
            self.assertNotIn(case, text)
        d = self.report['design']
        self.assertEqual(d['permutation_seed'], 20261115)
        self.assertEqual(d['split_seed'], ev.DEFAULT_SEED)
        self.assertEqual(d['feature_count'], 12)
        self.assertIn('prediction_eval_sha256', d['code'])
        self.assertIn('logistic regression', d['scope'])
        self.assertIn('multiple', d['multiple_comparisons'])
        self.assertFalse(d['patient_level_outputs'])


class FailClosedTests(unittest.TestCase):
    def test_scores_are_never_flipped(self):
        r = run(genes=('SYNTHA',), arm=InvertedArm)['genes']['SYNTHA']
        self.assertLess(r['observed']['auroc'], 0.3)
        self.assertEqual(r['p_values']['auroc_higher'], 1.0)

    def test_failed_permutation_gives_no_p_values(self):
        r = run(genes=('SYNTHA',), arm=BrokenOnPermutationArm, permutations=3)['genes']['SYNTHA']
        self.assertEqual(r['status'], 'error')
        self.assertIsNone(r['p_values'])

    def test_unavailable_pipeline_raises(self):
        with self.assertRaises(RuntimeError):
            run(genes=('SYNTHA',), arm=UnavailableArm, permutations=2)

    def test_rejects_duplicate_patients_and_bad_requests(self):
        ds = dataset(); ds['groups'] = [f'p{i // 2}' for i in range(len(ds['case_ids']))]
        with self.assertRaisesRegex(ValueError, 'one row per patient'):
            run(ds, permutations=2)
        ds = dataset(); ds['case_ids'][1] = ds['case_ids'][0]
        with self.assertRaises(ValueError):
            run(ds, permutations=2)
        with self.assertRaises(ValueError):
            run(genes=('NOTAGENE',), permutations=2)
        with self.assertRaises(ValueError):
            run(permutations=0)


class CliTests(unittest.TestCase):
    def test_parser_defaults_are_prespecified(self):
        args = pp.build_parser().parse_args(['--dataset', 'd.json', '--out', 'o.json'])
        self.assertEqual((args.permutations, args.genes, args.seed), (199, ['MYD88', 'CD79B'], 20261115))

    def test_default_pipeline_is_the_fixed_logistic_regression_arm(self):
        self.assertIs(pp.DEFAULT_ARM, ev.LogisticRegressionArm)

    @unittest.skipUnless(HAVE_SKLEARN, 'scikit-learn not installed on this host')
    def test_cli_runs_logistic_regression_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'd.json').write_text(json.dumps(dataset()))
            args = [sys.executable, '-m', 'pcnsl.prediction_permutation', '--dataset', str(tmp / 'd.json'),
                    '--out', str(tmp / 'o.json'), '--permutations', '3', '--genes', 'SYNTHA']
            self.assertEqual(subprocess.run(args, cwd=REPO).returncode, 0)
            report = json.loads((tmp / 'o.json').read_text())
            self.assertEqual(report['genes']['SYNTHA']['permutations_completed'], 3)
            self.assertIn('dataset_sha256', report['design'])
            self.assertNotEqual(subprocess.run(args, cwd=REPO, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
