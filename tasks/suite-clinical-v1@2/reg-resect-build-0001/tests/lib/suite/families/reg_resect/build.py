"""Build the verifier-side tests/ tree for reg_resect, run the specialist on hidden cases, and self-check.

    python -I -m suite.families.reg_resect.build STAGED_DIR WORK_DIR [--skip-specialist]

Produces under WORK_DIR:
  tests/task_config.json            suite-task-config/1 for suite.core.grading
  tests/hidden/<case>/{input,reference}/...
  tests/specialist/<case>/landmarks_us.csv, tests/specialist/runtime.json
  selfcheck/<kind>/{reward.json,metrics.json}   for oracle, identity, slow, lps, specialist
  selfcheck/summary.json

The specialist is executed through suite.core.runner (the grader's clock, same time limit and
thread cap as an agent pipeline), on this host. Its outputs and wall times are what the exported
task ships under tests/specialist/.
"""
import argparse
import io
import json
import shutil
import sys
from pathlib import Path

from suite.core import grading, runner

from . import pipelines
from .spec import SPEC

FAMILY_GRADER = 'suite.families.reg_resect.grader'


def task_config(cases):
    return {'schema': grading.CONFIG_SCHEMA, 'family': SPEC['family'], 'task_id': SPEC['task_id'],
            'grader_module': FAMILY_GRADER, 'time_limit_seconds': SPEC['time_limit_seconds_per_case'],
            'threads': SPEC['cpus'], 'memory_bytes': SPEC['pipeline_memory_bytes'],
            'grading_deadline_seconds': SPEC['grading_deadline_seconds'], 'cases': cases}


def build_tests(staged, tests):
    hidden = sorted(p.name for p in (Path(staged) / 'hidden').iterdir())
    shutil.copytree(Path(staged) / 'hidden', tests / 'hidden')
    (tests / 'task_config.json').write_text(json.dumps(task_config(hidden), indent=2) + '\n')
    return hidden


def run_specialist(tests, work, config, pipeline_path):
    pipe = pipelines.write_pipeline('specialist', work / 'specialist_pipeline', config=config)
    spec_dir = tests / 'specialist'
    spec_dir.mkdir()
    wall = {}
    for case in json.loads((tests / 'task_config.json').read_text())['cases']:
        out = spec_dir / case
        out.mkdir()
        r = runner.run_pipeline(pipe, tests / 'hidden' / case / 'input', out, SPEC['time_limit_seconds_per_case'],
                                home_dir=work / 'specialist_home' / case, log_path=work / 'specialist_logs' / f'{case}.log',
                                path=pipeline_path, threads=SPEC['cpus'])
        wall[case] = r.wall_seconds
        print(f'specialist {case}: {r.wall_seconds:.1f}s exit={r.exit_code} timeout={r.timed_out}', flush=True)
    (spec_dir / 'runtime.json').write_text(json.dumps({'wall_seconds': wall, 'threads': SPEC['cpus'],
                                                       'source': 'suite.core.runner monotonic clock'}, indent=2) + '\n')
    return wall


def selfcheck(tests, work, pipeline_path, kinds, config):
    results = {}
    for kind in kinds:
        pdir = work / 'pipelines' / kind
        # slow: a correct answer written only after 25 s, graded with the limit shortened to 20 s so the
        # check is quick; the mechanism is the same as at the real 120 s limit (runner.py hard kill).
        limit = 20.0 if kind == 'slow' else None
        pipelines.write_pipeline(kind, pdir, hidden_root=tests / 'hidden', config=config, sleep_seconds=25)
        logs, w = work / 'selfcheck' / kind, work / 'eval' / kind
        buf = io.StringIO()
        reward, metrics = grading.grade_task(tests, pdir, logs, w, sandbox_root=None, time_limit_seconds=limit,
                                             pipeline_path=pipeline_path, out=buf)
        results[kind] = {'reward': reward, 'per_case': [
            {'case': c['case'], 'failure': c['failure'], 'seconds': c['run']['wall_seconds'] if c['run'] else None,
             'mean_tre_mm': c.get('metrics', {}).get('mean_tre_mm'),
             'initial_mean_tre_mm': c.get('metrics', {}).get('initial_mean_tre_mm')} for c in metrics['cases']],
            'specialist': {'quality': metrics['specialist']['quality'],
                           'clinically_acceptable': metrics['specialist']['clinically_acceptable']}}
        print(kind, json.dumps(reward), flush=True)
    (work / 'selfcheck' / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    return results


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('staged')
    p.add_argument('work')
    p.add_argument('--config', default=None, help='specialist config JSON (default: spec SPECIALIST_CONFIG)')
    p.add_argument('--kinds', default='oracle,identity,lps,slow,specialist')
    p.add_argument('--pipeline-path', default=str(Path(sys.executable).parent) + ':/usr/bin:/bin')
    a = p.parse_args(argv)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=False)
    tests = work / 'tests'
    tests.mkdir()
    config = json.loads(a.config) if a.config else SPEC['specialist_config']
    build_tests(a.staged, tests)
    run_specialist(tests, work, config, a.pipeline_path)
    selfcheck(tests, work, a.pipeline_path, a.kinds.split(','), config)


if __name__ == '__main__':
    main()
