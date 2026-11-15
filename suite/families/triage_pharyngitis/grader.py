"""Grader for triage_pharyngitis (runs inside the verifier from tests/lib, via suite.core.grading).

The hidden set is graded as ONE cohort case ("cohort"): discrimination, calibration, net benefit and
subgroup metrics are defined over patients, not per patient. The pipeline is run once on all hidden
patients under a time limit of BATCH_OVERHEAD_SECONDS + SECONDS_PER_PATIENT * n (grader's clock).

Required output in OUTPUT_DIR:
  predictions.json  {"predictions": [{"case": "<case_id>", "probability": <p>}, ...]}
                    exactly one finite p in [0, 1] (probability of bacterial pharyngitis) per case_id in
                    INPUT_DIR/patients.csv; parsed by pcnsl.prediction_eval.parse_probabilities (strict).

Reference: physician panel vote (3-9 physicians per patient, photo + symptoms; no culture or rapid test).
Positive = at least half the panel called it bacterial. See docs/research/suite/triage_pharyngitis.md.

Clinical gate (fixed 2026-11-14 before any comparator or agent result was seen). Four components:
  1 operating_point  rule-out referral for a rapid antigen test: at the empirical operating point with
                     sensitivity >= 0.85 for bacterial cases, specificity >= 0.40.
  2 calibration      ECE (10 equal-width bins) <= 0.10 and calibration slope in [0.5, 2.0]; an undefined slope
                     fails (e.g. constant output) unless it is undefined because of perfect separation.
  3 net_benefit      at referral threshold probability 0.15 (refer if p >= 0.15), net benefit strictly
                     greater than both treat-all (refer everyone) and treat-none.
  4 subgroup         at the component-1 threshold, sensitivity >= 0.70 in every pre-declared group with
                     >= 10 bacterial cases (sex F/M; age <15 / >=15; capture device samsung/xiaomi/unknown).
acceptable = all four met. Graded through suite.core's cohort hook (GRADING = 'cohort', grade_cohort):
clinically_acceptable = 1 only if all four are met; each part and gate_fraction go to metrics.json.

quality = clip((AUROC - 0.5) / 0.5, 0, 1): chance or worse = 0, perfect ranking = 1.
"""
import csv
import json
import math

import numpy as np

from pcnsl.prediction_eval import ParseFailure, parse_probabilities
from suite.core import geometry
from suite.core import metrics as M

GRADING = 'cohort'
REQUIRED_OUTPUTS = ('predictions.json',)
PRIMARY_METRIC = 'auroc_mapped'
MAX_OUTPUT_BYTES = 2_000_000

SENSITIVITY_TARGET = 0.85
SPECIFICITY_FLOOR = 0.40
ECE_MAX = 0.10
ECE_BINS = 10
SLOPE_RANGE = (0.5, 2.0)
REFERRAL_THRESHOLD = 0.15
SUBGROUP_SENSITIVITY_FLOOR = 0.70
SUBGROUP_MIN_POSITIVES = 10
SUBGROUP_COLUMNS = ('sex', 'age_band', 'device')
SECONDS_PER_PATIENT = 2.0
BATCH_OVERHEAD_SECONDS = 60.0
BOOTSTRAP_RESAMPLES = 2000

CLINICAL_THRESHOLD = (
    f'all of: specificity >= {SPECIFICITY_FLOOR} at sensitivity >= {SENSITIVITY_TARGET}; ECE <= {ECE_MAX} and '
    f'calibration slope in [{SLOPE_RANGE[0]}, {SLOPE_RANGE[1]}]; net benefit at p_t={REFERRAL_THRESHOLD} above '
    f'treat-all and treat-none; sensitivity >= {SUBGROUP_SENSITIVITY_FLOOR} in every sex/age/device group with '
    f'>= {SUBGROUP_MIN_POSITIVES} bacterial cases (physician-vote reference)')


def time_limit_seconds(n_patients):
    return BATCH_OVERHEAD_SECONDS + SECONDS_PER_PATIENT * n_patients


def quality_from_auroc(auc):
    return float(min(1.0, max(0.0, (auc - 0.5) / 0.5)))


def read_case_ids(input_dir):
    with open(input_dir / 'patients.csv', newline='', encoding='utf-8') as f:
        return [row['case_id'] for row in csv.DictReader(f)]


def read_reference(reference_dir):
    with open(reference_dir / 'labels.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return {r['case_id']: r for r in rows}


def _sensitivity_at(y, p, threshold):
    pos = y == 1
    return float((p[pos] >= threshold).mean()) if pos.any() else None


def evaluate(y, p, groups, bootstrap=True):
    """All metrics and the gate for labels y (0/1), probabilities p, groups {column: array of names}."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    auc = M.auroc(y, p)
    op = M.specificity_at_sensitivity(y, p, SENSITIVITY_TARGET)
    cal = M.calibration_slope_intercept(y, p)
    ece = M.expected_calibration_error(y, p, ECE_BINS)
    nb = M.net_benefit(y, p, REFERRAL_THRESHOLD)
    at_ref = p >= REFERRAL_THRESHOLD
    sub = {}
    worst = None
    for col, g in groups.items():
        g = np.asarray(g)
        per = {}
        for name in sorted(set(g.tolist())):
            sel = g == name
            n_pos = int(y[sel].sum())
            se = _sensitivity_at(y[sel], p[sel], op['threshold'])
            try:
                g_auc = M.auroc(y[sel], p[sel])
            except ValueError:
                g_auc = None
            scored = n_pos >= SUBGROUP_MIN_POSITIVES
            per[name] = {'n': int(sel.sum()), 'n_bacterial': n_pos, 'sensitivity_at_op': se, 'auroc': g_auc,
                         'scored': scored}
            if scored and se is not None and (worst is None or se < worst['sensitivity']):
                worst = {'group': f'{col}={name}', 'sensitivity': se}
        aucs = [v['auroc'] for v in per.values() if v['scored'] and v['auroc'] is not None]
        sub[col] = {'groups': per, 'auroc_gap': (max(aucs) - min(aucs)) if len(aucs) > 1 else None}
    slope = cal['slope']
    components = {
        'operating_point': op['specificity'] >= SPECIFICITY_FLOOR - 1e-12,
        'calibration': ece <= ECE_MAX and ((slope is not None and SLOPE_RANGE[0] <= slope <= SLOPE_RANGE[1])
                                           or (slope is None and auc == 1.0)),
        'net_benefit': nb['net_benefit'] > max(nb['treat_all'], nb['treat_none']) + 1e-12,
        'subgroup': worst is not None and worst['sensitivity'] >= SUBGROUP_SENSITIVITY_FLOOR - 1e-12,
    }
    out = {
        'n': int(y.size), 'n_bacterial': int(y.sum()), 'prevalence': float(y.mean()),
        'auroc': auc, 'quality': quality_from_auroc(auc),
        'average_precision': M.average_precision(y, p), 'brier': M.brier(y, p),
        'ece': ece, 'calibration': cal, 'mean_probability': float(p.mean()),
        'operating_point': {**op, 'sensitivity_target': SENSITIVITY_TARGET, 'specificity_floor': SPECIFICITY_FLOOR},
        'at_referral_threshold': {'threshold': REFERRAL_THRESHOLD, 'referred_fraction': float(at_ref.mean()),
                                  'sensitivity': _sensitivity_at(y, p, REFERRAL_THRESHOLD),
                                  'specificity': float((~at_ref[y == 0]).mean())},
        'net_benefit': nb, 'subgroups': sub, 'worst_subgroup': worst,
        'gate_components': components, 'gate_fraction': sum(components.values()) / len(components),
        'acceptable': all(components.values()),
    }
    if bootstrap:
        def nb_gain(yy, pp):
            r = M.net_benefit(yy, pp, REFERRAL_THRESHOLD)
            return r['net_benefit'] - max(r['treat_all'], 0.0)
        out['bootstrap_95'] = {
            'auroc': M.bootstrap_ci(M.auroc, y, p, n_resamples=BOOTSTRAP_RESAMPLES),
            'specificity_at_sens_0_85': M.bootstrap_ci(
                lambda yy, pp: M.specificity_at_sensitivity(yy, pp, SENSITIVITY_TARGET)['specificity'], y, p,
                n_resamples=BOOTSTRAP_RESAMPLES),
            'ece': M.bootstrap_ci(lambda yy, pp: M.expected_calibration_error(yy, pp, ECE_BINS), y, p,
                                  n_resamples=BOOTSTRAP_RESAMPLES),
            'brier': M.bootstrap_ci(M.brier, y, p, n_resamples=BOOTSTRAP_RESAMPLES),
            'net_benefit_gain_over_best_default': M.bootstrap_ci(nb_gain, y, p, n_resamples=BOOTSTRAP_RESAMPLES),
        }
    return out


def _invalid(reason):
    return {'valid': False, 'acceptable': False, 'quality': 0.0, 'reason': reason, 'metrics': {}}


def grade_case(output_dir, input_dir, reference_dir):
    case_ids = read_case_ids(input_dir)
    ref = read_reference(reference_dir)
    if set(case_ids) != set(ref):
        raise RuntimeError('hidden inputs and references disagree')        # infrastructure, not the agent
    try:      # O_NOFOLLOW read: a symlink planted by the pipeline is refused, never followed
        raw = geometry.read_regular_file(output_dir / 'predictions.json', MAX_OUTPUT_BYTES)
    except geometry.GeometryError as error:
        return _invalid(f'predictions.json {error.code}: {error.detail}')
    try:
        p = parse_probabilities(raw.decode('utf-8'), case_ids)
    except UnicodeDecodeError:
        return _invalid('predictions.json is not UTF-8')
    except ParseFailure as error:
        return _invalid(f'predictions.json rejected: {error}')
    y = [int(ref[c]['bacterial']) for c in case_ids]
    groups = {col: [ref[c][col] for c in case_ids] for col in SUBGROUP_COLUMNS}
    m = evaluate(y, p, groups)
    y_strict = [int(ref[c]['bacterial_strict']) for c in case_ids]
    m['secondary_strict_majority_label'] = {'n_bacterial': int(sum(y_strict)), 'auroc': M.auroc(y_strict, p)}
    frac = np.array([float(ref[c]['bacterial_fraction']) for c in case_ids])
    m['secondary_brier_vs_vote_fraction'] = float(np.mean((np.asarray(p) - frac) ** 2))
    failed = [k for k, ok in m['gate_components'].items() if not ok]
    reason = None if not failed else 'gate components not met: ' + ', '.join(failed)
    if not all(math.isfinite(v) for v in (m['auroc'], m['quality'])):
        raise RuntimeError('non-finite metric')
    return {'valid': True, 'acceptable': m['acceptable'], 'quality': m['quality'], 'reason': reason, 'metrics': m}


def grade_cohort(output_dir, input_dir, reference_dir):
    """suite.core cohort hook: the same grading as grade_case, with the gate parts returned separately."""
    g = grade_case(output_dir, input_dir, reference_dir)
    gate = dict(g['metrics'].get('gate_components', {})) if g['valid'] else {}
    return {'valid': g['valid'], 'quality': g['quality'], 'reason': g['reason'], 'gate': gate,
            'metrics': g['metrics']}


def describe_gate():
    return json.dumps({'sensitivity_target': SENSITIVITY_TARGET, 'specificity_floor': SPECIFICITY_FLOOR,
                       'ece_max': ECE_MAX, 'slope_range': SLOPE_RANGE, 'referral_threshold': REFERRAL_THRESHOLD,
                       'subgroup_sensitivity_floor': SUBGROUP_SENSITIVITY_FLOOR,
                       'subgroup_min_positives': SUBGROUP_MIN_POSITIVES,
                       'seconds_per_patient': SECONDS_PER_PATIENT, 'batch_overhead_seconds': BATCH_OVERHEAD_SECONDS})
