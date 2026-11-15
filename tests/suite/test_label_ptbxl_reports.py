"""label_ptbxl_reports: direct-answer grader, metrics, export isolation (synthetic data; real export if present)."""
import json
import os
import tomllib
from pathlib import Path

import numpy as np
import pytest

from suite.core.reward import REWARD_KEYS
from suite.families.label_ptbxl_reports import grader, prepare_data, spec

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / 'dist' / 'suite-tasks-label-v1' / 'label_ptbxl_reports' / spec.TASK_ID
IDS = [f'r{i:08x}' for i in range(40)]


def _reference(seed=0):
    rng = np.random.default_rng(seed)
    ref = {}
    for i, rid in enumerate(IDS):
        labs = [c for c in grader.CLASSES if rng.random() < 0.35]
        ref[rid] = labs or [grader.CLASSES[i % 5]]
    return ref


def _tests_dir(tmp_path, ref, specialist):
    t = tmp_path / 'tests'
    (t / 'hidden' / 'cohort' / 'reference').mkdir(parents=True)
    (t / 'specialist').mkdir()
    (t / grader.REFERENCE).write_text(json.dumps(ref))
    (t / grader.SPECIALIST).write_text(json.dumps(specialist))
    (t / 'task_config.json').write_text(json.dumps({'family': spec.FAMILY, 'task_id': 'x', 'hidden_ids': sorted(ref),
                                                    'specialist_name': 's'}))
    return t


def _write(tmp_path, obj, name='labels.json'):
    p = tmp_path / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return p


# ---------------------------------------------------------------------------- parsing


@pytest.mark.parametrize('obj, fragment', [
    ([], 'top level'),
    ({i: ['NORM'] for i in IDS[:-1]}, 'missing'),
    ({**{i: ['NORM'] for i in IDS}, 'rffffffff': ['MI']}, 'unknown'),
    ({**{i: ['NORM'] for i in IDS}, IDS[0]: ['norm']}, 'unknown class'),
    ({**{i: ['NORM'] for i in IDS}, IDS[0]: ['MI', 'MI']}, 'duplicate'),
    ({**{i: ['NORM'] for i in IDS}, IDS[0]: 'MI'}, 'list'),
    ({**{i: ['NORM'] for i in IDS}, IDS[0]: [1]}, 'list'),
])
def test_parse_rejects(obj, fragment):
    labels, reason = grader.parse_labels(json.dumps(obj).encode(), IDS)
    assert labels is None and fragment in reason


def test_parse_rejects_nan_and_bad_utf8():
    text = '{' + ', '.join(f'"{i}": ["NORM"]' for i in IDS) + ', "x": NaN}'
    assert grader.parse_labels(text.encode(), IDS)[0] is None
    assert grader.parse_labels(b'\xff\xfe', IDS)[0] is None


def test_parse_accepts_empty_list_and_any_order():
    obj = {i: ['STTC', 'MI'] for i in IDS}
    obj[IDS[0]] = []
    labels, reason = grader.parse_labels(json.dumps(obj).encode(), IDS)
    assert reason is None and labels[IDS[0]] == frozenset() and labels[IDS[1]] == {'MI', 'STTC'}


# ---------------------------------------------------------------------------- metrics


def test_kappa_and_f1_match_sklearn():
    from sklearn.metrics import cohen_kappa_score, f1_score
    rng = np.random.default_rng(1)
    for _ in range(20):
        y, p = rng.random(200) < 0.3, rng.random(200) < 0.4
        assert grader.cohen_kappa(y, p) == pytest.approx(cohen_kappa_score(y, p))
        assert grader.f1(y, p) == pytest.approx(f1_score(y, p))


def test_kappa_edge_cases():
    y = np.array([1, 0, 1, 0], bool)
    assert grader.cohen_kappa(y, y) == pytest.approx(1.0)
    assert grader.cohen_kappa(y, np.zeros(4, bool)) == pytest.approx(0.0)
    assert grader.cohen_kappa(np.zeros(4, bool), np.zeros(4, bool)) == 0.0     # undefined -> 0


def test_gate_thresholds_inclusive():
    assert all(grader.gate({'min_kappa': 0.60, 'macro_f1': 0.80}).values())
    g = grader.gate({'min_kappa': 0.5999, 'macro_f1': 0.95})
    assert list(g.values()) == [False, True]


# ---------------------------------------------------------------------------- grading end to end


def test_perfect_labels_score_one_and_seven_keys(tmp_path):
    ref = _reference()
    tests = _tests_dir(tmp_path, ref, {i: ['NORM'] for i in IDS})
    reward, metrics = grader.grade(_write(tmp_path, ref), tests)
    assert tuple(reward) == REWARD_KEYS
    assert reward == {'reward': 1.0, 'ran': 1.0, 'valid': 1.0, 'within_time': 1.0, 'clinically_acceptable': 1.0,
                      'quality': 1.0, 'vs_specialist': 1.0}
    assert metrics['gate_fraction'] == 1.0 and metrics['agent']['metrics']['exact_match'] == 1.0


def test_constant_labels_fail_gate(tmp_path):
    ref = _reference()
    tests = _tests_dir(tmp_path, ref, ref)
    reward, metrics = grader.grade(_write(tmp_path, {i: ['NORM'] for i in IDS}), tests)
    assert reward['valid'] == 1.0 and reward['clinically_acceptable'] == 0.0 and reward['reward'] == 0.0
    assert 0.0 < reward['quality'] < 0.5 and reward['vs_specialist'] == reward['quality']
    assert metrics['agent']['metrics']['min_kappa'] == 0.0


def test_invalid_missing_and_symlink(tmp_path):
    ref = _reference()
    tests = _tests_dir(tmp_path, ref, ref)
    bad = _write(tmp_path, {i: ['NORM'] for i in IDS[:-1]}, 'bad.json')
    r, m = grader.grade(bad, tests)
    assert (r['ran'], r['valid'], r['reward'], r['quality']) == (1.0, 0.0, 0.0, 0.0)
    assert 'missing' in m['agent']['reason']
    r, _ = grader.grade(tmp_path / 'absent.json', tests)
    assert r == {k: 0.0 for k in REWARD_KEYS}
    good = _write(tmp_path, ref, 'good.json')
    link = tmp_path / 'link.json'
    link.symlink_to(good)
    r, m = grader.grade(link, tests)
    assert r['ran'] == 0.0 and 'symlink' in m['agent']['reason']


def test_main_writes_reward_and_refuses_shared_sandbox(tmp_path):
    ref = _reference()
    tests = _tests_dir(tmp_path, ref, ref)
    labels = _write(tmp_path, ref)
    logs = tmp_path / 'logs'
    assert grader.main(['--tests', str(tests), '--labels', str(labels), '--logs', str(logs), '--sandbox-root', 'none']) == 0
    assert json.loads((logs / 'reward.json').read_text())['reward'] == 1.0
    root = tmp_path / 'root'
    (root / 'solution').mkdir(parents=True)
    assert grader.main(['--tests', str(tests), '--labels', str(labels), '--logs', str(tmp_path / 'l2'),
                        '--sandbox-root', str(root)]) == 2
    assert not (tmp_path / 'l2' / 'reward.json').exists()


def test_reference_ids_must_match_config(tmp_path):
    ref = _reference()
    tests = _tests_dir(tmp_path, ref, ref)
    cfg = json.loads((tests / 'task_config.json').read_text())
    cfg['hidden_ids'] = cfg['hidden_ids'][:-1]
    (tests / 'task_config.json').write_text(json.dumps(cfg))
    with pytest.raises(grader.InfrastructureError):
        grader.grade(_write(tmp_path, ref), tests)


# ---------------------------------------------------------------------------- data selection helpers


def test_placeholder_reports_have_no_text():
    assert not prepare_data.has_text('trace only requested.')
    assert not prepare_data.has_text('  ')
    assert not prepare_data.has_text(float('nan'))
    assert prepare_data.has_text('sinusrhythmus lagetyp normal normales ekg')


def test_superclass_rule_ignores_likelihood():
    diag = {'IMI': 'MI', 'LVH': 'HYP', 'NDT': 'STTC'}
    assert prepare_data.superclasses("{'IMI': 15.0, 'SR': 0.0, 'LVH': 0.0}", diag) == ['MI', 'HYP']
    assert prepare_data.superclasses("{'SR': 0.0}", diag) == []


# ---------------------------------------------------------------------------- exported task (if built)


needs_dist = pytest.mark.skipif(not DIST.is_dir(), reason='dist/suite-tasks-label-v1 not exported')


@needs_dist
def test_export_isolation_and_contract():
    from suite.core.export import check_no_leak
    check_no_leak(DIST)
    spec.family_checks(DIST)
    ref = json.loads((DIST / 'tests' / grader.REFERENCE).read_text())
    assert len(ref) == 500
    env_files = {p.relative_to(DIST / 'environment').as_posix() for p in (DIST / 'environment').rglob('*') if p.is_file()}
    assert env_files == {'Dockerfile', 'data/README.md', 'data/LICENSE.txt', 'data/dev_reports.csv',
                         'data/hidden_reports.csv', 'data/diagnostic_statements.csv'}
    hidden_csv = (DIST / 'environment' / 'data' / 'hidden_reports.csv').read_text()
    assert hidden_csv.splitlines()[0] == 'record_id,report'
    for c in grader.CLASSES:      # no label column for hidden reports
        assert f',{c}' not in hidden_csv.splitlines()[0]
    instruction = (DIST / 'instruction.md').read_text()
    assert '/workspace/output/labels.json' in instruction and '45 minutes' in instruction
    toml = tomllib.loads((DIST / 'task.toml').read_text())
    assert toml['agent']['timeout_sec'] == spec.AGENT_TIMEOUT_SEC
    assert toml['verifier']['environment_mode'] == 'separate' and toml['verifier']['network_mode'] == 'no-network'


@needs_dist
def test_export_stored_specialist_matches_expected_reward(tmp_path):
    tests = DIST / 'tests'
    reward, metrics = grader.grade(tests / grader.SPECIALIST, tests)
    toml = tomllib.loads((DIST / 'task.toml').read_text())
    assert reward['reward'] == toml['metadata']['oracle_expected_reward']
    assert reward['vs_specialist'] == 1.0 and reward['valid'] == 1.0
    assert metrics['agent']['metrics']['macro_f1'] == pytest.approx(0.7353, abs=1e-4)


def test_family_checks_catch_hidden_id_in_dev(tmp_path):
    task = tmp_path / 'task'
    data = task / 'environment' / 'data'
    data.mkdir(parents=True)
    (task / 'solution').mkdir()
    (task / 'instruction.md').write_text('x')
    (task / 'tests' / 'hidden' / 'cohort' / 'reference').mkdir(parents=True)
    (task / 'tests' / grader.REFERENCE).write_text(json.dumps({'r1': ['MI']}))
    (data / 'hidden_reports.csv').write_text('record_id,report\nr1,text\n')
    (data / 'dev_reports.csv').write_text('record_id,report,NORM,MI,STTC,CD,HYP\nr1,text,0,1,0,0,0\n')
    with pytest.raises(Exception, match='hidden IDs appear among development rows'):
        spec.family_checks(task)
    (data / 'dev_reports.csv').write_text('record_id,report,NORM,MI,STTC,CD,HYP\nr2,text,0,1,0,0,0\n')
    (data / 'notes.txt').write_text('ecg_id 123')
    with pytest.raises(Exception, match='ecg_id'):
        spec.family_checks(task)
    os.remove(data / 'notes.txt')
    spec.family_checks(task)
