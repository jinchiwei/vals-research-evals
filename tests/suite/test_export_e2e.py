"""Export the toy task, validate it with the platform parsers, then run every toy pipeline
through the exported grader (tests/grade.py -> vendored suite.core) without Docker.

The platform checks call exp/suite-platform-probe/check_taskconfig.py and
scripts/validate_exports.py with .venv-valkyrie (skipped if that venv or the pinned Tracker
source in /tmp is absent). Privilege drop and network isolation need a root verifier sandbox
and are not exercised here.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from suite.core import export as E
from suite.core.reward import REWARD_KEYS
from suite.families.toy import pipelines
from suite.families.toy.spec import build_spec

REPO = Path(__file__).resolve().parents[2]
VALKYRIE_PY = REPO / '.venv-valkyrie' / 'bin' / 'python'
TRACKER_CONFIG = Path('/tmp/valkyrie-inspect-20261114/services/tracker/src/tracker/services/datasets/config.py')
PATH = f'{Path(sys.executable).parent}:/usr/bin:/bin'
TASK_ID = 'toy-sphere-volume-0001'


@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    root = tmp_path_factory.mktemp('toy')
    os.environ['SUITE_PIPELINE_PATH'] = PATH       # specialist run at export time uses this env's python
    spec = build_spec(root / 'work')
    task = E.export_task(spec, root / 'dist')
    for kind in ('slow', 'wrong_geometry', 'wrong_units'):
        pipelines.write_pipeline(kind, root / 'pipelines' / kind)
    return {'root': root, 'task': task, 'spec': spec, 'pipelines': {
        'oracle': task / 'solution' / 'pipeline',
        **{k: root / 'pipelines' / k for k in ('slow', 'wrong_geometry', 'wrong_units')}}}


def grade(exported, pipeline_dir, name, *extra):
    root, task = exported['root'], exported['task']
    logs, work = root / 'runs' / name / 'logs', root / 'runs' / name / 'eval'
    proc = subprocess.run([sys.executable, '-I', '-B', str(task / 'tests' / 'grade.py'),
                           '--tests', str(task / 'tests'), '--pipeline', str(pipeline_dir), '--logs', str(logs),
                           '--work', str(work), '--sandbox-root', 'none', '--pipeline-path', PATH, *extra],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    reward = json.loads((logs / 'reward.json').read_text())
    assert list(reward) == list(REWARD_KEYS)
    metrics = json.loads((logs / 'metrics.json').read_text())
    return reward, metrics, proc.stdout


# ----------------------------------------------------------------- structure and platform parsers

def test_layout_and_isolation(exported):
    task = exported['task']
    for rel in ('task.toml', 'instruction.md', 'environment/Dockerfile', 'tests/test.sh', 'tests/grade.py',
                'tests/task_config.json', 'solution/solve.sh', 'solution/pipeline/run.sh',
                'tests/specialist/runtime.json', 'tests/lib/suite/core/grading.py', 'tests/lib/pcnsl/imaging_eval.py',
                'tests/lib/suite/families/toy/grader.py'):
        assert (task / rel).is_file(), rel
    env_files = [p.name for p in (task / 'environment').rglob('*') if p.is_file()]
    assert 'measurements.json' in env_files                   # dev references are public
    hidden = set(os.listdir(task / 'tests' / 'hidden'))
    assert len(hidden) == 3 and not hidden & set(os.listdir(task / 'environment' / 'data' / 'dev'))
    assert '/opt/benchmark-venv' in (task / 'environment' / 'Dockerfile').read_text()
    assert 'timing you report yourself is ignored' in (task / 'instruction.md').read_text().lower()
    manifest = E.task_manifest(task)
    assert all(v['audience'] == 'verifier' for k, v in manifest.items() if '/hidden/' in k)
    E.check_no_leak(task)


@pytest.mark.skipif(not (VALKYRIE_PY.exists() and TRACKER_CONFIG.exists()), reason='.venv-valkyrie or Tracker source missing')
def test_platform_parsers_accept_task(exported):
    dist = exported['task'].parent
    out = subprocess.run([str(VALKYRIE_PY), '-I', str(REPO / 'exp/suite-platform-probe/check_taskconfig.py'), str(dist)],
                         capture_output=True, text=True, check=True).stdout
    assert f'{TASK_ID} problems [] separate True agent allowlist [\'api.anthropic.com\']' in out
    assert 'verifier no-network' in out and "artifacts ['/workspace/output']" in out
    val = subprocess.run([str(VALKYRIE_PY), str(REPO / 'scripts/validate_exports.py'), str(dist),
                          str(exported['root'] / 'validation')], capture_output=True, text=True)
    assert val.returncode == 0, val.stdout + val.stderr
    report = json.loads((exported['root'] / 'validation' / 'validation.json').read_text())
    assert report['hosted_run'] is False and report['tasks'][0]['problems'] == []


# ----------------------------------------------------------------- leak checks

def test_leak_check_catches_copied_reference(exported, tmp_path):
    task = tmp_path / 'copy'
    shutil.copytree(exported['task'], task)
    case = sorted(os.listdir(task / 'tests' / 'hidden'))[0]
    ref = task / 'tests' / 'hidden' / case / 'reference' / 'mask.nii.gz'
    shutil.copyfile(ref, task / 'environment' / 'data' / 'renamed.bin')
    with pytest.raises(E.ExportLeakError):
        E.check_no_leak(task)
    os.remove(task / 'environment' / 'data' / 'renamed.bin')
    import gzip
    import hashlib
    (task / 'environment' / 'data' / 'regz.nii.gz').write_bytes(gzip.compress(gzip.decompress(ref.read_bytes()), mtime=1))
    with pytest.raises(E.ExportLeakError, match='same content'):
        E.check_no_leak(task)
    os.remove(task / 'environment' / 'data' / 'regz.nii.gz')
    with open(task / 'instruction.md', 'a') as f:
        f.write(hashlib.sha256(ref.read_bytes()).hexdigest() + '\n')
    with pytest.raises(E.ExportLeakError, match='SHA-256'):
        E.check_no_leak(task)


def test_export_refuses_leaky_spec(exported, tmp_path):
    spec = exported['spec']
    leaky_public = tmp_path / 'public'
    shutil.copytree(spec.public_dir, leaky_public)
    case = sorted(spec.hidden_cases)[0]
    shutil.copyfile(Path(spec.hidden_cases[case]) / 'reference' / 'measurements.json', leaky_public / 'answers.json')
    spec2 = E.FamilySpec(**{**spec.__dict__, 'public_dir': leaky_public})
    with pytest.raises(E.ExportLeakError):
        E.export_task(spec2, tmp_path / 'dist')
    assert not (tmp_path / 'dist' / TASK_ID).exists() and not list((tmp_path / 'dist').glob('.*partial*'))


# ----------------------------------------------------------------- end to end: four pipelines

def test_oracle_gets_full_reward(exported):
    reward, metrics, stdout = grade(exported, exported['pipelines']['oracle'], 'oracle')
    assert reward == {k: 1.0 for k in REWARD_KEYS}
    assert all(c['failure'] is None for c in metrics['cases'])
    assert metrics['specialist']['quality'] < 1.0               # the specialist is imperfect
    assert '"summary"' in stdout and len(stdout) < 20_000


def test_slow_pipeline_fails_on_time(exported):
    reward, metrics, _ = grade(exported, exported['pipelines']['slow'], 'slow', '--time-limit', '2')
    assert reward['within_time'] == 0.0 and reward['reward'] == 0.0
    assert reward['ran'] == 1.0 and reward['valid'] == 1.0      # its outputs were fine, just late
    for case in metrics['cases']:
        assert case['failure'] == 'timeout' and case['run']['timed_out']
        assert 2.0 <= case['run']['wall_seconds'] < 5.0         # grader clock, not timing.json's 0.01 s


def test_wrong_geometry_fails_validity(exported):
    reward, metrics, _ = grade(exported, exported['pipelines']['wrong_geometry'], 'geom')
    assert reward['ran'] == 1.0 and reward['valid'] == 0.0 and reward['reward'] == 0.0
    assert reward['quality'] == 0.0
    for case in metrics['cases']:
        assert case['failure'].startswith('invalid: mask geometry') and 'spacing' in case['failure']


def test_wrong_units_fails_clinical_threshold(exported):
    reward, metrics, _ = grade(exported, exported['pipelines']['wrong_units'], 'units')
    assert (reward['ran'], reward['valid'], reward['within_time']) == (1.0, 1.0, 1.0)
    assert reward['clinically_acceptable'] == 0.0 and reward['reward'] == 0.0
    assert reward['quality'] == 1.0                              # mask is perfect; the units are wrong
    for case in metrics['cases']:
        assert case['failure'].startswith('below_clinical_threshold: reported volume')
        assert case['metrics']['reported']['volume_ml']['percent_error'] == pytest.approx(99900, rel=1e-3)


# ----------------------------------------------------------------- grader failure modes

def test_missing_pipeline_scores_zero(exported, tmp_path):
    reward, metrics, _ = grade(exported, tmp_path / 'nothing', 'missing')
    assert reward == {k: 0.0 for k in REWARD_KEYS}
    assert all(c['failure'].startswith('not_run') for c in metrics['cases'])


def test_symlinked_reference_is_not_accepted(exported, tmp_path):
    task = exported['task']
    case = sorted(os.listdir(task / 'tests' / 'hidden'))[0]
    ref = task / 'tests' / 'hidden' / case / 'reference'
    d = tmp_path / 'cheat'
    d.mkdir()
    (d / 'run.sh').write_text(f'#!/bin/bash\nln -s {ref}/mask.nii.gz "$2/mask.nii.gz"\n'
                              f'cp {ref}/measurements.json "$2/measurements.json"\n')
    reward, metrics, _ = grade(exported, d, 'cheat')
    assert reward['valid'] == 0.0 and reward['reward'] == 0.0
    assert 'not_regular_file' in metrics['cases'][0]['failure']


def test_shared_sandbox_is_infrastructure_error(exported, tmp_path):
    (tmp_path / 'solution').mkdir()
    logs = tmp_path / 'logs'
    proc = subprocess.run([sys.executable, '-I', '-B', str(exported['task'] / 'tests' / 'grade.py'),
                           '--tests', str(exported['task'] / 'tests'), '--pipeline', str(exported['pipelines']['oracle']),
                           '--logs', str(logs), '--work', str(tmp_path / 'eval'), '--sandbox-root', str(tmp_path)],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and 'infrastructure_error' in proc.stdout
    assert not (logs / 'reward.json').exists()
