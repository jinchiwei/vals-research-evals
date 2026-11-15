"""seg_spleen grader tests on synthetic volumes (no real data needed).

Run with the family env:
  ~/miniconda3/envs/vals-suite-seg_spleen/bin/python -m pytest tests/suite/test_seg_spleen.py -q
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

FAMILY = Path(__file__).resolve().parents[2] / "suite" / "families" / "seg_spleen"
sys.path.insert(0, str(FAMILY))
import grader  # noqa: E402

SPACING = (0.8, 0.8, 5.0)
SHAPE = (48, 40, 12)


def affine(spacing=SPACING):
    a = np.diag([*spacing, 1.0])
    a[:3, 3] = (-100.0, -80.0, 20.0)
    return a


def ellipsoid(shape=SHAPE, centre=(24, 20, 6), radii_mm=(10, 8, 20), spacing=SPACING):
    g = np.indices(shape).astype(float)
    r = sum(((g[i] - centre[i]) * spacing[i] / radii_mm[i]) ** 2 for i in range(3))
    return r <= 1.0


def write_case(d: Path, label: np.ndarray, aff=None):
    d.mkdir(parents=True, exist_ok=True)
    aff = affine() if aff is None else aff
    img = np.where(label, 120, -50).astype(np.int16)
    for arr, name in ((img, "image.nii.gz"), (label.astype(np.uint8), "label.nii.gz")):
        im = nib.Nifti1Image(arr, aff)
        im.header.set_xyzt_units("mm", "sec")
        nib.save(im, str(d / name))


def write_output(d: Path, mask, aff=None, ml=None, units="mm"):
    d.mkdir(parents=True, exist_ok=True)
    aff = affine() if aff is None else aff
    im = nib.Nifti1Image(np.asarray(mask), aff)
    im.header.set_xyzt_units(units, "sec")
    nib.save(im, str(d / "mask.nii.gz"))
    if ml is None:
        ml = float(np.count_nonzero(mask)) * abs(np.linalg.det(aff[:3, :3])) / 1000
    (d / "volume.json").write_text(json.dumps({"spleen_volume_ml": ml}))


# ------------------------------------------------------------------ metrics
def test_dice_and_volume_perfect():
    ref = ellipsoid()
    m = grader.case_metrics(ref, ref, affine())
    assert m["dice"] == 1.0 and m["nsd_2mm"] == 1.0 and m["hd95_mm"] == 0.0
    assert m["volume_rel_error"] == 0.0
    expected_ml = ref.sum() * 0.8 * 0.8 * 5.0 / 1000
    assert m["ref_volume_ml"] == pytest.approx(expected_ml)
    assert grader.acceptable(m)


def test_voxel_volume_uses_anisotropic_spacing():
    assert grader.voxel_volume_ml(affine()) == pytest.approx(0.0032)
    rot = affine().copy()
    rot[:3, :3] = rot[:3, :3] @ np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]])
    assert grader.voxel_volume_ml(rot) == pytest.approx(0.0032)


def test_shifted_mask_boundary_metrics():
    ref = ellipsoid()
    sub = np.roll(ref, 3, axis=0)  # 3 voxels x 0.8 mm = 2.4 mm shift
    m = grader.case_metrics(ref, sub, affine())
    assert 0.5 < m["dice"] < 0.95
    assert m["hd95_mm"] == pytest.approx(2.4, abs=0.5)
    assert m["nsd_2mm"] < 1.0


def test_empty_masks():
    ref = ellipsoid()
    empty = np.zeros_like(ref)
    m = grader.case_metrics(ref, empty, affine())
    assert m["dice"] == 0.0 and m["nsd_2mm"] == 0.0 and m["hd95_mm"] is None
    assert m["volume_rel_error"] == -1.0 and not grader.acceptable(m)


def test_threshold_edges():
    base = {"dice": 0.94, "volume_rel_error": 0.10}
    assert grader.acceptable(base)
    assert not grader.acceptable({**base, "dice": 0.9399})
    assert not grader.acceptable({**base, "volume_rel_error": -0.1001})


# ------------------------------------------------------------------ submission validity
def test_valid_submission(tmp_path):
    ref = ellipsoid()
    write_output(tmp_path, ref.astype(np.uint8))
    mask, ml = grader.load_submission(tmp_path, SHAPE, affine())
    assert mask.sum() == ref.sum() and ml > 0


@pytest.mark.parametrize("case", ["voxelcount", "mm3", "nan", "negative", "bool", "string"])
def test_bad_volume_rejected(tmp_path, case):
    ref = ellipsoid()
    n = int(ref.sum())
    ml = {"voxelcount": float(n), "mm3": n * 3.2, "nan": float("nan"), "negative": -1.0,
          "bool": True, "string": "12"}[case]
    write_output(tmp_path, ref.astype(np.uint8), ml=0.0)
    (tmp_path / "volume.json").write_text(json.dumps({"spleen_volume_ml": ml}))
    with pytest.raises(grader.SubmissionError):
        grader.load_submission(tmp_path, SHAPE, affine())


def test_wrong_grid_rejected(tmp_path):
    ref = ellipsoid()
    write_output(tmp_path, ref.astype(np.uint8), aff=affine((0.8, 0.8, 2.5)))
    with pytest.raises(grader.SubmissionError, match="grid"):
        grader.load_submission(tmp_path, SHAPE, affine())
    write_output(tmp_path, ref[:, :, :-1].astype(np.uint8))
    with pytest.raises(grader.SubmissionError, match="grid"):
        grader.load_submission(tmp_path, SHAPE, affine())


def test_non_binary_and_missing_rejected(tmp_path):
    ref = ellipsoid().astype(np.uint8) * 2
    write_output(tmp_path, ref)
    with pytest.raises(grader.SubmissionError, match="0/1"):
        grader.load_submission(tmp_path, SHAPE, affine())
    (tmp_path / "volume.json").unlink()
    with pytest.raises(grader.SubmissionError, match="missing"):
        grader.load_submission(tmp_path, SHAPE, affine())


def test_metre_units_rejected(tmp_path):
    write_output(tmp_path, ellipsoid().astype(np.uint8), units="meter")
    with pytest.raises(grader.SubmissionError, match="unit"):
        grader.load_submission(tmp_path, SHAPE, affine())


# ------------------------------------------------------------------ end-to-end grade
@pytest.fixture
def hidden(tmp_path):
    h = tmp_path / "hidden"
    write_case(h / "hid_a", ellipsoid())
    write_case(h / "hid_b", ellipsoid(centre=(20, 18, 5), radii_mm=(8, 7, 15)))
    return h


def _grade(tmp_path, hidden, pipeline, limit=30.0, env=None):
    os.environ["SEG_SPLEEN_PIPELINE_PATH"] = f"{Path(sys.executable).parent}:/usr/bin:/bin"
    return grader.grade(FAMILY / "selfcheck" / pipeline, hidden, tmp_path / f"work-{pipeline}",
                        {"mean_dice": 0.95}, limit, unprivileged=False,
                        extra_env={"SEG_SPLEEN_ORACLE_REFS": str(hidden), **(env or {})},
                        log=lambda s: None)


def test_grade_oracle_scores_one(tmp_path, hidden):
    reward, metrics = _grade(tmp_path, hidden, "oracle")
    assert set(reward) == set(grader.REWARD_KEYS)
    assert reward["reward"] == 1.0 and reward["quality"] == 1.0 and reward["vs_specialist"] == 1.0
    assert all(c["acceptable"] for c in metrics["cases"])


def test_grade_empty_scores_zero(tmp_path, hidden):
    reward, _ = _grade(tmp_path, hidden, "empty")
    assert reward["reward"] == 0.0 and reward["valid"] == 1.0 and reward["quality"] == 0.0


def test_grade_wrong_volume_units_invalid(tmp_path, hidden):
    reward, metrics = _grade(tmp_path, hidden, "wrong_volume")
    assert reward["valid"] == 0.0 and reward["reward"] == 0.0
    assert all("inconsistent" in c["error"] for c in metrics["cases"])


def test_grade_too_slow_times_out(tmp_path, hidden):
    reward, metrics = _grade(tmp_path, hidden, "too_slow", limit=1.0, env={"SEG_SPLEEN_SLOW_SEC": "5"})
    assert reward["within_time"] == 0.0 and reward["reward"] == 0.0 and reward["ran"] == 0.0
    assert all(c["timed_out"] and c["wall_sec"] < 4 for c in metrics["cases"])


def test_reward_json_contract(tmp_path, hidden):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"mean_dice": 0.95}))
    os.environ["SEG_SPLEEN_PIPELINE_PATH"] = f"{Path(sys.executable).parent}:/usr/bin:/bin"
    out = tmp_path / "logs"
    grader.main([str(FAMILY / "selfcheck" / "empty"), str(hidden), str(tmp_path / "w"), str(spec), str(out)])
    r = json.loads((out / "reward.json").read_text())
    assert list(r) == list(grader.REWARD_KEYS) or set(r) == set(grader.REWARD_KEYS)
    assert all(isinstance(v, float) and 0.0 <= v <= 1.0 for v in r.values())


def test_core_adapter_grade_case(tmp_path):
    case = tmp_path / "case"
    write_case(case / "input", ellipsoid())
    (case / "reference").mkdir()
    (case / "input" / "label.nii.gz").rename(case / "reference" / "label.nii.gz")
    out = tmp_path / "out"
    write_output(out, ellipsoid().astype(np.uint8))
    g = grader.grade_case(out, case / "input", case / "reference")
    assert g["valid"] and g["acceptable"] and g["quality"] == 1.0
    (out / "volume.json").unlink()
    (out / "volume.json").symlink_to(case / "reference" / "label.nii.gz")
    g = grader.grade_case(out, case / "input", case / "reference")
    assert not g["valid"] and "regular file" in g["reason"]
