"""Per-case grader for the toy family (runs inside the verifier from tests/lib).

Outputs required in OUTPUT_DIR:
  mask.nii.gz        binary mask on the input image grid (same shape and affine)
  measurements.json  {"volume_ml": <finite number>}  sphere volume in millilitres

Validity: both files are regular files; the mask passes geometry.load_mask_on_grid; the JSON
is an object with exactly the key volume_ml holding a finite number.
Clinical threshold (per case): Dice >= 0.90 and reported volume within 10 % of reference.
Quality (suite segmentation headline, metrics-review section 3): mean of Dice and NSD at 1 mm.
"""
import json
import math

from suite.core import geometry, metrics

REQUIRED_OUTPUTS = ('mask.nii.gz', 'measurements.json')
PRIMARY_METRIC = 'mean of Dice and NSD at 1 mm (metrics.segmentation_headline)'
DICE_MIN = 0.90
VOLUME_REL_TOL = 0.10
NSD_TOLERANCE_MM = 1.0
CLINICAL_THRESHOLD = (f'Dice >= {DICE_MIN:.2f} against the reference mask and reported volume_ml within '
                      f'{VOLUME_REL_TOL:.0%} of the reference volume')


def _invalid(reason, **extra):
    return {'valid': False, 'acceptable': False, 'quality': 0.0, 'reason': reason, 'metrics': extra}


def parse_measurements(raw):
    def reject(_):
        raise ValueError('non-finite number')

    def unique(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate key')
        return dict(pairs)
    data = json.loads(raw.decode('utf-8'), parse_constant=reject, object_pairs_hook=unique)
    if not isinstance(data, dict) or set(data) != {'volume_ml'}:
        raise ValueError('measurements.json must be an object with exactly the key volume_ml')
    v = data['volume_ml']
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError('volume_ml must be a finite number')
    return {'volume_ml': float(v)}


def grade_case(output_dir, input_dir, reference_dir):
    grid = geometry.load_reference_grid(input_dir / 'image.nii.gz')
    ref_mask, _ = geometry.load_volume(reference_dir / 'mask.nii.gz')
    ref_volume = json.loads((reference_dir / 'measurements.json').read_text())['volume_ml']
    try:
        mask, _, provenance = geometry.load_mask_on_grid(output_dir / 'mask.nii.gz', grid)
    except geometry.GeometryError as error:
        return _invalid(f'mask {error.code}: {error.detail}', reference_grid=grid.describe())
    try:
        reported = parse_measurements(geometry.read_regular_file(output_dir / 'measurements.json', 1_000_000))
    except geometry.GeometryError as error:
        return _invalid(f'measurements {error.code}: {error.detail}')
    except (ValueError, UnicodeDecodeError) as error:
        return _invalid(f'measurements format: {error}')
    spacing = grid.spacing
    ref = ref_mask > 0
    m = {'dice': metrics.dice(ref, mask),
         'nsd_at_1mm': metrics.normalized_surface_distance(ref, mask, spacing, NSD_TOLERANCE_MM),
         'headline': metrics.segmentation_headline(ref, mask, spacing, NSD_TOLERANCE_MM),
         'hd95_mm': metrics.hd95(ref, mask, spacing),
         'mask_volume': metrics.volume_errors(ref, mask, spacing),
         'lesion_detection': metrics.lesion_detection(ref, mask),
         'reported': metrics.measurement_errors(reported, {'volume_ml': ref_volume}, {'volume_ml': 'mL'},
                                                {'volume_ml': {'rel': VOLUME_REL_TOL}}),
         'spatial_units': provenance}
    problems = []
    if m['dice'] < DICE_MIN:
        problems.append(f"Dice {m['dice']:.3f} < {DICE_MIN}")
    vol = m['reported']['volume_ml']
    if not vol['within_tolerance']:
        problems.append(f"reported volume {vol['predicted']:.4g} mL vs reference {vol['reference']:.4g} mL "
                        f"({vol['percent_error']:+.1f}%)")
    return {'valid': True, 'acceptable': not problems, 'quality': m['headline'],
            'reason': '; '.join(problems) or None, 'metrics': m}
