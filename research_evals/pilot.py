"""Local Claude tool-agent pilot in an isolated filesystem. Not a hosted Valkyrie run.

Only synthetic inputs, OS runtime and the existing Claude login are mounted.
Neither the repository, generator, grader, answer key nor other home files exist
inside the pilot namespace. API network remains available for Claude authentication.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .cases import generate
from .experiment import fingerprint
from .grade import grade


def model_response_ids(values):
    """CLI-generated error messages use <synthetic>, not an actual model ID."""
    return sorted({v for v in values if isinstance(v, str) and v and not v.startswith('<')})


def sandbox_command(workspace, home, command):
    args = ['bwrap', '--die-with-parent', '--new-session', '--unshare-pid', '--unshare-ipc',
            '--clearenv', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    for path in ['/usr', '/bin', '/lib', '/lib64', '/etc']:
        if Path(path).exists():
            args += ['--ro-bind', path, path]
    # WSL's /etc/resolv.conf points outside /etc. Preserve that single target,
    # not the surrounding host filesystem.
    dns = Path('/etc/resolv.conf').resolve()
    if str(dns) != '/etc/resolv.conf':
        args += ['--ro-bind', str(dns), str(dns)]
    args += ['--bind', str(home), '/home/agent', '--bind', str(workspace), '/workspace',
             '--setenv', 'HOME', '/home/agent', '--setenv', 'USER', 'agent',
             '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
             '--setenv', 'TERM', 'dumb', '--chdir', '/workspace']
    return args + command


def run_pilot(out, seed, model='claude-opus-5-5', effort='high', max_tasks=4, timeout=240,
              budget=3.0, family=None, prompt_variant='base', workflow=False):
    if max_tasks < 1 or max_tasks > 4 or budget <= 0 or budget > 5:
        raise ValueError('Pilot caps: 1–4 tasks and 0 < per-task budget <= $5')
    if out.exists():
        raise FileExistsError('Use a new output directory; pilot results are immutable')
    binary = Path(shutil.which('claude') or '/missing').resolve()
    credential = Path.home() / '.claude' / '.credentials.json'
    if not binary.is_file() or not credential.is_file() or not shutil.which('bwrap'):
        raise RuntimeError('Claude login, native executable, and bubblewrap are required')
    out.mkdir(parents=True)
    cases = [c for c in generate(seed) if family is None or c['family'] == family][:max_tasks]
    if workflow:
        from .challenge import complicate
        cases = [complicate(c) for c in cases]
    if not cases:
        raise ValueError('No matching cases')
    manifest = dict(evidence='live-local-tool-agent; NOT hosted Valkyrie', seed=seed,
                    requested_model=model, effort=effort, timeout_per_task=timeout,
                    dollar_cap_per_task=budget, case_ids=[c['id'] for c in cases],
                    prompt_variant=prompt_variant, workflow=workflow, source_sha256=fingerprint())
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    results = []
    for case in cases:
        if (out / 'STOP').exists() or (out.parent / 'STOP').exists():
            break
        dest = out / case['id']
        dest.mkdir()
        workspace = dest / 'workspace'
        workspace.mkdir()
        (workspace / 'input.json').write_text(json.dumps(case['public'], indent=2))
        prompt = case['instruction'] + '\nInput: /workspace/input.json. Use Python via Bash for calculations. '
        prompt += 'Save your analysis and answer in /workspace. Do not install packages; Python stdlib is sufficient.'
        if prompt_variant == 'audit-check':
            prompt += (' Before finalizing, independently check your interpretation of the decision rule, '
                       'chronology, and uncertainty. Test your calculation on one small hand-computable example.')
        (dest / 'prompt.txt').write_text(prompt)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='vals-agent-home-') as temporary:
            home = Path(temporary)
            (home / '.claude').mkdir()
            # Login metadata only, not hooks, plugins, MCP configs, or memories.
            original = Path.home() / '.claude.json'
            settings = json.loads(original.read_text()) if original.exists() else {}
            (home / '.claude.json').write_text(json.dumps({
                'hasCompletedOnboarding': True,
                'oauthAccount': settings.get('oauthAccount', {}),
                'projects': {'/workspace': {'hasTrustDialogAccepted': True}},
            }))
            cmd = sandbox_command(workspace.resolve(), home, [])
            cmd += ['--ro-bind', str(binary), '/opt/claude',
                    '--ro-bind', str(credential), '/home/agent/.claude/.credentials.json',
                    '/opt/claude', '-p', '--safe-mode', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                    '--model', model, '--effort', effort, '--permission-mode', 'dontAsk',
                    '--tools', 'Read,Write,Edit,Bash', '--allowedTools', 'Read,Write,Edit,Bash',
                    '--no-session-persistence', '--max-budget-usd', str(budget),
                    '--output-format', 'stream-json', '--verbose']
            status, returncode = 'completed', None
            with (dest / 'trace.jsonl').open('w') as stdout, (dest / 'stderr.txt').open('w') as stderr:
                try:
                    process = subprocess.run(cmd, input=prompt, text=True, stdout=stdout, stderr=stderr,
                                             timeout=timeout)
                    returncode = process.returncode
                    if returncode:
                        status = 'runtime_error'
                except subprocess.TimeoutExpired:
                    status = 'timeout'
        actual_models, final, tools_used = set(), {}, []
        for line in (dest / 'trace.jsonl').read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            msg = event.get('message', {})
            if model_response_ids([msg.get('model')]):
                actual_models.add(msg['model'])
            for block in msg.get('content', []) if isinstance(msg.get('content'), list) else []:
                if block.get('type') == 'tool_use':
                    tools_used.append(block.get('name'))
            if event.get('type') == 'result':
                final = event
        try:
            answer_file = workspace / 'answer.json'
            if answer_file.is_symlink() or answer_file.stat().st_size > 1_000_000:
                raise ValueError('Invalid answer file')
            answer = json.loads(answer_file.read_text())
        except (OSError, ValueError):
            answer = None
        result = dict(case=case['id'], family=case['family'], status=status,
                      returncode=returncode, elapsed_seconds=round(time.monotonic()-started, 2),
                      actual_models=sorted(actual_models), tools_used=tools_used,
                      usage=final.get('usage'), cost_usd=final.get('total_cost_usd'),
                      agent_error=final.get('is_error'), **grade(case['expected'], answer))
        (dest / 'result.json').write_text(json.dumps(result, indent=2))
        results.append(result)
        with (out / 'experiments.jsonl').open('a') as handle:
            handle.write(json.dumps(result) + '\n')
        print(json.dumps(result), flush=True)
        # Model/login errors should not consume the budget of the remaining cases.
        if not actual_models:
            break
    (out / 'summary.json').write_text(json.dumps(dict(manifest=manifest, results=results), indent=2))
    return results
