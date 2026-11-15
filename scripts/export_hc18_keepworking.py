"""Export the round-3 "keep working" (K) variant of measure_hc18.

Round 3 workstream K (docs/research/suite/round3-prereg.md): the measure_hc18 task of
suite/clinical-v1@2 with one paragraph added to instruction.md and nothing else changed.
The task is built exactly as scripts/export_suite_tasks.py builds it (family build_spec,
then suite.core.export.export_task with absolute paths); the paragraph is then appended to
the exported instruction.md. suite/core/export.py is not changed, so the default export of
every family is unaffected.

    ~/miniconda3/envs/vals-suite/bin/python scripts/export_hc18_keepworking.py \
        --out dist/suite-tasks-k1
    ~/miniconda3/envs/vals-suite/bin/python scripts/export_hc18_keepworking.py \
        --out dist/suite-tasks-k2 --clock-check      # addendum K2: K plus the clock-check paragraph

Placement: the paragraph refers to "the clinical bar stated above", so it goes at the end of
instruction.md, after both scoring sections that state the bar.

This file lives in scripts/, not in suite/families/measure_hc18/, on purpose: export.py vendors
every top-level .py of the family package into tests/lib/, so a module there would change the
grader side of every measure_hc18 export.
"""
import argparse
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from suite.core.export import export_task  # noqa: E402

# Fixed in docs/research/suite/round3-prereg.md before any round-3 run. Do not edit.
KEEP_WORKING_PARAGRAPH = """**Using your session time.** Your session ends when you end your turn, and the pipeline is
then graded as found. If your own validation on the development cases is below the clinical bar
stated above, that is a reason to keep improving the pipeline, not to stop: use the remaining
session time to try better methods and re-validate, and keep the best working pipeline in place
at all times.
"""

# Addendum K2 in docs/research/suite/round3-prereg.md (registered 02:15 EST). Added after the K paragraph.
CLOCK_CHECK_PARAGRAPH = """**Checking the time.** Run `date` at the start of your session and note the time. Before you end
your turn, run `date` again and work out how much of the session remains. Do not end your turn
because you believe time is short without checking.
"""


def add_keep_working(instruction_text):
    """Return the instruction with the K paragraph appended as its own final paragraph."""
    if "**Using your session time.**" in instruction_text:
        raise ValueError("instruction already has the keep-working paragraph")
    return instruction_text.rstrip("\n") + "\n\n" + KEEP_WORKING_PARAGRAPH


def add_clock_check(instruction_text):
    """Return the K instruction with the K2 paragraph appended directly after the K paragraph."""
    if not instruction_text.endswith(KEEP_WORKING_PARAGRAPH):
        raise ValueError("expected the keep-working paragraph at the end of the instruction")
    if "**Checking the time.**" in instruction_text:
        raise ValueError("instruction already has the clock-check paragraph")
    return instruction_text + "\n" + CLOCK_CHECK_PARAGRAPH


def export_keep_working(out_dir, work_dir, data_root=None, clock_check=False):
    from suite.families.measure_hc18.spec import DATA_ROOT, build_spec
    spec = build_spec(Path(work_dir).resolve(), data_root=Path(data_root or DATA_ROOT).resolve())
    final = export_task(spec, Path(out_dir).resolve())
    try:
        path = final / "instruction.md"
        text = add_keep_working(path.read_text(encoding="utf-8"))
        if clock_check:
            text = add_clock_check(text)
        path.write_text(text, encoding="utf-8")
    except BaseException:
        shutil.rmtree(final, ignore_errors=True)
        raise
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="output folder; the task goes in OUT/measure_hc18/")
    parser.add_argument("--work", type=Path, default=None, help="scratch folder (default: OUT/_work)")
    parser.add_argument("--data-root", type=Path, default=Path("/home/jkwei/data/vals-suite/measure_hc18"))
    parser.add_argument("--clock-check", action="store_true",
                        help="also add the K2 clock-check paragraph (round3-prereg.md, addendum K2)")
    args = parser.parse_args()
    out = args.out.resolve()
    work = (args.work or out / "_work").resolve() / "measure_hc18"
    work.mkdir(parents=True, exist_ok=True)
    print("measure_hc18", export_keep_working(out / "measure_hc18", work, args.data_root,
                                                 clock_check=args.clock_check))


if __name__ == "__main__":
    main()
