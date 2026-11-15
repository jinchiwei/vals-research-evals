"""ecg_ptbxl grader: runs the agent's pipeline on the hidden ECGs and scores it.

Self-contained (stdlib + numpy) so it can be copied to the task's tests/ folder.

Harbor (verifier sandbox, root):   python -I /tests/grade.py
Local:                             python -I grade.py --pipeline DIR --hidden DIR --logs DIR [--specialist JSON]

Everything clinical below (GATE, TIME_RULE, QUALITY_RULE) was fixed before any comparator or agent
result was seen; sources are in docs/research/suite/ecg_ptbxl.md.
"""
import argparse
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

CLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
REWARD_KEYS = ["reward", "ran", "valid", "within_time", "clinically_acceptable", "quality", "vs_specialist"]

# Pre-fixed acceptability gate. clinically_acceptable = fraction of the three components met, where the
# calibration and subgroup components are credited only if the MI operating point is met (a model that
# cannot detect MI is not made acceptable by being calibrated or uniformly useless; added after the
# constant-prevalence self-check scored 2/3, before any agent run; thresholds unchanged).
GATE = {
    "central_target": "MI",
    "operating_specificity": 0.90,     # CSE study: median program specificity 91.3 % (Willems 1991)
    "min_sensitivity": 0.70,           # between CSE median program (0.66) and cardiologist (0.77) MI sensitivity
    "max_macro_ece": 0.05,             # mean over 5 classes, 10 equal-width bins (argued, see docs)
    "max_subgroup_gap": 0.05,          # overall macro AUROC minus worst sex / age-band macro AUROC
    "subgroups": {"sex": ["M", "F"], "age_band": ["age<55", "age55-69", "age>=70"]},
}
# Time: grader clock over the whole hidden set, one invocation of run.sh.
TIME_RULE = {"startup_allowance_s": 60.0, "per_ecg_s": 0.5, "hard_kill_factor": 2.0}
# quality = clip((macro AUROC - 0.5) / (0.928 - 0.5), 0, 1): chance -> 0, published benchmark -> 1.
QUALITY_RULE = {"chance": 0.5, "published_macro_auroc": 0.928}
N_BOOT = 1000
BOOT_SEED = 20261114
MAX_PRED_BYTES = 20 * 1024 * 1024
NOBODY = 65534


# ---------------------------------------------------------------- metrics (numpy only)
def _ranks(x):
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ranks = np.empty(len(x), dtype=float)
    i = 0
    n = len(x)
    # average ranks for ties
    starts = np.r_[0, np.flatnonzero(np.diff(xs)) + 1]
    ends = np.r_[starts[1:], n]
    avg = (starts + ends - 1) / 2.0 + 1.0
    ranks[order] = np.repeat(avg, ends - starts)
    return ranks


def auroc(y, p):
    y = np.asarray(y).astype(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = _ranks(np.asarray(p, dtype=float))
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def macro_auroc(Y, P):
    vals = [auroc(Y[:, k], P[:, k]) for k in range(Y.shape[1])]
    vals = [v for v in vals if not math.isnan(v)]
    return float(np.mean(vals)) if vals else float("nan")


def sensitivity_at_specificity(y, p, spec):
    """Threshold t = the ceil(spec * n_neg)-th smallest negative score; positive call iff p > t.
    Ties at t count as negative calls, so constant scores give sensitivity 0."""
    y = np.asarray(y).astype(bool)
    p = np.asarray(p, dtype=float)
    neg = np.sort(p[~y])
    if len(neg) == 0 or y.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    k = int(math.ceil(spec * len(neg))) - 1
    t = neg[k]
    return float((p[y] > t).mean()), float((p[~y] <= t).mean()), float(t)


def ece(y, p, bins=10):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    tot = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            tot += abs(y[m].mean() - p[m].mean()) * m.sum()
    return float(tot / len(y))


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def calibration_slope_intercept(y, p, iters=50):
    """Logistic recalibration y ~ a + b*logit(p) by Newton steps."""
    y = np.asarray(y, float)
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    X = np.c_[np.ones_like(lp), lp]
    w = np.zeros(2)
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-(X @ w)))
        g = X.T @ (y - mu)
        H = X.T @ (X * (mu * (1 - mu))[:, None]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, g)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    return float(w[1]), float(w[0])


def subgroup_table(Y, P, groups):
    out = {}
    for col, levels in GATE["subgroups"].items():
        for g in levels:
            m = groups[col] == g
            out[f"{col}={g}"] = {"n": int(m.sum()),
                                 "positives": {c: int(Y[m, k].sum()) for k, c in enumerate(CLASSES)},
                                 "macro_auroc": macro_auroc(Y[m], P[m]) if m.sum() else float("nan"),
                                 "mi_auroc": auroc(Y[m, 1], P[m, 1]) if m.sum() else float("nan")}
    return out


def core_metrics(Y, P, groups):
    mi = CLASSES.index(GATE["central_target"])
    sens, spec, thr = sensitivity_at_specificity(Y[:, mi], P[:, mi], GATE["operating_specificity"])
    eces = [ece(Y[:, k], P[:, k]) for k in range(len(CLASSES))]
    overall = macro_auroc(Y, P)
    sub = subgroup_table(Y, P, groups)
    worst_name = min(sub, key=lambda k: sub[k]["macro_auroc"] if not math.isnan(sub[k]["macro_auroc"]) else 9)
    return {"macro_auroc": overall, "mi_sensitivity_at_spec": sens, "mi_specificity_achieved": spec,
            "mi_threshold": thr, "macro_ece": float(np.mean(eces)),
            "subgroup_gap": overall - sub[worst_name]["macro_auroc"], "worst_subgroup": worst_name,
            "per_class_ece": dict(zip(CLASSES, eces)), "subgroups": sub}


def gate_components(m):
    return {"mi_operating_point": bool(m["mi_sensitivity_at_spec"] >= GATE["min_sensitivity"]),
            "calibration": bool(m["macro_ece"] <= GATE["max_macro_ece"]),
            "subgroup_gap": bool(m["subgroup_gap"] <= GATE["max_subgroup_gap"])}


def gate_fraction(g):
    if not g["mi_operating_point"]:
        return 0.0
    return (1 + g["calibration"] + g["subgroup_gap"]) / 3.0


def bootstrap(Y, P, groups, n_boot=N_BOOT, seed=BOOT_SEED):
    rng = np.random.default_rng(seed)
    n = len(Y)
    keys = ["macro_auroc", "mi_sensitivity_at_spec", "macro_ece", "subgroup_gap"]
    draws = {k: [] for k in keys}
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        g = {c: v[i] for c, v in groups.items()}
        m = core_metrics(Y[i], P[i], g)
        for k in keys:
            draws[k].append(m[k])
    return {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in draws.items()}


def full_report(Y, P, groups, n_boot=N_BOOT):
    m = core_metrics(Y, P, groups)
    m["per_class"] = {}
    for k, c in enumerate(CLASSES):
        s, i = calibration_slope_intercept(Y[:, k], P[:, k])
        m["per_class"][c] = {"auroc": auroc(Y[:, k], P[:, k]), "brier": brier(Y[:, k], P[:, k]),
                             "ece": m["per_class_ece"][c], "calibration_slope": s, "calibration_intercept": i,
                             "prevalence": float(Y[:, k].mean()), "mean_prediction": float(P[:, k].mean())}
    m["macro_brier"] = float(np.mean([m["per_class"][c]["brier"] for c in CLASSES]))
    # report-only (metrics-review.md): MI net benefit vs treat-all at stated thresholds, and MI false-negative
    # rate per subgroup at the overall 90 %-specificity threshold (underdiagnosis by group)
    y_mi, p_mi, n = Y[:, 1], P[:, 1], len(Y)
    m["mi_net_benefit"] = {}
    for pt in (0.1, 0.2, 0.3, 0.4):
        w = pt / (1 - pt)
        tp, fp = float(((p_mi >= pt) & (y_mi == 1)).sum()), float(((p_mi >= pt) & (y_mi == 0)).sum())
        m["mi_net_benefit"][str(pt)] = {"model": tp / n - fp / n * w,
                                        "treat_all": y_mi.mean() - (1 - y_mi.mean()) * w}
    for name, sg in m["subgroups"].items():
        col, g = name.split("=", 1)
        sel = (groups[col] == g) & (y_mi == 1)
        sg["mi_false_negative_rate_at_overall_threshold"] = float((p_mi[sel] <= m["mi_threshold"]).mean()) if sel.any() else float("nan")
    m["gate"] = gate_components(m)
    m["gate_fraction_met"] = gate_fraction(m["gate"])
    m["gate_all_met"] = all(m["gate"].values())
    if n_boot:
        m["ci95"] = bootstrap(Y, P, groups, n_boot)
    return m


def quality_score(macro):
    if macro is None or math.isnan(macro):
        return 0.0
    q = (macro - QUALITY_RULE["chance"]) / (QUALITY_RULE["published_macro_auroc"] - QUALITY_RULE["chance"])
    return float(min(1.0, max(0.0, q)))


def vs_specialist_score(macro, specialist_macro):
    if specialist_macro is None or macro is None or math.isnan(macro):
        return 0.0
    return float(min(1.0, max(0.0, (macro - 0.5) / (specialist_macro - 0.5))))


# ---------------------------------------------------------------- strict output parsing
class InvalidOutput(ValueError):
    pass


def parse_predictions(path, expected_ids):
    path = Path(path)
    if not path.is_file():
        raise InvalidOutput("predictions.csv missing")
    if path.stat().st_size > MAX_PRED_BYTES:
        raise InvalidOutput("predictions.csv too large")
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows or [h.strip() for h in rows[0]] != ["record_id"] + CLASSES:
        raise InvalidOutput(f"header must be record_id,{','.join(CLASSES)}")
    want = {r: i for i, r in enumerate(expected_ids)}
    P = np.full((len(expected_ids), len(CLASSES)), np.nan)
    seen = set()
    for line_no, row in enumerate(rows[1:], start=2):
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) != len(CLASSES) + 1:
            raise InvalidOutput(f"line {line_no}: expected {len(CLASSES) + 1} fields")
        rid = row[0].strip()
        if rid not in want:
            raise InvalidOutput(f"line {line_no}: unknown record_id")
        if rid in seen:
            raise InvalidOutput(f"line {line_no}: duplicate record_id")
        seen.add(rid)
        try:
            vals = [float(v) for v in row[1:]]
        except ValueError:
            raise InvalidOutput(f"line {line_no}: non-numeric probability")
        if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in vals):
            raise InvalidOutput(f"line {line_no}: probability not finite in [0,1]")
        P[want[rid]] = vals
    if len(seen) != len(expected_ids):
        raise InvalidOutput(f"{len(expected_ids) - len(seen)} records missing")
    return P


def load_reference(path):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    ids = [r["record_id"] for r in rows]
    Y = np.array([[int(r[c]) for c in CLASSES] for r in rows], dtype=int)
    groups = {"sex": np.array([r["sex"] for r in rows]), "age_band": np.array([r["age_band"] for r in rows])}
    return ids, Y, groups


# ---------------------------------------------------------------- running the pipeline
def time_budget(n):
    return TIME_RULE["startup_allowance_s"] + TIME_RULE["per_ecg_s"] * n


def kill_uid(uid):
    """Kill every process owned by uid (python:3.12-slim has no procps/pkill)."""
    import signal
    for st in Path("/proc").glob("[0-9]*/status"):
        try:
            for line in st.read_text().splitlines():
                if line.startswith("Uid:") and int(line.split()[1]) == uid:
                    os.kill(int(st.parent.name), signal.SIGKILL)
        except (OSError, ValueError):
            pass


def run_pipeline(pipeline_dir, input_dir, output_dir, budget, drop_privileges, threads=4):
    env = {"PATH": "/opt/benchmark-venv/bin:/usr/local/bin:/usr/bin:/bin",
           "HOME": str(Path(output_dir).parent / "home"), "LANG": "C.UTF-8",
           "OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads),
           "TORCH_NUM_THREADS": str(threads), "PYTHONDONTWRITEBYTECODE": "1"}
    if not drop_privileges:  # local self-check: keep the caller's interpreter on PATH
        env["PATH"] = os.path.dirname(sys.executable) + ":" + env["PATH"]
        env.update({k: v for k, v in os.environ.items() if k.startswith("ECG_SELFCHECK_")})
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    hard = budget * TIME_RULE["hard_kill_factor"]
    cmd = ["timeout", "-k", "5", f"{hard:.0f}", "bash", str(Path(pipeline_dir) / "run.sh"), str(input_dir), str(output_dir)]
    if drop_privileges:
        os.chown(env["HOME"], NOBODY, NOBODY)
        cmd = ["setpriv", f"--reuid={NOBODY}", f"--regid={NOBODY}", "--clear-groups", "--"] + cmd
    t0 = time.monotonic()
    proc = subprocess.run(cmd, env=env, cwd=str(output_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=True)
    elapsed = time.monotonic() - t0
    if drop_privileges:
        kill_uid(NOBODY)
    tail = proc.stdout[-2000:].decode("utf-8", "replace")
    return {"exit_code": proc.returncode, "elapsed_s": elapsed, "killed": proc.returncode in (124, 137),
            "hard_limit_s": hard, "log_tail": tail}


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=float))
    os.replace(tmp, path)


def grade(pipeline, hidden, logs, specialist_json=None, harbor=False, n_boot=N_BOOT):
    logs = Path(logs)
    zero = {k: 0.0 for k in REWARD_KEYS}
    write_json(logs / "reward.json", zero)          # provisional zero: a crash or hang still scores 0
    ids, Y, groups = load_reference(Path(hidden) / "reference.csv")
    n = len(ids)
    budget = time_budget(n)
    spec = json.loads(Path(specialist_json).read_text()) if specialist_json and Path(specialist_json).is_file() else {}

    if harbor:
        eval_root = Path("/eval")
        shutil.rmtree(eval_root, ignore_errors=True)
        shutil.copytree(Path(hidden) / "input", eval_root / "in")
        # symlinks=True: copy links as links, so a planted link to /tests stays unreadable (go-rwx) for uid 65534
        shutil.copytree(pipeline, eval_root / "pipeline", symlinks=True)
        for p in [eval_root, *eval_root.rglob("*")]:
            if p.is_symlink():
                continue
            os.chown(p, 0, 0)
            os.chmod(p, 0o755 if p.is_dir() else 0o644)
        (eval_root / "out").mkdir()
        os.chown(eval_root / "out", NOBODY, NOBODY)
        in_dir, out_dir, pipe_dir = eval_root / "in", eval_root / "out", eval_root / "pipeline"
    else:
        work = logs / "eval"
        shutil.rmtree(work, ignore_errors=True)
        (work / "out").mkdir(parents=True)
        in_dir, out_dir, pipe_dir = Path(hidden) / "input", work / "out", Path(pipeline)

    run = {"exit_code": None, "elapsed_s": None, "killed": False}
    if (Path(pipe_dir) / "run.sh").is_file():
        run = run_pipeline(pipe_dir, in_dir, out_dir, budget, drop_privileges=harbor)
    ran = float(run["exit_code"] == 0 and not run["killed"])
    within = float(ran == 1.0 and run["elapsed_s"] is not None and run["elapsed_s"] <= budget)

    metrics = {"n_hidden": n, "time_budget_s": budget, "time_rule": TIME_RULE, "gate_rule": GATE,
               "quality_rule": QUALITY_RULE, "run": {k: v for k, v in run.items() if k != "log_tail"},
               "per_ecg_s": (run["elapsed_s"] / n) if run.get("elapsed_s") else None}
    valid = 0.0
    P = None
    try:
        P = parse_predictions(Path(out_dir) / "predictions.csv", ids)
        valid = 1.0
    except InvalidOutput as e:
        metrics["invalid_reason"] = str(e)
    reward = dict(zero)
    reward.update(ran=ran, valid=valid, within_time=within)
    if valid:
        rep = full_report(Y, P, groups, n_boot=n_boot)
        metrics["scores"] = rep
        reward["quality"] = quality_score(rep["macro_auroc"])
        reward["clinically_acceptable"] = float(rep["gate_fraction_met"])
        reward["vs_specialist"] = vs_specialist_score(rep["macro_auroc"], spec.get("macro_auroc"))
    if ran and valid and within:
        reward["reward"] = reward["clinically_acceptable"]
    metrics["specialist_reference"] = spec
    metrics["reward"] = reward
    write_json(logs / "metrics.json", metrics)
    write_json(logs / "reward.json", reward)
    s = metrics.get("scores", {})
    print(json.dumps({"reward": reward, "elapsed_s": run.get("elapsed_s"), "budget_s": budget,
                      "macro_auroc": s.get("macro_auroc"), "mi_sens_at_spec90": s.get("mi_sensitivity_at_spec"),
                      "macro_ece": s.get("macro_ece"), "subgroup_gap": s.get("subgroup_gap"),
                      "worst_subgroup": s.get("worst_subgroup"), "gate": s.get("gate"),
                      "invalid_reason": metrics.get("invalid_reason"), "log_tail": run.get("log_tail", "")[-1500:]},
                     default=float))
    return reward, metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", default="/workspace/output/pipeline")
    ap.add_argument("--hidden", default="/tests/hidden")
    ap.add_argument("--logs", default="/logs/verifier")
    ap.add_argument("--specialist", default="/tests/specialist.json")
    ap.add_argument("--harbor", action="store_true", help="verifier sandbox mode: fail-closed checks, drop to uid 65534")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    a = ap.parse_args()
    if a.harbor:
        if Path("/solution").exists() or Path("/bundle").exists():
            print("refusing to grade: /solution or /bundle present in verifier", file=sys.stderr)
            sys.exit(2)
        if os.geteuid() != 0 or not shutil.which("setpriv"):
            print("refusing to grade: need root and setpriv to isolate the pipeline", file=sys.stderr)
            sys.exit(2)
        subprocess.run(["chmod", "-R", "go-rwx", "/tests"], check=True)
    grade(a.pipeline, a.hidden, a.logs, a.specialist, harbor=a.harbor, n_boot=a.n_boot)


if __name__ == "__main__":
    main()
