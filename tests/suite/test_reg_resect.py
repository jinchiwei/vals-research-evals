"""reg_resect grader tests on synthetic fixtures (no RESECT data needed).

Run: ~/miniconda3/envs/vals-suite-reg_resect/bin/python -m pytest -q tests/suite/test_reg_resect.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

nib = pytest.importorskip('nibabel')

from suite.core import grading
from suite.families.reg_resect import data as rdata
from suite.families.reg_resect import grader, pipelines
from suite.families.reg_resect import landmarks as lm

PATH = str(Path(sys.executable).parent) + ':/usr/bin:/bin'
SHIFT = np.array([3.0, 0.0, 0.0])            # known brain shift, RAS mm


def _write_us(path):
    """Ultrasound-like volume: 0.5 mm voxels, rotated about z, centred near (+45, -30, +30) RAS so that
    an LPS flip (-x, -y) lands ~90 mm away. Non-zero only inside a cone-like field of view."""
    shape = (80, 80, 80)
    c, s = math.cos(0.3), math.sin(0.3)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]]) * 0.5
    centre = np.array([45.0, -30.0, 30.0])
    affine = np.eye(4)
    affine[:3, :3] = rot
    affine[:3, 3] = centre - rot @ (np.array(shape) / 2)
    ijk = np.indices(shape).astype(float)
    r = np.sqrt((ijk[0] - 40) ** 2 + (ijk[1] - 40) ** 2)
    data = np.where(r < 10 + 0.4 * ijk[2], 50.0 + 10 * np.sin(ijk[0] / 3), 0.0).astype(np.float32)
    nib.save(nib.Nifti1Image(data, affine), str(path))
    return affine


def _make_case(root, n=12, seed=0):
    rng = np.random.default_rng(seed)
    inp, ref = Path(root) / 'input', Path(root) / 'reference'
    inp.mkdir(parents=True)
    ref.mkdir(parents=True)
    _write_us(inp / 'us.nii.gz')
    for name in ('mri_t1.nii.gz', 'mri_flair.nii.gz'):
        nib.save(nib.Nifti1Image(np.zeros((4, 4, 4), np.float32), np.eye(4)), str(inp / name))
    us_pts = np.array([45.0, -30.0, 35.0]) + rng.uniform(-4, 4, (n, 3))   # inside the field of view
    mri_pts = us_pts - SHIFT
    ids = [f'L{i + 1:02d}' for i in range(n)]
    lm.write_csv(inp / 'landmarks_mri.csv', ids, mri_pts)
    lm.write_csv(ref / 'landmarks_us.csv', ids, us_pts)
    return inp, ref, ids, mri_pts, us_pts


@pytest.fixture
def case(tmp_path):
    return _make_case(tmp_path / 'case')


def _grade(tmp_path, case, ids, pts):
    inp, ref = case[0], case[1]
    out = tmp_path / 'out'
    out.mkdir(exist_ok=True)
    lm.write_csv(out / 'landmarks_us.csv', ids, pts)
    return grader.grade_case(out, inp, ref)


def test_known_transform_recovers_known_error(tmp_path, case):
    _, _, ids, mri, us = case
    perfect = _grade(tmp_path, case, ids, mri + SHIFT)
    assert perfect['valid'] and perfect['acceptable']
    assert perfect['metrics']['mean_tre_mm'] == pytest.approx(0.0, abs=1e-3)
    assert perfect['quality'] == pytest.approx(1.0, abs=1e-3)
    off = _grade(tmp_path, case, ids, mri + SHIFT + np.array([0.0, 1.0, 0.0]))    # exactly 1 mm everywhere
    assert off['metrics']['mean_tre_mm'] == pytest.approx(1.0, abs=1e-3)
    assert off['metrics']['initial_mean_tre_mm'] == pytest.approx(3.0, abs=1e-3)
    assert off['acceptable'] and off['quality'] == pytest.approx(math.exp(-0.5), abs=1e-3)
    far = _grade(tmp_path, case, ids, mri + SHIFT + np.array([0.0, 0.0, 2.5]))
    assert far['valid'] and not far['acceptable'] and '>= 2.0 mm' in far['reason']


def test_identity_scores_initial_error_and_fails(tmp_path, case):
    _, _, ids, mri, _ = case
    g = _grade(tmp_path, case, ids, mri)
    assert g['valid'] and not g['acceptable']
    assert g['metrics']['mean_tre_mm'] == pytest.approx(3.0, abs=1e-3)
    assert not g['metrics']['improved']


def test_wrong_coordinate_frame_is_invalid(tmp_path, case):
    _, _, ids, mri, us = case
    g = _grade(tmp_path, case, ids, (mri + SHIFT) * lm.RAS_TO_LPS)
    assert not g['valid'] and g['quality'] == 0.0
    assert 'outside the ultrasound field of view' in g['reason'] and 'LPS' in g['reason']


def test_missing_extra_and_nonfinite_landmarks_are_invalid(tmp_path, case):
    _, _, ids, mri, _ = case
    g = _grade(tmp_path, case, ids[:-1], (mri + SHIFT)[:-1])
    assert not g['valid'] and 'missing' in g['reason']
    g = _grade(tmp_path, case, ids + ['L99'], np.vstack([mri + SHIFT, mri[:1] + SHIFT]))
    assert not g['valid'] and 'extra' in g['reason']
    bad = (mri + SHIFT).copy()
    bad[0, 0] = np.nan
    g = _grade(tmp_path, case, ids, bad)
    assert not g['valid'] and 'non-finite' in g['reason']
    out = tmp_path / 'out'
    (out / 'landmarks_us.csv').write_text('name,x,y,z\nL01,1,2,3\n')
    g = grader.grade_case(out, case[0], case[1])
    assert not g['valid'] and 'header' in g['reason']
    (out / 'landmarks_us.csv').unlink()
    g = grader.grade_case(out, case[0], case[1])
    assert not g['valid']


def test_row_order_does_not_matter(tmp_path, case):
    _, _, ids, mri, _ = case
    g = _grade(tmp_path, case, ids[::-1], (mri + SHIFT)[::-1])
    assert g['valid'] and g['metrics']['mean_tre_mm'] == pytest.approx(0.0, abs=1e-3)


def test_folding_reported_for_dense_field(tmp_path):
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    ok = np.zeros((10, 10, 10, 3), np.float32)
    nib.save(nib.Nifti1Image(ok, affine), str(tmp_path / 'ok.nii.gz'))
    assert grader.folding_fraction(tmp_path / 'ok.nii.gz') == 0.0
    fold = ok.copy()
    fold[..., 0] = -3.0 * np.indices((10, 10, 10))[0] * 2.0      # x -> x - 3x: Jacobian -2
    nib.save(nib.Nifti1Image(fold, affine), str(tmp_path / 'fold.nii.gz'))
    assert grader.folding_fraction(tmp_path / 'fold.nii.gz') == 1.0


def test_tag_parser_and_split_rule(tmp_path):
    tag = tmp_path / 'x.tag'
    tag.write_text('MNI Tag Point File\nVolumes = 2;\n% c\n\nPoints =\n 1 2 3 4 5 6 ""\n -1.5 2e1 3 4 5 6.25 "";\n')
    a, b = lm.read_tag(tag)
    assert a.tolist() == [[1, 2, 3], [-1.5, 20, 3]] and b.tolist() == [[4, 5, 6], [4, 5, 6.25]]
    cands = [{'patient': f'Case{i}', 'initial_mtre_mm': v} for i, v in enumerate([1.0, 2.0, 2.5, 3, 4, 5, 6, 7, 8, 9,
                                                                                     10, 11, 12])]
    s1, s2 = rdata.make_split(cands), rdata.make_split(cands)
    assert s1 == s2                                                     # deterministic for the fixed seed
    assert s1['excluded_initial_below_threshold'] == ['Case0', 'Case1']  # <= 2.0 mm excluded
    assert len(s1['hidden']) == rdata.N_HIDDEN and len(s1['development']) == rdata.N_DEV
    assert not set(s1['hidden']) & set(s1['development'])


def _tests_tree(tmp_path, limit):
    tests = tmp_path / 'tests'
    _make_case(tests / 'hidden' / 'cA', seed=1)
    _make_case(tests / 'hidden' / 'cB', seed=2)
    cfg = {'schema': grading.CONFIG_SCHEMA, 'family': 'reg_resect', 'task_id': 't',
           'grader_module': 'suite.families.reg_resect.grader', 'time_limit_seconds': limit, 'threads': 1,
           'cases': ['cA', 'cB']}
    (tests / 'task_config.json').write_text(json.dumps(cfg))
    return tests


def test_oracle_scores_one_and_timeout_is_enforced(tmp_path):
    tests = _tests_tree(tmp_path, limit=10.0)
    oracle = pipelines.write_pipeline('oracle', tmp_path / 'p_oracle', hidden_root=tests / 'hidden')
    reward, _ = grading.grade_task(tests, oracle, tmp_path / 'logs_o', tmp_path / 'work_o', sandbox_root=None,
                                   pipeline_path=PATH, out=open('/dev/null', 'w'))
    assert reward['reward'] == 1.0 and reward['quality'] == pytest.approx(1.0, abs=1e-3)
    identity = pipelines.write_pipeline('identity', tmp_path / 'p_id')
    reward, metrics = grading.grade_task(tests, identity, tmp_path / 'logs_i', tmp_path / 'work_i', sandbox_root=None,
                                         pipeline_path=PATH, out=open('/dev/null', 'w'))
    assert reward['valid'] == 1.0 and reward['clinically_acceptable'] == 0.0 and reward['reward'] == 0.0
    slow = pipelines.write_pipeline('slow', tmp_path / 'p_slow', hidden_root=tests / 'hidden', sleep_seconds=5)
    reward, metrics = grading.grade_task(tests, slow, tmp_path / 'logs_s', tmp_path / 'work_s', sandbox_root=None,
                                         time_limit_seconds=1.0, pipeline_path=PATH, out=open('/dev/null', 'w'))
    assert reward['within_time'] == 0.0 and reward['reward'] == 0.0
    assert all(c['failure'] == 'timeout' for c in metrics['cases'])
    assert all(c['run']['wall_seconds'] < 4.0 for c in metrics['cases'])   # killed at the limit, not after the sleep
