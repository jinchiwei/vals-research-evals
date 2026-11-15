import copy
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path


class CoreTests(unittest.TestCase):
    def test_package_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('prototype_evals'))

    def test_auc_handles_ties_and_reversed_scores(self):
        from prototype_evals.metrics import auc
        self.assertEqual(auc([0, 1, 0, 1], [0, 1, 0, 1]), 1)
        self.assertEqual(auc([0, 1], [1, 0]), 0)
        self.assertEqual(auc([0, 1], [4, 4]), .5)
        with self.assertRaises(ValueError):
            auc([1, 1], [0, 1])

    def test_scanner_offset_does_not_become_decline(self):
        from prototype_evals.metrics import trajectory
        rows = [{'year': t, 'value': v, 'scanner': s, 'sigma': .02}
                for t, v, s in [(0, 0, 'a'), (1, 0, 'a'), (2, -.8, 'b'), (3, -.8, 'b')]]
        result = trajectory(rows, {'a': 0, 'b': -.8})
        self.assertAlmostEqual(result['slope'], 0)
        self.assertAlmostEqual(result['se'], .02 / math.sqrt(5))
        self.assertEqual(result['verdict'], 'stable')
        self.assertEqual(trajectory(rows, {'a': 0, 'b': 0})['verdict'], 'decline')

    def test_generator_controls_and_reference(self):
        from prototype_evals.cases import generate
        from prototype_evals.grade import grade
        from prototype_evals.solve import solve
        cases = generate(11)
        self.assertEqual({c['family'] for c in cases}, {'audit', 'change', 'reports'})
        audits = [c for c in cases if c['family'] == 'audit']
        self.assertEqual({c['expected']['items'][0]['verdict'] for c in audits}, {'supported', 'unsupported'})
        for c in cases:
            with self.subTest(case=c['id']):
                self.assertEqual(grade(c['expected'], solve(c['public'], 'careful'))['score'], 1)

    def test_grader_rejects_nonfinite_missing_duplicate_and_wrong_evidence(self):
        from prototype_evals.grade import grade
        expected = {'items': [{'id': 'a', 'value': .5, 'evidence': 'No edema.'}]}
        self.assertEqual(grade(expected, copy.deepcopy(expected))['score'], 1)
        for bad in [None, {}, {'items': []}, {'items': expected['items'] * 2},
                    {'items': [{'id': 'a', 'value': math.nan, 'evidence': 'No edema.'}]},
                    {'items': [{'id': 'a', 'value': .5, 'evidence': 'Edema present.'}]}]:
            self.assertEqual(grade(expected, bad)['score'], 0)

    def test_export_keeps_answers_out_of_environment(self):
        from prototype_evals.cases import generate
        from prototype_evals.export import export_case
        case = generate(11)[0]
        with tempfile.TemporaryDirectory() as d:
            p = export_case(case, Path(d))
            self.assertTrue((p / 'tests' / 'expected.json').exists())
            self.assertFalse((p / 'environment' / 'expected.json').exists())
            self.assertEqual({f.name for f in (p / 'environment').iterdir()}, {'Dockerfile', 'input.json'})
            self.assertNotIn('expected', (p / 'environment' / 'input.json').read_text())


if __name__ == '__main__':
    unittest.main()
