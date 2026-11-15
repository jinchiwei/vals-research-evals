"""Run one coding agent once on an exported suite task in a local bubblewrap sandbox, then grade it
with the task's own tests/grade.py, the pipeline running in a second, network-less sandbox.

Local stand-in for a hosted Valkyrie run; see docs/research/suite/local-pilots.md for what it
does and does not reproduce.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

from . import runtime, sandbox

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / 'exp' / 'suite-pilots'
RELAY = Path(__file__).resolve().parent / 'relay.py'
CLAUDE_MODELS = ('claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5')
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
MAX_BUDGET_USD = 5.0
KILL_GRACE_SEC = 10
REWARD_KEYS = ('reward', 'ran', 'valid', 'within_time', 'clinically_acceptable', 'quality', 'vs_specialist')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,80}')
CODEX_HOSTS = ('api.openai.com', 'chatgpt.com')


class PilotError(RuntimeError):
    pass


def _sha_tree(paths):
    h = hashlib.sha256()
    for root in paths:
        root = Path(root)
        files = [root] if root.is_file() else sorted(p for p in root.rglob('*') if p.is_file()
                                                     and '__pycache__' not in p.parts)
        for p in files:
            h.update(p.relative_to(root.parent).as_posix().encode() + b'\0')
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def load_task(task_dir):
    task = Path(task_dir).resolve()
    config_path = task / 'tests' / 'task_config.json'
    for rel in ('task.toml', 'instruction.md', 'environment/data', 'tests/grade.py'):
        if not (task / rel).exists():
            raise PilotError(f'{task} is not an exported suite task (missing {rel})')
    if not config_path.is_file():
        raise PilotError(f'{task}: tests/task_config.json missing; only suite.core-graded tasks are supported')
    config = json.loads(config_path.read_text())
    if config.get('schema') != 'suite-task-config/1':
        raise PilotError(f'{task}: grader interface {config.get("schema")!r} is not suite-task-config/1')
    toml = tomllib.loads((task / 'task.toml').read_text())
    meta = toml.get('metadata', {})
    return {'dir': task, 'config': config, 'toml': toml, 'task_id': config['task_id'], 'family': config['family'],
            'tier': meta.get('tier', 'build' if 'toolbox' not in config['task_id'] else 'toolbox'),
            'allowed_hosts': tuple(toml.get('agent', {}).get('allowed_hosts', ())),
            'agent_timeout_sec': toml.get('agent', {}).get('timeout_sec'),
            'verifier_timeout_sec': toml.get('verifier', {}).get('timeout_sec', 600),
            'threads': config.get('threads'),
            'grader_sha256': _sha_tree([task / 'tests' / 'grade.py', task / 'tests' / 'test.sh',
                                        task / 'tests' / 'task_config.json', task / 'tests' / 'lib']),
            'agent_side_sha256': _sha_tree([task / 'instruction.md', task / 'environment'])}


def stop_requested(out_root, run_dir):
    return any((p / 'STOP').exists() for p in (Path(out_root), Path(run_dir)))


# ------------------------------------------------------------------------------- backends

def claude_argv(model, effort, budget, auth):
    argv = ['/opt/agent/claude', '--print', '--output-format', 'stream-json', '--verbose', '--model', model,
            '--effort', effort, '--max-budget-usd', f'{budget:g}', '--permission-mode', 'bypassPermissions',
            '--no-session-persistence', '--strict-mcp-config', '--disallowed-tools', 'WebFetch', 'WebSearch']
    # --bare refuses OAuth logins (API key only); with the local subscription login use --safe-mode,
    # which likewise disables CLAUDE.md, skills, plugins, hooks and MCP servers.
    argv.insert(1, '--bare' if auth == 'api-key' else '--safe-mode')
    return argv


def codex_argv(model, effort):
    return ['/opt/agent/codex', 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral',
            '--skip-git-repo-check', '--dangerously-bypass-approvals-and-sandbox', '--model', model,
            '-c', f'model_reasoning_effort="{effort}"', '-c', 'web_search="disabled"', '--json', '-']


def prepare_claude_home(home, auth, credentials):
    (home / '.claude').mkdir(parents=True)
    host_cfg = Path.home() / '.claude.json'
    settings = {}
    if auth == 'oauth' and host_cfg.is_file():
        settings = json.loads(host_cfg.read_text())
    (home / '.claude.json').write_text(json.dumps({
        'hasCompletedOnboarding': True, 'oauthAccount': settings.get('oauthAccount', {}),
        'projects': {'/workspace': {'hasTrustDialogAccepted': True}}}))
    if auth == 'oauth':
        return [(credentials, '/home/agent/.claude/.credentials.json')]
    return []


def _secrets(credentials, auth):
    """Strings that must never land in results (returned only for redaction)."""
    out = []
    if auth == 'oauth' and credentials and Path(credentials).is_file():
        data = json.loads(Path(credentials).read_text()).get('claudeAiOauth', {})
        out += [data.get('accessToken'), data.get('refreshToken')]
    if auth == 'api-key':
        out.append(os.environ.get('ANTHROPIC_API_KEY'))
    return [s for s in out if isinstance(s, str) and len(s) >= 16]


def _oauth_seconds_left(credentials):
    data = json.loads(Path(credentials).read_text()).get('claudeAiOauth', {})
    expires = data.get('expiresAt')
    return None if not expires else expires / 1000 - time.time()


def redact(paths, secrets):
    count = 0
    for root in paths:
        root = Path(root)
        files = [root] if root.is_file() else [p for p in root.rglob('*') if p.is_file() and not p.is_symlink()]
        for p in files:
            try:
                data = p.read_bytes()
            except OSError:
                continue
            new = data
            for s in secrets:
                new = new.replace(s.encode(), b'[REDACTED-CREDENTIAL]')
            if new != data:
                count += 1
                p.write_bytes(new)
    return count


def parse_trace(path):
    models, tools, result, events, init = set(), [], None, 0, None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            events += 1
            msg = event.get('message') if isinstance(event.get('message'), dict) else {}
            m = msg.get('model')
            if isinstance(m, str) and m and not m.startswith('<'):      # '<synthetic>' = CLI-made message
                models.add(m)
            if event.get('type') == 'system' and event.get('subtype') == 'init':
                init = {k: event.get(k) for k in ('model', 'tools', 'permissionMode', 'apiKeySource',
                                                  'claude_code_version', 'mcp_servers', 'cwd')}
            content = msg.get('content')
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get('type') == 'tool_use':
                    tools.append(block.get('name'))
            if event.get('type') == 'result':
                result = event
    usage_models = sorted((result or {}).get('modelUsage', {}) or {})
    return {'events': events, 'cli_init': init, 'models_in_messages': sorted(models), 'models_in_usage': usage_models,
            'tool_calls': len(tools), 'tools_used': sorted(set(t for t in tools if t)),
            'result': None if result is None else {k: result.get(k) for k in (
                'subtype', 'is_error', 'num_turns', 'total_cost_usd', 'duration_ms', 'duration_api_ms',
                'usage', 'modelUsage', 'stop_reason', 'session_id') if k in result}}


# ------------------------------------------------------------------------------- agent stage

def run_agent(task, run_dir, *, backend, model, effort, time_limit_sec, budget_usd, runtime_prefix,
              agent_bin, auth, credentials, egress, scratch, out_root, log=print):
    instruction = (task['dir'] / 'instruction.md').read_text()
    work = Path(tempfile.mkdtemp(prefix='suite-pilot-', dir=scratch))
    workspace, home = work / 'workspace', work / 'home'
    workspace.mkdir()
    (workspace / 'output').mkdir()
    (workspace / 'instruction.md').write_text(instruction)
    home.mkdir()
    extra_ro = []
    if backend == 'claude':
        extra_ro = prepare_claude_home(home, auth, credentials)
        command = claude_argv(model, effort, budget_usd, auth)
        agent_name = 'claude'
        hosts = task['allowed_hosts'] or ('api.anthropic.com',)
        env_extra = {'DISABLE_AUTOUPDATER': '1', 'DISABLE_TELEMETRY': '1', 'DISABLE_ERROR_REPORTING': '1',
                     'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'IS_SANDBOX': '1'}
        if auth == 'api-key':
            env_extra['ANTHROPIC_API_KEY'] = os.environ['ANTHROPIC_API_KEY']   # env only, never argv
    else:
        (home / '.codex').mkdir()
        if auth != 'none':
            extra_ro = [(credentials, '/home/agent/.codex/auth.json')]
        command = codex_argv(model, effort)
        agent_name = 'codex'
        hosts = CODEX_HOSTS
        env_extra = {}
    proxy, sock = None, None
    if egress == 'proxy':
        # AF_UNIX paths are limited to 107 bytes, so the socket lives in a short /tmp directory.
        sock = Path(tempfile.mkdtemp(prefix='suite-egress-', dir='/tmp')) / 'egress.sock'
        proxy = sandbox.EgressProxy(sock, hosts).start()
    argv = sandbox.agent_command(workspace=workspace, data_dir=task['dir'] / 'environment' / 'data', home=home,
                                 runtime_prefix=runtime_prefix, agent_bin=agent_bin, agent_name=agent_name,
                                 command=command, egress=egress, proxy_socket=sock,
                                 relay_script=RELAY, extra_ro=extra_ro)
    env = sandbox.agent_env(env_extra, threads=task['threads'], egress=egress)
    trace, stderr = run_dir / 'trace.jsonl', run_dir / 'agent-stderr.txt'
    secrets = _secrets(credentials, auth)          # read before the run: the host may refresh the file meanwhile
    status, code = 'completed', None
    log(f'agent start: {backend} {model} effort={effort} limit={time_limit_sec}s budget=${budget_usd:g} egress={egress}')
    started = time.monotonic()
    with trace.open('wb') as out, stderr.open('wb') as err:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=out, stderr=err, env=env,
                                start_new_session=True)
        try:
            proc.stdin.write(instruction.encode())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        deadline = started + time_limit_sec
        while True:
            try:
                code = proc.wait(timeout=2)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() >= deadline or stop_requested(out_root, run_dir.parent.parent):
                status = 'timeout' if time.monotonic() >= deadline else 'stopped'
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    try:
                        os.killpg(proc.pid, sig)
                    except ProcessLookupError:
                        break
                    try:
                        proc.wait(timeout=KILL_GRACE_SEC)
                        break
                    except subprocess.TimeoutExpired:
                        continue
                code = proc.wait()
                break
    wall = time.monotonic() - started
    if status == 'completed' and code != 0:
        status = 'nonzero_exit'
    egress_summary = None
    if proxy is not None:
        proxy.stop()
        egress_summary = proxy.summary()
        shutil.rmtree(sock.parent, ignore_errors=True)
    # Keep what the platform would carry (/workspace/output) plus a listing of the rest.
    kept = run_dir / 'workspace'
    kept.mkdir()
    shutil.copytree(workspace / 'output', kept / 'output', symlinks=True, ignore_dangling_symlinks=True,
                    ignore=_ignore_special)
    listing = []
    for p in sorted(workspace.rglob('*')):
        try:
            st = p.lstat()
        except OSError:
            continue
        listing.append({'path': '/' + p.relative_to(work).as_posix(), 'bytes': st.st_size,
                        'type': 'dir' if stat.S_ISDIR(st.st_mode) else 'link' if stat.S_ISLNK(st.st_mode)
                        else 'file' if stat.S_ISREG(st.st_mode) else 'special'})
        if len(listing) >= 20000:
            break
    sandbox.dump(kept / 'listing.json', listing)
    redactions = redact([trace, stderr, kept], secrets)
    record = {'status': status, 'exit_code': code, 'wall_seconds': round(wall, 3), 'egress': egress_summary,
              'credential_redactions': redactions,
              'argv_in_sandbox': command, 'agent_bin': str(agent_bin), 'trace': trace.name}
    if backend == 'claude':
        record['trace_summary'] = parse_trace(trace)
    return record, work


def _ignore_special(directory, names):
    bad = []
    for n in names:
        try:
            m = os.lstat(os.path.join(directory, n)).st_mode
        except OSError:
            bad.append(n)
            continue
        if not (stat.S_ISREG(m) or stat.S_ISDIR(m) or stat.S_ISLNK(m)):
            bad.append(n)
    return bad


# ------------------------------------------------------------------------------- grading stage

def grade(task, run_dir, live_output, *, runtime_prefix, scratch, log=print):
    """Run the task's tests/grade.py (outside any agent sandbox) with the pipeline wrapped in the
    no-network pipeline sandbox. Writes run_dir/grading/{reward.json, metrics.json, ...}."""
    run_dir, live_output, runtime_prefix = Path(run_dir).resolve(), Path(live_output).resolve(), Path(runtime_prefix).resolve()
    grading = run_dir / 'grading'
    grading.mkdir()
    tmp = Path(tempfile.mkdtemp(prefix='suite-grade-', dir=Path(scratch).resolve()))
    try:
        pipeline = live_output / 'pipeline'
        run_sh = pipeline / 'run.sh'
        wrapped = False
        submit = pipeline
        if run_sh.is_file() and not run_sh.is_symlink() and not _has_special(pipeline):
            shim_dir = tmp / 'submission'
            shutil.copytree(pipeline, shim_dir / 'agent', symlinks=True)
            sandbox.write_pipeline_shim(shim_dir, runtime_prefix=runtime_prefix,
                                        data_dir=task['dir'] / 'environment' / 'data', agent_output_dir=live_output)
            submit, wrapped = shim_dir, True
        logs, work = tmp / 'logs', tmp / 'eval'
        python = Path(runtime_prefix) / 'bin' / 'python'
        argv = [str(python), '-I', '-B', str(task['dir'] / 'tests' / 'grade.py'), '--tests', str(task['dir'] / 'tests'),
                '--pipeline', str(submit), '--logs', str(logs), '--work', str(work), '--sandbox-root', 'none']
        log(f'grading: {len(task["config"]["cases"])} hidden cases, {task["config"]["time_limit_seconds"]}s per case')
        started = time.monotonic()
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=float(task['verifier_timeout_sec']),
                              env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(tmp)})
        seconds = time.monotonic() - started
        (grading / 'verifier-stdout.txt').write_text(proc.stdout[-20000:])
        (grading / 'verifier-stderr.txt').write_text(proc.stderr[-20000:])
        for name in ('reward.json', 'metrics.json'):
            if (logs / name).is_file():
                shutil.copyfile(logs / name, run_dir / name)
        if (logs / 'pipeline_logs').is_dir():
            shutil.copytree(logs / 'pipeline_logs', grading / 'pipeline_logs')
        # A sandbox that failed to start must not be scored as the agent's failure.
        bwrap_failures = sorted(p.stem for p in (grading / 'pipeline_logs').glob('*.log')
                                if p.read_bytes()[:7] == b'bwrap: ') if wrapped and (grading / 'pipeline_logs').is_dir() else []
        if bwrap_failures:
            log(f'INFRASTRUCTURE ERROR: pipeline sandbox failed to start for {bwrap_failures}; reward is not valid')
        return {'exit_code': proc.returncode, 'seconds': round(seconds, 3), 'pipeline_wrapped_in_sandbox': wrapped,
                'infrastructure_error': bool(bwrap_failures) or proc.returncode != 0,
                'sandbox_start_failures': bwrap_failures,
                'grader_python': str(python), 'grader_argv': argv}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)        # holds copies of hidden inputs


def _has_special(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for n in dirnames + filenames:
            m = os.lstat(os.path.join(dirpath, n)).st_mode
            if not (stat.S_ISREG(m) or stat.S_ISDIR(m) or stat.S_ISLNK(m)):
                return True
    return False


# ------------------------------------------------------------------------------- orchestration

SANDBOX_FACTS = {
    'agent': {
        'tool': 'bubblewrap 0.9.0 (unprivileged user namespace)',
        'filesystem': 'empty root; read-only /usr, /etc (+ usr-merged symlinks); runtime env read-only at '
                      '/opt/benchmark-venv; agent CLI read-only at /opt/agent/; fresh writable HOME /home/agent; '
                      'writable /workspace with public data read-only at /workspace/data; private /tmp, /proc, /dev',
        'not_visible': 'repository, tests/ (hidden inputs and references, specialist outputs), solution/, '
                       '/home/jkwei (except the read-only bound login file), /home/jkwei/data, /mnt/c, other projects',
        'namespaces': 'pid, ipc, uts, cgroup; network namespace only with egress=proxy',
        'tools': 'WebFetch and WebSearch disallowed; no MCP servers; --safe-mode (OAuth) or --bare (API key)',
        'differences_from_hosted': 'host /usr has more tools (git, gcc, curl...) than python:3.12-slim; runs as '
                                   'the invoking uid, not root; no CPU/RAM caps on the agent',
    },
    'pipeline': {
        'tool': 'bubblewrap --unshare-all (user, pid, net, ipc, uts, cgroup)',
        'network': 'none (new network namespace with only loopback)',
        'filesystem': 'read-only /usr, /etc, /opt/benchmark-venv; pipeline at /eval/pipeline (ro); one case input '
                      '(ro) at /eval/in/<case>; writable /eval/out/<case> and /eval/home/<case>; agent '
                      '/workspace/output and public /workspace/data read-only, as in the hosted verifier image',
        'not_visible': 'tests/ (hidden references, other cases, specialist outputs), repository, user files',
        'differences_from_hosted': 'runs as the invoking uid inside a user namespace (no switch to uid 65534; '
                                   'isolation is by mount namespace); no CPU/RAM caps; bwrap start-up '
                                   '(~tens of ms) counts toward the per-case wall time',
    },
}


def run_pilot(task_dir, *, run_name, model, backend='claude', effort='high', time_limit_sec=900.0,
              budget_usd=3.0, out_root=DEFAULT_OUT, agent_bin=None, runtime_prefix=None, build_env=True,
              auth='oauth', credentials=None, egress='proxy', scratch=None, allow_codex=False, log=print):
    task = load_task(task_dir)
    if not NAME.fullmatch(run_name) or not NAME.fullmatch(model):
        raise PilotError('run name and model must be simple names')
    if effort not in EFFORTS:
        raise PilotError(f'effort must be one of {EFFORTS}')
    if not 0 < budget_usd <= MAX_BUDGET_USD:
        raise PilotError(f'budget must be in (0, {MAX_BUDGET_USD}]')
    if not 0 < time_limit_sec <= 4 * 3600:
        raise PilotError('time limit must be in (0, 4 h]')
    if egress not in ('proxy', 'open'):
        raise PilotError('egress must be proxy or open')
    if backend == 'codex' and not allow_codex:
        raise PilotError('the Codex backend is disabled (pass --allow-codex; the project lead wants credits saved)')
    if backend not in ('claude', 'codex'):
        raise PilotError(f'unknown backend {backend!r}')
    out_root = Path(out_root).resolve()
    run_dir = out_root / run_name / task['task_id'] / model
    if os.path.lexists(run_dir):
        raise FileExistsError(f'{run_dir} exists; pilot runs are never overwritten')
    if stop_requested(out_root, out_root / run_name):
        raise PilotError('STOP file present; not starting')
    if agent_bin is None:
        which = shutil.which(backend)
        if not which:
            raise PilotError(f'no {backend} executable on PATH')
        agent_bin = Path(which).resolve()
        if backend == 'codex':
            agent_bin = (agent_bin.parent.parent / 'node_modules/@openai/codex-linux-x64/vendor/'
                         'x86_64-unknown-linux-musl/bin/codex')
    agent_bin = Path(agent_bin).resolve()
    if not agent_bin.is_file():
        raise PilotError(f'agent executable {agent_bin} missing')
    if auth == 'oauth':
        credentials = Path(credentials or (Path.home() / ('.claude/.credentials.json' if backend == 'claude'
                                                          else '.codex/auth.json')))
        if not credentials.is_file():
            raise PilotError(f'login file {credentials} missing')
        if backend == 'claude':
            left = _oauth_seconds_left(credentials)
            if left is not None and left < time_limit_sec + 300:
                raise PilotError(f'Claude login token expires in {left / 60:.0f} min, before the run could end; '
                                 'refresh the host login first (the sandbox must not refresh it: the login '
                                 'file is read-only there and a refresh would rotate the host token)')
    elif auth == 'api-key' and not os.environ.get('ANTHROPIC_API_KEY'):
        raise PilotError('ANTHROPIC_API_KEY not set')
    pins, pin_source = runtime.task_requirements(task['dir'])
    if runtime_prefix is None:
        runtime_prefix, env_info = runtime.ensure_env(task['family'], pins, build=build_env, log=log)
    else:
        missing = runtime.check_env(runtime_prefix, pins)
        env_info = {'name': None, 'prefix': str(runtime_prefix), 'override': True, 'pins': pins,
                    'missing_pins': missing, 'requirements_sha256': runtime.requirements_sha(pins)}
    env_info['pin_source'] = pin_source
    scratch = Path(scratch or tempfile.gettempdir()).resolve()
    runtime_prefix = Path(runtime_prefix).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    record = {'schema': 'suite-local-pilot/1', 'evidence': 'local bubblewrap pilot; NOT a hosted Valkyrie run',
              'task_id': task['task_id'], 'family': task['family'], 'tier': task['tier'], 'task_dir': str(task['dir']),
              'agent_side_sha256': task['agent_side_sha256'], 'grader_version_sha256': task['grader_sha256'],
              'backend': backend, 'model_requested': model, 'effort': effort, 'attempts': 1, 'retries': 0,
              'limits': {'agent_time_limit_sec': time_limit_sec, 'budget_usd': budget_usd,
                         'task_agent_timeout_sec': task['agent_timeout_sec'],
                         'per_case_time_limit_sec': task['config']['time_limit_seconds'],
                         'max_turns': None, 'max_turns_note': '--max-turns not available in Claude Code 2.1.325'},
              'auth': auth, 'runtime_env': env_info, 'sandbox': SANDBOX_FACTS,
              'egress_mode': egress, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    if egress == 'open':
        record['network_note'] = 'agent sandbox shares the host network: general internet was reachable'
    else:
        record['network_note'] = ('agent sandbox has its own network namespace; only CONNECT to the allowlisted '
                                  'hosts on port 443 via the host proxy reaches the internet')
    sandbox.dump(run_dir / 'run.json', record)
    try:
        version = subprocess.run([str(agent_bin), '--version'], capture_output=True, text=True, timeout=30)
        record['agent_cli_version'] = version.stdout.strip()[:200]
    except (OSError, subprocess.SubprocessError):
        record['agent_cli_version'] = None
    agent, work = run_agent(task, run_dir, backend=backend, model=model, effort=effort, time_limit_sec=time_limit_sec,
                            budget_usd=budget_usd, runtime_prefix=runtime_prefix, agent_bin=agent_bin, auth=auth,
                            credentials=credentials, egress=egress, scratch=scratch, out_root=out_root, log=log)
    try:
        record['agent'] = agent
        summary = agent.get('trace_summary') or {}
        result = summary.get('result') or {}
        record['models_reported'] = sorted(set(summary.get('models_in_messages', []))
                                           | set(summary.get('models_in_usage', [])))
        record['cost_usd'] = result.get('total_cost_usd')
        record['num_turns'] = result.get('num_turns')
        sandbox.dump(run_dir / 'run.json', record)
        if stop_requested(out_root, out_root / run_name):
            record['grading'] = {'skipped': 'STOP file present'}
        else:
            record['grading'] = grade(task, run_dir, work / 'workspace' / 'output',
                                      runtime_prefix=runtime_prefix, scratch=scratch, log=log)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if (run_dir / 'reward.json').is_file():
        record['reward'] = json.loads((run_dir / 'reward.json').read_text())
    record['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    sandbox.dump(run_dir / 'run.json', record)
    return run_dir, record


# ------------------------------------------------------------------------------- summary

def summarize(run_dir):
    run_dir = Path(run_dir)
    rows = []
    for rec_path in sorted(run_dir.glob('*/*/run.json')):
        rec = json.loads(rec_path.read_text())
        d = rec_path.parent
        reward = json.loads((d / 'reward.json').read_text()) if (d / 'reward.json').is_file() else {}
        metrics = json.loads((d / 'metrics.json').read_text()) if (d / 'metrics.json').is_file() else {}
        cases = metrics.get('cases', [])
        valid = [c['quality'] for c in cases if c.get('valid')]
        spec = metrics.get('specialist', {})
        rows.append({'task': rec['task_id'], 'model': d.name, 'family': rec.get('family'),
                     **{k: reward.get(k) for k in REWARD_KEYS},
                     'headline_metric': metrics.get('primary_metric'),
                     'agent_headline_raw': (sum(valid) / len(valid)) if valid else None,
                     'specialist_headline': spec.get('quality'),
                     'specialist_clinically_acceptable': spec.get('clinically_acceptable'),
                     'agent_median_case_seconds': (metrics.get('summary') or {}).get('agent_wall_seconds_median'),
                     'cost_usd': rec.get('cost_usd'), 'turns': rec.get('num_turns'),
                     'agent_wall_seconds': (rec.get('agent') or {}).get('wall_seconds'),
                     'agent_status': (rec.get('agent') or {}).get('status'),
                     'infra_error': (rec.get('grading') or {}).get('infrastructure_error'),
                     'models_reported': rec.get('models_reported')})
    cols = ['task', 'model', *REWARD_KEYS, 'agent_headline_raw', 'specialist_headline', 'cost_usd', 'turns',
            'agent_wall_seconds', 'agent_status', 'infra_error']

    def fmt(v):
        if v is None:
            return '-'
        if isinstance(v, float):
            return f'{v:.3f}'
        return str(v)
    lines = ['| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(cols)]
    lines += ['| ' + ' | '.join(fmt(r[c]) for c in cols) + ' |' for r in rows]
    notes = sorted({f"- {r['task']}: headline = {r['headline_metric']} (agent value = mean over valid hidden "
                    'cases; specialist = mean quality on the same cases)' for r in rows})
    text = '\n'.join(lines + [''] + notes) + '\n'
    (run_dir / 'summary.md').write_text(text)
    sandbox.dump(run_dir / 'summary.json', rows)
    return text, rows
