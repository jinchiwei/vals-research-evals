"""Run any contract pipeline on staged cases with the grader's runner and score it.

Used for the specialist (TotalSegmentator), the classical reference and the
self-check pipelines. Timing is the grader's monotonic clock around run.sh.

  python -I evaluate_pipeline.py PIPELINE_DIR SPLIT_DIR(dev|hidden) OUT_DIR LABEL \
      [--cases a,b] [--limit 300] [--env K=V ...]

Pin CPUs from outside, e.g. `taskset -c 0-3 python ...`; OMP etc. are set to --threads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grader  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pipeline", type=Path)
    ap.add_argument("cases_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("label")
    ap.add_argument("--cases", default="")
    ap.add_argument("--limit", type=float, default=3600)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--env", nargs="*", default=[])
    args = ap.parse_args()
    extra = dict(kv.split("=", 1) for kv in args.env)
    os.environ.setdefault("SEG_SPLEEN_PIPELINE_PATH",
                          f"{Path(sys.executable).parent}:/usr/bin:/bin")
    cases = sorted(p.name for p in args.cases_dir.iterdir() if (p / "image.nii.gz").is_file())
    if args.cases:
        keep = set(args.cases.split(","))
        cases = [c for c in cases if c in keep]
    rows = []
    for case in cases:
        out_dir = args.out / args.label / case
        run = grader.run_case(args.pipeline, args.cases_dir / case, out_dir, args.limit,
                              args.threads, unprivileged=False, extra_env=extra)
        shape, affine, ref = grader._load_ref(args.cases_dir / case)
        row = {"case": case, "wall_sec": round(run["wall_sec"], 2), "exit_code": run["exit_code"],
               "timed_out": run["timed_out"]}
        try:
            mask, ml = grader.load_submission(out_dir, shape, affine)
            row.update(grader.case_metrics(ref, mask, affine, ml))
            row["valid"] = True
            row["acceptable"] = grader.acceptable(row)
        except grader.SubmissionError as e:
            row.update({"valid": False, "error": str(e), "acceptable": False, "dice": 0.0})
            if run["exit_code"]:
                row["log_tail"] = run["log_tail"]
        rows.append(row)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}),
              flush=True)
    res_path = args.out / f"{args.label}.json"
    res_path.write_text(json.dumps({"label": args.label, "threads": args.threads,
                                    "env": extra, "cases": rows}, indent=1))


if __name__ == "__main__":
    main()
