"""Aggregate audit tests: privacy boundaries, unique subjects, and byte identity."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class HostedInventoryTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec("pcnsl.inspect_hosted"),
                             "The hosted-release aggregate inspector must exist")
        from pcnsl.inspect_hosted import inspect_release
        return inspect_release

    def fixture(self, root):
        clinical = root / "csvs_for_amazon_anonymized"
        clinical.mkdir(parents=True)
        (clinical / "demographics.csv").write_text(
            "patientdurablekey,Sex,BirthDate,PatientName\n1,Female,1940-03-29,SECRET_PERSON\n2,Male,1950-04-02,SECRET_OTHER\n")
        (clinical / "ucsf500_mutations.csv").write_text(
            "patientdurablekey,gene,variantclassification,reportedalteration,geneticorigin,tumorcollecteddate\n"
            "1,MYD88,Pathogenic,True,Somatic,2001-02-03\n"
            "1,CD79B,Uncertain Significance,True,Somatic,2001-02-03\n"
            "2,IRF4,Pathogenic,False,SECRET_FREE_TEXT,2002-02-03\n")
        for sub, ses in [("sub-0001", "ses-0001"), ("sub-0001", "ses-0002"), ("sub-0002", "ses-0003")]:
            scan = root / "pyalfe" / sub / ses
            skull = scan / "skullstripped" / "lesions_FLAIR_space"
            skull.mkdir(parents=True)
            (skull / f"{sub}_{ses}_ADC_to_FLAIR_skullstripped.nii.gz").write_bytes(b"not-an-image")
            features = scan / "statistics" / "lesions_SummaryLesions"
            features.mkdir(parents=True)
            (features / f"{sub}_{ses}_FLAIR_SummaryLesions.csv").write_text("Label,Value\nvolume,1.5\n")
            headers = scan / "dicom_headers"
            headers.mkdir()
            (headers / "SECRET_FILENAME.json").write_text(json.dumps({
                "PatientName":"SECRET_PERSON", "PatientID":"SECRET_MRN", "StudyDate":"20010203",
                "00100030":{"vr":"DA","Value":["19400329"]},
                "SeriesDescription":"SECRET_FREE_TEXT"}))

    def test_counts_unique_patients_not_variant_rows_or_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root)
            result=self.api()(root)
            self.assertEqual(result["imaging"]["subjects"],2)
            self.assertEqual(result["imaging"]["sessions"],3)
            self.assertEqual(result["imaging"]["sequence_coverage"]["ADC"]["subjects"],2)
            self.assertEqual(result["genomics"]["subjects_with_records"],2)
            self.assertEqual(result["genomics"]["rows"],3)
            self.assertEqual(result["genomics"]["gene_subject_counts"]["MYD88"]["reported_pathogenic"],1)
            self.assertEqual(result["genomics"]["gene_subject_counts"]["CD79B"]["reported_pathogenic"],0)
            self.assertEqual(result["genomics"]["gene_subject_counts"]["IRF4"]["reported_pathogenic"],0)

    def test_output_excludes_row_values_dates_and_original_filenames(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root)
            result=self.api()(root)
            text=json.dumps(result)
            for secret in ["SECRET_PERSON","SECRET_OTHER","SECRET_MRN","SECRET_FREE_TEXT",
                           "1940-03-29","20010203","19400329","sub-0001","ses-0003","SECRET_FILENAME"]:
                self.assertNotIn(secret,text)
            self.assertEqual(result["json_metadata"]["sensitive_fields"]["PatientName"]["files_nonempty"],3)
            self.assertEqual(result["json_metadata"]["sensitive_fields"]["PatientBirthDate"]["files_nonempty"],3)

    def test_comparison_requires_bytes_not_just_names_or_sizes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"hosted"; box=Path(d)/"box"
            self.fixture(root); box.mkdir()
            (box/"demographics.csv").write_bytes((root/"csvs_for_amazon_anonymized/demographics.csv").read_bytes())
            (box/"ucsf500_mutations.csv").write_text("different content")
            rel="sub-0001/ses-0001/statistics/lesions_SummaryLesions/sub-0001_ses-0001_FLAIR_SummaryLesions.csv"
            feature=box/"features"/rel; feature.parent.mkdir(parents=True)
            feature.write_bytes((root/"pyalfe"/rel).read_bytes())
            result=self.api()(root,box)["box_comparison"]
            self.assertEqual(result["metadata"]["identical"],1)
            self.assertEqual(result["metadata"]["different"],1)
            self.assertEqual(result["features"]["identical"],1)
            self.assertFalse(result["whole_release_equivalence_established"])

    def test_symlinked_external_files_are_not_inspected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"hosted"; root.mkdir()
            outside=Path(d)/"outside.json"; outside.write_text('{"PatientName":"EXTERNAL_SECRET"}')
            (root/"outside.json").symlink_to(outside)
            result=self.api()(root)
            self.assertEqual(result["files"]["symlinks_skipped"],1)
            self.assertEqual(result["json_metadata"]["files_inspected"],0)

    def test_real_data_coverage_intersects_genomics_and_flair_features(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root)
            mutation=root/'csvs_for_amazon_anonymized/ucsf500_mutations.csv'
            with mutation.open('a') as stream:
                stream.write('3,MYD88,Pathogenic,True,Somatic,2003-02-03\n')
            result=self.api()(root)
            self.assertIn('cohort_coverage',result)
            coverage=result['cohort_coverage']
            self.assertEqual(coverage['genomic_and_imaging_subjects'],2)
            self.assertEqual(coverage['genomic_without_imaging_subjects'],1)
            self.assertEqual(coverage['genomic_with_flair_summary_and_one_sample_date'],2)
            self.assertEqual(coverage['flair_summary_one_sample_gene_counts']['MYD88']['reported_pathogenic'],1)

    def test_numeric_feature_coverage_rejects_missing_or_nonfinite_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root)
            regions=['Frontal','Parietal','Occipital','Temporal','AnteriorTemporal',
                     'MiddleTemporal','PosteriorTemporal','Parietal_Occipital',
                     'CorpusCallosum','CorpusCallosum_Rostrum']
            paths=sorted(root.glob('pyalfe/*/*/statistics/lesions_SummaryLesions/*.csv'))
            for path in paths:
                path.write_text('Label,Value\n'+''.join('percentage_volume_in_'+r+',0.1\n' for r in regions))
            paths[-1].write_text(paths[-1].read_text().replace('CorpusCallosum_Rostrum,0.1','CorpusCallosum_Rostrum,nan'))
            result=self.api()(root)
            self.assertIn('spatial_feature_quality',result)
            quality=result['spatial_feature_quality']
            self.assertEqual(quality['flair_summary_files_inspected'],3)
            self.assertEqual(quality['files_with_all_ten_finite_metrics'],2)
            self.assertEqual(result['cohort_coverage']['genomic_with_complete_ten_spatial_features_and_one_sample_date'],1)


class DownloadEnvironmentTests(unittest.TestCase):
    def api(self):
        from scripts import fetch_pcnsl_release
        self.assertTrue(hasattr(fetch_pcnsl_release, 'load_proxy_environment'),
                        'Detached downloads must load an explicit restricted proxy environment')
        return fetch_pcnsl_release

    def test_proxy_file_accepts_only_proxy_keys_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'proxy.json'
            path.write_text(json.dumps({'HTTPS_PROXY':'http://proxy.invalid:3128','NO_PROXY':'localhost'}))
            path.chmod(0o600)
            loaded=self.api().load_proxy_environment(path)
            self.assertEqual(loaded,{'HTTPS_PROXY':'http://proxy.invalid:3128','NO_PROXY':'localhost'})
            path.write_text(json.dumps({'HTTPS_PROXY':'http://proxy.invalid:3128','HOME':'forbidden'}))
            with self.assertRaises(ValueError): self.api().load_proxy_environment(path)
            path.write_text(json.dumps({'HTTPS_PROXY':'http://proxy.invalid:3128'}))
            path.chmod(0o644)
            with self.assertRaises(PermissionError): self.api().load_proxy_environment(path)

    def test_network_diagnostics_never_include_exception_url_or_credentials(self):
        import urllib.error
        api=self.api()
        exc=urllib.error.URLError(OSError(111,'SECRET_URL_AND_CREDENTIALS'))
        info=api.safe_error_details(exc)
        self.assertEqual(info['error_reason_type'],'ConnectionRefusedError')
        self.assertEqual(info['error_errno'],111)
        self.assertNotIn('SECRET',json.dumps(info))


class HostedBaselineInputTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('sklearn'),
                         'Numerical validation runs in the FAC research environment')
    def test_fixed_model_recovers_separable_signal_and_excludes_rare_target(self):
        from pcnsl.hosted_baseline import evaluate_fixed
        matrix=[[float(i)] for i in range(-20,20)]
        labels={'MYD88':[0]*20+[1]*20,'IRF4':[1]+[0]*39}
        result=evaluate_fixed(matrix,labels)
        self.assertEqual(len(result['runs']),6)
        for run in result['runs']:
            self.assertEqual(sum(f['test'] for f in run['fold_sizes']),40)
            if run['baseline']=='spatial_logreg':self.assertGreater(run['pooled_oof_auroc'],0.95)
        self.assertEqual(result['excluded_targets']['IRF4']['positive'],1)
        with self.assertRaises(ValueError):evaluate_fixed([[float('nan')],[0]],{'MYD88':[0,1]})

    def test_baseline_joins_only_genomic_subjects_with_complete_features(self):
        self.assertIsNotNone(importlib.util.find_spec('pcnsl.hosted_baseline'),
                             'A standalone hosted-input baseline loader must exist')
        from pcnsl.hosted_baseline import load_hosted_rows
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            HostedInventoryTests().fixture(root)
            regions=['Frontal','Parietal','Occipital','Temporal','AnteriorTemporal',
                     'MiddleTemporal','PosteriorTemporal','Parietal_Occipital',
                     'CorpusCallosum','CorpusCallosum_Rostrum']
            paths=sorted(root.glob('pyalfe/*/*/statistics/lesions_SummaryLesions/*.csv'))
            # Remove the second session: an ambiguous multi-scan subject must be rejected.
            paths[1].unlink()
            for path in (paths[0],paths[2]):
                path.write_text('Label,Value\n'+''.join('percentage_volume_in_'+r+',0.1\n' for r in regions))
            matrix,labels,summary=load_hosted_rows(root)
            self.assertEqual(len(matrix),2)
            self.assertEqual(labels['MYD88'],[1,0])
            self.assertEqual(labels['CD79B'],[0,0])
            self.assertEqual(summary['eligible_subjects'],2)
            paths[1].write_text(paths[0].read_text())
            with self.assertRaises(ValueError):load_hosted_rows(root)


if __name__=="__main__":
    unittest.main()
