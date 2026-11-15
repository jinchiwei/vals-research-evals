"""seg_spleen grader: metrics, submission validation, timed runner and reward.

Family-local because suite/core/ was empty when this family was built (2026-11-14).
Stdlib + numpy + scipy + nibabel only, so the same file runs inside the verifier
image (as tests/grade.py's library) and in the project conda env.

Contract (see task/README.md):
  run.sh INPUT_DIR OUTPUT_DIR
  INPUT_DIR/image.nii.gz            CT in HU
  OUTPUT_DIR/mask.nii.gz            binary spleen mask on the input grid
  OUTPUT_DIR/volume.json            {"spleen_volume_ml": <float>}
"""
from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

# ------------------------------------------------------------------ fixed config
# Thresholds were fixed before any agent run from Humpire-Mamani et al., Radiology:
# Artificial Intelligence 2020;2(4):e190102 (PMC8082410): independent second observer vs
# reference on 50 CT scans, Dice 0.964 +/- 0.012 and mean relative absolute volume
# difference 3.93 %. Derivations are in docs/research/suite/seg_spleen.md. Do not tune.
DICE_THRESHOLD = 0.94            # 0.964 - 2 * 0.012
VOLUME_REL_ERROR_THRESHOLD = 0.10  # ~95th pct of |error| if signed error ~ N(0, s), E|e| = 3.93 %
NSD_TOLERANCE_MM = 2.0           # reported, not thresholded
CASE_TIME_LIMIT_SEC = 300.0      # build tier default; toolbox tier set in family.json
VOLUME_CONSISTENCY_REL = 0.01    # reported mL vs mask voxels x voxel volume
VOLUME_CONSISTENCY_ABS_ML = 0.5
AFFINE_ATOL_MM = 1e-3
AFFINE_RTOL = 1e-5
REWARD_KEYS = ("reward", "ran", "valid", "within_time", "clinically_acceptable",
               "quality", "vs_specialist")


class SubmissionError(ValueError):
    """Output violates the task contract."""


# ------------------------------------------------------------------ geometry
def voxel_volume_ml(affine) -> float:
    a = np.asarray(affine, float)
    if a.shape != (4, 4) or not np.all(np.isfinite(a)):
        raise ValueError("affine must be a finite 4x4 matrix")
    v = abs(float(np.linalg.det(a[:3, :3])))
    if v <= 1e-12:
        raise ValueError("singular affine")
    return v / 1000.0


def spacing_from_affine(affine) -> tuple[float, float, float]:
    a = np.asarray(affine, float)
    return tuple(float(x) for x in np.sqrt((a[:3, :3] ** 2).sum(axis=0)))


def same_grid(shape_a, affine_a, shape_b, affine_b) -> bool:
    return tuple(shape_a)[:3] == tuple(shape_b)[:3] and np.allclose(
        np.asarray(affine_a, float), np.asarray(affine_b, float),
        rtol=AFFINE_RTOL, atol=AFFINE_ATOL_MM)


# ------------------------------------------------------------------ metrics
def dice(ref, sub) -> float:
    r, s = np.asarray(ref, bool), np.asarray(sub, bool)
    total = int(r.sum()) + int(s.sum())
    if total == 0:
        return 1.0
    return 2.0 * int(np.logical_and(r, s).sum()) / total


def _surface(mask):
    if not mask.any():
        return mask
    er = ndimage.binary_erosion(mask, structure=ndimage.generate_binary_structure(3, 1),
                                border_value=0)
    return mask & ~er


def surface_distances(ref, sub, spacing):
    """(distances ref-surface -> sub-surface, sub-surface -> ref-surface) in mm.

    Computed inside the joint bounding box padded by a margin, so it is fast on CT.
    Returns (None, None) if either mask is empty.
    """
    r, s = np.asarray(ref, bool), np.asarray(sub, bool)
    if not r.any() or not s.any():
        return None, None
    both = r | s
    idx = np.argwhere(both)
    lo = np.maximum(idx.min(0) - 3, 0)
    hi = np.minimum(idx.max(0) + 4, both.shape)
    sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    r, s = r[sl], s[sl]
    sr, ss = _surface(r), _surface(s)
    dt_s = ndimage.distance_transform_edt(~ss, sampling=spacing)
    dt_r = ndimage.distance_transform_edt(~sr, sampling=spacing)
    return dt_s[sr], dt_r[ss]


def hd95(ref, sub, spacing) -> float | None:
    a, b = surface_distances(ref, sub, spacing)
    if a is None:
        return None
    return float(max(np.percentile(a, 95), np.percentile(b, 95)))


def nsd(ref, sub, spacing, tol_mm=NSD_TOLERANCE_MM) -> float:
    """Normalised surface distance (surface Dice) at tolerance tol_mm (voxel-count version)."""
    r, s = np.asarray(ref, bool), np.asarray(sub, bool)
    if not r.any() and not s.any():
        return 1.0
    a, b = surface_distances(r, s, spacing)
    if a is None:
        return 0.0
    return float(((a <= tol_mm).sum() + (b <= tol_mm).sum()) / (a.size + b.size))


def case_metrics(ref, sub, affine, reported_ml=None) -> dict:
    spacing = spacing_from_affine(affine)
    vml = voxel_volume_ml(affine)
    ref_ml = int(np.count_nonzero(ref)) * vml
    mask_ml = int(np.count_nonzero(sub)) * vml
    vol = mask_ml if reported_ml is None else float(reported_ml)
    h = hd95(ref, sub, spacing)
    return {
        "dice": dice(ref, sub),
        "nsd_2mm": nsd(ref, sub, spacing),
        "hd95_mm": h,
        "ref_volume_ml": ref_ml,
        "mask_volume_ml": mask_ml,
        "reported_volume_ml": vol,
        "volume_error_ml": vol - ref_ml,
        "volume_rel_error": (vol - ref_ml) / ref_ml if ref_ml > 0 else None,
    }


def acceptable(m: dict) -> bool:
    return (m["dice"] >= DICE_THRESHOLD and m["volume_rel_error"] is not None
            and abs(m["volume_rel_error"]) <= VOLUME_REL_ERROR_THRESHOLD)


# ------------------------------------------------------------------ submission checks
def load_submission(out_dir: Path, image_shape, image_affine):
    """Return (bool mask, reported mL). Raise SubmissionError on any contract breach."""
    import nibabel as nib
    mpath, vpath = out_dir / "mask.nii.gz", out_dir / "volume.json"
    if not mpath.is_file():
        raise SubmissionError("mask.nii.gz missing")
    if not vpath.is_file():
        raise SubmissionError("volume.json missing")
    try:
        img = nib.load(str(mpath))
        arr = np.asanyarray(img.dataobj)
    except Exception as e:  # noqa: BLE001
        raise SubmissionError(f"mask unreadable: {type(e).__name__}") from None
    if arr.ndim == 4 and arr.shape[3] == 1:
        arr = arr[..., 0]
    if arr.ndim != 3:
        raise SubmissionError("mask is not 3D")
    unit = img.header.get_xyzt_units()[0]
    if unit not in ("mm", "unknown"):
        raise SubmissionError(f"mask spatial unit {unit!r} is not mm")
    if not same_grid(arr.shape, img.affine, image_shape, image_affine):
        raise SubmissionError("mask is not on the input grid (shape or affine differs)")
    if not np.issubdtype(arr.dtype, np.number) or not np.all(np.isfinite(arr)):
        raise SubmissionError("mask has non-numeric or non-finite values")
    vals = np.unique(arr)
    if not set(vals.tolist()) <= {0, 1}:
        raise SubmissionError(f"mask labels must be 0/1, found {vals[:6].tolist()}")
    mask = arr.astype(bool)
    try:
        payload = json.loads(vpath.read_text())
        ml = payload["spleen_volume_ml"]
    except Exception:  # noqa: BLE001
        raise SubmissionError("volume.json must be {\"spleen_volume_ml\": number}") from None
    if isinstance(ml, bool) or not isinstance(ml, (int, float)) or not math.isfinite(ml) or ml < 0:
        raise SubmissionError("spleen_volume_ml must be a finite non-negative number")
    mask_ml = int(mask.sum()) * voxel_volume_ml(image_affine)
    if abs(ml - mask_ml) > max(VOLUME_CONSISTENCY_REL * mask_ml, VOLUME_CONSISTENCY_ABS_ML):
        raise SubmissionError(
            f"reported volume {ml:.2f} mL inconsistent with mask ({mask_ml:.2f} mL from voxel spacing)")
    return mask, float(ml)


# ------------------------------------------------------------------ runner
def run_case(pipeline_dir: Path, in_dir: Path, out_dir: Path, limit_sec: float,
             threads: int = 4, unprivileged: bool | None = None, extra_env: dict | None = None):
    """Run run.sh on one case with the grader's monotonic clock. Never trusts pipeline timing."""
    out_dir.mkdir(parents=True, exist_ok=True)
    home = out_dir.parent / f".home-{out_dir.name}"
    home.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("SEG_SPLEEN_PIPELINE_PATH", "/opt/benchmark-venv/bin:/usr/bin:/bin"),
        "HOME": str(home), "LANG": "C.UTF-8",
        **{k: str(threads) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                     "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS", "NUMEXPR_NUM_THREADS")},
        **(extra_env or {}),
    }
    if unprivileged is None:
        unprivileged = os.geteuid() == 0
    cmd = ["bash", str(pipeline_dir / "run.sh"), str(in_dir), str(out_dir)]
    if unprivileged:
        for p in (out_dir, home):
            os.chown(p, 65534, 65534)
        cmd = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--"] + cmd
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True, cwd=str(home))
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=limit_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
    wall = time.monotonic() - t0
    try:  # nothing from this case may survive into scoring
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if unprivileged:
        subprocess.run(["pkill", "-KILL", "-u", "65534"], check=False)
    return {"exit_code": proc.returncode, "timed_out": timed_out, "wall_sec": wall,
            "log_tail": (out or b"")[-400:].decode("utf-8", "replace")}


# ------------------------------------------------------------------ grading
def _load_ref(case_dir: Path):
    import nibabel as nib
    img = nib.load(str(case_dir / "image.nii.gz"))
    ref = nib.load(str(case_dir / "label.nii.gz"))
    return img.shape[:3], img.affine, np.asanyarray(ref.dataobj) > 0


def grade(pipeline_dir: Path, hidden_dir: Path, work_dir: Path, specialist: dict | None,
          limit_sec: float = CASE_TIME_LIMIT_SEC, threads: int = 4, unprivileged=None,
          extra_env=None, log=print):
    """hidden_dir/<case>/{image.nii.gz,label.nii.gz}. specialist: {"mean_dice": float, ...}.

    Returns (reward dict, metrics dict). Only image.nii.gz is staged for the pipeline.
    """
    cases = sorted(p.name for p in hidden_dir.iterdir() if (p / "image.nii.gz").is_file())
    if not cases:
        raise RuntimeError("no hidden cases")
    per_case = []
    for case in cases:
        in_dir = work_dir / "in" / case
        in_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hidden_dir / case / "image.nii.gz", in_dir / "image.nii.gz")
        os.chmod(in_dir / "image.nii.gz", 0o644)
        out_dir = work_dir / "out" / case
        if out_dir.exists():
            shutil.rmtree(out_dir)
        run = run_case(pipeline_dir, in_dir, out_dir, limit_sec, threads, unprivileged, extra_env)
        rec = {"case": case, "exit_code": run["exit_code"], "timed_out": run["timed_out"],
               "wall_sec": round(run["wall_sec"], 2)}
        rec["ran"] = run["exit_code"] == 0 and not run["timed_out"]
        rec["within_time"] = (not run["timed_out"]) and run["wall_sec"] <= limit_sec
        shape, affine, ref = _load_ref(hidden_dir / case)
        try:
            mask, ml = load_submission(out_dir, shape, affine)
            rec["valid"] = True
            rec["error"] = None
            rec.update(case_metrics(ref, mask, affine, ml))
        except SubmissionError as e:
            rec["valid"] = False
            rec["error"] = str(e)
            rec.update({"dice": 0.0, "nsd_2mm": 0.0, "hd95_mm": None,
                        "volume_rel_error": None})
        rec["acceptable"] = bool(rec["valid"] and rec["within_time"] and rec["ran"]
                                 and acceptable(rec))
        if not rec["ran"]:
            rec["log_tail"] = run["log_tail"][-200:]
        per_case.append(rec)
        log(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()
                        if k in ("case", "dice", "nsd_2mm", "hd95_mm", "volume_rel_error", "wall_sec",
                                 "exit_code", "timed_out", "valid", "acceptable", "error")}))
    n = len(per_case)
    frac = lambda key: sum(bool(r[key]) for r in per_case) / n  # noqa: E731
    quality = float(np.mean([r["dice"] if (r["valid"] and r["within_time"]) else 0.0
                             for r in per_case]))
    spec_q = (specialist or {}).get("mean_dice")
    vs_spec = min(1.0, quality / spec_q) if spec_q else 0.0
    reward = {"ran": frac("ran"), "valid": frac("valid"), "within_time": frac("within_time"),
              "clinically_acceptable": frac("acceptable"), "quality": quality,
              "vs_specialist": vs_spec}
    gate = reward["ran"] == 1 and reward["valid"] == 1 and reward["within_time"] == 1
    reward["reward"] = reward["clinically_acceptable"] if gate else 0.0
    reward = {k: float(min(1.0, max(0.0, reward[k]))) for k in REWARD_KEYS}
    assert all(math.isfinite(v) for v in reward.values())
    metrics = {"cases": per_case, "time_limit_sec": limit_sec, "threads": threads,
               "thresholds": {"dice": DICE_THRESHOLD, "volume_rel_error": VOLUME_REL_ERROR_THRESHOLD},
               "specialist": specialist}
    return reward, metrics


# ------------------------------------------------------------------ suite/core plug-in adapter
# suite/core appeared while this family was being built; these let core.grading drive this
# grader (hidden layout <case>/input/image.nii.gz, <case>/reference/label.nii.gz).
REQUIRED_OUTPUTS = ("mask.nii.gz", "volume.json")
CLINICAL_THRESHOLD = (f"Dice >= {DICE_THRESHOLD} and |relative volume error| <= "
                      f"{VOLUME_REL_ERROR_THRESHOLD:.0%} (Humpire-Mamani 2020 inter-observer)")
PRIMARY_METRIC = "Dice"


def grade_case(output_dir, input_dir, reference_dir) -> dict:
    import nibabel as nib
    output_dir, input_dir, reference_dir = Path(output_dir), Path(input_dir), Path(reference_dir)
    for name in REQUIRED_OUTPUTS:  # never follow a planted symlink as root
        p = output_dir / name
        if p.is_symlink() or (p.exists() and not p.is_file()):
            return {"valid": False, "acceptable": False, "quality": 0.0,
                    "reason": f"{name} is not a regular file", "metrics": {}}
    img = nib.load(str(input_dir / "image.nii.gz"))
    ref = np.asanyarray(nib.load(str(reference_dir / "label.nii.gz")).dataobj) > 0
    try:
        mask, ml = load_submission(output_dir, img.shape[:3], img.affine)
    except SubmissionError as e:
        return {"valid": False, "acceptable": False, "quality": 0.0, "reason": str(e), "metrics": {}}
    m = case_metrics(ref, mask, img.affine, ml)
    ok = acceptable(m)
    return {"valid": True, "acceptable": ok, "quality": float(m["dice"]),
            "reason": None if ok else "below Dice or volume threshold", "metrics": m}


def zero_reward() -> dict:
    return {k: 0.0 for k in REWARD_KEYS}


def main(argv=None):
    """Verifier entry: grader.py PIPELINE_DIR HIDDEN_DIR WORK_DIR SPECIALIST_JSON OUT_DIR [LIMIT]."""
    argv = argv or sys.argv[1:]
    pipeline, hidden, work, spec, out = map(Path, argv[:5])
    limit = float(argv[5]) if len(argv) > 5 else CASE_TIME_LIMIT_SEC
    out.mkdir(parents=True, exist_ok=True)
    (out / "reward.json").write_text(json.dumps(zero_reward()))
    specialist = json.loads(spec.read_text()) if spec.is_file() else None
    reward, metrics = grade(pipeline, hidden, work, specialist, limit)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1, default=float))
    (out / "reward.json").write_text(json.dumps(reward))
    print(json.dumps({"summary": reward}))


if __name__ == "__main__":
    main()
