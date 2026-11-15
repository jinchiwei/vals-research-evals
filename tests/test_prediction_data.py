"""Boundary tests for the public patient-level prediction dataset."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class PredictionDataTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('pcnsl.prediction_data'),
                             'Public prediction extractor must exist')
        from pcnsl.prediction_data import load_dataset
        return load_dataset

    def fixture(self, root):
        (root/'ucsf500_mutations.csv').write_text(
            'patientdurablekey,gene,reportedalteration,variantclassification,geneticorigin,tumorcollecteddate\n'
            '1,MYD88,true,Pathogenic,Somatic,2000-01-01\n'
            '1,MYD88,true,Pathogenic,Somatic,2000-01-01'
            '\n2,MYD88,true,Uncertain Significance,Somatic,2000-02-01\n')
        (root/'demographics.csv').write_text('patientdurablekey,Sex,BirthDate\n1,Female,1940-01-01\n2,Male,1950-01-01\n')
        for patient in (1,2,3):
            scan=root/f'sub-{patient:04d}'/'ses-0001'/'statistics'
            for family,body in {
                'SummaryLesions':'Label,Value\ntotal_lesion_volume,4\npercentage_volume_in_Frontal,0.5\nmean_ADC_signal,nan\n',
                'IndividualLesions':'LesionNumber,total_lesion_volume,mean_ADC_signal,percentage_volume_in_Frontal\n1,1,2,0.2\n2,3,6,0.6\n',
                'radiomics':'Label,Value\noriginal_shape_Sphericity,0.7\noriginal_firstorder_Mean,5\ndiagnostics_Image-original_Hash,SECRET_HASH\n',
            }.items():
                target=scan/f'lesions_{family}';target.mkdir(parents=True)
                (target/f'sub-{patient:04d}_ses-0001_FLAIR_{family}.csv').write_text(body)

    def test_unique_patient_rows_and_unobserved_patients_have_no_negative_labels(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            result=self.api()(root,min_class_count=1)
            self.assertEqual(len(result['X']),2)
            self.assertEqual(sorted(result['labels']['MYD88']),[0,1])
            self.assertEqual(len(set(result['case_ids'])),2)
            for secret in ['sub-0001','ses-0001','2000-01-01','1940-01-01','SECRET_HASH','patientdurablekey']:
                self.assertNotIn(secret,json.dumps(result))

    def test_multilesion_features_aggregate_volume_and_weight_intensity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);result=self.api()(root,min_class_count=1)
            values=dict(zip(result['feature_names'],result['X'][0]))
            self.assertEqual(values['FLAIR_individual_sum_total_lesion_volume'],4.0)
            self.assertEqual(values['FLAIR_individual_weighted_mean_ADC_signal'],5.0)
            self.assertEqual(values['FLAIR_individual_largest_mean_ADC_signal'],6.0)
            self.assertIsNone(values['FLAIR_summary_mean_ADC_signal'])
            self.assertNotIn('age_at_scan',values)

    def test_duplicate_scan_mapping_rejected_instead_of_counted_twice(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            source=next(root.rglob('sub-0001*SummaryLesions.csv'))
            target=root/'duplicate'/source.relative_to(root);target.parent.mkdir(parents=True);target.write_bytes(source.read_bytes())
            with self.assertRaises(ValueError):self.api()(root,min_class_count=1)

    def test_leaked_numeric_feature_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            source=root/'sub-0001/ses-0001/statistics/lesions_SummaryLesions/sub-0001_ses-0001_FLAIR_SummaryLesions.csv'
            with source.open('a') as stream:stream.write('PatientID,1234567\n')
            with self.assertRaises(ValueError):self.api()(root,min_class_count=1)

    def test_gene_threshold_uses_patients_and_only_qualifying_reports(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            result=self.api()(root,min_class_count=2)
            self.assertEqual(result['labels'],{})
            self.assertEqual(result['metadata']['gene_catalog']['MYD88']['qualifying_positive'],1)

    def test_invalid_numeric_text_is_not_silently_converted_to_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            source=root/'sub-0001/ses-0001/statistics/lesions_SummaryLesions/sub-0001_ses-0001_FLAIR_SummaryLesions.csv'
            source.write_text(source.read_text().replace('mean_ADC_signal,nan','mean_ADC_signal,SECRET_TEXT'))
            with self.assertRaises(ValueError):self.api()(root,min_class_count=1)


if __name__=='__main__':unittest.main()
