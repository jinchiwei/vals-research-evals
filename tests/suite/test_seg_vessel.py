"""seg_vessel family: metrics, mask validation, per-image observer bar, core grading end to end.

Synthetic images only (no CHASE_DB1 data needed). The data-backed checks (export, leak check, oracle
reward) are in docs/research/suite/seg_vessel.md and run against /home/jkwei/data/vals-suite/seg_vessel.
"""
import json
import os
import stat
from pathlib import Path

import numpy as np
import pytest

PIL = pytest.importorskip('PIL')
pytest.importorskip('skimage')
from PIL import Image  # noqa: E402

from suite.core import grading  # noqa: E402
from suite.families.seg_vessel import grader  # noqa: E402

W, H = 120, 100


def tree():
    m = np.zeros((H, W), bool)
    m[48:52, 5:115] = True          # trunk, 4 px wide
    m[10:90, 60:62] = True          # branch, 2 px wide
    m[20:22, 20:50] = True          # thin twig
    return m


def write_png(path, arr, mode='L'):
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == '1':
        Image.fromarray(arr.astype(bool)).convert('1').save(path)
    else:
        Image.fromarray(arr.astype(np.uint8), mode=mode).save(path)


def make_case(root, bar=(0.8, 0.8)):
    inp, ref = root / 'input', root / 'reference'
    inp.mkdir(parents=True)
    rgb = np.zeros((H, W, 3), np.uint8)
    rgb[..., 1] = 200 - 100 * tree()
    Image.fromarray(rgb).save(inp / 'image.jpg', quality=95)
    write_png(ref / 'label.png', tree(), mode='1')        # like the original 1-bit PNGs
    (ref / 'bar.json').write_text(json.dumps({'dice_2ndHO': bar[0], 'cldice_2ndHO': bar[1]}))
    return inp, ref


# ------------------------------------------------------------------ metrics
def test_dice_and_cldice_perfect_and_empty():
    t = tree()
    assert grader.dice(t, t) == 1.0 and grader.cldice(t, t) == 1.0
    empty = np.zeros_like(t)
    assert grader.dice(t, empty) == 0.0 and grader.cldice(t, empty) == 0.0
    assert grader.dice(empty, empty) == 1.0 and grader.cldice(empty, empty) == 1.0


def test_cldice_penalises_a_missing_thin_vessel_more_than_dice():
    t = tree()
    p = t.copy()
    p[20:22, 20:50] = False                                  # drop the thin twig only (60 px of ~700)
    assert grader.dice(t, p) > 0.95
    assert grader.cldice(t, p) < grader.dice(t, p)


def test_cldice_ignores_vessel_width_errors():
    t = tree()
    thick = np.zeros_like(t)
    thick[47:53, 5:115] = True; thick[10:90, 59:63] = True; thick[19:23, 20:50] = True
    assert grader.cldice(t, thick) > 0.97
    assert grader.dice(t, thick) < 0.85


def test_cldice_matches_hand_computation():
    r = np.zeros((20, 30), bool); r[9:12, 2:28] = True       # one horizontal bar, skeleton = row 10
    p = np.zeros_like(r); p[9:12, 2:15] = True               # left half only
    sp, sr = grader.skeleton(p), grader.skeleton(r)
    tprec = (sp & r).sum() / sp.sum()
    tsens = (sr & p).sum() / sr.sum()
    assert tprec == 1.0
    assert grader.cldice(r, p) == pytest.approx(2 * tprec * tsens / (tprec + tsens))


def test_mode1_bool_arrays_do_not_crash_skeletonize():
    """PIL mode-1 arrays can hold 0/255 bytes in a bool dtype; skeleton() must canonicalise them."""
    a = np.zeros((10, 10), np.uint8); a[4:6, 1:9] = 255
    weird = a.view(bool)
    assert grader.skeleton(weird).sum() > 0


# ------------------------------------------------------------------ bar
def test_bar_needs_both_dice_and_cldice():
    bar = {'dice_2ndHO': 0.78, 'cldice_2ndHO': 0.84}
    assert grader.acceptable({'dice': 0.78, 'cldice': 0.84}, bar)        # equality passes (second observer)
    assert not grader.acceptable({'dice': 0.90, 'cldice': 0.83}, bar)
    assert not grader.acceptable({'dice': 0.77, 'cldice': 0.95}, bar)


# ------------------------------------------------------------------ grade_case
@pytest.mark.parametrize('mode,scale', [('L', 255), ('L', 1), ('1', 1)])
def test_grade_case_accepts_valid_encodings(tmp_path, mode, scale):
    inp, ref = make_case(tmp_path / 'c')
    write_png(tmp_path / 'out' / 'mask.png', tree() * scale if mode == 'L' else tree(), mode=mode)
    r = grader.grade_case(tmp_path / 'out', inp, ref)
    assert r['valid'] and r['acceptable'] and r['quality'] == 1.0
    assert r['metrics']['cldice'] == 1.0 and r['metrics']['dice_margin_vs_2ndHO'] == pytest.approx(0.2)


def test_grade_case_below_bar_reports_reason(tmp_path):
    inp, ref = make_case(tmp_path / 'c', bar=(0.99, 0.99))
    p = tree(); p[20:22, 20:50] = False
    write_png(tmp_path / 'out' / 'mask.png', p * 255)
    r = grader.grade_case(tmp_path / 'out', inp, ref)
    assert r['valid'] and not r['acceptable'] and 'clDice' in r['reason']


@pytest.mark.parametrize('bad,reason', [
    ('wrong_size', 'input is'), ('rgb', 'single-channel'), ('probabilities', 'values must be'),
    ('jpeg', 'not a PNG'), ('garbage', 'unreadable'),
])
def test_grade_case_rejects_bad_masks(tmp_path, bad, reason):
    inp, ref = make_case(tmp_path / 'c')
    out = tmp_path / 'out'; out.mkdir()
    t = tree().astype(np.uint8) * 255
    if bad == 'wrong_size':
        Image.fromarray(t[:, :-1]).save(out / 'mask.png')
    elif bad == 'rgb':
        Image.fromarray(np.stack([t] * 3, -1)).save(out / 'mask.png')
    elif bad == 'probabilities':
        Image.fromarray((tree() * 128).astype(np.uint8)).save(out / 'mask.png')
    elif bad == 'jpeg':
        Image.fromarray(t).save(out / 'mask.png', format='JPEG')
    else:
        (out / 'mask.png').write_bytes(b'not an image')
    r = grader.grade_case(out, inp, ref)
    assert not r['valid'] and r['quality'] == 0.0 and reason in r['reason']


def test_grade_case_refuses_symlinked_mask(tmp_path):
    inp, ref = make_case(tmp_path / 'c')
    out = tmp_path / 'out'; out.mkdir()
    os.symlink(ref / 'label.png', out / 'mask.png')           # would read the hidden reference
    r = grader.grade_case(out, inp, ref)
    assert not r['valid'] and 'not_regular_file' in r['reason']


def test_hidden_bar_is_not_in_the_mask_reader():
    """bar.json and label.png are read from reference_dir only, never from the output folder."""
    import inspect
    src = inspect.getsource(grader.grade_case)
    assert "output_dir / 'mask.png'" in src and 'bar.json' not in src.split('load_reference')[0][-50:]


# ------------------------------------------------------------------ core grading end to end
def _task(tmp_path, pipeline_body, n=2):
    tests = tmp_path / 'tests'
    for i in range(n):
        make_case(tests / 'hidden' / f'hid_{i}', bar=(0.9, 0.9))
        (tests / 'specialist' / f'hid_{i}').mkdir(parents=True)
        write_png(tests / 'specialist' / f'hid_{i}' / 'mask.png', tree() * 255)
    (tests / 'specialist' / 'runtime.json').write_text(json.dumps({'wall_seconds': {f'hid_{i}': 1.0 for i in range(n)}}))
    (tests / 'task_config.json').write_text(json.dumps({
        'schema': 'suite-task-config/1', 'family': 'seg_vessel', 'task_id': 't', 'grading': 'per_case',
        'grader_module': 'suite.families.seg_vessel.grader', 'cases': [f'hid_{i}' for i in range(n)],
        'time_limit_seconds': 20, 'threads': 1}))
    pipe = tmp_path / 'pipeline'; pipe.mkdir()
    (pipe / 'run.sh').write_text('#!/bin/bash\nset -eu\n' + pipeline_body)
    (pipe / 'run.sh').chmod(0o755)
    return tests, pipe


def _grade(tmp_path, tests, pipe, **kw):
    import sys
    path = f'{Path(sys.executable).parent}:/usr/bin:/bin'
    reward, metrics = grading.grade_task(tests, pipe, tmp_path / 'logs', tmp_path / 'work', sandbox_root=None,
                                         pipeline_path=path, out=open(os.devnull, 'w'), **kw)
    return reward, metrics


COPY_TREE = ('python3 -I -c "import sys,numpy as np; from PIL import Image; '
             'a=np.asarray(Image.open(sys.argv[1]+\'/image.jpg\'))[...,1]<150; '
             'Image.fromarray((a*255).astype(np.uint8)).save(sys.argv[2]+\'/mask.png\')" "$1" "$2"\n')


def test_end_to_end_perfect_pipeline_gets_reward_one(tmp_path):
    tests, pipe = _task(tmp_path, COPY_TREE)
    reward, metrics = _grade(tmp_path, tests, pipe)
    assert reward['reward'] == 1.0 and reward['clinically_acceptable'] == 1.0
    assert reward['vs_specialist'] == 1.0 and metrics['specialist']['clinically_acceptable'] == 1.0


def test_end_to_end_empty_mask_scores_zero_but_valid(tmp_path):
    body = ('python3 -I -c "import sys,numpy as np; from PIL import Image; '
            'Image.fromarray(np.zeros((%d,%d),np.uint8)).save(sys.argv[1]+\'/mask.png\')" "$2"\n' % (H, W))
    tests, pipe = _task(tmp_path, body)
    reward, _ = _grade(tmp_path, tests, pipe)
    assert reward['valid'] == 1.0 and reward['reward'] == 0.0 and reward['quality'] == 0.0


def test_end_to_end_timeout_zeroes_reward(tmp_path):
    tests, pipe = _task(tmp_path, 'sleep 5\n' + COPY_TREE)
    reward, _ = _grade(tmp_path, tests, pipe, time_limit_seconds=1)
    assert reward['within_time'] == 0.0 and reward['reward'] == 0.0


def test_end_to_end_one_invalid_image_zeroes_headline(tmp_path):
    body = 'if [ "$(basename "$2")" = hid_0 ]; then echo x > "$2/mask.png"; exit 0; fi\n' + COPY_TREE
    tests, pipe = _task(tmp_path, body)
    reward, _ = _grade(tmp_path, tests, pipe)
    assert reward['valid'] == 0.5 and reward['clinically_acceptable'] == 0.5 and reward['reward'] == 0.0


# ------------------------------------------------------------------ spec text (no data needed)
def test_task_readme_states_bar_and_contract():
    text = (Path(grader.__file__).parent / 'task' / 'README.md').read_text()
    for needle in ('label_1stHO.png', 'mask.png', 'clDice', 'second human', '{{LIMIT}}', '999 x 960'):
        assert needle in text


def test_family_files_are_not_world_writable_secrets():
    """No weights or data files with hidden content live in the family package (only dev-trained weights)."""
    fam = Path(grader.__file__).parent
    names = {p.name for p in fam.rglob('*') if p.is_file()}
    assert not any(n.endswith(('.jpg', '_1stHO.png', '_2ndHO.png')) for n in names)
    assert all(not (p.stat().st_mode & stat.S_ISUID) for p in fam.rglob('*') if p.is_file())
