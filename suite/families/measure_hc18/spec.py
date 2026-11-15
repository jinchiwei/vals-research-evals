"""Build the measure_hc18 FamilySpec for suite/core/export.py.

    from suite.families.measure_hc18.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec('/tmp/hc18-work'), 'dist/suite-measure_hc18')

Reads the staged split from DATA_ROOT (default /home/jkwei/data/vals-suite/measure_hc18/staged,
written by split.py) and the specialist's stored hidden-case outputs from
DATA_ROOT/comparators/<name>/outputs.json (written by run_comparator.py). Hidden references go only
to tests/hidden/<case>/reference/reference.json; environment/data/ gets development cases only.
"""
import json
import shutil
from pathlib import Path

from suite.core.export import DEFAULT_PACKAGES, FamilySpec

from . import grader

DATA_ROOT = Path("/home/jkwei/data/vals-suite/measure_hc18")
HERE = Path(__file__).resolve().parent
# Specialist = the comparator with the better development-set quality (decided on dev, not hidden).
SPECIALIST = json.loads((HERE / "split" / "specialist_choice.json").read_text())["specialist"] \
    if (HERE / "split" / "specialist_choice.json").exists() else "classical"

README = (HERE / "task" / "README.md").read_text() if (HERE / "task" / "README.md").exists() else ""
OUTPUT_FORMAT = f"""Each hidden case is a folder `INPUT_DIR` with:

- `image.png`: 8-bit greyscale 2D ultrasound image (about 800 x 540 pixels).
- `case.json`: `{{"case_id": "case_xxxxxx", "pixel_size_mm": <float>}}`. Pixels are square.

`run.sh INPUT_DIR OUTPUT_DIR` must write `OUTPUT_DIR/{grader.OUTPUT_NAME}`, a CSV with exactly this
header and one row:

```
case_id,hc_mm
case_xxxxxx,174.32
```

`hc_mm` is the head circumference in **millimetres** (a finite number). Values outside
{grader.VALID_RANGE_MM[0]:g}-{grader.VALID_RANGE_MM[1]:g} mm are treated as invalid (that is what an answer in
pixels or centimetres looks like). Limit: {grader.TIME_LIMIT_S:g} s wall clock per image, measured by the grader
from process start, on 4 CPUs, no GPU, no network.
"""


# Classical comparator on the 83 hidden images: 63 within 4.9 % (doc: "0.76 (0.66-0.84)").
EXPECTED_SOLUTION_REWARD = 63 / 83


def build_spec(work_dir, data_root=DATA_ROOT, task_id="measure-hc18-0001"):
    work = Path(work_dir)
    if work.exists():
        shutil.rmtree(work)
    st = Path(data_root) / "staged"
    public = work / "public"
    shutil.copytree(st / "visible", public / "dev")
    (public / "README.md").write_text(README + "\n\n## Output format\n\n" + OUTPUT_FORMAT)
    (public / "LICENSE-DATA.md").write_text(LICENSE_DATA)
    hidden = {}
    refs = {r.split(",")[0]: r.split(",") for r in (st / "hidden" / "references.csv").read_text().split()[1:]}
    for cid, (_, hc, stratum, band) in refs.items():
        d = work / "hidden" / cid
        shutil.copytree(st / "hidden" / "inputs" / cid, d / "input")
        (d / "reference").mkdir(parents=True)
        (d / "reference" / "reference.json").write_text(
            json.dumps({"hc_mm": float(hc), "stratum": stratum, "band": band}) + "\n")
        hidden[cid] = d
    # Specialist: stored outputs + grader-measured runtimes (U-Net needs torch, absent from the image).
    outs = json.loads((Path(data_root) / "comparators" / SPECIALIST / "outputs.json").read_text())
    spec_dir = work / "specialist"
    for cid, o in outs.items():
        (spec_dir / cid).mkdir(parents=True)
        (spec_dir / cid / grader.OUTPUT_NAME).write_text(f"case_id,hc_mm\n{cid},{o['hc_mm']}\n")
    (spec_dir / "runtime.json").write_text(json.dumps(
        {"name": SPECIALIST, "wall_seconds": {c: o["seconds"] for c, o in outs.items()},
         "note": "measured on teal (WSL2, 4 threads) through the family grader"}))
    # Oracle for the hosted check: the classical pipeline, built from agent-visible material only.
    oracle = work / "oracle"
    shutil.copytree(HERE / "pipelines" / "classical", oracle)
    return FamilySpec(
        family="measure_hc18", task_id=task_id,
        title="Fetal head circumference in mm from 2D ultrasound (HC18)",
        readme_md=README, output_format_md=OUTPUT_FORMAT,
        grader_module="suite.families.measure_hc18.grader",
        public_dir=public, hidden_cases=hidden, oracle_pipeline_dir=oracle,
        specialist_results_dir=spec_dir, specialist_name=f"{SPECIALIST} comparator",
        time_limit_seconds=grader.TIME_LIMIT_S, cpus=4, memory_mb=8192, tier="build",
        # solution/ ships the classical comparator: 76 % of hidden images within tolerance (measure_hc18.md).
        expected_solution_reward=EXPECTED_SOLUTION_REWARD, scored=True,
        packages=DEFAULT_PACKAGES + ("pillow==11.0.0", "pandas==2.2.3"),
        metadata={"dataset": "HC18 (Zenodo 1327317, CC BY 4.0)", "family_kind": "measurement",
                  "n_dev": len(list((public / "dev").glob("case_*"))), "n_hidden": len(hidden),
                  "tolerance": "4.9% of reference HC (Sarris 2012)", "time_limit_source": "Han 2024 Table 7"})


LICENSE_DATA = """# Data licence

Images and reference head circumferences are from the HC18 dataset: van den Heuvel TLA, de Bruijn D,
de Korte CL, van Ginneken B. Automated measurement of fetal head circumference using 2D ultrasound
images. PLoS ONE 2018;13(8):e0200412. Zenodo record 1327317 (doi:10.5281/zenodo.1327317).

Licence: Creative Commons Attribution 4.0 International (CC BY 4.0),
https://creativecommons.org/licenses/by/4.0/legalcode

Modifications: a subset of the training set; images re-encoded as metadata-free 8-bit greyscale PNG
(pixel values unchanged); files renamed to opaque case IDs; pixel size moved into case.json; the
annotation outline images re-encoded the same way.
"""
