"""Build the ecg_ptbxl FamilySpec for suite.core.export (cohort grading; replaces build_task.py).

    from suite.families.ecg_ptbxl.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec('/abs/work'), '/abs/dist/suite-tasks/ecg_ptbxl')

Reads DATA_ROOT/work (prepare_data.py, train_*.py, selfcheck.py):
  dev/{signals.npz,meta.csv,labels.csv}          -> environment/data/dev/ (agent-visible)
  hidden/input/{signals.npz,meta.csv}, hidden/reference.csv -> tests/hidden/cohort/{input,reference}/
  selfcheck/specialist/eval/out/predictions.csv  -> tests/specialist/cohort/ (stored specialist output)
  specialist.json (elapsed_s, grader-measured)   -> tests/specialist/runtime.json
  simple_pipeline/                               -> solution/pipeline (fitted on dev only)
"""
import json
import shutil
from pathlib import Path

from suite.core.export import FamilySpec, family_packages

from . import grader

DATA_ROOT = Path('/home/jkwei/data/vals-suite/ecg_ptbxl')
HERE = Path(__file__).resolve().parent
TASK_ID = 'ecg-ptbxl-superdiag-0001'
CASE = 'cohort'

OUTPUT_FORMAT = """`INPUT_DIR` holds `signals.npz` and `meta.csv` for every hidden ECG (development format;
`meta.csv` has only `record_id`, `age`, `sex`). Write `OUTPUT_DIR/predictions.csv` with header exactly
`record_id,NORM,MI,STTC,CD,HYP` and one row per `record_id`, each value a finite probability in [0, 1].
"""

LICENSE_DATA = """# Data licence and attribution

The ECGs and labels in `dev/` are derived from **PTB-XL, version 1.0.3**:

Wagner, P., Strodthoff, N., Bousseljot, R., Samek, W., & Schaeffter, T. (2022). PTB-XL, a large publicly
available electrocardiography dataset (version 1.0.3). PhysioNet. https://doi.org/10.13026/kfzx-aw45
(Wagner et al., Scientific Data 7, 154, 2020; Goldberger et al., PhysioNet, Circulation 101(23), 2000.)

Licence: Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/).

Modifications: 100 Hz records only, re-packed losslessly as int16 microvolts; a stratified subsample of the
dataset's folds 1-8; random record and patient identifiers; ages over 89 (coded 300) written as 90; sex coded
M/F; SCP-ECG statements aggregated to five diagnostic superclasses.
"""


def build_spec(work_dir, data_root=DATA_ROOT):
    work, data = Path(work_dir), Path(data_root) / 'work'
    readme = (HERE / 'README.md').read_text()
    public = work / 'public'
    (public / 'dev').mkdir(parents=True)
    for name in ('signals.npz', 'meta.csv', 'labels.csv'):
        shutil.copyfile(data / 'dev' / name, public / 'dev' / name)
    (public / 'README.md').write_text(readme)
    (public / 'LICENSE-DATA.md').write_text(LICENSE_DATA)

    hidden = work / 'hidden' / CASE
    shutil.copytree(data / 'hidden' / 'input', hidden / 'input')
    (hidden / 'reference').mkdir(parents=True)
    shutil.copyfile(data / 'hidden' / 'reference.csv', hidden / 'reference' / 'reference.csv')
    n = sum(1 for _ in open(hidden / 'reference' / 'reference.csv')) - 1

    spec_dir = work / 'specialist'
    (spec_dir / CASE).mkdir(parents=True)
    shutil.copyfile(data / 'selfcheck' / 'specialist' / 'eval' / 'out' / 'predictions.csv',
                    spec_dir / CASE / 'predictions.csv')
    measured = json.loads((data / 'specialist.json').read_text())
    (spec_dir / 'runtime.json').write_text(json.dumps({
        'name': 'xresnet1d-style CNN (folds 1-8, Platt-calibrated on fold 9)',
        'wall_seconds': {CASE: measured['elapsed_s']},
        'measured_on': 'teal (WSL2), 4 threads, CPU, through the family grader clock'}, indent=2) + '\n')

    packages, index = family_packages('ecg_ptbxl')
    return FamilySpec(
        family='ecg_ptbxl', task_id=TASK_ID, title='12-lead ECG triage: calibrated diagnostic probabilities',
        readme_md=readme, output_format_md=OUTPUT_FORMAT, grader_module='suite.families.ecg_ptbxl.grader',
        public_dir=public, hidden_cases={CASE: hidden}, oracle_pipeline_dir=data / 'simple_pipeline',
        specialist_results_dir=spec_dir, specialist_name='xresnet1d-style CNN specialist',
        time_limit_seconds=grader.time_limit_seconds(n), hard_kill_seconds=grader.hard_kill_seconds(n),
        grading='cohort', cohort_size=n, cpus=4, memory_mb=8192, agent_timeout_sec=1800.0,
        packages=packages, pip_extra_index_url=index, tier='build',
        # Shipped solution = simple reference: gate 2/3 (fails calibration narrowly, ECE 0.0503), so the
        # cohort rule gives 0.0 (docs/research/suite/ecg_ptbxl.md reported 0.67 under the old fraction rule).
        expected_solution_reward=0.0, scored=True,
        metadata={'category': 'clinical-ml', 'dataset': 'PTB-XL 1.0.3 (PhysioNet, CC BY 4.0)', 'n_hidden_ecgs': n, 'seed': 20261114,
                  'tags': ['ecg', 'classification', 'calibration', 'subgroups']})
