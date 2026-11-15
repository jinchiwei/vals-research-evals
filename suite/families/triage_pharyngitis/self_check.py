"""Grader self-check on the real hidden cohort through the exported task and suite.core.grading.

    python -m suite.families.triage_pharyngitis.self_check [--data DATA]

Exports the task to DATA/dist/, then grades: oracle (hidden labels as probabilities 0.02/0.98 via a lookup
pipeline; local only), the shipped solution (comparator d), constant development prevalence, overconfident
(symptoms model with logits x6), too slow (sleeps past the limit) and invalid (NaN). Writes
DATA/self_check.json and an aggregate copy in split/.
"""
import argparse
import csv
import io
import json
import shutil
import sys
from pathlib import Path

from suite.core.export import export_task
from suite.core.grading import grade_task

from . import comparators
from .prepare_data import DEFAULT_DATA, FAMILY_DIR
from .spec import build_spec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=DEFAULT_DATA)
    args = ap.parse_args(argv)
    data = args.data
    for d in ('dist', 'spec_work', 'self_check'):
        shutil.rmtree(data / d, ignore_errors=True)
    task = export_task(build_spec(data / 'spec_work', data), data / 'dist')
    tests = task / 'tests'
    with open(data / 'prepared/hidden/cohort/reference/labels.csv', newline='') as f:
        labels = {r['case_id']: int(r['bacterial']) for r in csv.DictReader(f)}
    sc = data / 'self_check'
    pipes = {
        'oracle_lookup': comparators.write_pipeline(sc / 'pipes/oracle', {'kind': 'lookup', 'probabilities': {
            c: 0.98 if y else 0.02 for c, y in labels.items()}}),
        # The shipped solution, with the weights path pointed at teal's copy (no /workspace here).
        'solution_combined': comparators.write_pipeline(sc / 'pipes/solution', {
            **json.loads((task / 'solution/pipeline/model.json').read_text()),
            'weights_path': str(data / 'models/resnet50_imagenet1k_v2.pth')}),
        'constant_prevalence': data / 'pipelines' / 'constant',
        'overconfident': data / 'pipelines' / 'overconfident',
        'too_slow': comparators.write_pipeline(sc / 'pipes/slow', {
            **json.loads((data / 'pipelines/symptoms/model.json').read_text()), 'kind': 'slow',
            'sleep_seconds': 1e6}),
        'invalid_nan': sc / 'pipes/nan',
    }
    (sc / 'pipes/nan').mkdir(parents=True)
    (sc / 'pipes/nan/run.sh').write_text('#!/bin/bash\nset -e\nprintf \'{"predictions": [{"case": "x", '
                                         '"probability": NaN}]}\' > "$2/predictions.json"\n')
    results = {}
    path = str(Path(sys.executable).parent) + ':/usr/bin:/bin'
    for name, pipe in pipes.items():
        limit = 30.0 if name == 'too_slow' else None
        reward, metrics = grade_task(tests, pipe, sc / name / 'logs', sc / name / 'work', sandbox_root=None,
                                     time_limit_seconds=limit, pipeline_path=path, out=io.StringIO())
        case = metrics['cases'][0]
        m = case.get('metrics') or {}
        results[name] = {'reward': reward, 'failure': case['failure'],
                         'seconds': case['run'] and round(case['run']['wall_seconds'], 2),
                         'auroc': m.get('auroc'), 'gate_fraction': m.get('gate_fraction'),
                         'gate_components': m.get('gate_components')}
        print(name, json.dumps(results[name]), flush=True)
    text = json.dumps({'task_dir': str(task), 'results': results}, indent=1) + '\n'
    (data / 'self_check.json').write_text(text)
    (FAMILY_DIR / 'split' / 'self_check.json').write_text(text)


if __name__ == '__main__':
    main()
