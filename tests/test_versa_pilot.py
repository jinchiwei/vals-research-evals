import json
from pathlib import Path
import tempfile
import unittest

from scripts import run_versa_prediction_pilot as pilot
from pcnsl.prediction_eval import synthetic_dataset


class VersaPilotTests(unittest.TestCase):
    def dataset(self):
        d = synthetic_dataset()
        d['labels'] = {'MYD88': d['labels']['SYNTH_A'], 'CD79B': d['labels']['SYNTH_B']}
        return d

    def test_preparation_has_exactly_four_requests_and_no_test_labels(self):
        jobs = pilot.prepare(self.dataset())
        self.assertEqual(len(jobs), 4)
        for job in jobs:
            p = json.loads(job['request'])
            self.assertTrue(all(set(r) == {'case', 'features'} for r in p['test']))
            self.assertEqual(len(job['truth']), len(p['test']))
            self.assertNotIn('truth', p)

    def test_size_gate_rejects_before_client_construction(self):
        with self.assertRaises(ValueError):
            pilot.prepare(self.dataset(), max_chars=100)

    def test_truncated_response_is_resource_failure_even_if_json_looks_valid(self):
        job = pilot.prepare(self.dataset())[0]
        text = json.dumps({'predictions': [{'case': c, 'probability': .5} for c in job['expected_ids']]})
        result = {'ok': True, 'text': text, 'truncated': False, 'stop_reason': 'max_tokens'}
        out = pilot.score(job, result)
        self.assertEqual(out['status'], 'resource_limit')
        self.assertNotIn('metrics', out)

    def test_valid_scores_are_separate_from_private_text(self):
        job = pilot.prepare(self.dataset())[0]
        text = json.dumps({'predictions': [{'case': c, 'probability': .5} for c in job['expected_ids']]})
        out = pilot.score(job, {'ok': True, 'text': text, 'stop_reason': 'end_turn'})
        self.assertEqual(out['metrics']['auroc'], .5)
        self.assertNotIn('text', out)
        self.assertNotIn('test-001', json.dumps(out))


if __name__ == '__main__':
    unittest.main()
