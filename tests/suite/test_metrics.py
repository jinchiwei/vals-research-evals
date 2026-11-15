"""Metric library: hand-computed values, edge cases, and cross-checks against scikit-learn,
SciPy and SimpleITK where available."""
import math

import numpy as np
import pytest

from suite.core import metrics as M

SP = (1.0, 1.0, 2.0)


def vol(shape=(8, 8, 8)):
    return np.zeros(shape, dtype=np.uint8)


# ----------------------------------------------------------------- segmentation: hand values

def test_dice_hand_and_edges():
    r, p = vol(), vol()
    r[2:4, 2:4, 2:4] = 1
    p[3:5, 2:4, 2:4] = 1                     # shifted one voxel: overlap 4 of 8 + 8
    assert M.dice(r, p) == pytest.approx(0.5)
    assert M.dice(vol(), vol()) == 1.0
    assert M.dice(r, vol()) == 0.0
    with pytest.raises(ValueError):
        M.dice(r, vol((8, 8, 7)))


def test_volume_in_ml_uses_spacing():
    r = vol()
    r[2:4, 2:4, 2:4] = 1                     # 8 voxels x 2 mm^3
    assert M.volume_ml(r, SP) == pytest.approx(0.016)
    e = M.volume_errors(r, vol(), SP)
    assert e['absolute_volume_error_ml'] == pytest.approx(0.016)
    assert e['relative_volume_error'] == pytest.approx(-1.0)
    assert M.volume_errors(vol(), r, SP)['relative_volume_error'] is None   # empty reference


def test_single_voxel_distances_anisotropic():
    r, p = vol(), vol()
    r[1, 1, 1] = 1
    p[1, 1, 4] = 1                           # 3 voxels along axis 2 at 2 mm = 6 mm
    assert M.hausdorff_distance(r, p, SP) == pytest.approx(6.0)
    assert M.hd95(r, p, SP) == pytest.approx(6.0)
    assert M.normalized_surface_distance(r, p, SP, 5.9) == 0.0
    assert M.normalized_surface_distance(r, p, SP, 6.0) == 1.0


def test_distance_edge_cases():
    r = vol()
    r[1, 1, 1] = 1
    assert M.hd95(vol(), vol(), SP) == 0.0
    assert math.isinf(M.hd95(r, vol(), SP)) and math.isinf(M.hd95(vol(), r, SP))
    assert M.normalized_surface_distance(vol(), vol(), SP, 1.0) == 1.0
    assert M.normalized_surface_distance(r, vol(), SP, 1.0) == 0.0
    assert M.distance_score(math.inf, 10) == 0.0 and M.distance_score(0, 10) == 1.0
    assert M.distance_score(10, 10) == pytest.approx(math.exp(-1))


def test_surface_counts_edge_voxels():
    m = np.ones((3, 3, 3), dtype=bool)
    s = M.surface_voxels(m)
    assert s.sum() == 26 and not s[1, 1, 1]      # centre is interior, array edge counts as border


def _surface_coords(mask, spacing):
    return np.argwhere(M.surface_voxels(mask)) * np.asarray(spacing)


def _random_blob(seed, shape=(20, 18, 12)):
    from scipy import ndimage
    rng = np.random.default_rng(seed)
    return ndimage.binary_opening(ndimage.gaussian_filter(rng.random(shape), 2) > 0.5)


@pytest.mark.parametrize('seed', [0, 1, 2])
def test_hd_and_hd95_match_brute_force(seed):
    from scipy.spatial.distance import cdist, directed_hausdorff
    sp = (0.8, 1.1, 2.5)
    a, b = _random_blob(seed), _random_blob(seed + 10)
    assert a.any() and b.any()
    ca, cb = _surface_coords(a, sp), _surface_coords(b, sp)
    d = cdist(ca, cb)
    hd95 = max(np.percentile(d.min(axis=1), 95), np.percentile(d.min(axis=0), 95))
    hd = max(directed_hausdorff(ca, cb)[0], directed_hausdorff(cb, ca)[0])
    assert M.hd95(a, b, sp) == pytest.approx(hd95, abs=1e-6)
    assert M.hausdorff_distance(a, b, sp) == pytest.approx(hd, abs=1e-6)
    nsd = ((d.min(axis=1) <= 2.0).sum() + (d.min(axis=0) <= 2.0).sum()) / (len(ca) + len(cb))
    assert M.normalized_surface_distance(a, b, sp, 2.0) == pytest.approx(nsd)


def test_against_simpleitk():
    sitk = pytest.importorskip('SimpleITK')
    sp = (0.8, 1.1, 2.5)
    a, b = vol((24, 24, 12)), vol((24, 24, 12))
    a[2:8, 3:9, 2:5] = 1
    b[12:20, 14:19, 6:10] = 1                   # disjoint boxes: surface HD == SimpleITK HD

    def img(x):
        i = sitk.GetImageFromArray(np.transpose(x, (2, 1, 0)).astype(np.uint8))
        i.SetSpacing(sp)
        return i
    hf = sitk.HausdorffDistanceImageFilter()
    hf.Execute(img(a), img(b))
    assert M.hausdorff_distance(a, b, sp) == pytest.approx(hf.GetHausdorffDistance(), abs=1e-6)
    c = vol((24, 24, 12))
    c[4:10, 3:9, 2:6] = 1
    lo = sitk.LabelOverlapMeasuresImageFilter()
    lo.Execute(img(a), img(c))
    assert M.dice(a, c) == pytest.approx(lo.GetDiceCoefficient())


def test_lesion_detection_rule():
    r, p = vol((12, 12, 12)), vol((12, 12, 12))
    r[1:3, 1:3, 1:3] = 1
    r[8:10, 8:10, 8:10] = 1                   # two reference lesions
    p[2:4, 2:4, 2:4] = 1                      # overlaps lesion 1
    p[1:2, 9:11, 1:2] = 1                     # false positive
    d = M.lesion_detection(r, p)
    assert (d['reference_lesions'], d['detected_reference_lesions'], d['false_positives']) == (2, 1, 1)
    assert d['sensitivity'] == 0.5
    assert M.lesion_detection(vol(), p[:8, :8, :8])['sensitivity'] is None
    s = M.lesion_detection_summary([d, M.lesion_detection(vol(), vol())])
    assert s['sensitivity'] == 0.5 and s['false_positives_per_case'] == 0.5


def test_lesion_f1_min_size_and_lesion_wise_dice():
    r, p = vol((12, 12, 12)), vol((12, 12, 12))
    r[1:3, 1:3, 1:3] = 1                      # lesion A, 8 voxels
    r[8:10, 8:10, 8:10] = 1                   # lesion B, 8 voxels (missed)
    p[1:3, 1:3, 2:4] = 1                      # hits A: overlap 4 -> Dice 0.5
    p[5, 5, 10] = 1                           # 1-voxel spurious component
    d = M.lesion_detection(r, p)
    assert d['precision'] == 0.5 and d['f1'] == pytest.approx(0.5)
    big = M.lesion_detection(r, p, min_lesion_voxels=2)      # the 1-voxel FP is below the declared size
    assert big['false_positives'] == 0 and big['f1'] == pytest.approx(2 * 0.5 / 1.5)
    assert M.lesion_wise_dice(r, p) == pytest.approx((0.5 + 0 + 0) / 3)
    assert M.lesion_wise_dice(r, p, min_lesion_voxels=2) == pytest.approx(0.25)
    assert M.lesion_wise_dice(vol(), vol()) == 1.0 and M.lesion_wise_dice(vol(), p[:8, :8, :8] * 0 + 1) == 0.0


def test_segmentation_headline():
    r, p = vol(), vol()
    r[1, 1, 1] = 1
    p[1, 1, 4] = 1                            # Dice 0, NSD@6mm 1
    assert M.segmentation_headline(r, p, SP, 6.0) == 0.5
    assert M.segmentation_headline(r, r, SP, 1.0) == 1.0


# ----------------------------------------------------------------- registration

def test_tre_hand_values():
    fixed = np.zeros((3, 3))
    mapped = np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, 0.0]])
    t = M.target_registration_error(fixed, mapped, threshold_mm=1.0)
    assert (t['mean_mm'], t['median_mm'], t['max_mm']) == pytest.approx((2.0, 1.0, 5.0))
    assert t['fraction_under_threshold'] == pytest.approx(2 / 3)
    imp = M.registration_improvement(fixed, mapped * 2, mapped)
    assert imp['improved'] and imp['mean_ratio'] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        M.target_registration_error(fixed, np.full((3, 3), np.nan))


def test_jacobian_folding_fraction():
    shape, sp = (6, 5, 4), (2.0, 1.0, 1.5)
    zero = np.zeros(shape + (3,))
    assert M.fraction_nonpositive_jacobian(zero, sp) == 0.0
    x_mm = np.indices(shape)[0] * sp[0]
    stretch = zero.copy()
    stretch[..., 0] = 0.5 * x_mm                 # du_x/dx = 0.5 -> det 1.5
    assert np.allclose(M.jacobian_determinant(stretch, sp), 1.5)
    fold = zero.copy()
    fold[..., 0] = -2.0 * x_mm                   # det = 1 - 2 = -1 everywhere
    assert M.fraction_nonpositive_jacobian(fold, sp) == 1.0
    half = np.zeros(shape, bool)
    half[:3] = True
    assert M.fraction_nonpositive_jacobian(fold, sp, mask=half) == 1.0
    with pytest.raises(ValueError):
        M.fraction_nonpositive_jacobian(fold, sp, mask=np.zeros(shape, bool))


# ----------------------------------------------------------------- classification and risk

def _data(seed=3, n=200):
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.01, 0.99, n)
    y = (rng.uniform(size=n) < p).astype(int)
    return y, np.round(p, 2)                      # rounding creates ties


def test_auroc_ap_brier_hand_and_sklearn():
    sk = pytest.importorskip('sklearn.metrics')
    assert M.auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    y, p = _data()
    assert M.auroc(y, p) == pytest.approx(sk.roc_auc_score(y, p))
    assert M.average_precision(y, p) == pytest.approx(sk.average_precision_score(y, p))
    assert M.brier(y, p) == pytest.approx(sk.brier_score_loss(y, p))
    with pytest.raises(ValueError):
        M.auroc([1, 1], [0.2, 0.3])
    with pytest.raises(ValueError):
        M.brier([0, 1], [0.2, 1.3])


def test_ece_hand():
    assert M.expected_calibration_error([0, 1], [0.2, 0.8]) == pytest.approx(0.2)
    assert M.expected_calibration_error([1, 1], [1.0, 1.0]) == pytest.approx(0.0)   # p = 1 in last bin


def test_calibration_slope_against_sklearn():
    pytest.importorskip('sklearn')
    from sklearn.linear_model import LogisticRegression
    y, p = _data(5, 400)
    p = np.clip(p ** 1.5, 0.01, 0.99)
    c = M.calibration_slope_intercept(y, p)
    lp = np.log(p / (1 - p))
    lr = LogisticRegression(penalty=None, tol=1e-10, max_iter=1000).fit(lp[:, None], y)
    assert c['slope'] == pytest.approx(lr.coef_[0][0], abs=1e-4)
    assert c['intercept'] == pytest.approx(lr.intercept_[0], abs=1e-4)


def test_calibration_edges():
    c = M.calibration_slope_intercept([0, 0, 0, 1], [0.5] * 4)
    assert c['slope'] is None                        # constant predictor: joint fit singular
    assert c['calibration_in_the_large'] == pytest.approx(math.log(1 / 3))
    sep = M.calibration_slope_intercept([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    assert sep['slope'] is None                      # perfect separation does not converge
    assert M.calibration_slope_intercept([1, 1], [0.3, 0.4])['slope'] is None


def test_operating_points_hand_and_sklearn():
    sk = pytest.importorskip('sklearn.metrics')
    y = [0, 0, 0, 0, 1, 1, 1, 1]
    p = [0.1, 0.2, 0.3, 0.6, 0.4, 0.7, 0.8, 0.9]
    r = M.sensitivity_at_specificity(y, p, 0.75)
    assert (r['sensitivity'], r['specificity'], r['threshold']) == (1.0, 0.75, 0.4)
    assert M.sensitivity_at_specificity(y, p, 1.0)['sensitivity'] == 0.75
    assert M.specificity_at_sensitivity(y, p, 1.0)['specificity'] == 0.75
    y2, p2 = _data(9)
    fpr, tpr, _ = sk.roc_curve(y2, p2, drop_intermediate=False)
    for target in (0.5, 0.8, 0.95):
        assert M.sensitivity_at_specificity(y2, p2, target)['sensitivity'] == pytest.approx(
            tpr[(1 - fpr) >= target].max())
        assert M.specificity_at_sensitivity(y2, p2, target)['specificity'] == pytest.approx(
            (1 - fpr)[tpr >= target].max())


def test_net_benefit_hand():
    nb = M.net_benefit([1, 1, 0, 0], [0.9, 0.6, 0.7, 0.1], 0.5)
    assert nb['net_benefit'] == pytest.approx(0.25) and nb['treat_all'] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        M.net_benefit([1, 0], [0.5, 0.5], 1.0)


def test_net_benefit_curve():
    c = M.net_benefit_curve([1, 1, 0, 0], [0.9, 0.6, 0.7, 0.1], [0.5, 0.65])
    # at 0.65: TP 1 (0.9), FP 1 (0.7): 0.25 - 0.25 * 0.65/0.35
    assert c['points'][1]['net_benefit'] == pytest.approx(0.25 - 0.25 * 0.65 / 0.35)
    assert c['mean_net_benefit'] == pytest.approx((0.25 + 0.25 - 0.25 * 0.65 / 0.35) / 2)


def test_subgroups_and_worst_gap():
    y = [0, 1, 0, 1, 0, 0]
    p = [0.2, 0.8, 0.6, 0.4, 0.1, 0.3]
    g = ['a', 'a', 'b', 'b', 'c', 'c']
    s = M.subgroup_breakdown(M.auroc, y, p, g)
    assert s['groups']['a']['value'] == 1.0 and s['groups']['b']['value'] == 0.0
    assert s['groups']['c']['value'] is None                 # one class: undefined, excluded
    assert s['worst_group'] == 'b' and s['worst_group_gap'] == 1.0
    lower = M.subgroup_breakdown(M.brier, y, p, g, higher_is_better=False)
    assert lower['worst_group'] == 'b'


# ----------------------------------------------------------------- measurement

def test_measurement_errors():
    e = M.measurement_errors({'v': 11.0, 'd': 4.9}, {'v': 10.0, 'd': 5.0, 'm': 1.0},
                             {'v': 'mL', 'd': 'mm', 'm': 'mm'},
                             {'v': {'rel': 0.05}, 'd': {'abs': 0.1}, 'm': {'abs': 1}})
    assert e['v']['absolute_error'] == pytest.approx(1.0) and e['v']['percent_error'] == pytest.approx(10.0)
    assert not e['v']['within_tolerance'] and e['d']['within_tolerance']
    assert e['m']['predicted'] is None and not e['m']['within_tolerance']   # missing
    assert e['v']['unit'] == 'mL'
    assert M.agreement_fraction(e) == pytest.approx(1 / 3)
    assert M.measurement_errors({'z': 1.0}, {'z': 0.0}, {}, {'z': {'abs': 1}})['z']['percent_error'] is None
    assert not M.measurement_errors({'z': float('nan')}, {'z': 0.0}, {}, {})['z']['within_tolerance']


def test_bland_altman_hand():
    ba = M.bland_altman([11.0, 9.0, 12.0, 10.0], [10.0, 10.0, 10.0, 10.0])   # diffs 1, -1, 2, 0
    assert ba['bias'] == pytest.approx(0.5)
    sd = float(np.std([1, -1, 2, 0], ddof=1))
    assert ba['sd'] == pytest.approx(sd) and ba['loa_high'] == pytest.approx(0.5 + 1.96 * sd)
    with pytest.raises(ValueError):
        M.bland_altman([1.0], [1.0])


# ----------------------------------------------------------------- statistics

def test_bootstrap_basics():
    const = M.bootstrap_ci(np.mean, np.full(10, 0.7))
    assert const['low'] == const['high'] == pytest.approx(0.7)
    x = np.random.default_rng(1).normal(size=40)
    a, b = M.bootstrap_ci(np.mean, x, seed=4), M.bootstrap_ci(np.mean, x, seed=4)
    assert a == b and a['low'] < a['estimate'] < a['high']
    scipy_stats = pytest.importorskip('scipy.stats')
    ref = scipy_stats.bootstrap((x,), np.mean, method='percentile', n_resamples=4000, random_state=0)
    assert a['low'] == pytest.approx(ref.confidence_interval.low, abs=0.08)
    assert a['high'] == pytest.approx(ref.confidence_interval.high, abs=0.08)


def test_bootstrap_skips_undefined_resamples():
    y = np.array([0, 0, 0, 0, 0, 0, 0, 1])
    p = np.linspace(0.1, 0.9, 8)
    r = M.bootstrap_ci(M.auroc, y, p, n_resamples=300)
    assert r['n_resamples_skipped'] > 0 and r['n_resamples_used'] + r['n_resamples_skipped'] == 300


def test_paired_bootstrap_difference():
    b = np.random.default_rng(2).uniform(size=15)
    r = M.paired_bootstrap_difference(np.mean, (b + 0.1,), (b,))
    assert r['difference'] == pytest.approx(0.1)
    assert r['low'] == pytest.approx(0.1) and r['high'] == pytest.approx(0.1)
    assert r['fraction_le_zero'] == 0.0
    y, p = _data(11, 60)
    r2 = M.paired_bootstrap_difference(M.auroc, (y, p), (y, 1 - p), n_resamples=200)
    assert r2['difference'] > 0 and r2['low'] > 0
