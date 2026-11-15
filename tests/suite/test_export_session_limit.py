"""v3 instruction fix (docs/research/suite/instructions-v3.md; pilot 1 "Our bugs" 1): every exported
instruction.md states, near the top, the agent session limit taken from the task's own
task.toml [agent] timeout_sec, that /workspace/output/pipeline is graded as found when the session
ends, a recommendation to put a working run.sh in place early, and the grader's pipeline time limit.

The exported-task checks run on the toy export (always) and on every task under
dist/suite-tasks-v3/ (skipped if that folder is absent).
"""
import os
import re
import sys
import tomllib
import types
from pathlib import Path

import pytest

from suite.core import export as E

REPO = Path(__file__).resolve().parents[2]
V3 = REPO / 'dist' / 'suite-tasks-v3'
V3_TASKS = sorted(p.parent for p in V3.glob('*/*/task.toml')) if V3.is_dir() else []
SCORED_V3 = {'reg_resect', 'seg_spleen', 'measure_hc18', 'ecg_ptbxl', 'risk_icu'}


def _spec(**kw):
    base = dict(packages=E.DEFAULT_PACKAGES, pip_extra_index_url=None, threads=None, cpus=4, family='x',
                grading='per_case', allowed_hosts=('api.anthropic.com',), title='T', readme_md='README BODY',
                output_format_md='F', time_limit_seconds=60.0, memory_mb=4096, specialist_name='S',
                cohort_size=None, hard_kill_seconds=None, agent_timeout_sec=2700.0)
    base.update(kw)
    return types.SimpleNamespace(**base)


SESSION_RE = re.compile(r'Your session lasts at most ([0-9.]+) minutes\*\* \(([0-9.]+) seconds\)')


def check_instruction(text, agent_timeout_sec, grading, time_limit, hard_kill=None):
    """Assert the v3 session statements; returns the stated minutes."""
    head = text.split('\n## ', 2)
    # The section is the first H2 after the title, i.e. before any task-specific text.
    assert head[1].startswith('Session limit and what is graded (read first)'), head[1][:80]
    m = SESSION_RE.search(text)
    assert m, 'session limit sentence missing'
    minutes, seconds = float(m.group(1)), float(m.group(2))
    assert seconds == float(agent_timeout_sec)
    assert minutes == pytest.approx(float(agent_timeout_sec) / 60.0)
    assert '`/workspace/output/pipeline/` when the session ends' in text
    assert 'exactly as\n  it is at that moment' in text
    assert 'putting a working `run.sh` in place early and improving it afterwards' in text
    limit = (f'{time_limit:g} seconds of wall-clock time for the whole hidden set' if grading == 'cohort'
             else f'{time_limit:g} seconds of wall-clock time per hidden case')
    section = head[1]
    assert limit in section
    if hard_kill and hard_kill > time_limit:
        assert f'killed at {hard_kill:g} seconds' in section
    return minutes


@pytest.mark.parametrize('timeout', [1800.0, 2700.0, 3600.0, 1500.0])
@pytest.mark.parametrize('grading', ['per_case', 'cohort'])
def test_instruction_states_session_limit_from_spec(grading, timeout):
    spec = _spec(grading=grading, agent_timeout_sec=timeout, cohort_size=100 if grading == 'cohort' else None,
                 time_limit_seconds=560.0 if grading == 'cohort' else 120.0,
                 hard_kill_seconds=1120.0 if grading == 'cohort' else None)
    text = E.instruction(spec, 3)
    check_instruction(text, timeout, grading, spec.time_limit_seconds, spec.hard_kill_seconds)
    # The section comes before the task's own README text.
    assert text.index('Session limit and what is graded') < text.index('README BODY')
    # The instruction and task.toml read the same spec value.
    assert tomllib.loads(_toml(spec))['agent']['timeout_sec'] == timeout


def _toml(spec):
    full = _spec(**vars(spec))
    full.tier, full.scored, full.metadata, full.expected_solution_reward = 'build', True, {}, None
    full.gpus, full.gpu_types = 0, ()
    return E.task_toml(full, 3)


def test_session_section_has_no_method_hints():
    text = E.session_section(_spec())
    for word in ('model', 'train', 'registration', 'segment', 'threshold', 'baseline', 'simple'):
        assert word not in text.lower(), word


def test_toy_export_instruction_matches_task_toml(tmp_path):
    from suite.families.toy.spec import build_spec
    os.environ.setdefault('SUITE_PIPELINE_PATH', f'{Path(sys.executable).parent}:/usr/bin:/bin')
    spec = build_spec(tmp_path / 'work')
    task = E.export_task(spec, tmp_path / 'dist')
    toml = tomllib.loads((task / 'task.toml').read_text())
    check_instruction((task / 'instruction.md').read_text(), toml['agent']['timeout_sec'], spec.grading,
                      spec.time_limit_seconds)


def test_v3_has_the_five_scored_tasks():
    if not V3_TASKS:
        pytest.skip('dist/suite-tasks-v3 not exported here')
    assert {p.parent.name for p in V3_TASKS} == SCORED_V3


@pytest.mark.parametrize('task', V3_TASKS, ids=[p.name for p in V3_TASKS])
def test_v3_instruction_states_task_toml_agent_timeout(task):
    toml = tomllib.loads((task / 'task.toml').read_text())
    config = __import__('json').loads((task / 'tests' / 'task_config.json').read_text())
    hard = config['hard_kill_seconds'] if config['grading'] == 'cohort' else None
    text = (task / 'instruction.md').read_text()
    check_instruction(text, toml['agent']['timeout_sec'], config['grading'], config['time_limit_seconds'], hard)
    assert toml['metadata']['runtime_budget_sec_per_case'] == config['time_limit_seconds']
