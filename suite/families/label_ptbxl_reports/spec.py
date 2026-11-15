"""Export the label_ptbxl_reports task (direct-answer contract) as a Harbor/Valkyrie task folder.

suite.core.export.export_task assumes the pipeline contract (run.sh on hidden inputs, core grader).
This family gives the agent the hidden reports and grades a labels file, so it has its own writer.
It reuses the core's Dockerfile builder, task.toml builder, leak check and file manifest unchanged,
and adds family checks (no hidden ID among development rows, no PTB-XL metadata in the image).

Layout written:
  <task_id>/task.toml, instruction.md
  environment/Dockerfile, environment/data/{README.md, dev_reports.csv, hidden_reports.csv,
      diagnostic_statements.csv, LICENSE.txt}
  tests/test.sh, tests/grade.py, tests/task_config.json
  tests/lib/suite/{core/reward.py, families/label_ptbxl_reports/grader.py} (+ package inits)
  tests/hidden/cohort/reference/labels.json   hidden labels (verifier only)
  tests/specialist/labels.json, runtime.json  stored specialist labels
  solution/solve.sh, solution/label_tfidf.py  oracle: retrains the specialist from agent-visible data

Usage:
  python -m suite.families.label_ptbxl_reports.spec DATA_ROOT OUT_DIR
"""
import csv
import json
import os
import shutil
import sys
from pathlib import Path

from suite.core import export as core_export

FAMILY = 'label_ptbxl_reports'
TASK_ID = 'label-ptbxl-reports-0001'
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AGENT_TIMEOUT_SEC = 2700.0
VERIFIER_TIMEOUT_SEC = 600.0
CPUS, MEMORY_MB = 2, 4096
FORBIDDEN_TEXT = (b'scp_codes', b'ptbxl_database', b'ecg_id', b'patient_id', b'strat_fold', b'validated_by')
EXPECTED_SOLUTION_REWARD = 0.0      # the specialist misses the gate on the hidden set (doc section 2)
TITLE = 'Label free-text ECG reports with diagnostic superclasses (PTB-XL)'


def session_section():
    minutes = AGENT_TIMEOUT_SEC / 60
    return f"""## Session limit and what is graded (read first)

- **Your session lasts at most {minutes:g} minutes** ({AGENT_TIMEOUT_SEC:g} seconds) of wall-clock time.
  When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is `/workspace/output/labels.json` as it is when the session ends.** Nothing is
  finished, fixed or rerun for you afterwards. If the file is missing or invalid at that moment, the
  score is 0.
- We recommend writing a complete, valid `labels.json` early and improving it afterwards."""


def instruction(n_hidden, n_dev, packages):
    return f"""# {TITLE}

{session_section()}

## The task

A cardiology research registry wants structured diagnoses from the free-text interpretations that
cardiologists wrote for 12-lead ECGs, so that it can build cohorts without re-reading every report.
Your job is to assign each report the **diagnostic superclasses** it states, using the coding
convention of the PTB-XL dataset.

You get {n_dev:,} development reports **with** their labels and {n_hidden} reports **without** labels
(`/workspace/data/hidden_reports.csv`). Label the {n_hidden} reports. Start with
`/workspace/data/README.md`: it describes the reports (mostly German, some English and Swedish), the
five superclasses (NORM, MI, STTC, CD, HYP), the statement-to-superclass mapping
(`diagnostic_statements.csv`) and the rule that hedged statements count as present.

How you produce the labels is up to you: reading the reports, writing code, or both.

## Required output

Write `/workspace/output/labels.json`: one JSON object mapping **every** `record_id` in
`hidden_reports.csv` (and nothing else) to a list of superclass names, for example

    {{"r0123abcd": ["MI", "STTC"], "r4567ef01": ["NORM"]}}

- Names must be exactly `NORM`, `MI`, `STTC`, `CD`, `HYP`, each at most once per record; order does not
  matter. An empty list is allowed (it means no superclass), although every record in this task has at
  least one.
- Standard JSON only (no comments, no NaN). The file must be a regular file under 5 MB.
- Only `/workspace/output/` is carried to the grader. Other files there are ignored.

## Environment

- Python: `{core_export.VENV_PYTHON}` (packages: {", ".join(packages)}). No package installation.
- Network access in this sandbox is limited to the model API (api.anthropic.com).
- {CPUS} CPUs and {MEMORY_MB} MB RAM.

## How you are scored

A separate grader compares your labels with the hidden labels. The clinical gate has two parts, and
both must be met:

1. Cohen's kappa of at least 0.60 in **each** of the five superclasses;
2. macro-averaged F1 over the five superclasses of at least 0.80.

The headline score is 1 if `labels.json` is present and valid and both parts are met; otherwise it is
0, with no partial credit. Macro F1 is also reported as a quality score and compared with a text
classifier trained on the development reports, on the same {n_hidden} reports.
"""


def family_spec(public_dir, oracle_dir):
    pins, index = core_export.family_packages(FAMILY)
    return core_export.FamilySpec(
        family=FAMILY, task_id=TASK_ID, title=TITLE, readme_md='', output_format_md='',
        grader_module=f'suite.families.{FAMILY}.grader', public_dir=public_dir, hidden_cases={},
        oracle_pipeline_dir=oracle_dir, cpus=CPUS, memory_mb=MEMORY_MB, agent_timeout_sec=AGENT_TIMEOUT_SEC,
        packages=pins, pip_extra_index_url=index, grading='direct_answer', tier='direct-answer control',
        expected_solution_reward=EXPECTED_SOLUTION_REWARD, scored=False, time_limit_seconds=0.0,
        metadata={'contract': 'direct_answer: agent writes /workspace/output/labels.json',
                  'specialist': 'TF-IDF char 2-5 + one-vs-rest logistic regression (dev reports)'})


def task_toml(spec):
    text = core_export.task_toml(spec, 1)
    lines = []
    for line in text.splitlines():
        if line.startswith('runtime_budget_sec_per_case'):
            continue
        if line.startswith('category = '):
            line = 'category = "clinical-text"'
        if line.startswith('timeout_sec = ') and lines and lines[-1] == '[verifier]':
            line = f'timeout_sec = {VERIFIER_TIMEOUT_SEC}'
        lines.append(line)
    return '\n'.join(lines) + '\n'


GRADE_PY = '''"""Generated verifier entry point (direct answer); the procedure is in lib/suite/families/label_ptbxl_reports/grader.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from suite.families.label_ptbxl_reports.grader import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
'''

SOLVE_SH = f'''#!/bin/bash
# Oracle: the specialist (TF-IDF + logistic regression), retrained here from agent-visible data only.
set -eu
mkdir -p /workspace/output
{core_export.VENV_PYTHON} -I /solution/label_tfidf.py /workspace/data /workspace/output/labels.json
'''


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def family_checks(task):
    """Fail unless hidden labels are unreachable from the agent side in the ways the core check cannot see."""
    data = task / 'environment' / 'data'
    ref = json.loads((task / 'tests' / 'hidden' / 'cohort' / 'reference' / 'labels.json').read_text())
    hidden_rows = read_csv(data / 'hidden_reports.csv')
    dev_rows = read_csv(data / 'dev_reports.csv')
    problems = []
    if list(hidden_rows[0].keys()) != ['record_id', 'report']:
        problems.append('hidden_reports.csv must have exactly record_id, report')
    if sorted(r['record_id'] for r in hidden_rows) != sorted(ref):
        problems.append('hidden_reports.csv IDs differ from the reference IDs')
    overlap = set(ref) & {r['record_id'] for r in dev_rows}
    if overlap:
        problems.append(f'{len(overlap)} hidden IDs appear among development rows')
    for p in sorted((task / 'environment').rglob('*')) + [task / 'instruction.md'] + sorted((task / 'solution').rglob('*')):
        if p.is_file():
            low = p.read_bytes().lower()
            problems += [f'{p.relative_to(task)} contains {w.decode()!r}' for w in FORBIDDEN_TEXT if w in low]
    if problems:
        raise core_export.ExportLeakError('; '.join(problems))


def build_task(data_root, out_dir):
    work = Path(data_root).resolve() / 'work'
    out_dir = Path(out_dir).resolve()
    final = out_dir / TASK_ID
    if os.path.lexists(final):
        raise FileExistsError(f'{final} already exists; refusing to overwrite')
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / f'.{TASK_ID}.partial-{os.getpid()}'
    staging.mkdir()
    try:
        data = staging / 'environment' / 'data'
        data.mkdir(parents=True)
        for name in ('dev_reports.csv', 'hidden_reports.csv', 'diagnostic_statements.csv'):
            shutil.copyfile(work / 'public' / name, data / name)
        shutil.copyfile(HERE / 'README_agent.md', data / 'README.md')
        shutil.copyfile(Path(data_root) / 'LICENSE.txt', data / 'LICENSE.txt')
        ref_dir = staging / 'tests' / 'hidden' / 'cohort' / 'reference'
        ref_dir.mkdir(parents=True)
        shutil.copyfile(work / 'hidden' / 'reference' / 'labels.json', ref_dir / 'labels.json')
        (staging / 'tests' / 'specialist').mkdir()
        for name in ('labels.json', 'runtime.json'):
            shutil.copyfile(work / 'specialist' / name, staging / 'tests' / 'specialist' / name)
        lib = staging / 'tests' / 'lib' / 'suite'
        (lib / 'core').mkdir(parents=True)
        (lib / 'families' / FAMILY).mkdir(parents=True)
        shutil.copyfile(REPO / 'suite' / '__init__.py', lib / '__init__.py')
        shutil.copyfile(REPO / 'suite' / 'core' / '__init__.py', lib / 'core' / '__init__.py')
        shutil.copyfile(REPO / 'suite' / 'core' / 'reward.py', lib / 'core' / 'reward.py')
        shutil.copyfile(REPO / 'suite' / 'families' / '__init__.py', lib / 'families' / '__init__.py')
        for name in ('__init__.py', 'grader.py'):
            shutil.copyfile(HERE / name, lib / 'families' / FAMILY / name)
        (staging / 'solution').mkdir()
        shutil.copyfile(HERE / 'label_tfidf.py', staging / 'solution' / 'label_tfidf.py')
        spec = family_spec(data, staging / 'solution')
        ref = json.loads((ref_dir / 'labels.json').read_text())
        simple = json.loads((work / 'comparators' / 'hidden_results.json').read_text())['keywords']
        config = {'schema': 'label-task-config/1', 'family': FAMILY, 'task_id': TASK_ID,
                  'grading': 'direct_answer', 'hidden_ids': sorted(ref),
                  'specialist_name': 'TF-IDF character n-grams + logistic regression trained on development reports',
                  'simple_comparator_summary': {'name': 'keyword rules', 'macro_f1': simple['metrics']['macro_f1'],
                                                'min_kappa': simple['metrics']['min_kappa'],
                                                'gate': simple['gate'], 'acceptable': simple['acceptable']}}
        files = {'task.toml': task_toml(spec),
                 'instruction.md': instruction(len(ref), len(read_csv(data / 'dev_reports.csv')), spec.packages),
                 'environment/Dockerfile': core_export.dockerfile(spec),
                 'tests/test.sh': core_export.TEST_SH, 'tests/grade.py': GRADE_PY,
                 'tests/task_config.json': json.dumps(config, indent=2) + '\n', 'solution/solve.sh': SOLVE_SH}
        for name, content in files.items():
            (staging / name).parent.mkdir(parents=True, exist_ok=True)
            (staging / name).write_text(content, encoding='utf-8')
        for name in ('tests/test.sh', 'solution/solve.sh'):
            (staging / name).chmod(0o755)
        core_export.check_no_leak(staging)
        family_checks(staging)
        os.rename(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


if __name__ == '__main__':
    task = build_task(sys.argv[1], sys.argv[2])
    manifest = Path(sys.argv[2]).resolve().parent / 'MANIFEST.json'
    manifest.write_text(json.dumps({TASK_ID: {'path': str(task.relative_to(manifest.parent)),
                                              'files': core_export.task_manifest(task)}}, indent=1) + '\n')
    print(task)
