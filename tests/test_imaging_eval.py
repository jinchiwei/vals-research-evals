"""Imaging scorer: pure-array metrics on hand-checked fixtures. No real images.

Needs numpy + scipy, e.g.:
  PYTHONPATH=/tmp/vals-prediction-deps python3.12 -m unittest tests.test_imaging_eval -v
Skipped (not faked) where they are absent; the nibabel loader test also skips without nibabel.
"""
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

HAVE_NUMPY = all(importlib.util.find_spec(m) for m in ('numpy', 'scipy'))
HAVE_NIBABEL = HAVE_NUMPY and importlib.util.find_spec('nibabel') is not None
if HAVE_NUMPY:
    import numpy as np
    from pcnsl import imaging_eval as ie

EYE = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def grid(shape=(6, 6, 6)):
    return np.zeros(shape, dtype=np.int16)


@unittest.skipUnless(HAVE_NUMPY, 'numpy/scipy not available')
class VolumeTests(unittest.TestCase):
    def test_voxel_volume_uses_absolute_determinant_in_ml(self):
        self.assertAlmostEqual(ie.voxel_volume_ml(np.diag([2.0, 2.0, 2.0, 1.0])), 0.008)
        # rotated/permuted axes with a flip: det = -6 mm^3
        sheared = np.array([[0, 3, 0, 5], [2, 0, 0, -1], [0, 0, 1, 7], [0, 0, 0, 1]], dtype=float)
        self.assertAlmostEqual(np.linalg.det(sheared[:3, :3]), -6.0)
        self.assertAlmostEqual(ie.voxel_volume_ml(sheared), 0.006)

    def test_rejects_degenerate_or_nonfinite_affine(self):
        for bad in (np.diag([1.0, 0.0, 1.0, 1.0]), np.full((4, 4), np.nan), np.eye(3)):
            with self.subTest(bad=bad.tolist()), self.assertRaises(ValueError):
                ie.voxel_volume_ml(bad)

    def test_mask_volume(self):
        m = grid(); m[0, 0, 0:5] = 1
        self.assertAlmostEqual(ie.mask_volume_ml(m > 0, np.diag([2.0, 2.0, 2.0, 1.0])), 0.04)


@unittest.skipUnless(HAVE_NUMPY, 'numpy/scipy not available')
class OverlapTests(unittest.TestCase):
    def test_dice_known_fixture(self):
        ref = grid(); ref[0, 0, 0:4] = 1
        sub = grid(); sub[0, 0, 2:6] = 1
        self.assertAlmostEqual(ie.dice(ref > 0, sub > 0), 2 * 2 / 8)

    def test_dice_empty_cases_are_explicit(self):
        empty, one = grid() > 0, grid() > 0
        one[1, 1, 1] = True
        self.assertEqual(ie.dice(empty, empty), 1.0)
        self.assertEqual(ie.dice(one, empty), 0.0)
        self.assertEqual(ie.dice(empty, one), 0.0)

    def test_instance_labels_count_distinct_ids_not_max_label(self):
        m = grid(); m[0, 0, 0] = 1; m[0, 0, 1] = 5; m[3, 3, 3] = 5   # IDs {1, 5}; 5 is non-contiguous
        self.assertEqual(ie.distinct_label_count(m), 2)
        self.assertEqual(ie.components(m > 0)[1], 2)              # {1,5 touching} + {lone 5}
        self.assertEqual(ie.distinct_label_count(grid()), 0)

    def test_components_are_26_connected(self):
        m = grid(); m[0, 0, 0] = 1; m[1, 1, 1] = 1        # corner-touching: one lesion
        self.assertEqual(ie.components(m > 0)[1], 1)
        m[4, 4, 4] = 1                                     # separated by a gap: second lesion
        self.assertEqual(ie.components(m > 0)[1], 2)


@unittest.skipUnless(HAVE_NUMPY, 'numpy/scipy not available')
class DetectionTests(unittest.TestCase):
    def test_overlap_rule_with_merge_and_false_positive(self):
        ref = grid((10, 10, 10))
        ref[0, 0, 0] = 1                 # lesion A
        ref[5, 0, 0] = 1                 # lesion B
        ref[5, 0, 2] = 1                 # lesion C (gap from B)
        sub = grid((10, 10, 10))
        sub[0, 0, 0:2] = 1               # hits A
        sub[5, 0, 0:3] = 1               # one component covering B and C (merge)
        sub[9, 9, 9] = 1                 # false positive
        d = ie.lesion_detection(ref > 0, sub > 0)
        self.assertEqual((d['reference_lesions'], d['submitted_lesions']), (3, 3))
        self.assertEqual((d['detected_reference_lesions'], d['matched_submitted_lesions']), (3, 2))
        self.assertEqual(d['false_positive_lesions'], 1)
        self.assertAlmostEqual(d['lesion_sensitivity'], 1.0)
        self.assertAlmostEqual(d['lesion_precision'], 2 / 3)
        self.assertAlmostEqual(d['lesion_f1'], 2 * 1.0 * (2 / 3) / (1.0 + 2 / 3))
        self.assertEqual(d['count_error'], 0)

    def test_detection_empty_cases(self):
        e, one = grid() > 0, grid() > 0
        one[2, 2, 2] = True
        both = ie.lesion_detection(e, e)
        self.assertEqual((both['lesion_sensitivity'], both['lesion_precision'], both['false_positive_lesions']),
                         (None, None, 0))
        missed = ie.lesion_detection(one, e)
        self.assertEqual((missed['lesion_sensitivity'], missed['lesion_precision'], missed['lesion_f1']),
                         (0.0, None, 0.0))
        spurious = ie.lesion_detection(e, one)
        self.assertEqual((spurious['lesion_sensitivity'], spurious['false_positive_lesions']), (None, 1))


@unittest.skipUnless(HAVE_NUMPY, 'numpy/scipy not available')
class SegmentationScoreTests(unittest.TestCase):
    def setUp(self):
        self.affine = np.diag([1.0, 1.0, 2.0, 1.0])
        self.ref = grid(); self.ref[1:3, 1:3, 1] = 1      # 4 voxels x 2 mm^3
        self.ref[4, 4, 4] = 2                             # second labeled lesion

    def test_full_score(self):
        sub = grid(); sub[1:3, 1:3, 1] = 1
        s = ie.score_segmentation(self.ref, self.affine, sub, self.affine)
        self.assertAlmostEqual(s['dice'], 2 * 4 / 9)
        self.assertAlmostEqual(s['reference_volume_ml'], 0.010)
        self.assertAlmostEqual(s['submitted_volume_ml'], 0.008)
        self.assertAlmostEqual(s['volume_error_ml'], -0.002)
        self.assertAlmostEqual(s['absolute_volume_error_ml'], 0.002)
        self.assertAlmostEqual(s['relative_volume_error'], -0.2)
        self.assertEqual(s['lesion_detection']['detected_reference_lesions'], 1)
        self.assertEqual(s['reference_distinct_labels'], 2)
        self.assertEqual(s['lesion_detection']['reference_lesions'], 2)
        json.dumps(s, allow_nan=False)

    def test_labels_or_binary_submissions_are_equivalent(self):
        a = grid(); a[1:3, 1:3, 1] = 1
        b = grid(); b[1:3, 1:3, 1] = 7
        self.assertEqual(ie.score_segmentation(self.ref, self.affine, a, self.affine),
                         ie.score_segmentation(self.ref, self.affine, b, self.affine))

    def test_rejects_invalid_submissions(self):
        good = grid()
        cases = {
            'shape': (np.zeros((6, 6, 5), np.int16), self.affine),
            'affine': (good, np.diag([1.0, 1.0, 2.5, 1.0])),
            'nan': (np.where(good == 0, np.nan, 0).astype(float), self.affine),
            'negative': (good - 1, self.affine),
            'fractional': (good + 0.5, self.affine),
            '4d': (np.zeros((6, 6, 6, 2), np.int16), self.affine),
        }
        for label, (arr, aff) in cases.items():
            with self.subTest(label), self.assertRaises(ie.SubmissionError):
                ie.score_segmentation(self.ref, self.affine, arr, aff)

    def test_tiny_affine_rounding_is_tolerated(self):
        sub = grid(); sub[1:3, 1:3, 1] = 1
        nudged = self.affine + 1e-6
        nudged[3] = [0, 0, 0, 1]
        self.assertIn('dice', ie.score_segmentation(self.ref, self.affine, sub, nudged))


@unittest.skipUnless(HAVE_NUMPY, 'numpy/scipy not available')
class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.affine = np.diag([2.0, 2.0, 2.0, 1.0])     # 0.008 mL voxels
        self.mask = grid(); self.mask[0, 0, 0:2] = 1; self.mask[3, 3, 3:5] = 1
        self.mask[0, 0, 1] = 2; self.mask[3, 3, 3:5] = 3  # instance IDs {1, 2, 3} on 2 components
        self.adc = np.zeros((6, 6, 6), np.float32)
        self.adc[0, 0, 0:2] = [100, 200]; self.adc[3, 3, 3:5] = [300, 400]
        self.adc[5, 5, 5] = 9999                          # outside the mask: ignored

    def test_reference_measurements_known_values(self):
        m = ie.reference_measurements(self.mask, self.affine, self.adc, self.affine)
        self.assertAlmostEqual(m['total_lesion_volume_ml'], 0.032)
        self.assertEqual(m['component_count_26'], 2)
        self.assertEqual(m['distinct_label_count'], 3)
        self.assertAlmostEqual(m['adc_native_mean'], 250.0)
        self.assertAlmostEqual(m['adc_native_median'], 250.0)
        self.assertAlmostEqual(m['adc_native_p5'], 100 + 0.05 * 3 * 100)   # linear interpolation, n=4

    def test_nonfinite_adc_inside_mask_is_excluded_and_counted(self):
        self.adc[0, 0, 0] = np.nan
        m = ie.reference_measurements(self.mask, self.affine, self.adc, self.affine)
        self.assertAlmostEqual(m['adc_native_mean'], 300.0)
        self.assertEqual(m['adc_voxels_excluded_nonfinite'], 1)

    def test_adc_grid_must_match_mask(self):
        with self.assertRaises(ValueError):
            ie.reference_measurements(self.mask, self.affine, self.adc, np.diag([1.0, 2.0, 2.0, 1.0]))

    def test_answer_grading_tolerances_and_strict_contract(self):
        ref = ie.reference_measurements(self.mask, self.affine, self.adc, self.affine)
        answer = {k: ref[k] for k in ie.MEASUREMENT_FIELDS}
        g = ie.grade_measurements(ref, json.dumps(answer))
        self.assertTrue(g['valid'])
        self.assertEqual(g['fraction_correct'], 1.0)
        close = dict(answer, adc_native_mean=answer['adc_native_mean'] * (1 + 1e-4))
        self.assertTrue(ie.grade_measurements(ref, json.dumps(close))['fields']['adc_native_mean']['correct'])
        off = dict(answer, total_lesion_volume_ml=answer['total_lesion_volume_ml'] * 1.02, component_count_26=3)
        g = ie.grade_measurements(ref, json.dumps(off))
        self.assertFalse(g['fields']['total_lesion_volume_ml']['correct'])
        self.assertFalse(g['fields']['component_count_26']['correct'])
        self.assertAlmostEqual(g['fraction_correct'], 4 / 6)
        self.assertAlmostEqual(g['fields']['total_lesion_volume_ml']['absolute_error'], 0.032 * 0.02)
        invalid = {
            'missing': {k: v for k, v in answer.items() if k != 'adc_native_p5'},
            'extra': dict(answer, note=1),
            'nan': json.dumps(answer).replace(str(answer['adc_native_mean']), 'NaN'),
            'count float': dict(answer, component_count_26=2.0),
            'label count float': dict(answer, distinct_label_count=2.0),
            'string': dict(answer, adc_native_median='250'),
            'not json': 'volume is 0.032 mL',
        }
        for label, bad in invalid.items():
            with self.subTest(label):
                text = bad if isinstance(bad, str) else json.dumps(bad)
                g = ie.grade_measurements(ref, text)
                self.assertFalse(g['valid'])
                self.assertEqual(g['fraction_correct'], 0.0)


@unittest.skipUnless(HAVE_NUMPY, 'numpy/scipy not available')
class VolumeValidationTests(unittest.TestCase):
    def test_validate_volume_requires_3d_mm_and_finite_affine(self):
        arr = np.zeros((4, 4, 4), np.int16)
        ie.validate_volume(arr, np.eye(4), 'mm')
        squeezed, _ = ie.validate_volume(np.zeros((4, 4, 4, 1), np.int16), np.eye(4), 'mm')
        self.assertEqual(squeezed.shape, (4, 4, 4))
        _, scaled = ie.validate_volume(arr, np.eye(4), 'micron')
        self.assertTrue(math.isclose(ie.voxel_volume_ml(scaled), 1e-12, rel_tol=1e-9))  # (1 um)^3
        _, metres = ie.validate_volume(arr, np.diag([0.001, 0.001, 0.002, 1.0]), 'meter')
        self.assertTrue(np.allclose(metres, np.diag([1.0, 1.0, 2.0, 1.0])))
        for label, args in {'unit': (arr, np.eye(4), 'unknown'), 'odd unit': (arr, np.eye(4), 'sec'),
                            '2d': (np.zeros((4, 4)), np.eye(4), 'mm'),
                            'affine': (arr, np.full((4, 4), np.inf), 'mm')}.items():
            with self.subTest(label), self.assertRaises(ValueError):
                ie.validate_volume(*args)
        ie.validate_volume(arr, np.eye(4), 'unknown', allow_unknown_units=True)

    def test_unknown_unit_mask_inherits_mm_from_matching_reference_image(self):
        # Real release case: masks have xyzt_units unknown; the same-space ADC image declares mm.
        mask = np.zeros((4, 4, 4), np.int16); mask[1, 1, 1] = 3
        aff = np.diag([1.0, 1.0, 3.0, 1.0])
        arr, mm, prov = ie.inherit_spatial_units(mask, aff, 'unknown', (4, 4, 4), aff, 'mm')
        self.assertTrue(np.allclose(mm, aff))
        self.assertAlmostEqual(ie.voxel_volume_ml(mm), 0.003)
        self.assertEqual(prov['spatial_unit'], 'mm')
        self.assertEqual(prov['spatial_unit_source'], 'inherited from same-grid reference image')
        self.assertEqual(prov['mask_header_unit'], 'unknown')
        self.assertTrue(prov['grid_match'])

    def test_unit_inheritance_fails_closed(self):
        mask = np.zeros((4, 4, 4), np.int16)
        aff = np.diag([1.0, 1.0, 3.0, 1.0])
        bad = {
            'absent reference': ((None, None, None), 'no same-grid known-unit reference'),
            'reference unknown too': (((4, 4, 4), aff, 'unknown'), 'reference image unit'),
            'shape mismatch': (((4, 4, 5), aff, 'mm'), 'not on the mask grid'),
            'affine mismatch': (((4, 4, 4), np.diag([1.0, 1.0, 2.0, 1.0]), 'mm'), 'not on the mask grid'),
            'unsupported reference unit': (((4, 4, 4), aff, 'sec'), 'reference image unit'),
        }
        for label, ((shape, raff, unit), message) in bad.items():
            with self.subTest(label), self.assertRaisesRegex(ValueError, message):
                ie.inherit_spatial_units(mask, aff, 'unknown', shape, raff, unit)

    def test_known_unit_mask_keeps_own_unit_and_must_agree_with_reference(self):
        mask = np.zeros((4, 4, 4), np.int16)
        aff = np.eye(4)
        _, mm, prov = ie.inherit_spatial_units(mask, aff, 'mm', None, None, None)
        self.assertEqual(prov['spatial_unit_source'], 'mask header')
        _, mm, prov = ie.inherit_spatial_units(mask, aff, 'mm', (4, 4, 4), aff, 'mm')
        self.assertTrue(prov['grid_match'])
        with self.assertRaises(ValueError):          # same raw grid, conflicting declared units
            ie.inherit_spatial_units(mask, aff, 'micron', (4, 4, 4), aff, 'mm')

    @unittest.skipUnless(HAVE_NIBABEL, 'nibabel not installed on this host')
    def test_nibabel_loader_round_trip(self):
        import nibabel as nib
        with tempfile.TemporaryDirectory() as tmp:
            arr = np.zeros((4, 4, 4), np.int16); arr[1, 1, 1] = 1
            img = nib.Nifti1Image(arr, np.diag([2.0, 2.0, 2.0, 1.0]))
            img.header.set_xyzt_units('mm')
            path = Path(tmp) / 'm.nii.gz'
            nib.save(img, path)
            data, affine = ie.load_nifti(path)
            self.assertEqual(int(data.sum()), 1)
            self.assertAlmostEqual(ie.voxel_volume_ml(affine), 0.008)


if __name__ == '__main__':
    unittest.main()
