"""Rebuild the five scored Harbor tasks from local data.

This is the script that produced the tasks pushed to Valkyrie as
suite/clinical-v1@2. Data are not in Git: each family's document under
docs/research/suite/ says where to download its dataset and how to place it under
DATA_ROOT (default /home/jkwei/data/vals-suite/<family>/).

    ~/miniconda3/envs/vals-suite/bin/python scripts/export_suite_tasks.py \
        --out dist/suite-tasks-v3 [--families reg_resect ...]

Paths are made absolute: a relative export path once left the specialist outputs
empty (see docs/research/suite/integration.md).
"""
import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from suite.core.export import export_task  # noqa: E402

FAMILIES = ["reg_resect", "seg_spleen", "measure_hc18", "ecg_ptbxl", "risk_icu"]


def build(family, work, data_root, reg_specialist):
    if family == "reg_resect":
        from suite.families.reg_resect.spec import build_spec
        return build_spec(work, specialist_results_dir=reg_specialist)
    if family == "seg_spleen":
        from suite.families.seg_spleen.spec import build_spec
        return build_spec(work)
    if family == "measure_hc18":
        from suite.families.measure_hc18.spec import build_spec
        return build_spec(work)
    if family == "ecg_ptbxl":
        from suite.families.ecg_ptbxl.spec import build_spec
        return build_spec(work)
    if family == "risk_icu":
        from suite.families.risk_icu.spec import build_spec
        return build_spec(str(data_root / "risk_icu"), work)
    raise ValueError(f"unknown family {family}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="output folder; one subfolder per family")
    parser.add_argument("--work", type=Path, default=None, help="scratch folder (default: OUT/_work)")
    parser.add_argument("--data-root", type=Path, default=Path("/home/jkwei/data/vals-suite"))
    parser.add_argument("--reg-specialist", type=Path, default=None,
                        help="stored specialist outputs for reg_resect (a previous export's tests/specialist)")
    parser.add_argument("--families", nargs="+", default=FAMILIES, choices=FAMILIES)
    args = parser.parse_args()
    out = args.out.resolve()
    work = (args.work or out / "_work").resolve()
    reg_specialist = (args.reg_specialist or
                      REPO / "dist/suite-tasks/reg_resect/reg-resect-build-0001/tests/specialist").resolve()
    for family in args.families:
        (work / family).mkdir(parents=True, exist_ok=True)
        spec = build(family, work / family, args.data_root.resolve(), reg_specialist)
        print(family, export_task(spec, out / family))


if __name__ == "__main__":
    main()
