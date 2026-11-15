"""Per-case grader for reg_resect (runs inside the verifier; plugs into suite.core.grading).

Required output in OUTPUT_DIR:
  landmarks_us.csv   id,x,y,z  - for every id in INPUT_DIR/landmarks_mri.csv, the predicted
                     position of that landmark in the ULTRASOUND image, RAS world mm (the same
                     convention as the input CSV and the NIfTI sform; not ITK/LPS).
Optional output:
  displacement_ras.nii.gz   dense displacement field (X,Y,Z,3) or (X,Y,Z,1,3), RAS mm, on any grid;
                     only used to report folding (fraction of voxels with Jacobian determinant <= 0).

Validity (all must hold, else the case is invalid and scores 0):
  - the CSV parses strictly (header id,x,y,z; finite numbers; no duplicate ids);
  - its id set equals the input id set exactly (no missing, no extra landmark);
  - every predicted point lies within FOV_MARGIN_MM of the ultrasound field of view (voxels > 0).
    Every reference landmark was placed inside that field of view, so a point far outside it is
    certainly wrong; this mainly catches a wrong coordinate frame (e.g. ITK LPS written as RAS).
Clinical threshold (per case, fixed from the literature before any agent result):
  mean TRE < 2.0 mm AND mean TRE lower than the initial (unregistered) mean TRE.
  Source: Gerard et al., Front Oncol 2021;10:618837 (citing Prada et al.: navigation accuracy restored
  "to below a critical threshold of 2 mm"); consistent with AAPM TG-132 (mean TRE < 2 mm, via Latifi
  et al. 2018). See docs/research/suite/metrics-review.md section 1(b).
Quality in [0, 1]: exp(-mean TRE / 2 mm)  (1.0 for a perfect answer, 0.37 at 2 mm).
"""
import math

import numpy as np

from suite.core import geometry, metrics

from . import landmarks as lm

REQUIRED_OUTPUTS = ('landmarks_us.csv',)
OPTIONAL_OUTPUTS = ('displacement_ras.nii.gz',)
PRIMARY_METRIC = 'mean_tre_mm'
THRESHOLD_MM = 2.0
QUALITY_SCALE_MM = 2.0
FOV_MARGIN_MM = 10.0
CLINICAL_THRESHOLD = (f'mean target registration error over the expert landmarks < {THRESHOLD_MM} mm and lower '
                      'than the initial (unregistered) mean error (Gerard et al. 2021, Front Oncol 10:618837)')


def _invalid(reason, **extra):
    return {'valid': False, 'acceptable': False, 'quality': 0.0, 'reason': reason, 'metrics': extra}


def us_world_bounds(us_path):
    """Axis-aligned RAS bounding box (min, max) of the ultrasound voxel grid corners, in mm."""
    import nibabel as nib
    img = nib.load(str(us_path))
    shape = np.array(img.shape[:3])
    corners = np.array([[i, j, k] for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5)
                        for k in (-0.5, shape[2] - 0.5)])
    world = corners @ img.affine[:3, :3].T + img.affine[:3, 3]
    return world.min(axis=0), world.max(axis=0)


def distance_to_fov_mm(us_path, points_ras, step=4):
    """Distance (mm) from each RAS point to the ultrasound field of view (voxels > 0).

    The FOV mask is subsampled by `step` per axis, so distances are exact to about step*spacing.
    Points outside the image grid get the distance to the grid plus the in-grid distance bound (inf
    if far). Assumes orthogonal voxel axes (true for RESECT: rotation + isotropic spacing)."""
    import nibabel as nib
    from scipy import ndimage
    img = nib.load(str(us_path))
    fov = np.asanyarray(img.dataobj)[::step, ::step, ::step] > 0
    spacing = np.linalg.norm(img.affine[:3, :3], axis=0) * step
    dist = ndimage.distance_transform_edt(~fov, sampling=spacing)
    ijk = (np.c_[points_ras, np.ones(len(points_ras))] @ np.linalg.inv(img.affine).T)[:, :3] / step
    idx = np.round(ijk).astype(int)
    out = np.full(len(points_ras), np.inf)
    inside = np.all((idx >= 0) & (idx < np.array(fov.shape)), axis=1)
    out[inside] = dist[tuple(idx[inside].T)]
    return out


def folding_fraction(path):
    """Fraction of voxels with non-positive Jacobian for a RAS displacement field NIfTI."""
    import nibabel as nib
    img = nib.load(str(path))
    u = np.asanyarray(img.dataobj, dtype=float)
    if u.ndim == 5 and u.shape[3] == 1:
        u = u[:, :, :, 0, :]
    if u.ndim != 4 or u.shape[3] != 3:
        raise ValueError(f'displacement field must be (X,Y,Z,3), got {u.shape}')
    a = img.affine[:3, :3]
    spacing = np.linalg.norm(a, axis=0)
    direction = a / spacing                      # columns: world direction of each voxel axis
    u_axes = u @ direction                      # world RAS displacement -> components along voxel axes
    return metrics.fraction_nonpositive_jacobian(u_axes, spacing)


def grade_case(output_dir, input_dir, reference_dir):
    in_ids, mri = lm.read_csv(input_dir / 'landmarks_mri.csv')
    ref_ids, ref = lm.read_csv(reference_dir / 'landmarks_us.csv')
    ref_map = dict(zip(ref_ids, ref))
    try:
        raw = geometry.read_regular_file(output_dir / 'landmarks_us.csv', lm.MAX_CSV_BYTES)
    except geometry.GeometryError as error:
        return _invalid(f'landmarks_us.csv {error.code}: {error.detail}')
    try:
        ids, pred = lm.parse_csv(raw)
    except (ValueError, UnicodeDecodeError) as error:
        return _invalid(f'landmarks_us.csv format: {error}')
    missing, extra = sorted(set(in_ids) - set(ids)), sorted(set(ids) - set(in_ids))
    if missing or extra:
        return _invalid(f'landmark ids do not match the input: missing {missing[:5]}, extra {extra[:5]}',
                        n_missing=len(missing), n_extra=len(extra))
    pred_map = dict(zip(ids, pred))
    pred = np.array([pred_map[i] for i in in_ids])
    fixed = np.array([ref_map[i] for i in in_ids])
    us_path = input_dir / 'us.nii.gz'
    outside = distance_to_fov_mm(us_path, pred) > FOV_MARGIN_MM
    if outside.any():
        flipped_ok = not np.any(distance_to_fov_mm(us_path, pred * lm.RAS_TO_LPS) > FOV_MARGIN_MM)
        hint = ' (the LPS-flipped points would lie inside: coordinates look like ITK/LPS, expected RAS)' \
            if flipped_ok else ''
        return _invalid(f'{int(outside.sum())} of {len(pred)} predicted points lie more than {FOV_MARGIN_MM:.0f} mm '
                        f'outside the ultrasound field of view{hint}', n_outside=int(outside.sum()))
    imp = metrics.registration_improvement(fixed, mri, pred, threshold_mm=THRESHOLD_MM)
    mean_tre = imp['final']['mean_mm']
    m = {'mean_tre_mm': mean_tre, 'median_tre_mm': imp['final']['median_mm'], 'max_tre_mm': imp['final']['max_mm'],
         'initial_mean_tre_mm': imp['initial']['mean_mm'], 'tre_ratio_final_over_initial': imp['mean_ratio'],
         'improvement_mm': imp['initial']['mean_mm'] - mean_tre, 'improved': imp['improved'],
         'fraction_landmarks_under_2mm': imp['final']['fraction_under_threshold'],
         'per_landmark_tre_mm': imp['final']['per_landmark_mm'], 'n_landmarks': imp['final']['n_landmarks']}
    disp = output_dir / 'displacement_ras.nii.gz'
    if disp.is_file() and not disp.is_symlink():
        try:
            m['folding_fraction'] = folding_fraction(disp)
        except Exception as error:               # report-only; never invalidates the case
            m['folding_error'] = f'{type(error).__name__}: {str(error)[:120]}'
    problems = []
    if not mean_tre < THRESHOLD_MM:
        problems.append(f'mean TRE {mean_tre:.2f} mm >= {THRESHOLD_MM} mm')
    if not imp['improved']:
        problems.append(f"no improvement over initial {imp['initial']['mean_mm']:.2f} mm")
    quality = metrics.distance_score(mean_tre, QUALITY_SCALE_MM)
    if not math.isfinite(quality):
        quality = 0.0
    return {'valid': True, 'acceptable': not problems, 'quality': quality,
            'reason': '; '.join(problems) or None, 'metrics': m}
