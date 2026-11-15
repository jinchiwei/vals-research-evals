"""Scorers for quantitative brain-imaging agent tasks (prototype; no hosted execution claimed).

Two task contracts (docs/research/imaging-eval.md):

1. Segmentation: the agent writes a lesion mask on the grid of a given
   reference image; it is scored against a hidden reference mask with Dice,
   volume error in mL, and 26-connected lesion detection.
2. Measurement: given images plus a mask, the agent reports total lesion
   volume (mL), lesion count (26-connected) and ADC statistics within the
   mask, in the ADC image's stored units; graded against the same reference
   functions below with prespecified tolerances.

Pure array functions take numpy arrays and 4x4 voxel-to-world affines in mm.
The NIfTI loader is optional (nibabel). This is a scorer, not a segmentation
method, and it has not been validated on the real release.
"""
import json
import math

import numpy as np
from scipy import ndimage

CONNECTIVITY_26 = np.ones((3, 3, 3), dtype=bool)
AFFINE_RTOL, AFFINE_ATOL = 1e-5, 1e-4          # same tolerance as the release header audit
MEASUREMENT_FIELDS = ('total_lesion_volume_ml', 'component_count_26', 'distinct_label_count',
                      'adc_native_mean', 'adc_native_median', 'adc_native_p5')
COUNT_FIELDS = ('component_count_26', 'distinct_label_count')
SPATIAL_UNIT_TO_MM = {'mm': 1.0, 'meter': 1000.0, 'micron': 0.001}
RELATIVE_TOLERANCE = 1e-3                        # 0.1 % for volume and ADC statistics; count is exact
ABSOLUTE_FLOOR = 1e-9


class SubmissionError(ValueError):
    """The agent's output violates the task contract."""


# ------------------------------------------------------------------ geometry and volume

def voxel_volume_ml(affine):
    """|det| of the affine's 3x3 spatial block (mm^3), converted to mL."""
    a = np.asarray(affine, dtype=float)
    if a.shape != (4, 4) or not np.all(np.isfinite(a)):
        raise ValueError('affine must be a finite 4x4 matrix')
    volume_mm3 = abs(float(np.linalg.det(a[:3, :3])))
    if volume_mm3 <= 1e-12:
        raise ValueError('affine is singular')
    return volume_mm3 / 1000.0


def mask_volume_ml(mask, affine):
    return int(np.count_nonzero(mask)) * voxel_volume_ml(affine)


def same_grid(shape_a, affine_a, shape_b, affine_b):
    return (tuple(shape_a) == tuple(shape_b)
            and np.allclose(np.asarray(affine_a, float), np.asarray(affine_b, float),
                            rtol=AFFINE_RTOL, atol=AFFINE_ATOL))


# ------------------------------------------------------------------ overlap and lesions

def dice(reference, submitted):
    """Binary Dice. Both empty -> 1.0 (agreement); exactly one empty -> 0.0."""
    r, s = np.asarray(reference, bool), np.asarray(submitted, bool)
    total = int(r.sum()) + int(s.sum())
    if total == 0:
        return 1.0
    return 2.0 * int(np.logical_and(r, s).sum()) / total


def distinct_label_count(labels):
    """Number of distinct positive IDs in an instance-label mask (not the max label; contiguity not assumed)."""
    a = np.asarray(labels)
    return int(np.unique(a[a > 0]).size)


def components(mask):
    """(label array, count) of 26-connected components of a binary mask."""
    labels, count = ndimage.label(np.asarray(mask, bool), structure=CONNECTIVITY_26)
    return labels, int(count)


def lesion_detection(reference, submitted):
    """Lesion-level matching by any-voxel overlap between 26-connected components.

    A reference lesion is detected if any submitted voxel overlaps it. A submitted
    component is matched if it overlaps any reference lesion; otherwise it is a
    false positive. Merges and splits are therefore not penalised beyond the count
    error. Sensitivity is undefined (None) with no reference lesions; precision is
    undefined with no submitted lesions.
    """
    r_labels, n_ref = components(reference)
    s_labels, n_sub = components(submitted)
    overlap = np.logical_and(r_labels > 0, s_labels > 0)
    detected = len(np.unique(r_labels[overlap]))
    matched = len(np.unique(s_labels[overlap]))
    sensitivity = detected / n_ref if n_ref else None
    precision = matched / n_sub if n_sub else None
    if sensitivity is None:
        f1 = None
    elif not sensitivity or precision is None or not precision:
        f1 = 0.0
    else:
        f1 = 2 * sensitivity * precision / (sensitivity + precision)
    return {'reference_lesions': n_ref, 'submitted_lesions': n_sub,
            'detected_reference_lesions': detected, 'matched_submitted_lesions': matched,
            'false_positive_lesions': n_sub - matched, 'lesion_sensitivity': sensitivity,
            'lesion_precision': precision, 'lesion_f1': f1, 'count_error': n_sub - n_ref,
            'matching_rule': 'any-voxel overlap of 26-connected components'}


# ------------------------------------------------------------------ segmentation scoring

def _binary_mask(array, what, error=ValueError):
    a = np.asarray(array)
    if a.ndim != 3:
        raise error(f'{what} must be a 3D volume')
    if a.dtype == bool:
        return a
    if not np.issubdtype(a.dtype, np.number):
        raise error(f'{what} must be numeric')
    if not np.all(np.isfinite(a)):
        raise error(f'{what} contains non-finite values')
    if np.any(a < 0) or np.any(a != np.round(a)):
        raise error(f'{what} must hold non-negative integer labels')
    return a > 0


def score_segmentation(reference, reference_affine, submitted, submitted_affine):
    """Metrics for one case. Raises SubmissionError for an invalid submission.

    The released reference keeps instance IDs; its distinct-ID count is reported
    separately from the 26-connected component counts used for detection.
    """
    ref = _binary_mask(reference, 'reference mask')
    ref_ids = distinct_label_count(reference)
    sub = _binary_mask(submitted, 'submitted mask', SubmissionError)
    if not same_grid(ref.shape, reference_affine, sub.shape, submitted_affine):
        raise SubmissionError('submitted mask is not on the reference grid (shape or affine differs)')
    voxel = voxel_volume_ml(reference_affine)
    ref_ml, sub_ml = int(ref.sum()) * voxel, int(sub.sum()) * voxel
    return {'dice': dice(ref, sub), 'reference_volume_ml': ref_ml, 'submitted_volume_ml': sub_ml,
            'volume_error_ml': sub_ml - ref_ml, 'absolute_volume_error_ml': abs(sub_ml - ref_ml),
            'relative_volume_error': (sub_ml - ref_ml) / ref_ml if ref_ml else None,
            'lesion_detection': lesion_detection(ref, sub), 'reference_distinct_labels': ref_ids,
            'voxel_volume_ml': voxel}


# ------------------------------------------------------------------ measurement task

def reference_measurements(mask, mask_affine, adc, adc_affine):
    """Trusted answers: volume (mL), 26-connected component count, distinct label-ID
    count, and image-native ADC mean/median/5th percentile.

    "Image-native" means the voxel values as loaded (after any NIfTI scl_slope /
    scl_inter scaling), with no unit conversion; this does not establish mm^2/s.
    Statistics are over
    mask voxels with finite ADC; the percentile uses linear interpolation
    (numpy 'linear'). Non-finite ADC voxels inside the mask are excluded and counted.
    """
    m = _binary_mask(mask, 'mask')
    a = np.asarray(adc, dtype=float)
    if not same_grid(m.shape, mask_affine, a.shape, adc_affine):
        raise ValueError('ADC image is not on the mask grid')
    values = a[m]
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError('no finite ADC values inside the mask')
    return {'total_lesion_volume_ml': int(m.sum()) * voxel_volume_ml(mask_affine),
            'component_count_26': components(m)[1], 'distinct_label_count': distinct_label_count(mask),
            'adc_native_mean': float(finite.mean()), 'adc_native_median': float(np.median(finite)),
            'adc_native_p5': float(np.percentile(finite, 5, method='linear')),
            'adc_voxels_excluded_nonfinite': int(values.size - finite.size)}


def _parse_answer(text):
    def reject(_):
        raise SubmissionError('non-finite number')
    try:
        answer = json.loads(text, parse_constant=reject)
    except (TypeError, ValueError) as error:
        raise SubmissionError(f'answer is not valid JSON: {type(error).__name__}') from None
    if not isinstance(answer, dict) or set(answer) != set(MEASUREMENT_FIELDS):
        raise SubmissionError('answer must be a JSON object with exactly: ' + ', '.join(MEASUREMENT_FIELDS))
    for key, value in answer.items():
        if key in COUNT_FIELDS:
            if type(value) is not int or value < 0:
                raise SubmissionError(f'{key} must be a non-negative integer')
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise SubmissionError(f'{key} must be a finite number')
    return answer


def grade_measurements(reference, text):
    """Per-field correctness (count exact; others within 0.1 % relative) and absolute errors."""
    try:
        answer = _parse_answer(text)
    except SubmissionError as error:
        return {'valid': False, 'submission_error': str(error), 'fields': None, 'fraction_correct': 0.0}
    fields = {}
    for key in MEASUREMENT_FIELDS:
        truth, value = reference[key], answer[key]
        error = abs(value - truth)
        if key in COUNT_FIELDS:
            correct = value == truth
        else:
            correct = error <= max(RELATIVE_TOLERANCE * abs(truth), ABSOLUTE_FLOOR)
        fields[key] = {'correct': bool(correct), 'absolute_error': float(error)}
    return {'valid': True, 'submission_error': None, 'fields': fields,
            'fraction_correct': sum(f['correct'] for f in fields.values()) / len(fields)}


# ------------------------------------------------------------------ NIfTI loading

def validate_volume(array, affine, spatial_unit, allow_unknown_units=False):
    """Return (3D array, affine in mm). Drops a trailing singleton dimension.

    The NIfTI spatial unit (mm, meter, micron) is converted to mm. 'unknown' is
    rejected unless explicitly allowed, in which case mm is assumed and must be recorded.
    """
    a = np.asarray(array)
    if a.ndim == 4 and a.shape[3] == 1:
        a = a[..., 0]
    if a.ndim != 3:
        raise ValueError('expected a 3D volume')
    if spatial_unit in SPATIAL_UNIT_TO_MM:
        scale = SPATIAL_UNIT_TO_MM[spatial_unit]
    elif allow_unknown_units and spatial_unit == 'unknown':
        scale = 1.0
    else:
        raise ValueError(f'unsupported spatial unit {spatial_unit!r}')
    mm = np.array(affine, dtype=float)
    if mm.shape != (4, 4):
        raise ValueError('affine must be 4x4')
    mm[:3, :] *= scale
    voxel_volume_ml(mm)
    return a, mm


def inherit_spatial_units(array, affine, mask_unit, reference_shape, reference_affine, reference_unit):
    """Return (3D array, affine in mm, provenance) for a mask.

    A mask with a known spatial unit uses its own header. A mask whose unit is
    'unknown' (the released masks) may inherit the unit ONLY from a caller-supplied
    reference image that declares a known unit and has the same shape and raw affine;
    otherwise ValueError. If both declare units, they must agree on that grid.
    """
    has_reference = reference_shape is not None and reference_affine is not None and reference_unit is not None
    grid_match = None
    if has_reference:
        if reference_unit not in SPATIAL_UNIT_TO_MM:
            raise ValueError(f'reference image unit {reference_unit!r} is not a known spatial unit')
        a = np.asarray(array)
        shape = a.shape[:3] if a.ndim == 4 and a.shape[3] == 1 else a.shape
        grid_match = same_grid(shape, affine, reference_shape, reference_affine)
        if not grid_match:
            raise ValueError('reference image is not on the mask grid (shape or affine differs)')
    if mask_unit in SPATIAL_UNIT_TO_MM:
        if has_reference and SPATIAL_UNIT_TO_MM[mask_unit] != SPATIAL_UNIT_TO_MM[reference_unit]:
            raise ValueError('mask and reference declare different spatial units for the same grid')
        unit, source = mask_unit, 'mask header'
    elif mask_unit == 'unknown':
        if not has_reference:
            raise ValueError('mask spatial unit is unknown and no same-grid known-unit reference was supplied')
        unit, source = reference_unit, 'inherited from same-grid reference image'
    else:
        raise ValueError(f'unsupported mask spatial unit {mask_unit!r}')
    data, mm = validate_volume(array, affine, unit)
    provenance = {'spatial_unit': unit, 'spatial_unit_source': source, 'mask_header_unit': mask_unit,
                  'reference_unit': reference_unit if has_reference else None, 'grid_match': grid_match,
                  'grid_tolerance': {'rtol': AFFINE_RTOL, 'atol': AFFINE_ATOL}}
    return data, mm, provenance


def load_mask_with_reference(mask_path, reference_path=None):
    """Load a mask via nibabel, resolving its spatial unit with inherit_spatial_units.

    The reference image's voxel data are not read; only its shape, affine and unit.
    """
    import nibabel as nib
    mask = nib.load(str(mask_path))
    ref = nib.load(str(reference_path)) if reference_path is not None else None
    return inherit_spatial_units(
        np.asanyarray(mask.dataobj), mask.affine, mask.header.get_xyzt_units()[0],
        None if ref is None else ref.shape[:3], None if ref is None else ref.affine,
        None if ref is None else ref.header.get_xyzt_units()[0])


def load_nifti(path, allow_unknown_units=False):
    """(array, affine in mm) via nibabel; header text/extensions are never read or returned.

    Voxel values include NIfTI scl_slope/scl_inter scaling (nibabel dataobj); that
    intensity scaling does not establish physical ADC units.
    """
    import nibabel as nib
    image = nib.load(str(path))
    unit = image.header.get_xyzt_units()[0]
    return validate_volume(np.asanyarray(image.dataobj), image.affine, unit, allow_unknown_units)
