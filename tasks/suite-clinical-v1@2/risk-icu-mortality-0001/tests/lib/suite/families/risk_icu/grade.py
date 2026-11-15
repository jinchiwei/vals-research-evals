"""risk_icu grader: strict output validation, metrics, the clinical gate and reward.json.

Family-local because suite/core was empty when this family was built (2026-11-14).
numpy only, so it runs in the task image's /opt/benchmark-venv.

Library use:   validate_predictions(), score(), reward_from()
Command line:  python -I grade.py --pipeline DIR --input DIR --outcomes CSV [--gate JSON]
                                  --workdir DIR [--limit SEC] [--specialist JSON] [--reward PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional

import numpy as np

HEADER = ["RecordID", "risk"]
REWARD_KEYS = ("reward", "ran", "valid", "within_time", "clinically_acceptable", "quality", "vs_specialist")
EPS = 1e-6


class InvalidOutput(ValueError):
    pass


# --------------------------------------------------------------------------- validation
def validate_predictions(path: str, expected_ids: List[int]) -> Dict[int, float]:
    """Exactly one finite probability in [0,1] per expected RecordID, nothing else."""
    if not os.path.isfile(path):
        raise InvalidOutput("predictions.csv missing")
    if os.path.getsize(path) > 5_000_000:
        raise InvalidOutput("predictions.csv larger than 5 MB")
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or [c.strip() for c in rows[0]] != HEADER:
        raise InvalidOutput("header must be exactly 'RecordID,risk'")
    out: Dict[int, float] = {}
    for n, row in enumerate(rows[1:], start=2):
        if len(row) == 0 or (len(row) == 1 and row[0].strip() == ""):
            continue
        if len(row) != 2:
            raise InvalidOutput(f"line {n}: expected 2 fields")
        rid_text, risk_text = row[0].strip(), row[1].strip()
        if not rid_text.isdigit():
            raise InvalidOutput(f"line {n}: RecordID must be an integer")
        rid = int(rid_text)
        try:
            risk = float(risk_text)
        except ValueError:
            raise InvalidOutput(f"line {n}: risk is not a number") from None
        if not math.isfinite(risk) or risk < 0.0 or risk > 1.0:
            raise InvalidOutput(f"line {n}: risk must be finite and in [0,1]")
        if rid in out:
            raise InvalidOutput(f"line {n}: duplicate RecordID {rid}")
        out[rid] = risk
    expected = set(expected_ids)
    if set(out) != expected:
        missing, extra = len(expected - set(out)), len(set(out) - expected)
        raise InvalidOutput(f"RecordIDs do not match the input: {missing} missing, {extra} unexpected")
    return out


# --------------------------------------------------------------------------- metrics
def auroc(y, p) -> float:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    _, inverse, counts = np.unique(p, return_inverse=True, return_counts=True)
    starts = np.cumsum(counts) - counts  # 0-based first rank of each tie block
    ranks = (starts + (counts + 1) / 2.0)[inverse]  # average 1-based rank within ties
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def brier(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def _logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _logistic_fit(X, y, offset=None, iters=100):
    """Newton-Raphson logistic regression; returns coefficients or None if singular."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    off = np.zeros(len(y)) if offset is None else np.asarray(offset, float)
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ beta + off, -35, 35)
        mu = 1 / (1 + np.exp(-eta))
        W = mu * (1 - mu)
        H = X.T @ (X * W[:, None])
        g = X.T @ (y - mu)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            return None
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    if not np.all(np.isfinite(beta)):
        return None
    return beta


def calibration_slope_intercept(y, p):
    """Slope: logit(y) ~ a + b*logit(p). Calibration-in-the-large: intercept with offset logit(p), slope fixed at 1."""
    lp = _logit(p)
    slope = float("nan")
    if np.std(lp) > 1e-9:
        b = _logistic_fit(np.column_stack([np.ones_like(lp), lp]), y)
        if b is not None:
            slope = float(b[1])
    c = _logistic_fit(np.ones((len(lp), 1)), y, offset=lp)
    citl = float(c[0]) if c is not None else float("nan")
    return slope, citl


def event1(y, p) -> Dict[str, float]:
    """Challenge event-1 score min(Se, PPV) for a binary call derived from the risk alone.

    Rule (fixed): flag the K highest-risk patients, K = round(sum of predicted risks), i.e. as many
    as the model itself expects to die; ties at the cut are all flagged. This removes any
    threshold the agent could tune and couples event 1 to calibration-in-the-large.
    """
    y, p = np.asarray(y, int), np.asarray(p, float)
    k = int(round(float(p.sum())))
    if k <= 0:
        flag = np.zeros(len(p), bool)
    else:
        cut = np.sort(p)[::-1][min(k, len(p)) - 1]
        flag = p >= cut
    tp = int(np.sum(flag & (y == 1)))
    fp = int(np.sum(flag & (y == 0)))
    fn = int(np.sum(~flag & (y == 1)))
    se = tp / (tp + fn) if tp + fn else 0.0
    ppv = tp / (tp + fp) if tp + fp else 0.0
    return {"event1": min(se, ppv), "se": se, "ppv": ppv, "k_expected": k, "n_flagged": int(flag.sum())}


def hosmer_lemeshow_event2(y, p) -> float:
    """Challenge event-2: range-normalised Hosmer-Lemeshow H over risk deciles (score.c)."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    order = np.lexsort((np.arange(len(p)), p))
    groups = np.array_split(order, 10)
    h, cents = 0.0, []
    for g in groups:
        c = p[g].mean()
        cents.append(c)
        h += (y[g].sum() - len(g) * c) ** 2 / (len(g) * (c * (1 - c) + 0.001))
    rng = cents[-1] - cents[0]
    return float(h / rng) if rng > 0 else float("inf")


def net_benefit(y, p, pt):
    y, p = np.asarray(y, int), np.asarray(p, float)
    n = len(y)
    flag = p >= pt
    tp = np.sum(flag & (y == 1)) / n
    fp = np.sum(flag & (y == 0)) / n
    w = pt / (1 - pt)
    prev = y.mean()
    return float(tp - fp * w), float(prev - (1 - prev) * w)


def subgroup_aurocs(y, p, groups: Dict[str, np.ndarray], min_events: int):
    out = {}
    for name, mask in groups.items():
        yy = np.asarray(y)[mask]
        if yy.sum() >= min_events and (len(yy) - yy.sum()) >= min_events:
            out[name] = {"n": int(mask.sum()), "deaths": int(yy.sum()), "auroc": auroc(yy, np.asarray(p)[mask])}
    return out


def point_metrics(y, p, gate, groups) -> Dict:
    slope, citl = calibration_slope_intercept(y, p)
    nb, nb_all = net_benefit(y, p, gate["net_benefit"]["threshold"])
    e1 = event1(y, p)
    a = auroc(y, p)
    subs = subgroup_aurocs(y, p, groups, gate["subgroup"]["min_events_per_class"])
    worst_name = min(subs, key=lambda k: subs[k]["auroc"]) if subs else None
    return {
        "n": int(len(y)), "deaths": int(np.sum(y)), "auroc": a, "brier": brier(y, p),
        "mean_risk": float(np.mean(p)), "observed_rate": float(np.mean(y)),
        "event1": e1["event1"], "event1_se": e1["se"], "event1_ppv": e1["ppv"], "event1_k": e1["k_expected"],
        "event2_hl": hosmer_lemeshow_event2(y, p),
        "cal_slope": slope, "cal_intercept_citl": citl,
        "net_benefit": nb, "net_benefit_treat_all": nb_all, "net_benefit_treat_none": 0.0,
        "subgroups": subs, "worst_subgroup": worst_name,
        "worst_subgroup_auroc": subs[worst_name]["auroc"] if worst_name else float("nan"),
    }


def gate_components(m: Dict, gate: Dict) -> Dict[str, bool]:
    g = gate
    fin = lambda v: v is not None and isinstance(v, float) and math.isfinite(v)  # noqa: E731
    c1 = fin(m["event1"]) and m["event1"] >= g["event1"]["bar"]
    c2 = (fin(m["cal_slope"]) and g["calibration"]["slope_min"] <= m["cal_slope"] <= g["calibration"]["slope_max"]
          and fin(m["cal_intercept_citl"]) and abs(m["cal_intercept_citl"]) <= g["calibration"]["citl_abs_max"])
    c3 = m["net_benefit"] > max(m["net_benefit_treat_all"], 0.0) + g["net_benefit"]["margin"]
    c4 = (fin(m["worst_subgroup_auroc"]) and fin(m["auroc"])
          and m["worst_subgroup_auroc"] >= m["auroc"] - g["subgroup"]["max_auroc_gap"])
    return {"event1_vs_saps": bool(c1), "calibration": bool(c2), "net_benefit": bool(c3), "worst_subgroup": bool(c4)}


def bootstrap(y, p, gate, groups, n_boot=1000, seed=20261114) -> Dict[str, List[float]]:
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    keys = ("auroc", "event1", "cal_slope", "cal_intercept_citl", "net_benefit", "brier", "worst_subgroup_auroc")
    draws = {k: [] for k in keys}
    pass_counts = {k: 0 for k in ("event1_vs_saps", "calibration", "net_benefit", "worst_subgroup")}
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        g = {k: v[idx] for k, v in groups.items()}
        m = point_metrics(y[idx], p[idx], gate, g)
        for k in keys:
            draws[k].append(m[k])
        for k, ok in gate_components(m, gate).items():
            pass_counts[k] += ok
    ci = {}
    for k, v in draws.items():
        v = np.asarray(v, float)
        v = v[np.isfinite(v)]
        ci[k] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan")] * 2
    ci["gate_pass_rate"] = {k: c / n_boot for k, c in pass_counts.items()}
    return ci


def make_groups(rows: List[Dict]) -> Dict[str, np.ndarray]:
    icu = np.array([str(r["icu_type"]) for r in rows])
    sex = np.array([str(r["gender"]) for r in rows])
    names = {"1": "CCU", "2": "CSRU", "3": "MICU", "4": "SICU"}
    groups = {f"icu_{names[k]}": icu == k for k in names}
    groups["sex_female"] = sex == "0"
    groups["sex_male"] = sex == "1"
    return groups


def score(pred: Dict[int, float], outcomes: List[Dict], gate: Dict, n_boot=1000) -> Dict:
    rows = sorted(outcomes, key=lambda r: int(r["RecordID"]))
    y = np.array([int(r["in_hospital_death"]) for r in rows])
    p = np.array([pred[int(r["RecordID"])] for r in rows])
    groups = make_groups(rows)
    m = point_metrics(y, p, gate, groups)
    comps = gate_components(m, gate)
    m["gate"] = comps
    m["clinically_acceptable"] = sum(comps.values()) / len(comps)
    if n_boot:
        m["ci95"] = bootstrap(y, p, gate, groups, n_boot=n_boot)
    return m


def quality_from_auroc(a: float) -> float:
    """quality = clip(2*AUROC - 1, 0, 1) (Somers' D / Gini): 0 at chance, 1 at perfect ranking."""
    return float(min(1.0, max(0.0, 2 * a - 1))) if math.isfinite(a) else 0.0


def reward_from(ran: bool, valid: bool, within_time: bool, metrics: Optional[Dict],
                specialist_auroc: Optional[float]) -> Dict[str, float]:
    r = {k: 0.0 for k in REWARD_KEYS}
    r["ran"], r["valid"], r["within_time"] = float(ran), float(valid), float(within_time)
    if metrics is not None and valid:
        r["clinically_acceptable"] = float(metrics["clinically_acceptable"])
        r["quality"] = quality_from_auroc(metrics["auroc"])
        if specialist_auroc is not None and specialist_auroc > 0.5:
            r["vs_specialist"] = float(min(1.0, max(0.0, (metrics["auroc"] - 0.5) / (specialist_auroc - 0.5))))
    if ran and valid and within_time:
        r["reward"] = r["clinically_acceptable"]
    return {k: float(v) for k, v in r.items()}


# --------------------------------------------------------------------------- runner
def run_pipeline(pipeline_dir: str, input_dir: str, output_dir: str, limit: float,
                 as_nobody: bool = False) -> Dict:
    """Run `bash run.sh INPUT OUTPUT` once for the whole hidden set under a wall-clock limit."""
    os.makedirs(output_dir, exist_ok=True)
    env = {"PATH": os.environ.get("RISK_ICU_PATH", os.path.dirname(sys.executable) + ":/usr/bin:/bin"),
           "HOME": output_dir, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4",
           "MKL_NUM_THREADS": "4", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"}
    cmd = ["bash", os.path.join(pipeline_dir, "run.sh"), input_dir, output_dir]
    if as_nobody:
        cmd = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--"] + cmd
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=output_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True)
    timed_out = False
    try:
        log, _ = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, 9)
        log, _ = proc.communicate()
    wall = time.monotonic() - start
    if as_nobody:
        subprocess.run(["pkill", "-KILL", "-u", "65534"], check=False)
    return {"exit_code": proc.returncode, "timed_out": timed_out, "wall_s": round(wall, 3),
            "log_tail": log.decode("utf-8", "replace")[-2000:]}


def read_outcomes(path: str) -> List[Dict]:
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def grade(pipeline: str, input_dir: str, outcomes_path: str, gate: Dict, workdir: str, limit: float,
          specialist_auroc: Optional[float], n_boot: int = 1000, as_nobody: bool = False) -> Dict:
    outcomes = read_outcomes(outcomes_path)
    ids = [int(r["RecordID"]) for r in outcomes]
    out_dir = os.path.join(workdir, "out")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    run = run_pipeline(pipeline, input_dir, out_dir, limit, as_nobody=as_nobody)
    ran = run["exit_code"] == 0 and not run["timed_out"]
    within = (not run["timed_out"]) and run["wall_s"] <= limit
    metrics, error = None, None
    valid = False
    try:
        pred = validate_predictions(os.path.join(out_dir, "predictions.csv"), ids)
        valid = True
        metrics = score(pred, outcomes, gate, n_boot=n_boot)
    except InvalidOutput as exc:
        error = str(exc)
    reward = reward_from(ran, valid, within, metrics, specialist_auroc)
    return {"reward": reward, "run": run, "metrics": metrics, "validation_error": error, "limit_s": limit}


def load_gate(path: Optional[str] = None) -> Dict:
    if path:
        with open(path) as handle:
            return json.load(handle)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gate import GATE  # noqa: E402
    return GATE


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--outcomes", required=True)
    ap.add_argument("--gate", default=None, help="JSON gate; default is gate.GATE next to this file")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--limit", type=float, default=None)
    ap.add_argument("--specialist", default=None, help="JSON with the specialist's hidden-set metrics")
    ap.add_argument("--reward", default=None)
    ap.add_argument("--metrics-out", default=None)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--as-nobody", action="store_true")
    a = ap.parse_args(argv)
    gate = load_gate(a.gate)
    limit = a.limit if a.limit is not None else gate["time_limit_s"]
    spec_auroc = None
    if a.specialist:
        with open(a.specialist) as handle:
            spec_auroc = json.load(handle)["auroc"]
    if a.reward:  # provisional zero reward so a crash still scores 0
        os.makedirs(os.path.dirname(a.reward), exist_ok=True)
        with open(a.reward, "w") as handle:
            json.dump({k: 0.0 for k in REWARD_KEYS}, handle)
    result = grade(a.pipeline, a.input, a.outcomes, gate, a.workdir, limit, spec_auroc, a.n_boot, a.as_nobody)
    if a.reward:
        with open(a.reward, "w") as handle:
            json.dump(result["reward"], handle)
    if a.metrics_out:
        with open(a.metrics_out, "w") as handle:
            json.dump(result, handle, indent=1, default=float)
    summary = {"reward": result["reward"], "wall_s": result["run"]["wall_s"], "exit": result["run"]["exit_code"],
               "timed_out": result["run"]["timed_out"], "validation_error": result["validation_error"]}
    if result["metrics"]:
        m = result["metrics"]
        summary.update({k: m[k] for k in ("auroc", "event1", "cal_slope", "cal_intercept_citl", "net_benefit",
                                          "net_benefit_treat_all", "worst_subgroup", "worst_subgroup_auroc", "gate")})
    print(json.dumps(summary, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
