"""Local pilot runner (suite/pilot, scripts/run_suite_pilot.py) with a fake agent in place of the Claude CLI.

No model calls. The fake agent is a Python script bound at /opt/agent/claude inside the agent sandbox;
it probes what it can see, then leaves (or does not leave) a pipeline. Run:
    ~/miniconda3/envs/vals-suite/bin/python -m pytest tests/suite/test_pilot_runner.py -q
"""
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from suite.core import export as E
from suite.core.reward import REWARD_KEYS
from suite.families.toy.spec import build_spec
from suite.pilot import pilot

REPO = Path(__file__).resolve().parents[2]
PATH = f'{Path(sys.executable).parent}:/usr/bin:/bin'
pytestmark = pytest.mark.skipif(not Path('/usr/bin/bwrap').exists(), reason='bubblewrap missing')

FAKE_HEAD = '''#!/usr/bin/python3
import base64, json, os, socket, sys
prompt = sys.stdin.read()
print(json.dumps({"type": "system", "subtype": "init", "model": "fake-model-1", "cwd": os.getcwd()}), flush=True)
os.makedirs("/workspace/output", exist_ok=True)
'''
FAKE_TAIL = '''
print(json.dumps({"type": "assistant", "message": {"model": "fake-model-1", "content": [
    {"type": "tool_use", "name": "Bash", "input": {}}]}}), flush=True)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
                  "total_cost_usd": 0.0, "modelUsage": {"fake-model-1": {}}}), flush=True)
'''


def fake_agent(path, body):
    path.write_text(FAKE_HEAD + body + FAKE_TAIL)
    path.chmod(0o755)
    return path


def write_files_body(files):
    """Body that writes {relpath: text} under /workspace/output/pipeline."""
    blob = base64.b64encode(json.dumps(files).encode()).decode()
    return f'''
files = json.loads(base64.b64decode("{blob}"))
for rel, text in files.items():
    p = os.path.join("/workspace/output/pipeline", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)
    os.chmod(p, 0o755)
'''


@pytest.fixture(scope='module')
def task(tmp_path_factory):
    root = tmp_path_factory.mktemp('pilot')
    os.environ['SUITE_PIPELINE_PATH'] = PATH
    return E.export_task(build_spec(root / 'work'), root / 'dist')


def run(task, tmp_path, agent, name='r1', model='fake-model', **kw):
    kw.setdefault('egress', 'proxy')
    return pilot.run_pilot(task, run_name=name, model=model, time_limit_sec=120, budget_usd=0.01,
                           out_root=tmp_path / 'out', agent_bin=agent, runtime_prefix=Path(sys.prefix),
                           auth='none', scratch=tmp_path, log=lambda *_: None, **kw)


def direct_reward(task, pipeline_dir, tmp_path):
    logs = tmp_path / 'direct-logs'
    proc = subprocess.run([sys.executable, '-I', '-B', str(task / 'tests' / 'grade.py'), '--tests', str(task / 'tests'),
                           '--pipeline', str(pipeline_dir), '--logs', str(logs), '--work', str(tmp_path / 'direct-eval'),
                           '--sandbox-root', 'none', '--pipeline-path', PATH], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads((logs / 'reward.json').read_text())


def test_agent_sandbox_hides_hidden_references_repo_and_user_files(task, tmp_path):
    ref = next((task / 'tests' / 'hidden').iterdir()) / 'reference' / 'measurements.json'
    assert ref.is_file()
    targets = {'hidden_reference': str(ref), 'tests_dir': str(task / 'tests'), 'solution': str(task / 'solution'),
               'repo_readme': str(REPO / 'README.md'), 'repo_dir': str(REPO), 'home': str(Path.home()),
               'user_claude_json': str(Path.home() / '.claude.json'), 'data_root': '/home/jkwei/data', 'mnt_c': '/mnt/c'}
    body = f'''
targets = {json.dumps(targets)}
seen = {{}}
for key, p in targets.items():
    try:
        if os.path.isdir(p):
            seen[key] = "listed:" + ",".join(sorted(os.listdir(p))[:3])
        else:
            open(p, "rb").read(); seen[key] = "read"
    except OSError as e:
        seen[key] = "blocked:" + type(e).__name__
direct = "connected"
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3).close()
except OSError as e:
    direct = "blocked:" + type(e).__name__
s = socket.create_connection(("127.0.0.1", 18080), timeout=5)
s.sendall(b"CONNECT example.com:443 HTTP/1.1\\r\\nHost: example.com:443\\r\\n\\r\\n")
proxied = s.recv(200).decode().split("\\r\\n")[0]
import shutil as sh
out = {{"seen": seen, "direct": direct, "proxy_disallowed": proxied, "cwd": os.getcwd(),
       "public_readme": os.path.isfile("/workspace/data/README.md"),
       "instruction": os.path.isfile("/workspace/instruction.md"),
       "data_writable": os.access("/workspace/data", os.W_OK),
       "python3": sh.which("python3"), "home": os.environ.get("HOME"), "home_files": sorted(os.listdir(os.environ["HOME"]))}}
json.dump(out, open("/workspace/output/probe.json", "w"))
'''
    run_dir, record = run(task, tmp_path, fake_agent(tmp_path / 'probe-agent', body))
    probe = json.loads((run_dir / 'workspace' / 'output' / 'probe.json').read_text())
    assert all(v.startswith('blocked:') for v in probe['seen'].values()), probe['seen']
    assert probe['direct'].startswith('blocked:')
    assert '403' in probe['proxy_disallowed']
    assert probe['public_readme'] and probe['instruction'] and not probe['data_writable']
    assert probe['cwd'] == '/workspace' and probe['python3'] == '/opt/benchmark-venv/bin/python3'
    assert probe['home'] == '/home/agent' and '.credentials.json' not in json.dumps(probe['home_files'])
    egress = record['agent']['egress']
    assert egress['allowlist'] == ['api.anthropic.com'] and egress['by_target']['example.com:443']['denied'] == 1
    assert record['agent']['status'] == 'completed' and record['num_turns'] == 3
    assert record['models_reported'] == ['fake-model-1']
    assert record['reward'] == {k: 0.0 for k in REWARD_KEYS}          # no pipeline left


def test_fake_agent_pipeline_gets_same_reward_as_direct_grading(task, tmp_path):
    oracle = task / 'solution' / 'pipeline'
    files = {p.name: p.read_text() for p in oracle.iterdir() if p.is_file()}
    run_dir, record = run(task, tmp_path, fake_agent(tmp_path / 'oracle-agent', write_files_body(files)))
    assert record['grading']['pipeline_wrapped_in_sandbox'] is True
    assert record['grading']['infrastructure_error'] is False
    reward = json.loads((run_dir / 'reward.json').read_text())
    assert reward == direct_reward(task, oracle, tmp_path) == {k: 1.0 for k in REWARD_KEYS}
    metrics = json.loads((run_dir / 'metrics.json').read_text())
    assert all(c['failure'] is None for c in metrics['cases'])
    assert (run_dir / 'workspace' / 'output' / 'pipeline' / 'run.sh').is_file()
    assert record['grader_version_sha256'] and record['runtime_env']['missing_pins'] == []


def test_agent_that_leaves_nothing_scores_zero(task, tmp_path):
    run_dir, record = run(task, tmp_path, fake_agent(tmp_path / 'idle-agent', 'pass\n'))
    assert json.loads((run_dir / 'reward.json').read_text()) == {k: 0.0 for k in REWARD_KEYS}
    assert record['grading']['pipeline_wrapped_in_sandbox'] is False
    metrics = json.loads((run_dir / 'metrics.json').read_text())
    assert all(c['failure'].startswith('not_run') for c in metrics['cases'])


def test_pipeline_sandbox_has_no_network_and_no_hidden_references(task, tmp_path):
    ref = next((task / 'tests' / 'hidden').iterdir()) / 'reference' / 'measurements.json'
    probe = f'''import json, os, socket
r = {{}}
for name, addr in (("internet", ("1.1.1.1", 53)), ("api", ("api.anthropic.com", 443))):
    try:
        socket.create_connection(addr, timeout=3).close(); r[name] = "connected"
    except OSError as e:
        r[name] = "blocked:" + type(e).__name__
for name, p in (("reference", {str(ref)!r}), ("tests", {str(task / 'tests')!r}), ("repo", {str(REPO)!r}),
                ("hidden_eval", "/eval/in")):
    try:
        r[name] = "listed:" + ",".join(os.listdir(p)) if os.path.isdir(p) else (open(p).read() and "read")
    except OSError as e:
        r[name] = "blocked:" + type(e).__name__
r["public_data"] = os.path.isfile("/workspace/data/README.md")
r["own_output"] = os.path.isfile("/workspace/output/pipeline/run.sh")
print("PROBE " + json.dumps(r))
'''
    files = {'run.sh': '#!/bin/bash\nHERE="$(cd "$(dirname "$0")" && pwd)"\npython3 "$HERE/probe.py"\n'
                       'echo "pwd=$PWD here=$HERE"\n', 'probe.py': probe}
    run_dir, record = run(task, tmp_path, fake_agent(tmp_path / 'net-agent', write_files_body(files)))
    logs = sorted((run_dir / 'grading' / 'pipeline_logs').glob('*.log'))
    assert len(logs) == 3
    for log in logs:
        text = log.read_text()
        result = json.loads(text.split('PROBE ', 1)[1].splitlines()[0])
        assert result['internet'].startswith('blocked:') and result['api'].startswith('blocked:'), result
        assert result['reference'].startswith('blocked:') and result['tests'].startswith('blocked:')
        assert result['repo'].startswith('blocked:')
        assert result['hidden_eval'] == 'listed:' + log.stem         # only its own case input
        assert result['public_data'] and result['own_output']
        assert f'pwd=/eval/home/{log.stem} here=/eval/pipeline' in text
    assert record['reward']['ran'] == 0.0


def test_existing_run_directory_is_never_overwritten(task, tmp_path):
    agent = fake_agent(tmp_path / 'idle', 'pass\n')
    run_dir, _ = run(task, tmp_path, agent)
    before = (run_dir / 'run.json').read_bytes()
    with pytest.raises(FileExistsError):
        run(task, tmp_path, agent)
    assert (run_dir / 'run.json').read_bytes() == before


def test_stop_file_and_codex_guard(task, tmp_path):
    agent = fake_agent(tmp_path / 'idle', 'pass\n')
    (tmp_path / 'out').mkdir()
    (tmp_path / 'out' / 'STOP').write_text('')
    with pytest.raises(pilot.PilotError, match='STOP'):
        run(task, tmp_path, agent)
    os.remove(tmp_path / 'out' / 'STOP')
    with pytest.raises(pilot.PilotError, match='Codex'):
        run(task, tmp_path, agent, backend='codex')
    assert not (tmp_path / 'out' / 'r1').exists()


def test_summarize_table(task, tmp_path):
    oracle = task / 'solution' / 'pipeline'
    files = {p.name: p.read_text() for p in oracle.iterdir() if p.is_file()}
    run(task, tmp_path, fake_agent(tmp_path / 'oracle-agent', write_files_body(files)), model='fake-a')
    run(task, tmp_path, fake_agent(tmp_path / 'idle', 'pass\n'), model='fake-b')
    out = subprocess.run([sys.executable, str(REPO / 'scripts' / 'run_suite_pilot.py'), 'summarize',
                          str(tmp_path / 'out' / 'r1')], capture_output=True, text=True, check=True).stdout
    assert all(k in out for k in REWARD_KEYS) and 'fake-a' in out and 'fake-b' in out
    rows = {r['model']: r for r in json.loads((tmp_path / 'out' / 'r1' / 'summary.json').read_text())}
    assert rows['fake-a']['reward'] == 1.0 and rows['fake-b']['reward'] == 0.0
    assert rows['fake-a']['agent_headline_raw'] == 1.0
    assert 0 < rows['fake-a']['specialist_headline'] < 1.0
