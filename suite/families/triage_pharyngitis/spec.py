"""FamilySpec for triage_pharyngitis (build tier), for suite.core.export.export_task.

    from suite.families.triage_pharyngitis.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec(work_dir), 'dist/suite-triage')

Needs the prepared data (prepare_data.py), the ImageNet ResNet-50 weights in DATA/models/ and the
comparator outputs (comparators.py). The hidden cohort is ONE grader case named 'cohort'.
Specialist = comparator (d), image features + symptoms, whose hidden outputs and runtime were measured
on teal by comparators.py. Oracle (solution/pipeline) = the same comparator pipeline: it was fitted only
on development patients and reads only /workspace/data, so it is buildable from agent-visible material.
"""
import json
import shutil
from pathlib import Path

from suite.core.export import FamilySpec, family_packages

from . import grader
from .prepare_data import DEFAULT_DATA, FAMILY_DIR

TASK_ID = 'triage-pharyngitis-0001'
SPECIALIST = 'combined'

OUTPUT_FORMAT = """`run.sh INPUT_DIR OUTPUT_DIR` is called **once for the whole hidden cohort**. `INPUT_DIR` holds
`patients.csv` (same columns as `dev/input/patients.csv`) and `images/<case_id>.jpg`. Write
`OUTPUT_DIR/predictions.json`:

    {"predictions": [{"case": "<case_id>", "probability": 0.27}, ...]}

exactly one entry per `case_id` in `patients.csv`, each probability a finite number in [0, 1] (the
probability that the case is bacterial by the panel definition). No other keys, no duplicates, no NaN;
anything else makes the whole submission invalid. Nothing is clipped or repaired.
"""


def build_public(data, dest):
    """Agent-visible tree: README.md, dev/input/{patients.csv,images/}, dev/reference/labels.csv, models/."""
    dest = Path(dest)
    pub = data / 'prepared' / 'public' / 'dev'
    shutil.copytree(pub / 'images', dest / 'dev' / 'input' / 'images')
    shutil.copyfile(pub / 'patients.csv', dest / 'dev' / 'input' / 'patients.csv')
    (dest / 'dev' / 'reference').mkdir(parents=True)
    shutil.copyfile(pub / 'labels.csv', dest / 'dev' / 'reference' / 'labels.csv')
    (dest / 'models').mkdir()
    shutil.copyfile(data / 'models' / 'resnet50_imagenet1k_v2.pth', dest / 'models' / 'resnet50_imagenet1k_v2.pth')
    (dest / 'README.md').write_text(readme() + '\n## Required outputs\n\n' + OUTPUT_FORMAT)
    (dest / 'LICENSE-data.txt').write_text(
        'Throat images, symptoms and physician votes: PGUPharyngitis, Shojaei N. et al., Scientific Data 12:1418 '
        '(2025), figshare doi:10.6084/m9.figshare.28163513.v1, licensed CC BY 4.0 '
        '(https://creativecommons.org/licenses/by/4.0/). Modified: EXIF/XMP metadata removed, files renamed, one '
        'PNG re-encoded as JPEG, binary labels derived from the votes, patients split.\n'
        'ResNet-50 weights: torchvision IMAGENET1K_V2 (BSD-3-Clause code; trained on ImageNet-1k).\n')
    return dest


def readme():
    return (FAMILY_DIR / 'task_readme.md').read_text()


def build_spec(work_dir, data=DEFAULT_DATA):
    work, data = Path(work_dir), Path(data)
    public = build_public(data, work / 'public')
    hidden = data / 'prepared' / 'hidden' / 'cohort'
    n = sum(1 for _ in open(hidden / 'input' / 'patients.csv')) - 1
    spec_dir = work / 'specialist' / 'cohort'
    spec_dir.mkdir(parents=True)
    comp = data / 'comparators' / SPECIALIST
    shutil.copyfile(comp / 'predictions.json', spec_dir / 'predictions.json')
    summary = json.loads((data / 'comparators' / 'summary.json').read_text())
    (work / 'specialist' / 'runtime.json').write_text(json.dumps({
        'name': 'image features + symptoms logistic stacker',
        'wall_seconds': {'cohort': summary['hidden'][SPECIALIST]['run']['wall_seconds']},
        'measured_on': 'teal via suite.core.runner, 2 threads, CPU'}, indent=2) + '\n')
    oracle = work / 'oracle'
    packages, index = family_packages('triage_pharyngitis')
    shutil.copytree(data / 'pipelines' / SPECIALIST, oracle)
    return FamilySpec(
        family='triage_pharyngitis', task_id=TASK_ID,
        title='Sore-throat triage: bacterial pharyngitis probability from a phone throat photo and symptoms',
        readme_md=readme(), output_format_md=OUTPUT_FORMAT,
        grader_module='suite.families.triage_pharyngitis.grader', public_dir=public,
        hidden_cases={'cohort': hidden}, oracle_pipeline_dir=oracle, specialist_results_dir=work / 'specialist',
        specialist_name='frozen ImageNet ResNet-50 features + symptoms logistic stacker (fitted on development)',
        time_limit_seconds=grader.time_limit_seconds(n), cpus=2, memory_mb=8192, threads=2,
        packages=packages, pip_extra_index_url=index, grading='cohort', cohort_size=n, tier='build',
        # Shipped solution = comparator (d), gate 2/4 -> 0.0. No comparator passes the gate, so the task is
        # excluded from scoring and kept as a worked example (DESIGN.md).
        expected_solution_reward=0.0, scored=False,
        metadata={'category': 'clinical-ml', 'dataset': 'PGUPharyngitis (figshare 28163513 v1, CC BY 4.0)', 'tier': 'build',
                  'n_hidden_patients': n, 'grading_unit': 'cohort (one run on all hidden patients)',
                  'tags': ['classification', 'calibration', 'smartphone-photo', 'physician-vote-label']})
