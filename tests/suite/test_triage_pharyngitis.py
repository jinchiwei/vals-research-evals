"""triage_pharyngitis on synthetic data only (no real patients needed).

Run: ~/miniconda3/envs/vals-suite-triage_pharyngitis/bin/python -m pytest tests/suite/test_triage_pharyngitis.py -q
"""
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from suite.families.triage_pharyngitis import grader, records

PIPE_SRC = Path(__file__).resolve().parents[2] / 'suite' / 'families' / 'triage_pharyngitis' / 'pipeline_src'
sys.path.insert(0, str(PIPE_SRC))
import predict as P  # noqa: E402


def synthetic_cohort(n=200, seed=0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.3).astype(int)
    y[:2] = [0, 1]
    groups = {'sex': rng.choice(['F', 'M'], n), 'age_band': rng.choice(['child_lt15', 'adult_ge15'], n),
              'device': rng.choice(['samsung', 'xiaomi'], n)}
    return y, groups, rng


def test_quality_mapping_and_time_limit():
    assert grader.quality_from_auroc(0.5) == 0.0
    assert grader.quality_from_auroc(0.3) == 0.0
    assert grader.quality_from_auroc(0.75) == pytest.approx(0.5)
    assert grader.quality_from_auroc(1.0) == 1.0
    assert grader.time_limit_seconds(180) == pytest.approx(420.0)


def test_gate_separates_oracle_constant_overconfident():
    y, groups, rng = synthetic_cohort()
    oracle = grader.evaluate(y, np.where(y == 1, 0.98, 0.02), groups, bootstrap=False)
    assert oracle['acceptable'] and oracle['gate_fraction'] == 1.0 and oracle['quality'] == 1.0
    const = grader.evaluate(y, np.full(y.size, y.mean()), groups, bootstrap=False)
    assert not const['acceptable']
    assert not const['gate_components']['operating_point'] and not const['gate_components']['net_benefit']
    assert not const['gate_components']['calibration']           # slope undefined, no separation
    # A well-calibrated informative score: p drawn so that P(y=1 | p) = p.
    p = rng.beta(1.2, 2.8, 4000)
    yy = (rng.random(4000) < p).astype(int)
    g = {'sex': rng.choice(['F', 'M'], 4000)}
    good = grader.evaluate(yy, p, g, bootstrap=False)
    assert good['gate_components']['calibration']
    over = grader.evaluate(yy, 1 / (1 + np.exp(-6 * np.log(p / (1 - p)))), g, bootstrap=False)
    assert not over['gate_components']['calibration']
    assert over['auroc'] == pytest.approx(good['auroc'])          # same ranking, worse calibration


def test_subgroup_component_flags_missed_group():
    y, groups, rng = synthetic_cohort(600, 1)
    groups['device'] = np.where(rng.random(y.size) < 0.12, 'xiaomi', 'samsung')   # small group, >= 10 positives
    assert y[groups['device'] == 'xiaomi'].sum() >= 10
    p = np.where(y == 1, 0.9, 0.1).astype(float)
    bad = (groups['device'] == 'xiaomi') & (y == 1)
    p[bad] = 0.05                                                 # misses every bacterial xiaomi case
    m = grader.evaluate(y, p, groups, bootstrap=False)
    assert m['worst_subgroup']['group'] == 'device=xiaomi'
    assert not m['gate_components']['subgroup']


def _write_cohort(tmp, n=200, seed=3):
    y, groups, _ = synthetic_cohort(n, seed)
    ids = [f'p{i:04d}' for i in range(n)]
    inp, ref, out = tmp / 'input', tmp / 'reference', tmp / 'out'
    for d in (inp, ref, out):
        d.mkdir()
    with open(inp / 'patients.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['case_id', 'age', 'sex', *records.SYMPTOM_COLUMNS])
        for c in ids:
            w.writerow([c, 30, 'F'] + [0] * 20)
    with open(ref / 'labels.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['case_id', 'bacterial', 'bacterial_strict', 'bacterial_fraction', 'n_votes', 'sex', 'age_band',
                    'device'])
        for i, c in enumerate(ids):
            w.writerow([c, y[i], y[i], float(y[i]), 4, groups['sex'][i], groups['age_band'][i], groups['device'][i]])
    return ids, y, inp, ref, out


def _write_preds(out, items):
    (out / 'predictions.json').write_text(json.dumps({'predictions': items}))


def test_grade_case_valid_and_invalid(tmp_path):
    ids, y, inp, ref, out = _write_cohort(tmp_path)
    _write_preds(out, [{'case': c, 'probability': 0.98 if v else 0.02} for c, v in zip(ids, y)])
    g = grader.grade_case(out, inp, ref)
    assert g['valid'] and g['acceptable'] and g['quality'] == 1.0
    bad_cases = {
        'missing': [{'case': c, 'probability': 0.5} for c in ids[1:]],
        'extra': [{'case': c, 'probability': 0.5} for c in ids] + [{'case': 'zzz', 'probability': 0.5}],
        'range': [{'case': c, 'probability': 1.5} for c in ids],
        'string': [{'case': c, 'probability': '0.5'} for c in ids],
    }
    for name, items in bad_cases.items():
        _write_preds(out, items)
        assert not grader.grade_case(out, inp, ref)['valid'], name
    (out / 'predictions.json').write_text('{"predictions": [{"case": "%s", "probability": NaN}]}' % ids[0])
    assert not grader.grade_case(out, inp, ref)['valid']
    (out / 'predictions.json').unlink()
    (out / 'predictions.json').symlink_to(ref / 'labels.csv')
    assert not grader.grade_case(out, inp, ref)['valid']                 # symlink refused
    (out / 'predictions.json').unlink()
    dup = [{'case': ids[0], 'probability': 0.1}] * 2 + [{'case': c, 'probability': 0.5} for c in ids[1:]]
    _write_preds(out, dup)
    assert not grader.grade_case(out, inp, ref)['valid']


def test_partial_mcisaac():
    rows = [{'age': '8', 'pyrexia': '1', 'cough': '0'}, {'age': '50', 'pyrexia': '0', 'cough': '1'},
            {'age': '30', 'pyrexia': '1', 'cough': '1'}, {'age': '2', 'pyrexia': '0', 'cough': '0'}]
    assert P.mcisaac_partial(rows).tolist() == [3, -1, 1, 1]


def test_load_table_labels_and_ties(tmp_path):
    pd = pytest.importorskip('pandas')
    pytest.importorskip('openpyxl')
    base = {'patient_ID': [1, 2, 3, 4], 'Age': [10, 40, 50, 20], 'Gender': ['Male', 'Female', 'Male', 'Female']}
    for s in records.SYMPTOMS:
        base[s] = [0, 1, 0, 1]
    votes = [['Bacterial'] * 4, ['Bacterial', 'Bacterial', 'Non Bacterial', 'Non Bacterial'],
             ['Bacterial', 'Non Bacterial', 'Non Bacterial', None, 'Non Bacterial'], ['Non Bacterial'] * 3]
    for i in range(9):
        base[f'Diagnosis #{i + 1}'] = [v[i] if i < len(v) else None for v in votes]
    pd.DataFrame(base).to_excel(tmp_path / 'x.xlsx', index=False)
    t = records.load_table(tmp_path / 'x.xlsx')
    assert t['n_votes'].tolist() == [4, 4, 4, 3]
    assert t['label'].tolist() == [1, 1, 0, 0]                    # tie counts as bacterial
    assert t['label_strict'].tolist() == [1, 0, 0, 0]
    assert t['tie'].tolist() == [0, 1, 0, 0] and t['unanimous'].tolist() == [1, 0, 0, 1]
    assert t['age_band'].tolist() == ['child_lt15', 'adult_ge15', 'adult_ge15', 'adult_ge15']


def test_strip_jpeg_metadata_is_lossless(tmp_path):
    Image = pytest.importorskip('PIL.Image')
    im = Image.fromarray((np.random.default_rng(0).random((32, 48, 3)) * 255).astype(np.uint8))
    exif = Image.Exif()
    exif[271] = 'samsung'
    exif[0x8825] = {1: 'N', 2: (37.0, 46.0, 1.0)}
    src = tmp_path / 'a.jpg'
    im.save(src, 'JPEG', exif=exif, quality=90)
    assert b'samsung' in src.read_bytes()
    assert records.write_clean_image(src, tmp_path / 'b.jpg') == 'jpeg_metadata_stripped'
    clean = (tmp_path / 'b.jpg').read_bytes()
    assert b'samsung' not in clean and b'Exif' not in clean
    assert np.array_equal(np.asarray(Image.open(src)), np.asarray(Image.open(io.BytesIO(clean))))
