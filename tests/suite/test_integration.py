"""Integration tests for the suite core: export path handling, the cohort grading hook,
per-family image packages, and the cohort family plug-ins (synthetic data only, no Docker).

    ~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite/test_integration.py -q
"""
import csv
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from suite.core import export as E
from suite.core import grading
from suite.core.reward import REWARD_KEYS

REPO = Path(__file__).resolve().parents[2]
PATH = f'{Path(sys.executable).parent}:/usr/bin:/bin'


# ----------------------------------------------------------------- export: paths and specialist outputs

def test_relative_export_paths_fill_specialist(tmp_path, monkeypatch):
    """Regression: a relative output path used to leave tests/specialist/<case>/ empty (the specialist
    pipeline runs with cwd = a fresh home), so the specialist scored 0."""
    from suite.families.toy.spec import build_spec
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SUITE_PIPELINE_PATH', PATH)
    spec = build_spec('work')                                   # relative work dir too
    task = E.export_task(spec, 'dist')
    assert task.is_absolute() and task == (tmp_path / 'dist' / spec.task_id)
    cases = json.loads((task / 'tests' / 'task_config.json').read_text())['cases']
    runtime = json.loads((task / 'tests' / 'specialist' / 'runtime.json').read_text())['wall_seconds']
    for case in cases:
        for name in ('mask.nii.gz', 'measurements.json'):
            assert (task / 'tests' / 'specialist' / case / name).stat().st_size > 0, (case, name)
        assert runtime[case] > 0


def test_export_fails_loudly_without_specialist_outputs(tmp_path, monkeypatch):
    from suite.families.toy.spec import build_spec
    monkeypatch.setenv('SUITE_PIPELINE_PATH', PATH)
    spec = build_spec(tmp_path / 'work')
    empty = tmp_path / 'specialist'
    empty.mkdir()
    (empty / 'runtime.json').write_text(json.dumps({'wall_seconds': {}}))
    spec2 = E.FamilySpec(**{**spec.__dict__, 'specialist_pipeline_dir': None, 'specialist_results_dir': empty})
    with pytest.raises(E.ExportError, match='specialist'):
        E.export_task(spec2, tmp_path / 'dist')
    assert not (tmp_path / 'dist' / spec.task_id).exists() and not list((tmp_path / 'dist').glob('.*partial*'))
    # one case present but its measurements.json missing, and no runtime entry: still refused
    case = sorted(spec.hidden_cases)[0]
    (empty / case).mkdir()
    (empty / case / 'mask.nii.gz').write_bytes(b'x')
    with pytest.raises(E.ExportError, match='measurements.json missing'):
        E.export_task(spec2, tmp_path / 'dist')


# ----------------------------------------------------------------- per-family image packages

def test_family_packages_and_dockerfile():
    for family in ('risk_icu', 'ecg_ptbxl'):
        pins, _ = E.family_packages(family)
        names = {E._import_name(p) for p in pins}
        assert {'numpy', 'scipy'} <= names
        assert not names & {'SimpleITK', 'nibabel', 'skimage'}, family
    pins, index = E.family_packages('ecg_ptbxl')
    spec = types.SimpleNamespace(packages=pins, pip_extra_index_url=index, threads=None, cpus=4, family='ecg_ptbxl')
    text = E.dockerfile(spec)
    pip_lines = [ln for ln in text.splitlines() if ln.startswith('RUN') and 'pip install' in ln]
    assert len(pip_lines) == 1 and '/opt/benchmark-venv/bin/python -m pip install' in pip_lines[0]
    assert '--extra-index-url=https://download.pytorch.org/whl/cpu' in pip_lines[0]
    tokens = pip_lines[0].split('pip install --no-cache-dir ', 1)[1].split()
    assert [t for t in tokens if not t.startswith('-')] == list(pins)       # what the pilot runner reads
    assert 'SimpleITK' not in text and 'import numpy, scipy, pandas, sklearn, torch' in text
    with pytest.raises(ValueError, match='pip options'):
        E.dockerfile(types.SimpleNamespace(**{**spec.__dict__, 'packages': pins + ('--index-url', 'x')}))
    with pytest.raises(ValueError, match='verifier dependencies'):
        E.dockerfile(types.SimpleNamespace(**{**spec.__dict__, 'packages': ('pandas==2.2.3',)}))


def test_cohort_graders_import_without_imaging_libraries():
    """risk_icu and ecg_ptbxl images carry no nibabel/SimpleITK/scikit-image: their vendored graders
    (and suite.core.grading) must import without them."""
    code = ("import sys\n"
            "for m in ('nibabel', 'SimpleITK', 'skimage', 'pandas', 'sklearn', 'torch'):\n"
            "    sys.modules[m] = None\n"
            "import suite.core.grading\n"
            "import suite.families.risk_icu.grader as r, suite.families.ecg_ptbxl.grader as e\n"
            "assert r.GRADING == e.GRADING == 'cohort'\n")
    proc = subprocess.run([sys.executable, '-c', code], cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


# ----------------------------------------------------------------- cohort hook in suite.core.grading

def _fake_cohort_family():
    """Gate parts come from the pipeline's own parts.json (the core's plumbing is what is tested)."""
    mod = types.ModuleType('suite_test_cohort_family')
    mod.GRADING = 'cohort'
    mod.REQUIRED_OUTPUTS = ('parts.json',)
    mod.CLINICAL_THRESHOLD = 'all of p1, p2, p3'

    def grade_cohort(output_dir, input_dir, reference_dir):
        n = len((Path(input_dir) / 'records.txt').read_text().split())
        parts = json.loads((Path(output_dir) / 'parts.json').read_text())
        if parts.get('n') != n:
            return {'valid': False, 'quality': 0.0, 'reason': 'wrong record count', 'gate': {}, 'metrics': {}}
        gate = {k: bool(parts[k]) for k in ('p1', 'p2', 'p3')}
        return {'valid': True, 'quality': sum(gate.values()) / 3, 'reason': None, 'gate': gate,
                'metrics': {'n_records': n}}
    mod.grade_cohort = grade_cohort
    return mod


def _cohort_tests_dir(root, specialist_parts, hard_kill=None):
    tests = root / 'tests'
    (tests / 'hidden' / 'cohort' / 'input').mkdir(parents=True)
    (tests / 'hidden' / 'cohort' / 'reference').mkdir()
    (tests / 'hidden' / 'cohort' / 'input' / 'records.txt').write_text('a b c d\n')
    (tests / 'hidden' / 'cohort' / 'reference' / 'labels.txt').write_text('1 0 1 0\n')
    (tests / 'specialist' / 'cohort').mkdir(parents=True)
    (tests / 'specialist' / 'cohort' / 'parts.json').write_text(json.dumps({'n': 4, **specialist_parts}))
    (tests / 'specialist' / 'runtime.json').write_text(json.dumps({'wall_seconds': {'cohort': 1.0}}))
    (tests / 'task_config.json').write_text(json.dumps({
        'schema': grading.CONFIG_SCHEMA, 'family': 'fake', 'task_id': 'fake-cohort-0001',
        'grader_module': 'suite_test_cohort_family', 'cases': ['cohort'], 'grading': 'cohort',
        'time_limit_seconds': 2.0, 'hard_kill_seconds': hard_kill or 2.0, 'threads': 1}))
    return tests


def _pipeline(root, name, parts, sleep=0.0):
    d = root / name
    d.mkdir()
    (d / 'run.sh').write_text(f'#!/bin/bash\nsleep {sleep}\necho \'{json.dumps(parts)}\' > "$2/parts.json"\n')
    return d


@pytest.fixture
def cohort_family(monkeypatch):
    monkeypatch.setitem(sys.modules, 'suite_test_cohort_family', _fake_cohort_family())


def _run(root, tests, pipe, name):
    run = root / 'runs' / name
    with open(os.devnull, 'w') as sink:
        reward, _ = grading.grade_task(tests, pipe, run / 'logs', run / 'work', sandbox_root=None,
                                       pipeline_path=PATH, out=sink)
    on_disk = json.loads((run / 'logs' / 'reward.json').read_text())
    assert list(on_disk) == list(REWARD_KEYS) and on_disk == reward
    return reward, json.loads((run / 'logs' / 'metrics.json').read_text())


def test_cohort_all_parts_met_scores_one(tmp_path, cohort_family):
    tests = _cohort_tests_dir(tmp_path, {'p1': True, 'p2': True, 'p3': False})
    pipe = _pipeline(tmp_path, 'good', {'n': 4, 'p1': True, 'p2': True, 'p3': True})
    reward, m = _run(tmp_path, tests, pipe, 'good')
    assert reward == {k: 1.0 for k in REWARD_KEYS}            # specialist misses p3, so vs_specialist caps at 1
    assert m['grading'] == 'cohort' and m['gate'] == {'p1': True, 'p2': True, 'p3': True} and m['gate_fraction'] == 1.0
    assert m['specialist']['gate_fraction'] == pytest.approx(2 / 3) and m['specialist']['clinically_acceptable'] == 0.0
    assert m['specialist']['reward_if_on_time'] == 0.0


def test_cohort_partial_gate_earns_nothing(tmp_path, cohort_family):
    tests = _cohort_tests_dir(tmp_path, {'p1': True, 'p2': True, 'p3': True})
    pipe = _pipeline(tmp_path, 'partial', {'n': 4, 'p1': True, 'p2': True, 'p3': False})
    reward, m = _run(tmp_path, tests, pipe, 'partial')
    assert (reward['ran'], reward['valid'], reward['within_time']) == (1.0, 1.0, 1.0)
    assert reward['clinically_acceptable'] == 0.0 and reward['reward'] == 0.0
    assert reward['quality'] == pytest.approx(2 / 3) and reward['vs_specialist'] == pytest.approx(2 / 3)
    assert m['gate_fraction'] == pytest.approx(2 / 3) and m['gate']['p3'] is False
    assert m['cases'][0]['failure'].startswith('below_clinical_threshold') and 'p3' in m['cases'][0]['failure']
    assert m['summary']['gate_fraction'] == pytest.approx(2 / 3) and m['specialist']['reward_if_on_time'] == 1.0


def test_cohort_invalid_and_late(tmp_path, cohort_family):
    tests = _cohort_tests_dir(tmp_path, {'p1': True, 'p2': True, 'p3': True}, hard_kill=8.0)
    bad = _pipeline(tmp_path, 'bad', {'n': 3, 'p1': True, 'p2': True, 'p3': True})
    reward, m = _run(tmp_path, tests, bad, 'bad')
    assert reward['ran'] == 1.0 and reward['valid'] == 0.0 and reward['reward'] == 0.0
    assert m['gate'] == {} and m['gate_fraction'] == 0.0
    late = _pipeline(tmp_path, 'late', {'n': 4, 'p1': True, 'p2': True, 'p3': True}, sleep=3)
    reward, m = _run(tmp_path, tests, late, 'late')        # after the 2 s limit, before the 8 s hard kill
    assert reward['ran'] == 1.0 and reward['valid'] == 1.0 and reward['within_time'] == 0.0
    assert reward['clinically_acceptable'] == 1.0 and reward['reward'] == 0.0
    assert m['cases'][0]['failure'].startswith('over_time_limit') and not m['cases'][0]['run']['timed_out']


def test_cohort_config_errors(tmp_path, cohort_family):
    tests = _cohort_tests_dir(tmp_path, {'p1': True, 'p2': True, 'p3': True})
    cfg = json.loads((tests / 'task_config.json').read_text())
    (tests / 'task_config.json').write_text(json.dumps({**cfg, 'cases': ['cohort', 'other']}))
    with pytest.raises(grading.InfrastructureError, match='exactly one'):
        grading.grade_task(tests, tmp_path, tmp_path / 'l1', tmp_path / 'w1', sandbox_root=None)
    (tests / 'task_config.json').write_text(json.dumps({**cfg, 'grader_module': 'suite.families.toy.grader'}))
    with pytest.raises(grading.InfrastructureError, match='grade_cohort'):
        grading.grade_task(tests, tmp_path, tmp_path / 'l2', tmp_path / 'w2', sandbox_root=None)


def test_relative_grading_paths(tmp_path, cohort_family, monkeypatch):
    """Regression: relative --work/--pipeline paths made run.sh unreachable from the pipeline's cwd."""
    _cohort_tests_dir(tmp_path, {'p1': True, 'p2': True, 'p3': True})
    _pipeline(tmp_path, 'good', {'n': 4, 'p1': True, 'p2': True, 'p3': True})
    monkeypatch.chdir(tmp_path)
    with open(os.devnull, 'w') as sink:
        reward, _ = grading.grade_task('tests', 'good', 'runs/rel/logs', 'runs/rel/work', sandbox_root=None,
                                       pipeline_path=PATH, out=sink)
    assert reward['reward'] == 1.0


# ----------------------------------------------------------------- cohort family plug-ins

def test_ecg_grade_cohort(tmp_path, monkeypatch):
    from suite.families.ecg_ptbxl import grader as eg
    monkeypatch.setattr(eg, 'N_BOOT', 0)
    rng = np.random.default_rng(1)
    n = 400
    Y = (rng.random((n, 5)) < 0.3).astype(int)
    ids = [f'h{i:05x}' for i in range(n)]
    ref = tmp_path / 'reference'
    ref.mkdir()
    with open(ref / 'reference.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record_id', *eg.G.CLASSES, 'sex', 'age', 'age_band'])
        for i, r in enumerate(ids):
            w.writerow([r, *Y[i], 'MF'[i % 2], 60, ['age<55', 'age55-69', 'age>=70'][i % 3]])
    out = tmp_path / 'out'
    out.mkdir()
    P = np.clip(0.8 * Y + 0.1 + 0.05 * rng.standard_normal(Y.shape), 0, 1)
    with open(out / 'predictions.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record_id', *eg.G.CLASSES])
        w.writerows([[r, *P[i]] for i, r in enumerate(ids)])
    g = eg.grade_cohort(out, tmp_path, ref)
    assert g['valid'] and set(g['gate']) == {'mi_operating_point', 'calibration', 'subgroup_gap'}
    assert 0 < g['quality'] <= 1 and g['metrics']['gate_fraction_met'] == eg.G.gate_fraction(g['gate'])
    os.remove(out / 'predictions.csv')
    os.symlink(ref / 'reference.csv', out / 'predictions.csv')
    g = eg.grade_cohort(out, tmp_path, ref)
    assert not g['valid'] and 'regular file' in g['reason']


def test_risk_icu_and_triage_declare_cohort_grading():
    from suite.families.risk_icu import grader as rg
    from suite.families.triage_pharyngitis import grader as tg
    for mod in (rg, tg):
        assert mod.GRADING == 'cohort' and callable(mod.grade_cohort) and mod.REQUIRED_OUTPUTS


# ----------------------------------------------------------------- suite manifest

MANIFEST = REPO / 'docs' / 'research' / 'suite' / 'task-manifest.json'


@pytest.mark.skipif(not MANIFEST.exists(), reason='task manifest not written yet')
def test_task_manifest_fields():
    rows = json.loads(MANIFEST.read_text())['tasks']
    families = {r['family'] for r in rows}
    assert {'reg_resect', 'seg_spleen', 'measure_hc18', 'ecg_ptbxl', 'risk_icu', 'triage_pharyngitis', 'toy'} <= families
    for r in rows:
        for key in ('task_id', 'tier', 'data_licence', 'n_development', 'n_hidden', 'limits', 'resources',
                    'expected_solution_reward', 'specialist_reward', 'specialist_headline', 'bytes', 'sha256', 'scored'):
            assert key in r, (r['task_id'], key)
        assert 0.0 <= r['expected_solution_reward'] <= 1.0
    triage = [r for r in rows if r['family'] == 'triage_pharyngitis']
    assert triage and not any(r['scored'] for r in triage)
