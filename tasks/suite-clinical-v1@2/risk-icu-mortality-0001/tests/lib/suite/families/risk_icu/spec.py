"""Build the risk_icu FamilySpec for suite.core.export (packaging only; nothing is uploaded).

    from suite.families.risk_icu.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec('/home/jkwei/data/vals-suite/risk_icu', work_dir), 'dist/suite-risk-icu')

Needs DATA_ROOT/split/ (prepare_data.py), DATA_ROOT/pipelines/gbm (comparators/fit_gbm.py) and
DATA_ROOT/results/selfcheck/oracle.json (selfcheck.py, for the measured specialist runtime).

Cohort grading (suite.core grading='cohort'): one hidden folder "cohort" = all 4,000 set-B stays (re-drawn RecordIDs) with
reference/outcomes.csv; the agent sees set A under environment/data/dev/{input,reference}/.
The specialist is the gradient-boosted comparator; its hidden-set predictions and measured
runtime are shipped precomputed in tests/specialist/. The oracle is the same pipeline, which was
fitted on set A only, so it is buildable from agent-visible material.
"""
import json
import shutil
from pathlib import Path

from suite.core.export import FamilySpec, family_packages

from .gate import GATE

HERE = Path(__file__).resolve().parent
TASK_ID = 'risk-icu-mortality-0001'
CASE = 'cohort'

OUTPUT_FORMAT = """`INPUT_DIR` holds the record files of every stay to score (`<RecordID>.txt`, same format as
`/workspace/data/dev/input/`). `run.sh` must write `OUTPUT_DIR/predictions.csv`: header `RecordID,risk`,
then exactly one row per input file, `risk` a finite probability of in-hospital death in [0, 1].
The pipeline is called once on the whole hidden cohort (about 4,000 stays); the time limit covers all of it.
"""

LICENSE_DATA = """# Data licence and attribution

Development data: set A of "Predicting Mortality of ICU Patients: The PhysioNet/Computing in Cardiology
Challenge 2012", version 1.0.0, https://physionet.org/content/challenge-2012/1.0.0/ (files set-a.tar.gz and
Outcomes-a.txt, unmodified; record files moved into dev/input/, outcomes into dev/reference/).

Licence: Open Data Commons Attribution License v1.0 (ODC-By),
https://opendatacommons.org/licenses/by/1-0/

Please cite: Silva I, Moody G, Scott DJ, Celi LA, Mark RG. Predicting In-Hospital Mortality of ICU Patients:
The PhysioNet/Computing in Cardiology Challenge 2012. Computing in Cardiology 2012;39:245-248.
Goldberger AL et al. PhysioBank, PhysioToolkit, and PhysioNet. Circulation 2000;101(23):e215-e220.
"""


def _link_or_copy_tree(src, dst):
    shutil.copytree(src, dst)


def build_spec(data_root, work_dir):
    root, work = Path(data_root), Path(work_dir)
    split = root / 'split'
    public = work / 'public'
    (public / 'dev' / 'reference').mkdir(parents=True)
    _link_or_copy_tree(split / 'dev' / 'records', public / 'dev' / 'input')
    shutil.copyfile(split / 'dev' / 'Outcomes-a.txt', public / 'dev' / 'reference' / 'Outcomes-a.txt')
    readme = (HERE / 'README.md').read_text()
    (public / 'README.md').write_text(readme)
    (public / 'LICENSE-DATA.md').write_text(LICENSE_DATA)

    hidden = work / 'hidden' / CASE
    (hidden / 'reference').mkdir(parents=True)
    _link_or_copy_tree(split / 'hidden' / 'records', hidden / 'input')
    shutil.copyfile(split / 'hidden' / 'outcomes.csv', hidden / 'reference' / 'outcomes.csv')

    n = len(list((hidden / 'input').glob('*.txt')))
    packages, _ = family_packages('risk_icu')
    oracle_run = json.loads((root / 'results' / 'selfcheck' / 'oracle.json').read_text())
    spec_dir = work / 'specialist'
    (spec_dir / CASE).mkdir(parents=True)
    shutil.copyfile(root / 'results' / 'gbm' / 'predictions.csv', spec_dir / CASE / 'predictions.csv')
    (spec_dir / 'runtime.json').write_text(json.dumps({
        'name': 'gradient-boosted comparator (HistGradientBoosting + isotonic, fit on set A)',
        'wall_seconds': {CASE: oracle_run['run']['wall_s']},
        'measured_on': 'teal (WSL2, 16 logical CPUs, thread caps 4) via risk_icu grade.run_pipeline'}, indent=2) + '\n')

    return FamilySpec(
        family='risk_icu', task_id=TASK_ID, title='48-hour ICU in-hospital mortality risk (calibrated)',
        readme_md=readme, output_format_md=OUTPUT_FORMAT, grader_module='suite.families.risk_icu.grader',
        public_dir=public, hidden_cases={CASE: hidden}, oracle_pipeline_dir=root / 'pipelines' / 'gbm',
        specialist_results_dir=spec_dir, specialist_name='gradient-boosted specialist model',
        time_limit_seconds=float(GATE['time_limit_s']), cpus=4, memory_mb=8192, packages=packages,
        grading='cohort', cohort_size=n, tier='build', expected_solution_reward=1.0, scored=True,
        metadata={'category': 'clinical-ml', 'dataset': 'PhysioNet/CinC Challenge 2012 v1.0.0 (ODC-BY 1.0)', 'tier': 'build',
                  'hidden': 'set B, 4000 stays, re-drawn RecordIDs', 'tags': ['tabular', 'risk', 'calibration']})
