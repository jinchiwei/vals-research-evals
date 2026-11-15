"""Build the causal_ate FamilySpec for suite.core.export (packaging only; nothing is uploaded).

    from suite.families.causal_ate.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec('/home/jkwei/data/vals-suite/causal_ate', '/abs/work'), '/abs/dist/suite-tasks-causal-v1')

Needs DATA_ROOT/split/ (datagen/prepare_data.py) and DATA_ROOT/results/hidden/{dr_att/estimates.json,
dr_att/runtime.json,summary.json} (comparators/run_comparators.py). Cohort grading: one hidden folder "cohort" holding the 48
hidden datasets (input/<id>/data.csv) and reference/truth.csv. The agent sees only the 32 development
datasets with their true SATT, the README and the covariate licence. The data-generating code
(datagen/) and its seed are not exported anywhere: export.vendor_library copies only the family's
top-level *.py files (grader, gate, spec) into tests/lib.
"""
import json
import shutil
from pathlib import Path

from suite.core.export import FamilySpec, family_packages

from .gate import GATE, N_HIDDEN

HERE = Path(__file__).resolve().parent
TASK_ID = 'causal-satt-0001'
CASE = 'cohort'
ORACLE = HERE / 'comparators' / 'pipelines' / 'dr_att'

OUTPUT_FORMAT = """`run.sh INPUT_DIR OUTPUT_DIR` must write `OUTPUT_DIR/estimates.json`:

```json
{"estimand": "SATT",
 "datasets": {"<dataset_id>": {"estimate": 1.23, "ci_lower": 0.98, "ci_upper": 1.48}, ...}}
```

- one entry for **every** dataset folder in `INPUT_DIR` (keys are the folder names);
- `estimate` is the SATT in the outcome's own units; `ci_lower`/`ci_upper` bound your 95% interval;
- all three are finite numbers with `ci_lower <= estimate <= ci_upper`.

A missing dataset, a non-finite number or a malformed file makes the whole output invalid (score 0).
The pipeline is called once on all 48 hidden datasets; the time limit covers all of them.
"""

LICENSE_DATA = """# Data licence and attribution

Covariates: derived from set A of "Predicting Mortality of ICU Patients: The PhysioNet/Computing in Cardiology
Challenge 2012", version 1.0.0, https://physionet.org/content/challenge-2012/1.0.0/ (first/extreme values of
routine measurements per stay, cleaned and median-imputed; record identifiers removed). Treatment `z` and
outcome `y` are simulated and are not data from the challenge.

Licence of the source data: Open Data Commons Attribution License v1.0 (ODC-By),
https://opendatacommons.org/licenses/by/1-0/

Please cite: Silva I, Moody G, Scott DJ, Celi LA, Mark RG. Predicting In-Hospital Mortality of ICU Patients:
The PhysioNet/Computing in Cardiology Challenge 2012. Computing in Cardiology 2012;39:245-248.
Goldberger AL et al. PhysioBank, PhysioToolkit, and PhysioNet. Circulation 2000;101(23):e215-e220.
Simulation design after: Dorie V, Hill J, Shalit U, Scott M, Cervone D. Automated versus do-it-yourself
methods for causal inference: lessons learned from a data analysis competition. Statistical Science
2019;34(1):43-68.
"""


def build_spec(data_root, work_dir):
    root, work = Path(data_root).resolve(), Path(work_dir).resolve()
    split = root / 'split'
    public = work / 'public'
    (public / 'dev' / 'reference').mkdir(parents=True)
    shutil.copytree(split / 'dev' / 'input', public / 'dev' / 'input')
    shutil.copyfile(split / 'dev' / 'reference' / 'truth.csv', public / 'dev' / 'reference' / 'truth.csv')
    readme = (HERE / 'README.md').read_text()
    (public / 'README.md').write_text(readme)
    (public / 'LICENSE-DATA.md').write_text(LICENSE_DATA)

    hidden = work / 'hidden' / CASE
    hidden.mkdir(parents=True)
    shutil.copytree(split / 'hidden' / 'input', hidden / 'input')
    shutil.copytree(split / 'hidden' / 'reference', hidden / 'reference')
    n = len([p for p in (hidden / 'input').iterdir() if p.is_dir()])
    if n != N_HIDDEN:
        raise ValueError(f'expected {N_HIDDEN} hidden datasets, found {n}')

    results = root / 'results' / 'hidden' / 'dr_att'
    run = json.loads((results / 'runtime.json').read_text())
    summary = json.loads((root / 'results' / 'hidden' / 'summary.json').read_text())['dr_att']
    expected = 1.0 if summary['all_parts'] else 0.0      # the oracle is the specialist pipeline
    spec_dir = work / 'specialist'
    (spec_dir / CASE).mkdir(parents=True)
    shutil.copyfile(results / 'estimates.json', spec_dir / CASE / 'estimates.json')
    (spec_dir / 'runtime.json').write_text(json.dumps({
        'name': 'cross-fitted doubly robust (AIPW) SATT estimator, gradient boosting + linear nuisance models',
        'wall_seconds': {CASE: run['wall_seconds']},
        'measured_on': run['measured_on']}, indent=2) + '\n')

    packages, _ = family_packages('causal_ate')
    return FamilySpec(
        family='causal_ate', task_id=TASK_ID,
        title='Average treatment effect on the treated with a valid 95% interval (semi-synthetic ICU data)',
        readme_md=readme, output_format_md=OUTPUT_FORMAT, grader_module='suite.families.causal_ate.grader',
        public_dir=public, hidden_cases={CASE: hidden}, oracle_pipeline_dir=ORACLE,
        specialist_results_dir=spec_dir, specialist_name='cross-fitted doubly robust (AIPW) specialist estimator',
        time_limit_seconds=float(GATE['time_limit_s']), cpus=4, memory_mb=8192, threads=4, packages=packages,
        grading='cohort', cohort_size=None, agent_timeout_sec=2700.0, tier='build',
        expected_solution_reward=expected, scored=True,
        metadata={'category': 'causal-inference', 'dataset': 'semi-synthetic over PhysioNet/CinC 2012 covariates '
                  '(ODC-BY 1.0); ACIC-2016-style DGP', 'hidden': '48 datasets (16 settings x 3), set-B stays',
                  'estimand': 'SATT', 'tags': ['tabular', 'causal', 'interval-coverage']})
