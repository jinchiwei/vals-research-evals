"""Grader self-check on the real hidden cases (local, project env).

  python -I selfcheck/run_selfcheck.py STAGED_HIDDEN_DIR SPECIALIST_JSON WORK_DIR [--limit 300]

Runs oracle, empty, wrong_volume and too_slow through grader.grade(). too_slow runs
with a short limit (5 s, pipeline sleeps 8 s) so the check takes seconds instead of
40 minutes; the timeout code path is identical to the real limit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import grader  # noqa: E402

EXPECT = {  # name: (expected reward, expected valid fraction, expected within_time)
    "oracle": (1.0, 1.0, 1.0),
    "empty": (0.0, 1.0, 1.0),
    "wrong_volume": (0.0, 0.0, 1.0),
    "too_slow": (0.0, None, 0.0),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hidden", type=Path)
    ap.add_argument("specialist", type=Path)
    ap.add_argument("work", type=Path)
    ap.add_argument("--limit", type=float, default=grader.CASE_TIME_LIMIT_SEC)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.environ.setdefault("SEG_SPLEEN_PIPELINE_PATH", f"{Path(sys.executable).parent}:/usr/bin:/bin")
    spec = json.loads(a.specialist.read_text())
    results, ok = {}, True
    for name, (exp_reward, exp_valid, exp_time) in EXPECT.items():
        if a.only and name not in a.only.split(","):
            continue
        limit = 5.0 if name == "too_slow" else a.limit
        env = {"SEG_SPLEEN_ORACLE_REFS": str(a.hidden), "SEG_SPLEEN_SLOW_SEC": "8"}
        reward, metrics = grader.grade(HERE / name, a.hidden, a.work / name, spec, limit,
                                       unprivileged=False, extra_env=env, log=lambda s: None)
        passed = (abs(reward["reward"] - exp_reward) < 1e-9
                  and (exp_valid is None or abs(reward["valid"] - exp_valid) < 1e-9)
                  and abs(reward["within_time"] - exp_time) < 1e-9)
        ok &= passed
        errs = sorted({c["error"] for c in metrics["cases"] if c.get("error")})
        results[name] = {"reward": reward, "passed": passed, "errors": errs}
        print(name, "PASS" if passed else "FAIL", json.dumps(reward), errs[:2], flush=True)
    (a.work / "selfcheck.json").write_text(json.dumps(results, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
