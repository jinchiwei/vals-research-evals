"""suite/core plug-in for causal_ate: cohort grading over many datasets (runs inside the verifier from tests/lib).

The exported task has ONE hidden folder ("cohort"): input/<dataset_id>/data.csv for each of the 48 hidden
datasets and reference/truth.csv (dataset_id,satt). suite.core.grading runs the pipeline once on the whole
input folder under the cohort limit and calls grade_cohort().

Required output: estimates.json = {"estimand": "SATT", "datasets": {<id>: {"estimate": x, "ci_lower": l,
"ci_upper": u}}} with one entry per input dataset, finite numbers, l <= x <= u.
Errors are scaled by each dataset's observed outcome sd (sd of y in its data.csv, ddof=1).
Gate parts: coverage, rmse, bias, interval_length (gate.GATE); all must hold.
"""
import csv
import json
import math
from pathlib import Path

from suite.core.geometry import GeometryError, read_regular_file

from .gate import GATE

GRADING = 'cohort'
REQUIRED_OUTPUTS = ('estimates.json',)
PRIMARY_METRIC = 'clip(1 - RMSE/0.5, 0, 1), RMSE of the SATT estimate in outcome-sd units'
MAX_BYTES = 4 * 1024 * 1024
CLINICAL_THRESHOLD = (
    f"over the hidden datasets: 95% interval coverage of the true SATT >= {GATE['coverage']['min']}; "
    f"RMSE <= {GATE['rmse']['max']} outcome sd; |mean bias| <= {GATE['bias']['max_abs']} outcome sd; "
    f"mean interval length <= {GATE['interval_length']['max_mean']} outcome sd")


class InvalidOutput(ValueError):
    pass


def dataset_ids(input_dir):
    return sorted(p.name for p in Path(input_dir).iterdir() if (p / 'data.csv').is_file())


def outcome_sd(data_csv):
    """Sample sd (ddof=1) of the y column, read with the csv module (verifier needs numpy/scipy only)."""
    with open(data_csv, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        k = header.index('y')
        ys = [float(row[k]) for row in reader]
    m = sum(ys) / len(ys)
    return math.sqrt(sum((v - m) ** 2 for v in ys) / (len(ys) - 1))


def read_truth(reference_dir):
    with open(Path(reference_dir) / 'truth.csv', newline='') as f:
        return {r['dataset_id']: float(r['satt']) for r in csv.DictReader(f)}


def _number(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise InvalidOutput(f'{what} must be a finite number')
    return float(v)


def parse_estimates(raw, ids):
    try:
        doc = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidOutput(f'estimates.json is not valid JSON: {error}') from None
    if not isinstance(doc, dict) or not isinstance(doc.get('datasets'), dict):
        raise InvalidOutput('estimates.json must be an object with a "datasets" object')
    if str(doc.get('estimand', '')).upper() != 'SATT':
        raise InvalidOutput('estimates.json "estimand" must be "SATT"')
    got = doc['datasets']
    missing = [i for i in ids if i not in got]
    if missing:
        raise InvalidOutput(f'{len(missing)} dataset(s) missing from estimates.json, e.g. {missing[:3]}')
    out = {}
    for i in ids:
        r = got[i]
        if not isinstance(r, dict):
            raise InvalidOutput(f'{i}: entry must be an object')
        est = _number(r.get('estimate'), f'{i}.estimate')
        lo = _number(r.get('ci_lower'), f'{i}.ci_lower')
        hi = _number(r.get('ci_upper'), f'{i}.ci_upper')
        if not lo <= est <= hi:
            raise InvalidOutput(f'{i}: need ci_lower <= estimate <= ci_upper')
        out[i] = (est, lo, hi)
    return out


def score(estimates, truth, sds):
    """Cohort metrics in outcome-sd units and the gate. estimates/truth/sds keyed by dataset id."""
    errs, covered, lengths, per = [], [], [], {}
    for i, (est, lo, hi) in estimates.items():
        t, sd = truth[i], sds[i]
        e = (est - t) / sd
        c = lo <= t <= hi
        length = (hi - lo) / sd
        errs.append(e)
        covered.append(c)
        lengths.append(length)
        per[i] = {'err_sd': e, 'covered': c, 'length_sd': length}
    n = len(errs)
    m = {'n_datasets': n, 'coverage': sum(covered) / n, 'n_covered': sum(covered),
         'bias_sd': sum(errs) / n, 'rmse_sd': math.sqrt(sum(e * e for e in errs) / n),
         'mae_sd': sum(abs(e) for e in errs) / n, 'max_abs_err_sd': max(abs(e) for e in errs),
         'mean_length_sd': sum(lengths) / n, 'per_dataset': per}
    gate = {'coverage': m['coverage'] >= GATE['coverage']['min'],
            'rmse': m['rmse_sd'] <= GATE['rmse']['max'],
            'bias': abs(m['bias_sd']) <= GATE['bias']['max_abs'],
            'interval_length': m['mean_length_sd'] <= GATE['interval_length']['max_mean']}
    return m, gate


def quality_from_rmse(rmse_sd):
    return min(1.0, max(0.0, 1.0 - rmse_sd / 0.5))


def grade_cohort(output_dir, input_dir, reference_dir):
    ids = dataset_ids(input_dir)
    try:
        raw = read_regular_file(str(Path(output_dir) / 'estimates.json'), max_bytes=MAX_BYTES)
        est = parse_estimates(raw, ids)
    except GeometryError as error:
        return {'valid': False, 'quality': 0.0, 'reason': f'estimates.json: {error}', 'gate': {}, 'metrics': {}}
    except InvalidOutput as error:
        return {'valid': False, 'quality': 0.0, 'reason': str(error), 'gate': {}, 'metrics': {}}
    truth = read_truth(reference_dir)
    sds = {i: outcome_sd(Path(input_dir) / i / 'data.csv') for i in ids}
    m, gate = score(est, truth, sds)
    failed = [k for k, ok in gate.items() if not ok]
    return {'valid': True, 'quality': quality_from_rmse(m['rmse_sd']), 'gate': gate,
            'reason': ('gate failed: ' + ', '.join(failed)) if failed else None, 'metrics': m}
