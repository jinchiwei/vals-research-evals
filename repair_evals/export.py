"""Harbor/Valkyrie task export; packaging is not a hosted execution claim.

Runtime: Python 3.12+ on Linux. Hosted grading requires root to drop privileges;
non-root local grading requires working bubblewrap user namespaces. The latter
isolates files/processes, not network. These measures separate hidden answers
from submitted analysis code; they are not a general hostile-agent sandbox.
"""
import argparse
import hashlib
import inspect
import json
from pathlib import Path, PurePosixPath

from .cases import make_case
from .scoring import compare


VERIFIER = r'''
import argparse
import ctypes
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile


class SubmissionError(ValueError):
    pass


def copy_public(source, destination):
    """Copy regular workspace files only, never links/devices/sockets."""
    total = 0
    members = list(source.rglob('*'))
    if len(members) > 250:
        raise SubmissionError('Workspace exceeds 250 entries')
    for item in members:
        mode = item.lstat().st_mode
        target = destination / item.relative_to(source)
        if stat.S_ISDIR(mode):
            target.mkdir(parents=True, exist_ok=True)
        elif stat.S_ISREG(mode):
            total += item.stat().st_size
            if total > 20_000_000:
                raise SubmissionError('Workspace exceeds 20 MB')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)
            target.chmod(0o644)
        else:
            raise SubmissionError('Workspace contains a non-regular file')


def child_limits(drop):
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2_000_000, 2_000_000))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if drop:
        # Prevent regaining privilege through setuid executables/file capabilities.
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'no_new_privs failed')
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)
        if os.geteuid() != 65534 or os.getgroups():
            raise RuntimeError('Privilege drop failed')


def protect(path):
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError('Private directory must be a real directory')
    os.chown(path, 0, 0)
    path.chmod(0o700)


def command(work, root):
    if root:
        return [sys.executable, '-B', str(work / 'analysis.py'),
                str(work / '_evaluation_input.json'), str(work / '_evaluation_output.json')]
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise RuntimeError('Non-root verification requires bubblewrap; refusing unsafe execution')
    cmd = [bwrap, '--die-with-parent', '--new-session', '--unshare-pid', '--unshare-ipc',
           '--clearenv', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    for runtime in ('/usr', '/bin', '/lib', '/lib64'):
        if Path(runtime).exists():
            cmd += ['--ro-bind', runtime, runtime]
    cmd += ['--bind', str(work), '/workspace', '--chdir', '/workspace',
            '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin',
            '--setenv', 'HOME', '/tmp', '--setenv', 'LANG', 'C.UTF-8',
            '/usr/bin/python3', '-B', '/workspace/analysis.py',
            '/workspace/_evaluation_input.json', '/workspace/_evaluation_output.json']
    return cmd


def run_fixture(work, root):
    args = command(work, root)
    # Log files are opened by the trusted parent, not paths exposed to the child.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(args, cwd=work, stdout=stdout, stderr=stderr,
                                   stdin=subprocess.DEVNULL, close_fds=True,
                                   start_new_session=True,
                                   env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp',
                                        'LANG': 'C.UTF-8'},
                                   preexec_fn=lambda: child_limits(root))
        timed_out = False
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        if timed_out:
            return None, 'timeout'
        if process.returncode:
            stderr.seek(0)
            detail = stderr.read(2048).decode('utf-8', errors='replace')
            if not root and 'bwrap:' in detail:
                raise RuntimeError('Bubblewrap isolation failed: ' + detail)
            return None, 'submission exit ' + str(process.returncode)
    output = work / '_evaluation_output.json'
    try:
        mode = output.lstat().st_mode
        if not stat.S_ISREG(mode) or output.stat().st_size > 1_000_000:
            raise ValueError('Invalid output file')
        def reject_constant(value):
            raise ValueError('Nonfinite JSON constant')
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate JSON key')
                result[key] = value
            return result
        actual = json.loads(output.read_text(), parse_constant=reject_constant,
                            object_pairs_hook=unique_object)
        return actual, None
    except (OSError, ValueError):
        return None, 'missing, malformed, or oversized output'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, default=Path('/workspace'))
    parser.add_argument('--logs', type=Path, default=Path('/logs/verifier'))
    args = parser.parse_args()
    private = Path(__file__).resolve().parent
    root = os.geteuid() == 0
    result = {'passed': False, 'fixtures': [], 'infrastructure_error': None, 'submission_error': None,
              'isolation': 'unprivileged-uid' if root else 'bubblewrap-filesystem'}
    args.logs.mkdir(parents=True, exist_ok=True)
    if root:
        protect(args.logs)
    (args.logs / 'reward.txt').write_text('0\n')
    try:
        if root:
            protect(private)
            solution = private.parent / 'solution'
            if solution.exists():
                protect(solution)
        fixtures = json.loads((private / 'fixtures.json').read_text())
        if not fixtures:
            raise RuntimeError('No private fixtures')
        with tempfile.TemporaryDirectory(prefix='repair-verifier-') as temp:
            parent = Path(temp)
            # Unprivileged execution can traverse this directory but not private/tests/logs.
            parent.chmod(0o755)
            for index, fixture in enumerate(fixtures):
                work = parent / str(index)
                work.mkdir()
                copy_public(args.workspace, work)
                for reserved in ('_evaluation_input.json', '_evaluation_output.json'):
                    p = work / reserved
                    if p.exists():
                        p.unlink()
                (work / '_evaluation_input.json').write_text(json.dumps(fixture['input']))
                if root:
                    # Each run gets an independent working tree; no hidden expected values enter it.
                    for item in [work, *work.rglob('*')]:
                        os.chown(item, 65534, 65534)
                        if item.is_dir():
                            item.chmod(0o700)
                actual, error = run_fixture(work, root)
                row = compare(fixture['expected'], actual)
                row.update(index=index, execution_error=error)
                if error:
                    row['passed'] = False
                result['fixtures'].append(row)
        result['passed'] = all(row['passed'] for row in result['fixtures'])
    except SubmissionError as error:
        result['submission_error'] = str(error)
    except Exception as error:
        result['infrastructure_error'] = type(error).__name__ + ': ' + str(error)
    (args.logs / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    (args.logs / 'reward.txt').write_text('1\n' if result['passed'] else '0\n')


if __name__ == '__main__':
    main()
'''


def export_case(case, destination, *, oracle_source=None):
    """Create an immutable self-contained task folder, returning its Path."""
    task_id = case['id']
    if not task_id or PurePosixPath(task_id).name != task_id or task_id in ('.', '..'):
        raise ValueError('Invalid task ID')
    for name in case['files']:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('Public filenames must be relative paths without traversal')
    if oracle_source is None:
        factory = make_case
        if case['family'] == 'integrated':
            from .integrated import make_case as make_integrated
            fresh = make_integrated(case['seed'], case['variant'])
            valid = make_integrated(case['seed'], 'valid')
        else:
            fresh = factory(case['family'], case['seed'], case['variant'])
            valid = factory(case['family'], case['seed'], 'valid')
        if fresh != case:
            raise ValueError('Frozen case does not match current generator; supply its captured oracle_source')
        oracle_source = valid['files']['analysis.py']
    if not isinstance(oracle_source, str) or not oracle_source.strip():
        raise ValueError('oracle_source must be nonempty Python source')
    root = Path(destination) / task_id
    root.mkdir(parents=True, exist_ok=False)
    for name in ('environment/workspace', 'tests', 'solution'):
        (root / name).mkdir(parents=True)
    for name, content in case['files'].items():
        target = root / 'environment' / 'workspace' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    (root / 'instruction.md').write_text(case['instruction'] + '\n\nWork in /workspace. '
        'The verifier invokes python analysis.py INPUT.json OUTPUT.json on unseen inputs.\n\n'
        'Per replay: 8 CPU seconds, 12 wall-clock seconds, 512 MiB address space, '
        '2 MB maximum individual file writes, and 1 MB accepted JSON output. '
        'The submitted workspace must contain only regular files/directories, '
        'at most 250 entries and 20 MB total. Preserve correct behavior on clean inputs.\n')
    (root / 'task.toml').write_text('''schema_version = "1.4"
[metadata]
category = "scientific-reasoning"
tags = ["synthetic", "research", "repository-repair"]
[agent]
timeout_sec = 600.0
[verifier]
timeout_sec = 90.0
[environment]
cpus = 1
memory_mb = 1024
storage_mb = 2048
''')
    (root / 'environment' / 'Dockerfile').write_text(
        'FROM python:3.12-slim\nWORKDIR /workspace\nCOPY workspace/ /workspace/\n')
    (root / 'tests' / 'fixtures.json').write_text(json.dumps(case['hidden'], indent=2))
    (root / 'tests' / 'grade.py').write_text('import math\n' + inspect.getsource(compare) + '\n' + VERIFIER)
    (root / 'tests' / 'test.sh').write_text('#!/bin/sh\nset -eu\npython3 -I /tests/grade.py\n')
    (root / 'solution' / 'analysis.py').write_text(oracle_source)
    (root / 'solution' / 'oracle.sha256').write_text(hashlib.sha256(oracle_source.encode()).hexdigest() + '\n')
    (root / 'solution' / 'solve.sh').write_text(
        '#!/bin/sh\nset -eu\ncp /solution/analysis.py /workspace/analysis.py\n')
    (root / 'tests' / 'test.sh').chmod(0o755)
    (root / 'solution' / 'solve.sh').chmod(0o755)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', default=[11, 101])
    parser.add_argument('--families', nargs='+', choices=['endpoint', 'claims', 'geometry', 'integrated'],
                        default=['endpoint', 'claims', 'geometry'])
    parser.add_argument('--variants', nargs='+', choices=['flawed', 'valid'], default=['flawed', 'valid'])
    args = parser.parse_args()
    count = 0
    for family in args.families:
        for seed in args.seeds:
            for variant in args.variants:
                if family == 'integrated':
                    from .integrated import make_case as make_integrated
                    case = make_integrated(seed, variant)
                else:
                    case = make_case(family, seed, variant)
                export_case(case, args.out)
                count += 1
    print(f'Exported {count} Harbor tasks; no hosted execution or upload performed.')


if __name__ == '__main__':
    main()
