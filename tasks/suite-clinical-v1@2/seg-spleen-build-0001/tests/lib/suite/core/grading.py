"""Verifier procedure shared by every family (platform-brief section 3.2).

tests/grade.py in every exported task calls main(). Steps:
 1. Fail closed (exit 2, no reward file -> infrastructure error) if /solution or /bundle exists:
    that means the verifier is sharing the agent sandbox, where references could leak.
 2. Write a provisional all-zero reward.json, so a crash or verifier timeout still scores 0.
 3. As root: make the tests tree root-only (chmod go-rwx), so the pipeline user cannot read
    hidden references or specialist results.
 4. Copy the submitted pipeline to WORK/pipeline (root-owned, read-only for others), refusing
    special files and enforcing size/count caps.
 5. For each hidden case: copy its inputs to WORK/in/<case> (world-readable), make an empty
    WORK/out/<case> owned by the run user, and run the pipeline through runner.run_pipeline
    under the per-case wall-clock limit. Grade outputs with the family's grade_case() against
    the hidden reference (always reading the trusted originals under tests/, never the copy).
 6. Grade the shipped specialist outputs for the same cases with the same grade_case().
 7. Aggregate to the reward contract (reward.py), write reward.json + metrics.json, and print
    one compact JSON line per case plus a summary on stdout (Valkyrie keeps 20 000 chars).

A family grader module must define:
    REQUIRED_OUTPUTS: tuple of file names the pipeline must write into OUTPUT_DIR
    CLINICAL_THRESHOLD: one-line human description of the acceptability rule
and, for per-case grading (task_config "grading": "per_case", the default):
    grade_case(output_dir, input_dir, reference_dir) -> dict with keys
        valid (bool), reason (str|None, why invalid or not acceptable),
        quality (float in [0,1], 0 if not valid), acceptable (bool, implies valid), metrics (dict)
or, for cohort grading (task_config "grading": "cohort"; ECG, ICU risk, pharyngitis):
    grade_cohort(output_dir, input_dir, reference_dir) -> dict with keys
        valid (bool), reason (str|None), quality (float in [0,1]),
        gate ({part name: bool}, every part of the clinical gate; may be empty only if not valid),
        metrics (dict of raw cohort metrics)

Cohort grading: the hidden set is ONE folder tests/hidden/<cohort>/{input,reference}; the pipeline
runs once on all of it under the cohort time limit (optionally with a later hard kill,
task_config "hard_kill_seconds": finishing after the limit but before the kill is ran, not
within_time). Reward rule (DESIGN.md, cohort families): clinically_acceptable = 1.0 only if the
output is valid and every gate part is met, else 0.0. metrics.json gets "gate" (each part) and
"gate_fraction" (parts met / parts) for the agent and the specialist, so a constant predictor
that meets some parts cannot earn partial reward. The seven reward.json keys are unchanged.
"""
import argparse
import importlib
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from statistics import median

from . import reward as rw
from .runner import DEFAULT_PATH, UNPRIVILEGED_UID, run_pipeline

CONFIG_SCHEMA = 'suite-task-config/1'
GRADING_MODES = ('per_case', 'cohort')
SHARED_SANDBOX_MARKERS = ('solution', 'bundle')
MAX_PIPELINE_BYTES = 512 * 1024 * 1024      # = the Valkyrie per-artifact limit
MAX_PIPELINE_FILES = 20_000
STDOUT_BUDGET_CHARS = 18_000


class InfrastructureError(RuntimeError):
    pass


def _is_root():
    return os.geteuid() == 0


def protect_tree(root):
    """chmod go-rwx on every entry (no symlink following). Root-only data afterwards."""
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            if not os.path.islink(p):
                os.chmod(p, stat.S_IMODE(os.lstat(p).st_mode) & 0o700)
    os.chmod(root, 0o700)


def copy_tree_checked(source, dest, max_bytes=MAX_PIPELINE_BYTES, max_files=MAX_PIPELINE_FILES, readonly=True):
    """Copy regular files, directories and symlinks (kept as links, never followed by the copy).

    Refuses devices, sockets and FIFOs and enforces size/count caps. With readonly, files end
    up 0644/0755 (exec bit kept) and directories 0755, so other users can read but not write.
    """
    source, dest = Path(source), Path(dest)
    total, count = 0, 0
    for dirpath, dirnames, filenames in os.walk(source):
        for name in dirnames + filenames:
            st = os.lstat(os.path.join(dirpath, name))
            count += 1
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
            elif not (stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode)):
                raise ValueError(f'special file in submission: {name}')
            if count > max_files or total > max_bytes:
                raise ValueError('submission exceeds the size or file-count cap')
    shutil.copytree(source, dest, symlinks=True)
    if readonly:
        for dirpath, dirnames, filenames in os.walk(dest):
            os.chmod(dirpath, 0o755)
            for name in filenames:
                p = os.path.join(dirpath, name)
                if not os.path.islink(p):
                    mode = os.lstat(p).st_mode
                    os.chmod(p, 0o755 if mode & 0o111 else 0o644)
    return {'files': count, 'bytes': total}


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _failure_reason(run, ran, grade, within_time=True):
    """First applicable reason, in a fixed order. None means the case passed."""
    if run is None:
        return 'not_run'
    if run['timed_out']:
        return 'timeout'
    if ran and not within_time:
        return 'over_time_limit (finished after the limit, before the hard kill)'
    if not ran:
        return f"no_output (exit code {run['exit_code']})"
    if not grade['valid']:
        return f"invalid: {grade['reason']}"
    if not grade['acceptable']:
        return f"below_clinical_threshold: {grade['reason']}"
    return None


def _cohort_result(g):
    """Map a grade_cohort() result to the per-case shape with the cohort reward rule (all parts met)."""
    valid = bool(g['valid'])
    gate = {str(k): bool(v) for k, v in (g.get('gate') or {}).items()}
    if valid and not gate:
        raise InfrastructureError('cohort grader returned a valid result without gate parts')
    acceptable = valid and all(gate.values())
    fraction = sum(gate.values()) / len(gate) if gate else 0.0
    metrics = dict(g.get('metrics') or {})
    metrics.update(gate=gate, gate_fraction=fraction)
    reason = g.get('reason')
    if valid and not acceptable and not reason:
        reason = 'gate parts not met: ' + ', '.join(k for k, ok in gate.items() if not ok)
    return {'valid': valid, 'acceptable': acceptable, 'quality': g.get('quality', 0.0), 'reason': reason,
            'metrics': metrics}


def _grade_safely(family, output_dir, input_dir, reference_dir, mode='per_case'):
    try:
        if mode == 'cohort':
            g = family.grade_cohort(Path(output_dir), Path(input_dir), Path(reference_dir))
        else:
            g = family.grade_case(Path(output_dir), Path(input_dir), Path(reference_dir))
    except Exception as error:      # a malformed output must not crash grading; record it
        return {'valid': False, 'acceptable': False, 'quality': 0.0,
                'metrics': {'gate': {}, 'gate_fraction': 0.0} if mode == 'cohort' else {},
                'reason': f'grader_exception {type(error).__name__}: {str(error)[:200]}'}
    if mode == 'cohort':
        g = _cohort_result(g)
    q = float(g.get('quality', 0.0)) if g.get('valid') else 0.0
    if not 0.0 <= q <= 1.0 or q != q:
        raise InfrastructureError(f'family grader returned quality {q!r} outside [0, 1]')
    return {'valid': bool(g['valid']), 'acceptable': bool(g['valid'] and g['acceptable']), 'quality': q,
            'reason': g.get('reason'), 'metrics': g.get('metrics', {})}


def grade_task(tests_dir, pipeline_dir, logs_dir, work_dir, *, sandbox_root='/', time_limit_seconds=None,
               pipeline_path=None, out=sys.stdout):
    """Run the whole verifier procedure; returns (reward dict, metrics dict)."""
    # Absolute paths: the pipeline runs with cwd = its fresh home, so a relative work dir would make
    # `bash run.sh` (and its IN/OUT arguments) point nowhere.
    tests_dir, logs_dir, work_dir = (Path(tests_dir).absolute(), Path(logs_dir).absolute(), Path(work_dir).absolute())
    pipeline_dir = Path(pipeline_dir).absolute()
    if sandbox_root is not None:
        found = [m for m in SHARED_SANDBOX_MARKERS if os.path.lexists(os.path.join(sandbox_root, m))]
        if found:
            raise InfrastructureError('refusing to score: verifier appears to share the agent sandbox (found /'
                                      + ', /'.join(found) + '); the task requires a separate verifier')
    rw.write_provisional_zero(logs_dir)
    started = time.monotonic()
    config = json.loads((tests_dir / 'task_config.json').read_text())
    if config.get('schema') != CONFIG_SCHEMA:
        raise InfrastructureError('task_config.json has the wrong schema')
    family = importlib.import_module(config['grader_module'])
    mode = config.get('grading', 'per_case')
    if mode not in GRADING_MODES:
        raise InfrastructureError(f'unknown grading mode {mode!r}')
    if mode == 'cohort' and not callable(getattr(family, 'grade_cohort', None)):
        raise InfrastructureError(f"{config['grader_module']} has no grade_cohort() for cohort grading")
    limit = float(time_limit_seconds or config['time_limit_seconds'])
    hard_limit = limit if time_limit_seconds else max(limit, float(config.get('hard_kill_seconds') or limit))
    path = pipeline_path or config.get('pipeline_path', DEFAULT_PATH)
    deadline = float(config.get('grading_deadline_seconds', 1e9))
    cases = list(config['cases'])
    if mode == 'cohort' and len(cases) != 1:
        raise InfrastructureError('cohort grading needs exactly one hidden folder (the whole hidden set)')
    root = _is_root()
    if root:
        protect_tree(tests_dir)
    if work_dir.exists() and any(work_dir.iterdir()):
        raise InfrastructureError(f'work dir {work_dir} is not empty')
    for sub in ('in', 'out', 'home'):
        (work_dir / sub).mkdir(parents=True, exist_ok=True)
        os.chmod(work_dir / sub, 0o755)
    os.chmod(work_dir, 0o755)

    submission = {'pipeline_present': False}
    staged_pipeline = work_dir / 'pipeline'
    run_sh = Path(pipeline_dir) / 'run.sh'
    if run_sh.is_file() and not run_sh.is_symlink():
        try:
            submission.update(copy_tree_checked(pipeline_dir, staged_pipeline), pipeline_present=True)
        except ValueError as error:
            submission['error'] = str(error)
    else:
        submission['error'] = 'pipeline/run.sh missing or not a regular file'

    per_case = []
    for case in cases:
        hidden = tests_dir / 'hidden' / case
        entry = {'case': case, 'run': None, 'ran': False, 'within_time': False,
                 'valid': False, 'acceptable': False, 'quality': 0.0}
        if submission['pipeline_present'] and time.monotonic() - started + hard_limit <= deadline:
            in_dir, out_dir, home = work_dir / 'in' / case, work_dir / 'out' / case, work_dir / 'home' / case
            copy_tree_checked(hidden / 'input', in_dir, max_bytes=1 << 40, max_files=10**6)
            out_dir.mkdir()
            home.mkdir()
            if root:
                os.chown(out_dir, UNPRIVILEGED_UID, UNPRIVILEGED_UID)
            result = run_pipeline(staged_pipeline, in_dir, out_dir, hard_limit, home_dir=home,
                                  log_path=logs_dir / 'pipeline_logs' / f'{case}.log', path=path,
                                  threads=config.get('threads'), memory_bytes=config.get('memory_bytes'))
            entry['run'] = result.to_dict()
            entry['ran'] = all(os.path.lexists(out_dir / name) for name in family.REQUIRED_OUTPUTS)
            entry['within_time'] = (entry['ran'] and not result.timed_out
                                    and (hard_limit == limit or result.wall_seconds <= limit))
            if entry['ran']:
                g = _grade_safely(family, out_dir, hidden / 'input', hidden / 'reference', mode)
                entry.update(valid=g['valid'], acceptable=g['acceptable'], quality=g['quality'],
                             grade_reason=g['reason'], metrics=g['metrics'])
            else:
                g = {'valid': False, 'acceptable': False, 'reason': None}
            entry['failure'] = _failure_reason(entry['run'], entry['ran'], g, entry['within_time'])
        else:
            entry['failure'] = 'not_run: ' + (submission.get('error') or 'verifier deadline reached')
        per_case.append(entry)

    specialist = _grade_specialist(family, tests_dir, cases, mode)
    agent_seconds = [c['run']['wall_seconds'] for c in per_case if c['run'] and not c['run']['timed_out']]
    ratios = [c['run']['wall_seconds'] / specialist['runtime_seconds'][c['case']] for c in per_case
              if c['run'] and not c['run']['timed_out'] and specialist['runtime_seconds'].get(c['case'])]
    quality = _mean([c['quality'] for c in per_case])
    reward = rw.build_reward(ran=_mean([c['ran'] for c in per_case]), valid=_mean([c['valid'] for c in per_case]),
                             within_time=_mean([c['within_time'] for c in per_case]),
                             clinically_acceptable=_mean([c['acceptable'] for c in per_case]),
                             quality=quality, specialist_quality=specialist['quality'])
    metrics = {'schema': 'suite-metrics/1', 'family': config.get('family'), 'task_id': config.get('task_id'),
               'clinical_threshold': getattr(family, 'CLINICAL_THRESHOLD', None),
               'primary_metric': getattr(family, 'PRIMARY_METRIC', None),
               'grading': mode, 'time_limit_seconds_per_case': limit, 'hard_kill_seconds': hard_limit,
               'timing_source': 'grader monotonic clock (runner.py)',
               'ran_as_uid': per_case[0]['run']['ran_as_uid'] if per_case and per_case[0]['run'] else None,
               'submission': submission, 'cases': per_case, 'specialist': specialist,
               'summary': {'reward': reward, 'n_cases': len(cases),
                           'agent_wall_seconds_median': median(agent_seconds) if agent_seconds else None,
                           'runtime_ratio_vs_specialist_median': median(ratios) if ratios else None,
                           'failures': {c['case']: c['failure'] for c in per_case if c['failure']},
                           'grading_seconds': time.monotonic() - started}}
    if mode == 'cohort':
        agent_m = per_case[0].get('metrics') or {}
        spec_m = specialist['cases'][cases[0]].get('metrics') or {}
        metrics['gate'] = agent_m.get('gate', {})
        metrics['gate_fraction'] = agent_m.get('gate_fraction', 0.0)
        metrics['specialist']['gate'] = spec_m.get('gate', {})
        metrics['specialist']['gate_fraction'] = spec_m.get('gate_fraction', 0.0)
        metrics['summary'].update(gate=metrics['gate'], gate_fraction=metrics['gate_fraction'],
                                  specialist_gate_fraction=metrics['specialist']['gate_fraction'])
    rw.write_reward(logs_dir, reward, metrics)
    _print_summary(per_case, metrics['summary'], out)
    return reward, metrics


def _grade_specialist(family, tests_dir, cases, mode='per_case'):
    """Grade the precomputed specialist outputs (tests/specialist/<case>/) with the same rule."""
    base = tests_dir / 'specialist'
    runtime = {}
    if (base / 'runtime.json').is_file():
        runtime = json.loads((base / 'runtime.json').read_text()).get('wall_seconds', {})
    per = {}
    for case in cases:
        hidden = tests_dir / 'hidden' / case
        if (base / case).is_dir():
            g = _grade_safely(family, base / case, hidden / 'input', hidden / 'reference', mode)
        else:
            g = {'valid': False, 'acceptable': False, 'quality': 0.0, 'reason': 'specialist output missing'}
        per[case] = {'valid': g['valid'], 'quality': g['quality'], 'acceptable': g['acceptable'],
                     'reason': g['reason'], 'metrics': g.get('metrics', {})}
    valid = _mean([v['valid'] for v in per.values()])
    acceptable = _mean([v['acceptable'] for v in per.values()])
    return {'quality': _mean([v['quality'] for v in per.values()]),
            'valid': valid, 'clinically_acceptable': acceptable,
            # The agent's scalar rule applied to the stored outputs, taking them as on time (their
            # runtime was measured at export, not here): the number to compare an agent's reward with.
            'reward_if_on_time': acceptable if valid == 1.0 else 0.0,
            'runtime_seconds': runtime, 'runtime_source': 'measured at export time on the export host',
            'cases': per}


def _print_summary(per_case, summary, out):
    budget = STDOUT_BUDGET_CHARS
    for c in per_case:
        line = json.dumps({'case': c['case'], 'failure': c['failure'], 'ran': c['ran'], 'valid': c['valid'],
                           'within_time': c['within_time'], 'acceptable': c['acceptable'],
                           'quality': round(c['quality'], 4),
                           'seconds': None if not c['run'] else round(c['run']['wall_seconds'], 3),
                           'exit': None if not c['run'] else c['run']['exit_code']}, allow_nan=False)
        budget -= len(line) + 1
        if budget < 2000:
            print('[per-case lines truncated]', file=out)
            break
        print(line, file=out)
    print(json.dumps({'summary': rw.json_safe(summary)}, allow_nan=False)[:1800], file=out)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Suite verifier (generated tasks call this from tests/grade.py).')
    parser.add_argument('--tests', default='/tests')
    parser.add_argument('--pipeline', default='/workspace/output/pipeline')
    parser.add_argument('--logs', default='/logs/verifier')
    parser.add_argument('--work', default='/eval')
    parser.add_argument('--sandbox-root', default='/', help="'none' disables the shared-sandbox check (local runs)")
    parser.add_argument('--time-limit', type=float, help='override the per-case limit (local tests only)')
    parser.add_argument('--pipeline-path', help='PATH for the pipeline (local tests only)')
    args = parser.parse_args(argv)
    try:
        grade_task(args.tests, args.pipeline, args.logs, args.work,
                   sandbox_root=None if args.sandbox_root == 'none' else args.sandbox_root,
                   time_limit_seconds=args.time_limit, pipeline_path=args.pipeline_path)
    except InfrastructureError as error:
        print(json.dumps({'infrastructure_error': str(error)}))
        return 2
    return 0
