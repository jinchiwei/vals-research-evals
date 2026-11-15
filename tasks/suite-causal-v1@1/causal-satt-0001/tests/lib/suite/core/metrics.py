"""Metric library for the healthcare suite. Pure numpy/scipy; no heavy dependencies.

Conventions used everywhere in this module:
- Masks are 3D arrays; any non-zero voxel is foreground. Spacing is a length-3 sequence in mm,
  one entry per array axis (use geometry.spacing_mm(affine) to get it from a NIfTI affine).
- Distances are Euclidean in mm between voxel centres. For an oblique but orthogonal affine
  this is exact; for a sheared affine it is an approximation (the grader should reject shears).
- Volumes are reported in mL (1 mL = 1000 mm^3).
- Labels for classification are 0/1; probabilities are finite numbers in [0, 1].
- A metric that is mathematically undefined for the inputs returns None (or math.inf for a
  distance to an empty set), never a silent 0. Each docstring states the edge cases.
- Bad input (wrong shapes, non-finite values) raises ValueError.

Reuse: Dice, volume and lesion matching come from pcnsl/imaging_eval.py; AUROC, average
precision and Brier come from pcnsl/prediction_eval.py. This module adds thin array adapters.
"""
import math

import numpy as np
from scipy import ndimage

from pcnsl import imaging_eval as _ie
from pcnsl import prediction_eval as _pe

# ====================================================================== helpers


def _as_mask(a, name):
    a = np.asarray(a)
    if a.ndim != 3:
        raise ValueError(f'{name} must be a 3D array, got {a.ndim}D')
    if a.dtype != bool:
        if not np.issubdtype(a.dtype, np.number) or not np.all(np.isfinite(a)):
            raise ValueError(f'{name} must be numeric and finite')
        a = a != 0
    return a


def _pair(reference, prediction):
    r, p = _as_mask(reference, 'reference'), _as_mask(prediction, 'prediction')
    if r.shape != p.shape:
        raise ValueError(f'shape mismatch {r.shape} vs {p.shape}')
    return r, p


def _spacing(spacing):
    s = np.asarray(spacing, dtype=float)
    if s.shape != (3,) or not np.all(np.isfinite(s)) or np.any(s <= 0):
        raise ValueError('spacing must be three positive finite numbers (mm)')
    return s


# ====================================================================== segmentation


def dice(reference, prediction):
    """Dice = 2|R∩P| / (|R|+|P|). Both empty -> 1.0 (agreement on absence); exactly one empty -> 0.0.

    Delegates to pcnsl.imaging_eval.dice.
    """
    r, p = _pair(reference, prediction)
    return float(_ie.dice(r, p))


def volume_ml(mask, spacing):
    """Foreground voxel count × voxel volume (product of spacing, mm^3) / 1000."""
    return int(np.count_nonzero(_as_mask(mask, 'mask'))) * float(np.prod(_spacing(spacing))) / 1000.0


def volume_errors(reference, prediction, spacing):
    """Volumes in mL and their errors (prediction minus reference).

    relative_volume_error = (P - R) / R; None when the reference is empty (undefined).
    """
    r, p = _pair(reference, prediction)
    rv, pv = volume_ml(r, spacing), volume_ml(p, spacing)
    return {'reference_volume_ml': rv, 'predicted_volume_ml': pv,
            'volume_error_ml': pv - rv, 'absolute_volume_error_ml': abs(pv - rv),
            'relative_volume_error': (pv - rv) / rv if rv > 0 else None,
            'absolute_relative_volume_error': abs(pv - rv) / rv if rv > 0 else None}


def surface_voxels(mask):
    """Border voxels: foreground voxels with at least one 6-connected (face) neighbour that is
    background. Voxels on the array edge count as border (the volume is padded with background)."""
    m = _as_mask(mask, 'mask')
    padded = np.pad(m, 1, constant_values=False)
    eroded = ndimage.binary_erosion(padded, structure=ndimage.generate_binary_structure(3, 1))
    return (padded & ~eroded)[1:-1, 1:-1, 1:-1]


def _directed_surface_distances(from_border, to_border, spacing):
    """Distance (mm) from each border voxel of one mask to the nearest border voxel of the other."""
    if not to_border.any():
        return np.full(int(from_border.sum()), np.inf)
    dt = ndimage.distance_transform_edt(~to_border, sampling=spacing)
    return dt[from_border]


def surface_distances(reference, prediction, spacing):
    """(d_ref_to_pred, d_pred_to_ref): arrays of border-to-border distances in mm."""
    r, p = _pair(reference, prediction)
    s = _spacing(spacing)
    br, bp = surface_voxels(r), surface_voxels(p)
    return _directed_surface_distances(br, bp, s), _directed_surface_distances(bp, br, s)


def hausdorff_distance(reference, prediction, spacing, percentile=100.0):
    """Symmetric (percentile) Hausdorff distance in mm between mask borders.

    Definition (MONAI convention): max(Pq(d(R->P)), Pq(d(P->R))) where d are the directed
    border-to-border distances and Pq is numpy's linear-interpolated q-th percentile.
    percentile=100 gives the classical Hausdorff distance; 95 gives HD95.
    Edge cases: both masks empty -> 0.0; exactly one empty -> math.inf (undefined; a quality
    mapping must treat it as worst). Returned in mm.
    """
    r, p = _pair(reference, prediction)
    if not r.any() and not p.any():
        return 0.0
    if not r.any() or not p.any():
        return math.inf
    d_rp, d_pr = surface_distances(r, p, spacing)
    return float(max(np.percentile(d_rp, percentile), np.percentile(d_pr, percentile)))


def hd95(reference, prediction, spacing):
    """95th-percentile Hausdorff distance in mm; see hausdorff_distance for definition and edge cases."""
    return hausdorff_distance(reference, prediction, spacing, 95.0)


def normalized_surface_distance(reference, prediction, spacing, tolerance_mm):
    """Normalized surface distance (surface Dice) at a tolerance in mm, in [0, 1].

    NSD = (#{border(R) within tol of border(P)} + #{border(P) within tol of border(R)})
          / (#border(R) + #border(P)).
    Border elements are counted as voxels, not surfel areas (a voxel approximation of
    Nikolov et al. 2021); "within" means distance <= tolerance_mm.
    Edge cases: both empty -> 1.0; exactly one empty -> 0.0.
    """
    if tolerance_mm < 0 or not math.isfinite(tolerance_mm):
        raise ValueError('tolerance_mm must be finite and >= 0')
    r, p = _pair(reference, prediction)
    if not r.any() and not p.any():
        return 1.0
    if not r.any() or not p.any():
        return 0.0
    d_rp, d_pr = surface_distances(r, p, spacing)
    return float((np.sum(d_rp <= tolerance_mm) + np.sum(d_pr <= tolerance_mm)) / (d_rp.size + d_pr.size))


LESION_MATCHING_RULE = ('26-connected components; components smaller than min_lesion_voxels are removed from '
                        'both masks first; a reference lesion is detected if any predicted voxel overlaps it; a '
                        'predicted component overlapping no reference lesion is a false positive')


def remove_small_components(mask, min_voxels):
    """Drop 26-connected components with fewer than min_voxels voxels (min_voxels <= 1: no-op)."""
    m = _as_mask(mask, 'mask')
    if min_voxels <= 1:
        return m
    labels, n = _ie.components(m)
    if n == 0:
        return m
    sizes = np.bincount(labels.ravel())
    keep = sizes >= min_voxels
    keep[0] = False
    return keep[labels]


def lesion_detection(reference, prediction, min_lesion_voxels=1):
    """Lesion-wise detection for one case (matching rule: LESION_MATCHING_RULE).

    Delegates matching to pcnsl.imaging_eval.lesion_detection after removing components below
    the declared minimum size. Returns counts, sensitivity (None when the reference has no
    lesions), precision (None when the prediction has none), F1 (None when the reference has
    no lesions; 0 when nothing is detected) and false_positives. Merges and splits are not
    penalised beyond the component counts.
    """
    r, p = _pair(reference, prediction)
    r, p = remove_small_components(r, min_lesion_voxels), remove_small_components(p, min_lesion_voxels)
    out = _ie.lesion_detection(r, p)
    return {'reference_lesions': out['reference_lesions'], 'predicted_lesions': out['submitted_lesions'],
            'detected_reference_lesions': out['detected_reference_lesions'],
            'false_positives': out['false_positive_lesions'], 'sensitivity': out['lesion_sensitivity'],
            'precision': out['lesion_precision'], 'f1': out['lesion_f1'],
            'min_lesion_voxels': int(min_lesion_voxels), 'matching_rule': LESION_MATCHING_RULE}


def lesion_wise_dice(reference, prediction, min_lesion_voxels=1):
    """Mean per-lesion Dice with 0 for missed and spurious lesions (BraTS/autoPET style).

    For each reference lesion L: Dice(L, union of predicted components overlapping L)
    (0 if missed). Each predicted component overlapping no reference lesion adds a 0.
    Result = mean over (reference lesions + false-positive components).
    Edge cases: no reference lesions and no predicted lesions -> 1.0 (declared empty-reference
    rule: correct absence); no reference lesions but some predicted -> 0.0.
    """
    r, p = _pair(reference, prediction)
    r, p = remove_small_components(r, min_lesion_voxels), remove_small_components(p, min_lesion_voxels)
    rl, nr = _ie.components(r)
    pl, npred = _ie.components(p)
    if nr == 0:
        return 1.0 if npred == 0 else 0.0
    scores = []
    matched_pred = set()
    for i in range(1, nr + 1):
        lesion = rl == i
        hits = np.unique(pl[lesion & (pl > 0)])
        matched_pred.update(int(h) for h in hits)
        scores.append(float(_ie.dice(lesion, np.isin(pl, hits))) if hits.size else 0.0)
    scores += [0.0] * (npred - len(matched_pred))
    return float(np.mean(scores))


def segmentation_headline(reference, prediction, spacing, tolerance_mm):
    """Suite headline for organ/structure segmentation (metrics-review section 3):
    mean of Dice and NSD at tolerance_mm for one case, in [0, 1]. Average over cases outside."""
    return 0.5 * (dice(reference, prediction)
                  + normalized_surface_distance(reference, prediction, spacing, tolerance_mm))


def lesion_detection_summary(per_case):
    """Pool lesion_detection results over cases.

    sensitivity = total detected / total reference lesions (None if there are none);
    false_positives_per_case = mean false positives over all cases (cases without
    reference lesions included, which is where false positives matter most).
    """
    if not per_case:
        raise ValueError('need at least one case')
    ref = sum(c['reference_lesions'] for c in per_case)
    det = sum(c['detected_reference_lesions'] for c in per_case)
    return {'sensitivity': det / ref if ref else None,
            'false_positives_per_case': sum(c['false_positives'] for c in per_case) / len(per_case),
            'cases': len(per_case), 'reference_lesions': ref, 'matching_rule': LESION_MATCHING_RULE}


def distance_score(distance_mm, scale_mm):
    """Map a distance to (0, 1], higher better: exp(-d/scale). inf/None -> 0.0; 0 -> 1.0."""
    if scale_mm <= 0:
        raise ValueError('scale_mm must be positive')
    if distance_mm is None or not math.isfinite(distance_mm):
        return 0.0
    if distance_mm < 0:
        raise ValueError('distance must be >= 0')
    return float(math.exp(-distance_mm / scale_mm))


# ====================================================================== registration


def _points(a, name):
    a = np.asarray(a, dtype=float)
    if a.ndim != 2 or a.shape[1] != 3 or a.shape[0] == 0:
        raise ValueError(f'{name} must be an (N, 3) array of landmarks in mm with N >= 1')
    if not np.all(np.isfinite(a)):
        raise ValueError(f'{name} contains non-finite coordinates')
    return a


def target_registration_error(fixed_mm, mapped_mm, threshold_mm=None):
    """TRE between corresponding landmark pairs, in mm.

    fixed_mm[i] and mapped_mm[i] are the same anatomical landmark (fixed image landmark and
    the moving landmark after the submitted transform), both in world mm. Per-landmark error
    is the Euclidean distance. Returns mean, median, max and per-landmark errors, plus
    fraction_under_threshold = fraction with error <= threshold_mm when a threshold is given.
    """
    f, m = _points(fixed_mm, 'fixed_mm'), _points(mapped_mm, 'mapped_mm')
    if f.shape != m.shape:
        raise ValueError('landmark arrays must have the same shape')
    e = np.linalg.norm(f - m, axis=1)
    out = {'n_landmarks': int(e.size), 'mean_mm': float(e.mean()), 'median_mm': float(np.median(e)),
           'max_mm': float(e.max()), 'per_landmark_mm': [float(x) for x in e]}
    if threshold_mm is not None:
        out['threshold_mm'] = float(threshold_mm)
        out['fraction_under_threshold'] = float(np.mean(e <= threshold_mm))
    return out


def registration_improvement(fixed_mm, moving_initial_mm, moving_final_mm, threshold_mm=None):
    """Initial-versus-final TRE. initial = no transform applied; final = after registration.

    mean_ratio = final mean / initial mean (None if the initial mean is 0); improved is
    True when the final mean TRE is strictly lower than the initial mean TRE.
    """
    initial = target_registration_error(fixed_mm, moving_initial_mm, threshold_mm)
    final = target_registration_error(fixed_mm, moving_final_mm, threshold_mm)
    return {'initial': initial, 'final': final,
            'mean_ratio': final['mean_mm'] / initial['mean_mm'] if initial['mean_mm'] > 0 else None,
            'improved': final['mean_mm'] < initial['mean_mm']}


def jacobian_determinant(displacement_mm, spacing):
    """Jacobian determinant of x -> x + u(x) for a dense displacement field.

    displacement_mm: array (X, Y, Z, 3); component k is the displacement in mm along array
    axis k (the field must be expressed in the voxel-axis frame, as ITK/ANTs fields are after
    resampling to the reference direction). Derivatives use numpy.gradient (central
    differences inside, one-sided at the edges) with the voxel spacing in mm.
    """
    u = np.asarray(displacement_mm, dtype=float)
    if u.ndim != 4 or u.shape[3] != 3 or min(u.shape[:3]) < 2:
        raise ValueError('displacement field must be (X, Y, Z, 3) with every spatial size >= 2')
    if not np.all(np.isfinite(u)):
        raise ValueError('displacement field contains non-finite values')
    s = _spacing(spacing)
    jac = np.empty(u.shape[:3] + (3, 3))
    for k in range(3):
        grads = np.gradient(u[..., k], *s)
        for j in range(3):
            jac[..., k, j] = grads[j] + (1.0 if j == k else 0.0)
    return np.linalg.det(jac)


def fraction_nonpositive_jacobian(displacement_mm, spacing, mask=None):
    """Fraction of voxels (inside mask if given) with Jacobian determinant <= 0 (folding).

    A mask with no voxels raises ValueError (the fraction would be undefined).
    """
    det = jacobian_determinant(displacement_mm, spacing)
    if mask is not None:
        m = _as_mask(mask, 'mask')
        if m.shape != det.shape:
            raise ValueError('mask shape does not match the field')
        if not m.any():
            raise ValueError('mask is empty')
        det = det[m]
    return float(np.mean(det <= 0))


# ====================================================================== classification and risk


def _labels_probs(y, p):
    y = np.asarray(y)
    p = np.asarray(p, dtype=float)
    if y.ndim != 1 or p.ndim != 1 or y.size != p.size or y.size == 0:
        raise ValueError('y and p must be non-empty 1D arrays of equal length')
    if not np.all(np.isin(y, (0, 1))):
        raise ValueError('labels must be 0 or 1')
    if not np.all(np.isfinite(p)) or np.any(p < 0) or np.any(p > 1):
        raise ValueError('probabilities must be finite and in [0, 1]')
    return y.astype(int), p


def auroc(y, p):
    """Area under the ROC curve; ties count one half; direction never flipped.

    Raises ValueError when only one class is present (undefined). Delegates to prediction_eval.
    """
    y, p = _labels_probs(y, p)
    return float(_pe.auroc(y.tolist(), p.tolist()))


def average_precision(y, p):
    """Step-wise average precision over distinct thresholds (scikit-learn's definition).

    Raises ValueError with no positive case. Delegates to prediction_eval.
    """
    y, p = _labels_probs(y, p)
    return float(_pe.average_precision(y.tolist(), p.tolist()))


def brier(y, p):
    """Mean squared difference between probability and 0/1 outcome (lower is better)."""
    y, p = _labels_probs(y, p)
    return float(_pe.brier(y.tolist(), p.tolist()))


def expected_calibration_error(y, p, n_bins=10):
    """ECE with equal-width bins on [0, 1]: sum_b (n_b/n) |mean(p in b) - mean(y in b)|.

    Bin b covers [b/B, (b+1)/B), except the last bin, which also includes 1.0. Empty bins
    contribute nothing. Bin-count sensitive and biased upward in small samples; report n.
    """
    y, p = _labels_probs(y, p)
    if n_bins < 1:
        raise ValueError('n_bins must be >= 1')
    idx = np.minimum((p * n_bins).astype(int), n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        sel = idx == b
        if sel.any():
            ece += sel.mean() * abs(p[sel].mean() - y[sel].mean())
    return float(ece)


def _logit(p, eps):
    q = np.clip(p, eps, 1 - eps)
    return np.log(q / (1 - q))


def _fit_logistic(x, y, offset=None, max_iter=100, tol=1e-10):
    """Unpenalised logistic regression by Newton-Raphson. x: (n, k) design incl. intercept column.

    Returns coefficients, or None if it does not converge (e.g. perfect separation).
    """
    beta = np.zeros(x.shape[1])
    off = np.zeros(len(y)) if offset is None else offset
    for _ in range(max_iter):
        eta = x @ beta + off
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = mu * (1 - mu)
        hess = x.T @ (x * w[:, None])
        try:
            step = np.linalg.solve(hess, x.T @ (y - mu))
        except np.linalg.LinAlgError:
            return None
        beta = beta + step
        if not np.all(np.isfinite(beta)) or np.max(np.abs(beta)) > 1e6:
            return None
        if np.max(np.abs(step)) < tol:
            return beta
    return None


def calibration_slope_intercept(y, p, eps=1e-6):
    """Logistic recalibration: fit logit P(y=1) = a + b * logit(p).

    Returns slope b (ideal 1; < 1 means over-confident predictions), intercept a (ideal 0) from
    that joint fit, and calibration_in_the_large = a' from the fit with b fixed at 1
    (logit(p) as an offset; ideal 0, > 0 means risks are under-estimated on average).
    p is clipped to [eps, 1-eps] before the logit. Values are None when the fit does not
    converge (perfect separation) or when only one class is present.
    """
    y, p = _labels_probs(y, p)
    out = {'slope': None, 'intercept': None, 'calibration_in_the_large': None, 'n': int(y.size)}
    if y.min() == y.max():
        return out
    lp = _logit(p, eps)
    ones = np.ones_like(lp)
    joint = _fit_logistic(np.column_stack([ones, lp]), y.astype(float))
    if joint is not None:
        out['intercept'], out['slope'] = float(joint[0]), float(joint[1])
    citl = _fit_logistic(ones[:, None], y.astype(float), offset=lp)
    if citl is not None:
        out['calibration_in_the_large'] = float(citl[0])
    return out


def _operating_points(y, p):
    """(threshold, sensitivity, specificity) for rule 'positive if p >= t' at every distinct score
    plus t = +inf (all negative). Ties are never split."""
    pos, neg = int(y.sum()), int((1 - y).sum())
    if not pos or not neg:
        raise ValueError('need both classes')
    pts = [(math.inf, 0.0, 1.0)]
    for t in np.unique(p)[::-1]:
        called = p >= t
        pts.append((float(t), float((called & (y == 1)).sum() / pos), float((~called & (y == 0)).sum() / neg)))
    return pts


def sensitivity_at_specificity(y, p, specificity):
    """Highest sensitivity among empirical operating points with specificity >= target.

    Rule 'positive if p >= threshold'; no ROC interpolation; ties are kept together.
    Returns {'sensitivity', 'specificity', 'threshold'} for the chosen point (threshold inf
    means 'call nobody positive'). Raises ValueError with one class.
    """
    y, p = _labels_probs(y, p)
    ok = [pt for pt in _operating_points(y, p) if pt[2] >= specificity - 1e-12]
    t, se, sp = max(ok, key=lambda pt: (pt[1], pt[2]))
    return {'sensitivity': se, 'specificity': sp, 'threshold': t}


def specificity_at_sensitivity(y, p, sensitivity):
    """Highest specificity among empirical operating points with sensitivity >= target (as above).

    The lowest distinct score as threshold calls everyone positive (sensitivity 1), so a
    point always exists for targets <= 1.
    """
    y, p = _labels_probs(y, p)
    ok = [pt for pt in _operating_points(y, p) if pt[1] >= sensitivity - 1e-12]
    t, se, sp = max(ok, key=lambda pt: (pt[2], pt[1]))
    return {'sensitivity': se, 'specificity': sp, 'threshold': t}


def net_benefit(y, p, threshold):
    """Decision-curve net benefit at threshold probability pt (Vickers & Elkin 2006).

    NB = TP/n - FP/n * pt / (1 - pt), treating 'p >= pt' as positive. Also returns the
    treat-all and treat-none (0) references. pt must be in (0, 1).
    """
    y, p = _labels_probs(y, p)
    if not 0 < threshold < 1:
        raise ValueError('threshold must be in (0, 1)')
    n = y.size
    called = p >= threshold
    w = threshold / (1 - threshold)
    tp = int((called & (y == 1)).sum())
    fp = int((called & (y == 0)).sum())
    prevalence = y.mean()
    return {'net_benefit': tp / n - fp / n * w, 'treat_all': float(prevalence - (1 - prevalence) * w),
            'treat_none': 0.0, 'threshold': float(threshold)}


def net_benefit_curve(y, p, thresholds):
    """net_benefit() at each threshold in a declared range, plus the mean over the range
    (a simple area-under-the-decision-curve summary; same sign conventions)."""
    rows = [net_benefit(y, p, t) for t in thresholds]
    if not rows:
        raise ValueError('need at least one threshold')
    return {'points': rows, 'mean_net_benefit': float(np.mean([r['net_benefit'] for r in rows])),
            'mean_treat_all': float(np.mean([r['treat_all'] for r in rows]))}


def subgroup_breakdown(metric, y, p, groups, higher_is_better=True, min_n=1):
    """Apply metric(y, p) within each subgroup and report the worst-group gap.

    A group's value is None (excluded from worst/gap) when it has fewer than min_n cases or
    the metric is undefined there (raises ValueError, e.g. AUROC with one class).
    worst_group_gap = best - worst over defined groups (>= 0, in the metric's units);
    None with fewer than two defined groups.
    """
    y = np.asarray(y)
    p = np.asarray(p, dtype=float)
    g = np.asarray(groups)
    if not (y.shape == p.shape == g.shape) or y.ndim != 1:
        raise ValueError('y, p and groups must be 1D arrays of equal length')
    per = {}
    for name in sorted(set(g.tolist()), key=str):
        sel = g == name
        value = None
        if sel.sum() >= min_n:
            try:
                value = float(metric(y[sel], p[sel]))
            except ValueError:
                value = None
        per[str(name)] = {'n': int(sel.sum()), 'value': value}
    defined = {k: v['value'] for k, v in per.items() if v['value'] is not None}
    if not defined:
        return {'groups': per, 'worst_group': None, 'worst_value': None, 'worst_group_gap': None}
    pick = min if higher_is_better else max
    worst = pick(defined, key=defined.get)
    gap = max(defined.values()) - min(defined.values()) if len(defined) > 1 else None
    return {'groups': per, 'worst_group': worst, 'worst_value': defined[worst], 'worst_group_gap': gap}


# ====================================================================== measurement


def measurement_errors(predicted, reference, units, tolerances):
    """Per-quantity error for a measurement table.

    predicted, reference: {quantity: number}; units: {quantity: unit string}, recorded only
    (all values must already be in that unit); tolerances: {quantity: {'abs': a, 'rel': r}}
    with either key optional. A value agrees when |pred - ref| <= max(abs, rel * |ref|).
    percent_error = 100 * (pred - ref) / |ref|, None when ref == 0.
    A missing or non-finite predicted value gives error None and within_tolerance False.
    """
    out = {}
    for q, ref in reference.items():
        ref = float(ref)
        if not math.isfinite(ref):
            raise ValueError(f'reference {q} is not finite')
        tol = tolerances.get(q, {})
        allowed = max(float(tol.get('abs', 0.0)), float(tol.get('rel', 0.0)) * abs(ref))
        value = predicted.get(q)
        ok_value = (value is not None and not isinstance(value, bool) and isinstance(value, (int, float))
                    and math.isfinite(value))
        if not ok_value:
            out[q] = {'unit': units.get(q), 'reference': ref, 'predicted': None, 'absolute_error': None,
                      'percent_error': None, 'allowed_error': allowed, 'within_tolerance': False}
            continue
        err = float(value) - ref
        out[q] = {'unit': units.get(q), 'reference': ref, 'predicted': float(value),
                  'absolute_error': abs(err), 'percent_error': 100.0 * err / abs(ref) if ref else None,
                  'allowed_error': allowed, 'within_tolerance': abs(err) <= allowed}
    return out


def agreement_fraction(errors):
    """Fraction of quantities within tolerance in a measurement_errors result (empty -> ValueError)."""
    if not errors:
        raise ValueError('no quantities')
    return sum(e['within_tolerance'] for e in errors.values()) / len(errors)


def bland_altman(predicted, reference):
    """Bland-Altman agreement over cases for one quantity (same units for both arrays).

    bias = mean(pred - ref); sd = sample SD of the differences (ddof=1);
    limits of agreement = bias -/+ 1.96 sd. Needs >= 2 finite pairs.
    """
    a, b = np.asarray(predicted, dtype=float), np.asarray(reference, dtype=float)
    if a.shape != b.shape or a.ndim != 1 or a.size < 2:
        raise ValueError('need two 1D arrays of equal length >= 2')
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
        raise ValueError('values must be finite')
    d = a - b
    bias, sd = float(d.mean()), float(d.std(ddof=1))
    return {'bias': bias, 'sd': sd, 'loa_low': bias - 1.96 * sd, 'loa_high': bias + 1.96 * sd, 'n': int(d.size)}


# ====================================================================== small-sample statistics


def _resample_ok(statistic, arrays, idx):
    try:
        v = float(statistic(*(a[idx] for a in arrays)))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def bootstrap_ci(statistic, *arrays, n_resamples=2000, confidence=0.95, seed=20261114):
    """Percentile bootstrap interval for statistic(*arrays) over cases.

    Cases (rows shared by all arrays) are resampled with replacement, jointly across arrays.
    Resamples on which the statistic is undefined (raises ValueError, or is non-finite, e.g.
    AUROC with one class) are skipped and counted. Interval: numpy linear percentiles at
    (1-confidence)/2 and 1-(1-confidence)/2. With fewer than ~20 cases the interval is crude;
    report n with it. Deterministic for a given seed.
    """
    arrays = [np.asarray(a) for a in arrays]
    n = len(arrays[0])
    if n == 0 or any(len(a) != n for a in arrays):
        raise ValueError('arrays must be non-empty and of equal length')
    rng = np.random.default_rng(seed)
    values, skipped = [], 0
    for _ in range(n_resamples):
        v = _resample_ok(statistic, arrays, rng.integers(0, n, n))
        if v is None:
            skipped += 1
        else:
            values.append(v)
    alpha = (1 - confidence) / 2
    return {'estimate': float(statistic(*arrays)),
            'low': float(np.percentile(values, 100 * alpha)) if values else None,
            'high': float(np.percentile(values, 100 * (1 - alpha))) if values else None,
            'confidence': confidence, 'n': n, 'n_resamples_used': len(values), 'n_resamples_skipped': skipped}


def paired_bootstrap_difference(statistic, arrays_a, arrays_b, n_resamples=2000, confidence=0.95,
                                seed=20261114):
    """Bootstrap of statistic(*arrays_a) - statistic(*arrays_b) on the same cases.

    Both systems are evaluated on the same resampled case indices (paired). For per-case
    scores use statistic=np.mean, arrays_a=(scores_a,), arrays_b=(scores_b,). For AUROC of
    two models use statistic=auroc, arrays_a=(y, p_a), arrays_b=(y, p_b).
    Returns the observed difference, a percentile interval, and fraction_le_zero = share of
    resamples with difference <= 0 (a one-sided bootstrap p-value for 'a better than b').
    """
    arrays_a = [np.asarray(a) for a in arrays_a]
    arrays_b = [np.asarray(b) for b in arrays_b]
    n = len(arrays_a[0])
    if n == 0 or any(len(a) != n for a in arrays_a + arrays_b):
        raise ValueError('all arrays must be non-empty and share the same cases')
    rng = np.random.default_rng(seed)
    diffs, skipped = [], 0
    for _ in range(n_resamples):
        idx = rng.integers(0, n, n)
        a, b = _resample_ok(statistic, arrays_a, idx), _resample_ok(statistic, arrays_b, idx)
        if a is None or b is None:
            skipped += 1
        else:
            diffs.append(a - b)
    alpha = (1 - confidence) / 2
    d = np.asarray(diffs)
    return {'difference': float(statistic(*arrays_a) - statistic(*arrays_b)),
            'low': float(np.percentile(d, 100 * alpha)) if d.size else None,
            'high': float(np.percentile(d, 100 * (1 - alpha))) if d.size else None,
            'fraction_le_zero': float(np.mean(d <= 0)) if d.size else None,
            'confidence': confidence, 'n': n, 'n_resamples_used': int(d.size), 'n_resamples_skipped': skipped}
