import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from repair_evals import compare


def hand_input():
    clinical = {'protocol': {'gene': 'G', 'gene_aliases': {}, 'as_of_day': 20, 'lookback_days': 10},
                'participants': [], 'specimens': [], 'reports': [], 'scans': []}
    for pid, label in [('A', 1), ('B', 0)]:
        clinical['participants'].append(dict(participant_id=pid, age=40, confirmed_pcnsl=True, therapy_day=None))
        clinical['specimens'].append(dict(sample_id='s'+pid, participant_id=pid, day=10, type='tumor', assay_status='passed'))
        clinical['scans'].append(dict(scan_id='m'+pid, participant_id=pid, day=9, qc_pass=True, sequences=['FLAIR','T1POST']))
        clinical['reports'].append(dict(report_id='r'+pid, sample_id='s'+pid, revision=1, issued_day=11, status='final', genes_tested=['G'], variants=[dict(gene='G',classification='Pathogenic',reported=True,detection='Detected')] if label else []))
    artifacts = [dict(artifact_id='source', parents=[], operation='source', subjects=['A','B'], available_day=1, selection_split=None),
                 dict(artifact_id='clean', parents=['source'], operation='fit_model', subjects=['T'], available_day=10, selection_split=None),
                 dict(artifact_id='transform', parents=['source'], operation='fit_transform', subjects=['b-alias2'], available_day=9, selection_split=None),
                 dict(artifact_id='dirty', parents=['transform'], operation='fit_model', subjects=['T'], available_day=10, selection_split=None)]
    predictions = [dict(row_id='p'+pid, scan_id='m'+pid, subject_id=pid, exported_day=15, revision=1, probability=.9 if pid=='A' else .1, cached_label=0 if pid=='A' else 1) for pid in ('A','B')]
    return dict(clinical=clinical, identity={'canonical_subjects':['A','B','T'], 'links':[['B','b-alias1'],['b-alias1','b-alias2']]},
                artifacts=artifacts, plan=dict(alpha=.5, evaluation_lock_day=20, hypotheses=[{'hypothesis_id':'H1','run_id':'R1'},{'hypothesis_id':'H2','run_id':'R2'}], null_orders=[['B','A']]*3),
                runs=[dict(run_id='R1',artifact_id='clean',freeze_day=12,probability_for_class=1,predictions=predictions),dict(run_id='R2',artifact_id='dirty',freeze_day=12,probability_for_class=1,predictions=predictions)],
                manuscript=[dict(hypothesis_id='H1',n_patients=2,auroc=1.,reject=True),dict(hypothesis_id='H2',n_patients=2,auroc=1.,reject=True)])


class IntegratedTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('repair_evals.integrated'), 'integrated task must exist')
        from repair_evals.integrated import make_case, reference
        self.make_case, self.reference = make_case, reference

    def test_hand_derived_endpoint_identity_and_holm_chain(self):
        result = self.reference(hand_input())
        h1, h2 = result['statistics']['hypotheses']
        self.assertEqual(h1['auroc'], 1.)
        self.assertAlmostEqual(h1['brier'], .01)
        self.assertEqual(h1['p_value'], .25)
        self.assertEqual(h1['holm_p'], .5)
        self.assertTrue(h1['reject'])
        self.assertEqual(h2['reason'], 'patient_overlap')
        self.assertEqual(h2['holm_p'], 1.)
        self.assertEqual(result['provenance'][1]['transform_fit_subjects'], ['B'])
        self.assertEqual(result['manuscript'][0]['status'], 'consistent')
        self.assertEqual(result['manuscript'][1]['status'], 'revise')

    def test_source_and_application_membership_do_not_imply_fitting(self):
        data = hand_input()
        data['artifacts'][2]['operation'] = 'apply'
        result = self.reference(data)
        self.assertTrue(result['statistics']['hypotheses'][1]['eligible'])
        self.assertEqual(result['provenance'][1]['transform_fit_subjects'], [])

    def test_ancestor_availability_and_selection_have_priority(self):
        data = hand_input()
        data['artifacts'][2]['available_day'] = 21
        result = self.reference(data)
        self.assertEqual(result['statistics']['hypotheses'][1]['reason'], 'evaluation_selection')
        data['artifacts'][2].update(available_day=9, operation='select', selection_split='evaluation')
        self.assertEqual(self.reference(data)['statistics']['hypotheses'][1]['reason'], 'evaluation_selection')

    def test_selected_scan_and_asof_prediction_export_are_authoritative(self):
        data = hand_input()
        data['runs'][0]['predictions'].extend([
            dict(data['runs'][0]['predictions'][0], row_id='future', exported_day=21, probability=.01),
            dict(data['runs'][0]['predictions'][0], row_id='revised', exported_day=16, probability=.8)])
        result = self.reference(data)
        self.assertAlmostEqual(result['statistics']['hypotheses'][0]['brier'], .025)
        self.assertEqual(result['provenance'][0]['prediction_rows'], ['pB','revised'])

    def test_null_order_is_projected_before_assigning_positive_labels(self):
        data = hand_input()
        data['clinical']['participants'].append(dict(participant_id='C',age=16,confirmed_pcnsl=True,therapy_day=None))
        data['identity']['canonical_subjects'].append('C')
        data['plan']['null_orders'] = [['C','B','A']] * 3
        result = self.reference(data)
        self.assertEqual(result['statistics']['hypotheses'][0]['p_value'], .25)
        self.assertEqual(result['cohort']['excluded'], [{'participant_id':'C','reason':'ineligible_participant'}])

    def test_artifact_and_identity_row_order_have_no_semantic_effect(self):
        data = hand_input()
        permuted = copy.deepcopy(data)
        permuted['artifacts'].reverse()
        permuted['identity']['links'].reverse()
        permuted['runs'].reverse()
        self.assertTrue(compare(self.reference(data),self.reference(permuted))['passed'])

    def test_frozen_controls_and_hidden_generalization(self):
        for variant in ('valid','flawed'):
            case = self.make_case(11, variant)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name, content in case['files'].items():
                    (root/name).write_text(content)
                outcomes = []
                for fixture in case['hidden']:
                    (root/'fixture.json').write_text(json.dumps(fixture['input']))
                    subprocess.run([sys.executable,str(root/'analysis.py'),str(root/'fixture.json'),str(root/'out.json')], check=True, capture_output=True)
                    outcomes.append(compare(fixture['expected'],json.loads((root/'out.json').read_text()))['passed'])
                self.assertEqual(all(outcomes), variant=='valid', outcomes)
            visible = self.reference(json.loads(case['files']['input.json']))
            self.assertTrue(any(not compare(f['expected'],visible)['passed'] for f in case['hidden']))
            self.assertEqual(set(case['files']), {'analysis.py','input.json','protocol.md','schema.md','handoff.md'})


if __name__ == '__main__':
    unittest.main()
