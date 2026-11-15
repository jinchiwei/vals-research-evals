"""Grader self-check: build the reference and failure pipelines and grade each on the hidden set.

Pipelines (all follow the agent contract run.sh INPUT_DIR OUTPUT_DIR):
  oracle        the specialist gradient-boosted pipeline (fit on set A only; comparators/fit_gbm.py)
  constant      every stay gets the set-A mortality 0.1385
  overconfident oracle ranking with logits multiplied by 3 (good AUROC, miscalibrated)
  slow          oracle preceded by a 400 s sleep (exceeds the 300 s limit)
  invalid       oracle output with one risk replaced by NaN

Usage: python -I selfcheck.py DATA_ROOT [names...]
Writes DATA_ROOT/results/selfcheck/<name>.json and summary.json (individual predictions stay under DATA_ROOT).
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade  # noqa: E402

RUN_PY = '#!/usr/bin/env bash\nset -euo pipefail\nHERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'


def build(root: str) -> dict:
    base = os.path.join(root, "pipelines")
    gbm = os.path.join(base, "gbm")
    assert os.path.isfile(os.path.join(gbm, "model.pkl")), "fit the gbm comparator first"
    paths = {"oracle": gbm}
    for name, body in {
        "overconfident": 'exec python3 -I "$HERE/predict.py" "$1" "$2" overconfident\n',
        "slow": 'sleep 400\nexec python3 -I "$HERE/predict.py" "$1" "$2"\n',
        "invalid": 'python3 -I "$HERE/predict.py" "$1" "$2"\nsed -i "2s/,.*/,nan/" "$2/predictions.csv"\n',
    }.items():
        d = os.path.join(base, name)
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(gbm, d)
        with open(os.path.join(d, "run.sh"), "w") as h:
            h.write(RUN_PY + body)
        paths[name] = d
    d = os.path.join(base, "constant")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "run.sh"), "w") as h:
        h.write(RUN_PY + 'mkdir -p "$2"\n{ echo "RecordID,risk"; for f in "$1"/*.txt; do b="${f##*/}"; b="${b%.txt}"; '
                'echo "$b,0.1385"; done; } > "$2/predictions.csv"\n')
    paths["constant"] = d
    return paths


def main(root: str, names=None):
    paths = build(root)
    gate = grade.load_gate()
    out_dir = os.path.join(root, "results", "selfcheck")
    os.makedirs(out_dir, exist_ok=True)
    spec_path = os.path.join(out_dir, "oracle.json")
    names = names or ["oracle", "constant", "overconfident", "invalid", "slow"]
    for name in names:
        spec = None
        if name != "oracle" and os.path.exists(spec_path):
            with open(spec_path) as h:
                spec = json.load(h)["metrics"]["auroc"]
        res = grade.grade(paths[name], os.path.join(root, "split", "hidden", "records"),
                          os.path.join(root, "split", "hidden", "outcomes.csv"), gate,
                          os.path.join(root, "work", name), gate["time_limit_s"],
                          specialist_auroc=spec, n_boot=1000 if name in ("oracle", "overconfident") else 200)
        if name == "oracle" and res["metrics"]:  # the oracle is the specialist: vs_specialist against itself
            r = res["reward"]
            res["reward"] = grade.reward_from(r["ran"] == 1.0, r["valid"] == 1.0, r["within_time"] == 1.0,
                                              res["metrics"], res["metrics"]["auroc"])
        with open(os.path.join(out_dir, f"{name}.json"), "w") as h:
            json.dump(res, h, indent=1, default=float)
        m = res["metrics"] or {}
        print(name, json.dumps({"reward": res["reward"], "wall_s": res["run"]["wall_s"],
                                "err": res["validation_error"],
                                **{k: m.get(k) for k in ("auroc", "event1", "cal_slope", "cal_intercept_citl",
                                                         "net_benefit", "net_benefit_treat_all", "worst_subgroup",
                                                         "worst_subgroup_auroc", "gate")}}, default=float), flush=True)
    summary = {}
    for name in ["oracle", "constant", "overconfident", "invalid", "slow"]:
        p = os.path.join(out_dir, f"{name}.json")
        if os.path.exists(p):
            with open(p) as h:
                summary[name] = json.load(h)["reward"]
    with open(os.path.join(out_dir, "summary.json"), "w") as h:
        json.dump(summary, h, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or None)
