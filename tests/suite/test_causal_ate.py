"""causal_ate tests on a synthetic covariate pool (no PhysioNet data needed).

Run: ~/miniconda3/envs/vals-suite-causal_ate/bin/python -m pytest tests/suite/test_causal_ate.py -q
"""
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from suite.core import export, grading
from suite.families.causal_ate import grader
from suite.families.causal_ate.datagen import dgp
from suite.families.causal_ate.gate import GATE, N_HIDDEN

REPO = Path(__file__).resolve().parents[2]
ORACLE = REPO / 'suite' / 'families' / 'causal_ate' / 'comparators' / 'pipelines' / 'dr_att'
COLS = ['age', 'female', 'weight_kg', 'mech_vent', 'hr_first', 'hr_max', 'map_first', 'map_min', 'temp_first',
        'temp_max', 'gcs_first', 'gcs_min', 'bun_first', 'creatinine_first', 'glucose_first', 'hco3_first',
        'hct_first', 'potassium_first', 'sodium_first', 'platelets_first', 'wbc_first', 'magnesium_first',
        'urine_total_ml']


def synthetic_pool(n=2500, seed=1):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({c: rng.lognormal(1, 0.4, n) for c in COLS})
    df['female'] = rng.integers(0, 2, n).astype(float)
    df['mech_vent'] = rng.integers(0, 2, n).astype(float)
    df['icu_type'] = rng.integers(1, 5, n)
    df.insert(0, 'record_id', np.arange(n))
    return df


def make_split(tmp_path, n_datasets=4, n=600, seed=3):
    pool = synthetic_pool()
    inp, ref = tmp_path / 'input', tmp_path / 'reference'
    inp.mkdir(parents=True)
    ref.mkdir()
    rows = []
    settings = dgp.settings_design()
    rng = np.random.default_rng(seed)
    for k in range(n_datasets):
        data, satt, diag = dgp.generate(pool, settings[k % len(settings)], rng, n=n)
        did = f'd{k:07x}'
        (inp / did).mkdir()
        data.to_csv(inp / did / 'data.csv', index=False)
        rows.append({'dataset_id': did, 'satt': satt})
    pd.DataFrame(rows).to_csv(ref / 'truth.csv', index=False, float_format='%.10g')
    return inp, ref, {r['dataset_id']: r['satt'] for r in rows}


def write_est(out, entries, estimand='SATT'):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'estimates.json').write_text(json.dumps({'estimand': estimand, 'datasets': entries}))


# ----------------------------------------------------------------------------- DGP
def test_design_is_balanced_fractional_factorial():
    s = dgp.settings_design()
    assert len(s) == 16 and len(set(s)) == 16
    for knob in dgp.KNOBS:
        values = [getattr(x, knob) for x in s]
        assert len(set(values)) == 2 and values.count(values[0]) == 8


def test_dgp_truth_is_mean_effect_on_treated_and_reproducible():
    pool = synthetic_pool()
    setting = dgp.settings_design()[5]
    a = dgp.generate(pool, setting, np.random.default_rng(7), n=800)
    b = dgp.generate(pool, setting, np.random.default_rng(7), n=800)
    pd.testing.assert_frame_equal(a[0], b[0])
    assert a[1] == b[1]
    data, satt, diag = a
    assert set(data['z'].unique()) <= {0, 1} and 0.15 < data['z'].mean() < 0.85
    assert math_isfinite(satt) and diag['max_e_treated'] <= 0.95 + 1e-12
    assert 'record_id' not in data.columns


def math_isfinite(x):
    return bool(np.isfinite(x))


# ----------------------------------------------------------------------------- grader
def test_truth_as_estimate_passes_every_part(tmp_path):
    inp, ref, truth = make_split(tmp_path)
    write_est(tmp_path / 'out', {d: {'estimate': t, 'ci_lower': t - 0.01, 'ci_upper': t + 0.01} for d, t in truth.items()})
    g = grader.grade_cohort(tmp_path / 'out', inp, ref)
    assert g['valid'] and all(g['gate'].values()) and g['quality'] == pytest.approx(1.0)
    assert g['metrics']['coverage'] == 1.0 and g['metrics']['rmse_sd'] < 1e-8


def test_wide_intervals_fail_length_and_biased_estimates_fail(tmp_path):
    inp, ref, truth = make_split(tmp_path)
    sds = {d: grader.outcome_sd(inp / d / 'data.csv') for d in truth}
    write_est(tmp_path / 'wide', {d: {'estimate': t, 'ci_lower': t - 5 * sds[d], 'ci_upper': t + 5 * sds[d]}
                                  for d, t in truth.items()})
    g = grader.grade_cohort(tmp_path / 'wide', inp, ref)
    assert g['valid'] and g['gate'] == {'coverage': True, 'rmse': True, 'bias': True, 'interval_length': False}
    write_est(tmp_path / 'off', {d: {'estimate': t + 0.3 * sds[d], 'ci_lower': t + 0.29 * sds[d],
                                     'ci_upper': t + 0.31 * sds[d]} for d, t in truth.items()})
    g = grader.grade_cohort(tmp_path / 'off', inp, ref)
    assert g['valid'] and not g['gate']['coverage'] and not g['gate']['rmse'] and not g['gate']['bias']
    assert abs(g['metrics']['bias_sd'] - 0.3) < 1e-9


@pytest.mark.parametrize('mutate,needle', [
    (lambda e: e.pop(next(iter(e))), 'missing'),
    (lambda e: e[next(iter(e))].update(estimate=float('nan')), 'finite'),
    (lambda e: e[next(iter(e))].update(ci_lower=1e9), 'ci_lower <= estimate'),
    (lambda e: e[next(iter(e))].update(estimate='1.0'), 'finite'),
])
def test_malformed_outputs_are_invalid(tmp_path, mutate, needle):
    inp, ref, truth = make_split(tmp_path, n_datasets=2)
    entries = {d: {'estimate': t, 'ci_lower': t - 1, 'ci_upper': t + 1} for d, t in truth.items()}
    mutate(entries)
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'estimates.json').write_text(json.dumps({'estimand': 'SATT', 'datasets': entries}).replace('NaN', 'NaN'))
    g = grader.grade_cohort(out, inp, ref)
    assert not g['valid'] and needle in g['reason']


def test_wrong_estimand_and_symlink_refused(tmp_path):
    inp, ref, truth = make_split(tmp_path, n_datasets=2)
    write_est(tmp_path / 'ate', {d: {'estimate': t, 'ci_lower': t, 'ci_upper': t} for d, t in truth.items()}, 'ATE')
    assert 'estimand' in grader.grade_cohort(tmp_path / 'ate', inp, ref)['reason']
    link = tmp_path / 'link'
    link.mkdir()
    os.symlink(tmp_path / 'ate' / 'estimates.json', link / 'estimates.json')
    g = grader.grade_cohort(link, inp, ref)
    assert not g['valid'] and 'not_regular_file' in g['reason']


# ----------------------------------------------------------------------------- comparators and verifier
def _run_method(method, inp, out):
    sys.path.insert(0, str(ORACLE))
    try:
        import estimate
        estimate.main(method, inp, out)
    finally:
        sys.path.remove(str(ORACLE))


def test_comparators_write_valid_outputs(tmp_path):
    inp, ref, truth = make_split(tmp_path, n_datasets=3)
    for method in ('naive', 'ols', 'dr_att'):
        _run_method(method, inp, tmp_path / method)
        g = grader.grade_cohort(tmp_path / method, inp, ref)
        assert g['valid'], (method, g['reason'])


def test_gate_constants_match_readme():
    readme = (REPO / 'suite' / 'families' / 'causal_ate' / 'README.md').read_text()
    assert f"{GATE['rmse']['max']:.2f}" in readme and f"{GATE['bias']['max_abs']:.2f}" in readme
    assert f"{GATE['interval_length']['max_mean']:.2f}" in readme and '41 of 48' in readme
    assert f"{GATE['time_limit_s']} seconds" in readme and N_HIDDEN == 48
    assert int(np.ceil(GATE['coverage']['min'] * N_HIDDEN)) == 41


def test_export_hides_truth_dgp_and_runs_oracle(tmp_path, monkeypatch):
    """A miniature export through the shared exporter: no hidden data, hidden truth or DGP code on the
    agent side; the verifier grades the oracle end to end (cohort mode)."""
    dev_in, dev_ref, _ = make_split(tmp_path / 'dev', n_datasets=2)
    hid = tmp_path / 'hidden' / 'cohort'
    hid.mkdir(parents=True)
    h_in, h_ref, _ = make_split(hid, n_datasets=3, seed=11)
    public = tmp_path / 'public'
    (public / 'dev').mkdir(parents=True)
    shutil.copytree(dev_in, public / 'dev' / 'input')
    shutil.copytree(dev_ref, public / 'dev' / 'reference')
    (public / 'README.md').write_text('x')
    spec_dir = tmp_path / 'specialist'
    _run_method('dr_att', h_in, spec_dir / 'cohort')
    (spec_dir / 'runtime.json').write_text(json.dumps({'wall_seconds': {'cohort': 1.0}}))
    from suite.families.causal_ate import spec as spec_mod
    spec = export.FamilySpec(
        family='causal_ate', task_id='causal-test', title='t', readme_md='r', output_format_md=spec_mod.OUTPUT_FORMAT,
        grader_module='suite.families.causal_ate.grader', public_dir=public, hidden_cases={'cohort': hid},
        oracle_pipeline_dir=ORACLE, specialist_results_dir=spec_dir, time_limit_seconds=300, cpus=2,
        packages=export.family_packages('causal_ate')[0], grading='cohort')
    task = export.export_task(spec, tmp_path / 'dist')
    agent_side = [p for p in (task / 'environment').rglob('*') if p.is_file()] + [task / 'instruction.md']
    assert not any('datagen' in str(p) or p.name == 'dgp.py' for p in task.rglob('*'))
    for p in agent_side:
        assert p.read_bytes() != (h_ref / 'truth.csv').read_bytes()
    assert not (task / 'environment' / 'data' / 'hidden').exists()
    text = (task / 'instruction.md').read_text()
    assert 'whole hidden set in one call' in text
    logs, work = tmp_path / 'logs', tmp_path / 'work'
    reward, metrics = grading.grade_task(task / 'tests', task / 'solution' / 'pipeline', logs, work, sandbox_root=None,
                                         pipeline_path=os.path.dirname(sys.executable) + ':/usr/bin:/bin')
    assert reward['ran'] == 1.0 and reward['valid'] == 1.0 and reward['within_time'] == 1.0
    assert set(metrics['gate']) == {'coverage', 'rmse', 'bias', 'interval_length'}
    assert metrics['specialist']['valid'] == 1.0
