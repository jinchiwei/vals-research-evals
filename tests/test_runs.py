import json
import tempfile
import unittest
from pathlib import Path


class RunTests(unittest.TestCase):
    def test_smoke_loop_selects_on_development_only(self):
        from prototype_evals.experiment import smoke_loop
        with tempfile.TemporaryDirectory() as d:
            result = smoke_loop(Path(d), [11, 23], [101])
            self.assertEqual(result['selected'], 'careful')
            self.assertEqual(result['heldout']['score'], 1)
            self.assertEqual(result['selection_split'], 'development')
            self.assertEqual(len(result['iterations']), 3)
            self.assertLess(result['iterations'][0]['score'], 1)
            self.assertTrue((Path(d) / 'experiments.jsonl').exists())

    def test_stop_file_and_overlapping_splits(self):
        from prototype_evals.experiment import smoke_loop
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                smoke_loop(root, [11], [11])
            (root / 'STOP').touch()
            self.assertEqual(smoke_loop(root, [11], [101])['status'], 'stopped')

    def test_report_gold_handles_late_signature_and_addendum(self):
        from prototype_evals.solve import solve
        data = dict(family='reports', queries=[dict(id='x', finding='superficial siderosis')], reports=[
            dict(id='old', subject='x', exam_date='2024-01-01', signed_at='2026-02-03', text='New edema is present.'),
            dict(id='new', subject='x', exam_date='2026-01-01', signed_at='2026-01-02', text='No edema is seen.'),
            dict(id='correction', subject='x', exam_date='2026-01-01', signed_at='2026-01-03', replaces='new',
                 text='Possible new superficial siderosis; artifact cannot be excluded.')])
        item = solve(data)['items'][0]
        self.assertEqual(item['source_id'], 'correction')
        self.assertEqual(item['status'], 'uncertain')
        self.assertEqual(item['change'], 'unknown')


if __name__ == '__main__':
    unittest.main()
