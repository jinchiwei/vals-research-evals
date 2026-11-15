"""Family-local grader for measure_hc18 (suite/core was empty when this was written).

Contract (DESIGN.md): reward.json is flat, finite, keys exactly
reward, ran, valid, within_time, clinically_acceptable, quality, vs_specialist, each in [0,1].
Raw mm and seconds go to metrics.json.

Fixed rules (set before any agent or comparator result was seen; see docs/research/suite/measure_hc18.md):
- Per-image time limit: TIME_LIMIT_S = 10 s wall clock, measured by the grader, per hidden image,
  including interpreter start-up. Source: manual HC measurement takes a senior sonographer
  10.66 s on average (Han et al., BMC Pregnancy Childbirth 2024, Table 7); an automated tool used
  during a scan should be no slower than the human it replaces.
- Per-image tolerance: |error| <= 4.9 % of the reference HC. Source: inter-observer 95 % limits of
  agreement for HC, +/-4.9 % (Sarris et al., Ultrasound Obstet Gynecol 2012;39:266-273, INTERGROWTH-21st).
- Clinical bar for the family: clinically_acceptable >= 0.90.
- quality = mean over hidden images of clip(1 - |error| / 7.26 mm, 0, 1) (0 for an invalid image):
  0.5 at the HC18 paper's own inter-observer mean absolute difference (3.63 mm, trimester-weighted
  from van den Heuvel et al. 2018 Table 4), 0 at twice that.
- validity: exactly one finite value per image in [40, 400] mm (fetal HC from ~11 weeks to term);
  answers in pixels or centimetres fall outside this range.
- vs_specialist = min(1, quality_agent / quality_specialist) (suite/core rule).
- ran, valid, within_time are fractions of hidden images (suite/core rule).
- reward = clinically_acceptable if ran == valid == within_time == 1 else 0.
"""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

TIME_LIMIT_S = 10.0
TOL_FRACTION = 0.049
CLINICAL_BAR = 0.90
QUALITY_ZERO_MAE_MM = 7.26
VALID_RANGE_MM = (40.0, 400.0)
REWARD_KEYS = ("reward", "ran", "valid", "within_time", "clinically_acceptable", "quality", "vs_specialist")
OUTPUT_NAME = "measurement.csv"
OUTPUT_HEADER = ["case_id", "hc_mm"]


def read_output(path: Path, case_id: str) -> tuple[float | None, str]:
    """Parse OUTPUT_DIR/measurement.csv. Returns (value or None, reason)."""
    if not path.is_file():
        return None, "missing_file"
    try:
        rows = list(csv.reader(open(path, newline="")))
    except Exception:
        return None, "unreadable"
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows or [c.strip() for c in rows[0]] != OUTPUT_HEADER:
        return None, "bad_header"
    body = rows[1:]
    if len(body) != 1:
        return None, f"expected_1_row_got_{len(body)}"
    r = [c.strip() for c in body[0]]
    if len(r) != 2 or r[0] != case_id:
        return None, "wrong_case_id"
    try:
        v = float(r[1])
    except ValueError:
        return None, "not_a_number"
    if not math.isfinite(v):
        return None, "not_finite"
    return v, "ok"


def case_quality(err_mm: float) -> float:
    return float(np.clip(1.0 - abs(err_mm) / QUALITY_ZERO_MAE_MM, 0.0, 1.0))


PRIMARY_METRIC = "mean over images of clip(1 - |HC error mm| / 7.26, 0, 1); MAE in mm reported in metrics"
CLINICAL_THRESHOLD = (f"|HC error| <= {TOL_FRACTION:.1%} of reference HC (Sarris 2012 inter-observer 95% LoA); "
                      f"family bar: >= {CLINICAL_BAR:.0%} of hidden images")
REQUIRED_OUTPUTS = (OUTPUT_NAME,)


def parse_output_bytes(raw: bytes, case_id: str) -> tuple[float | None, str]:
    """Same rules as read_output, on bytes (suite/core reads agent files safely as bytes)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not_utf8"
    rows = [r for r in csv.reader(text.splitlines()) if any(c.strip() for c in r)]
    if not rows or [c.strip() for c in rows[0]] != OUTPUT_HEADER:
        return None, "bad_header"
    body = rows[1:]
    if len(body) != 1:
        return None, f"expected_1_row_got_{len(body)}"
    r = [c.strip() for c in body[0]]
    if len(r) != 2 or r[0] != case_id:
        return None, "wrong_case_id"
    try:
        v = float(r[1])
    except ValueError:
        return None, "not_a_number"
    if not math.isfinite(v):
        return None, "not_finite"
    return v, "ok"


def grade_case(output_dir, input_dir, reference_dir) -> dict:
    """suite/core per-case interface. input_dir: image.png + case.json; reference_dir: reference.json."""
    from suite.core import geometry as core_geometry

    output_dir, input_dir, reference_dir = Path(output_dir), Path(input_dir), Path(reference_dir)
    case_id = json.loads((input_dir / "case.json").read_text())["case_id"]
    ref = json.loads((reference_dir / "reference.json").read_text())
    ref_mm = float(ref["hc_mm"])
    try:
        raw = core_geometry.read_regular_file(output_dir / OUTPUT_NAME, 100_000)
    except Exception as error:  # GeometryError: missing, symlink, too large
        return {"valid": False, "acceptable": False, "quality": 0.0, "reason": f"output: {error}",
                "metrics": {"ref_mm": ref_mm, "stratum": ref.get("stratum"), "band": ref.get("band")}}
    v, why = parse_output_bytes(raw, case_id)
    m = {"ref_mm": ref_mm, "pred_mm": v, "stratum": ref.get("stratum"), "band": ref.get("band")}
    if v is None:
        return {"valid": False, "acceptable": False, "quality": 0.0, "reason": why, "metrics": m}
    if not is_valid(v):
        return {"valid": False, "acceptable": False, "quality": 0.0, "metrics": m,
                "reason": f"{v:g} outside plausible HC range {VALID_RANGE_MM} mm (pixels or cm?)"}
    err = v - ref_mm
    ok = abs(err) <= TOL_FRACTION * ref_mm
    m.update(err_mm=err, abs_err_mm=abs(err), pct_err=100 * err / ref_mm, tolerance_mm=TOL_FRACTION * ref_mm)
    return {"valid": True, "acceptable": bool(ok), "quality": case_quality(err), "metrics": m,
            "reason": None if ok else f"error {err:+.2f} mm exceeds {TOL_FRACTION:.1%} of {ref_mm:.1f} mm"}


def is_valid(v: float | None) -> bool:
    return v is not None and math.isfinite(v) and VALID_RANGE_MM[0] <= v <= VALID_RANGE_MM[1]


def score(refs: dict, preds: dict, runs: dict, specialist_quality: float | None = None) -> tuple[dict, dict]:
    """refs: case -> {hc_mm, stratum}; preds: case -> value or None; runs: case -> {seconds, exit_code, timed_out}.

    Missing/invalid cases count as outside tolerance and carry abs error = reference HC in the MAE
    (as if 0 mm had been answered), so quality cannot be raised by skipping hard images.
    """
    cases = sorted(refs)
    n = len(cases)
    per = []
    for c in cases:
        ref = float(refs[c]["hc_mm"])
        v = preds.get(c)
        ok = is_valid(v)
        run = runs.get(c, {"seconds": None, "exit_code": None, "timed_out": True})
        err = (v - ref) if ok else None
        per.append({"case_id": c, "stratum": refs[c].get("stratum", "all"), "band": refs[c].get("band", "all"),
                    "ref_mm": ref,
                    "pred": v, "valid": ok, "err_mm": err,
                    "abs_err_mm_scored": abs(err) if ok else ref,
                    "within_tol": bool(ok and abs(err) <= TOL_FRACTION * ref),
                    "seconds": run.get("seconds"), "exit_code": run.get("exit_code"),
                    "timed_out": bool(run.get("timed_out")),
                    "in_time": (not run.get("timed_out")) and run.get("seconds") is not None
                    and run["seconds"] <= TIME_LIMIT_S})
    # ran: run.sh existed and no case crashed (cases killed by the time limit are judged by within_time)
    # Gates are means over hidden cases (suite/core contract); the scalar gate needs all three == 1.
    ran = float(np.mean([p["exit_code"] == 0 or p["timed_out"] for p in per])) if n else 0.0
    valid = float(np.mean([p["valid"] for p in per])) if n else 0.0
    within_time = float(np.mean([p["in_time"] for p in per])) if n else 0.0
    ca = float(np.mean([p["within_tol"] for p in per])) if n else 0.0
    mae = float(np.mean([p["abs_err_mm_scored"] for p in per])) if n else float("inf")
    quality = float(np.mean([case_quality(p["err_mm"]) if p["valid"] else 0.0 for p in per])) if n else 0.0
    if specialist_quality is None or specialist_quality <= 0:
        vs = 0.0
    else:
        vs = float(min(1.0, quality / specialist_quality))
    reward = ca if (ran == 1.0 and valid == 1.0 and within_time == 1.0) else 0.0
    rew = {"reward": reward, "ran": float(ran), "valid": float(valid), "within_time": float(within_time),
           "clinically_acceptable": ca, "quality": quality, "vs_specialist": vs}
    rew = {k: float(rew[k]) if math.isfinite(rew[k]) else 0.0 for k in REWARD_KEYS}

    def summary(ps):
        valid_errs = [p["err_mm"] for p in ps if p["valid"]]
        return {"n": len(ps), "n_valid": len(valid_errs),
                "mae_mm": float(np.mean([p["abs_err_mm_scored"] for p in ps])),
                "mae_valid_only_mm": float(np.mean(np.abs(valid_errs))) if valid_errs else None,
                "mean_signed_err_mm": float(np.mean(valid_errs)) if valid_errs else None,
                "median_abs_err_mm": float(np.median(np.abs(valid_errs))) if valid_errs else None,
                "p95_abs_err_mm": float(np.percentile(np.abs(valid_errs), 95)) if valid_errs else None,
                "frac_within_tol": float(np.mean([p["within_tol"] for p in ps]))}

    strata = sorted({p["stratum"] for p in per})
    by = {s: summary([p for p in per if p["stratum"] == s]) for s in strata}
    worst = max(strata, key=lambda s: by[s]["mae_mm"]) if strata else None
    bands = sorted({p["band"] for p in per})
    by_band = {b: summary([p for p in per if p["band"] == b]) for b in bands}
    secs = [p["seconds"] for p in per if p["seconds"] is not None]
    metrics = {
        "n_cases": n, "overall": summary(per) if n else {}, "by_stratum": by,
        "worst_subgroup": {"stratum": worst, **(by[worst] if worst else {})},
        "by_hc_band": by_band,
        "runtime_s": {"median": float(np.median(secs)) if secs else None,
                      "max": float(np.max(secs)) if secs else None,
                      "n_timed_out": sum(p["timed_out"] for p in per), "limit_s": TIME_LIMIT_S},
        "n_invalid": sum(not p["valid"] for p in per),
        "invalid_examples": [{"case_id": p["case_id"], "pred": p["pred"]} for p in per if not p["valid"]][:5],
        "specialist_quality": specialist_quality,
        "clinical_bar": {"frac_within_tol_required": CLINICAL_BAR, "tolerance_fraction": TOL_FRACTION,
                         "passes": bool(rew["reward"] >= CLINICAL_BAR)},
        "per_case": per,
    }
    return rew, metrics


def run_pipeline(pipeline_dir: Path, inputs_dir: Path, work_dir: Path, limit_s: float = TIME_LIMIT_S,
                 extra_env: dict | None = None, threads: int = 4) -> tuple[dict, dict]:
    """Run run.sh once per case on the grader's monotonic clock. Returns (preds, runs)."""
    preds, runs = {}, {}
    run_sh = pipeline_dir / "run.sh"
    as_nobody = os.geteuid() == 0 and shutil.which("setpriv")
    for case_dir in sorted(p for p in inputs_dir.iterdir() if p.is_dir()):
        cid = case_dir.name
        out = work_dir / "out" / cid
        home = work_dir / "home" / cid
        out.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)
        if as_nobody:
            os.chown(out, 65534, 65534)
            os.chown(home, 65534, 65534)
        if not run_sh.is_file():
            preds[cid], runs[cid] = None, {"seconds": None, "exit_code": None, "timed_out": False}
            continue
        env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "HOME": str(home),
               "OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads),
               "MKL_NUM_THREADS": str(threads), "LC_ALL": "C.UTF-8", **(extra_env or {})}
        cmd = ["bash", str(run_sh), str(case_dir), str(out)]
        if as_nobody:
            cmd = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--"] + cmd
        t0 = time.monotonic()
        try:
            p = subprocess.run(cmd, env=env, cwd=str(home), stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=limit_s, start_new_session=True)
            code, to = p.returncode, False
        except subprocess.TimeoutExpired:
            code, to = None, True
        dt = time.monotonic() - t0
        if as_nobody:
            subprocess.run(["pkill", "-KILL", "-u", "65534"], check=False)
        v, _ = read_output(out / OUTPUT_NAME, cid)
        preds[cid] = None if to else v
        runs[cid] = {"seconds": dt, "exit_code": code, "timed_out": to}
    return preds, runs


def load_refs(path: Path) -> dict:
    return {r["case_id"]: {"hc_mm": float(r["hc_mm"]), "stratum": r.get("stratum", "all"),
                           "band": r.get("band", "all")}
            for r in csv.DictReader(open(path))}


def grade(pipeline_dir: Path, inputs_dir: Path, refs_csv: Path, out_dir: Path,
          specialist_json: Path | None = None, extra_env: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reward.json").write_text(json.dumps({k: 0.0 for k in REWARD_KEYS}))  # provisional zero
    refs = load_refs(refs_csv)
    spec = json.loads(specialist_json.read_text()) if specialist_json and specialist_json.is_file() else None
    work = out_dir / "work"
    if work.exists():
        shutil.rmtree(work)
    # Like the verifier: run a copy of the pipeline from the grader's own work area (local disk).
    shutil.copytree(pipeline_dir, work / "pipeline", ignore=shutil.ignore_patterns("__pycache__"))
    preds, runs = run_pipeline(work / "pipeline", inputs_dir, work, extra_env=extra_env)
    rew, metrics = score(refs, preds, runs, spec["quality"] if spec else None)
    if spec:
        metrics["specialist"] = spec
    (out_dir / "reward.json").write_text(json.dumps(rew))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=1))
    print(json.dumps({"reward": rew, "mae_mm": metrics["overall"].get("mae_mm"),
                      "worst": metrics["worst_subgroup"].get("stratum"),
                      "median_s": metrics["runtime_s"]["median"]}))
    return {"reward": rew, "metrics": metrics}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("pipeline_dir", type=Path)
    ap.add_argument("inputs_dir", type=Path)
    ap.add_argument("refs_csv", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--specialist", type=Path)
    a = ap.parse_args()
    grade(a.pipeline_dir, a.inputs_dir, a.refs_csv, a.out_dir, a.specialist)
