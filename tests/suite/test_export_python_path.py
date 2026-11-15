"""Fix 1 from the first hosted smoke run (docs/research/suite/hosted-smoke.md, finding 1): the registry
agent runs `bash -lc`, Debian's /etc/profile resets PATH in login shells, and the agent's `python3`
was the system Python. Every exported image must put /opt/benchmark-venv/bin first on PATH for login
and non-login shells, and the instruction must name the interpreter by absolute path.
No Docker here: /etc/profile is emulated with a fake profile that resets PATH the way Debian's does.
"""
import shutil
import subprocess
import types

import pytest

from suite.core import export as E
from suite.core import runner


def _spec(**kw):
    base = dict(packages=E.DEFAULT_PACKAGES, pip_extra_index_url=None, threads=None, cpus=4, family='x',
                grading='per_case', allowed_hosts=('api.anthropic.com',), title='T', readme_md='R',
                output_format_md='F', time_limit_seconds=60.0, memory_mb=4096, specialist_name='S',
                cohort_size=None, hard_kill_seconds=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _run_lines(text):
    return [ln for ln in text.splitlines() if ln.startswith('RUN')]


def test_dockerfile_profile_script_and_build_check():
    text = E.dockerfile(_spec())
    lines = text.splitlines()
    assert f'ENV PATH={E.VENV}/bin:$PATH' in text                      # non-login shells (unchanged)
    profile = [ln for ln in lines if E.PROFILE_SCRIPT in ln and 'echo' in ln]
    assert profile == [f"RUN echo '{E.profile_snippet()}' > {E.PROFILE_SCRIPT} && chmod 0644 {E.PROFILE_SCRIPT}"]
    check = [ln for ln in lines if ln.startswith('RUN for s in')]
    assert len(check) == 1
    for shell in E.PATH_CHECK_SHELLS:
        assert f"'{shell}'" in check[0]
    # Order: venv installed, profile written, then checked, all before the data layer.
    i_pip = next(i for i, ln in enumerate(lines) if 'pip install' in ln)
    assert i_pip < lines.index(profile[0]) < lines.index(check[0]) < lines.index('COPY data/ /workspace/data/')
    # Still exactly one pip line (the local pilot runner parses it).
    assert len([ln for ln in _run_lines(text) if 'pip install' in ln]) == 1


def _fake_venv(tmp_path):
    venv = tmp_path / 'opt' / 'benchmark-venv'
    (venv / 'bin').mkdir(parents=True)
    py = venv / 'bin' / 'python3'
    py.write_text('#!/bin/sh\necho venv\n')
    py.chmod(0o755)
    return venv


def _fake_etc_profile(tmp_path, snippet):
    """Debian-like /etc/profile: reset PATH, then source profile.d/*.sh."""
    d = tmp_path / 'etc' / 'profile.d'
    d.mkdir(parents=True)
    if snippet is not None:
        (d / '00-benchmark-venv.sh').write_text(snippet + '\n')
    prof = tmp_path / 'etc' / 'profile'
    prof.write_text('PATH="/usr/local/bin:/usr/bin:/bin"\nexport PATH\n'
                    f'for i in {d}/*.sh; do if [ -r "$i" ]; then . "$i"; fi; done\nunset i\n')
    return prof


@pytest.mark.parametrize('shell', ['bash', 'sh'])
def test_profile_snippet_wins_after_profile_resets_path(tmp_path, shell):
    if not shutil.which(shell):
        pytest.skip(f'no {shell}')
    venv = _fake_venv(tmp_path)
    prof = _fake_etc_profile(tmp_path, E.profile_snippet(str(venv)))
    for env_path in ('/usr/bin:/bin', f'{venv}/bin:/usr/bin:/bin'):   # without / with the image ENV PATH
        out = subprocess.run(['env', '-i', f'PATH={env_path}', shell, '-c', f'. {prof}; command -v python3'],
                             capture_output=True, text=True, check=True).stdout.strip()
        assert out == f'{venv}/bin/python3'
    # Without the snippet the reset PATH loses the venv: the failure seen in the hosted run.
    bare = tmp_path / 'bare'
    bare.mkdir()
    prof2 = _fake_etc_profile(bare, None)
    out = subprocess.run(['env', '-i', f'PATH={venv}/bin:/usr/bin:/bin', shell, '-c', f'. {prof2}; command -v python3'],
                         capture_output=True, text=True).stdout.strip()
    assert out != f'{venv}/bin/python3'


def test_build_check_fails_closed():
    """The RUN check loop parses under /bin/sh and exits non-zero when a shell resolves another python3."""
    check = next(ln for ln in _run_lines(E.dockerfile(_spec())) if ln.startswith('RUN for s in'))[4:]
    subprocess.run(['sh', '-n', '-c', check], check=True)
    wrong = check.replace(E.VENV_PYTHON, '/nonexistent/python3')
    proc = subprocess.run(['sh', '-c', wrong], capture_output=True, text=True)
    assert proc.returncode == 1 and 'resolves python3 to' in proc.stderr


@pytest.mark.parametrize('grading', ['per_case', 'cohort'])
def test_instruction_names_absolute_interpreter(grading):
    spec = _spec(grading=grading, cohort_size=100 if grading == 'cohort' else None)
    text = E.instruction(spec, 3)
    assert f'`{E.VENV_PYTHON}`' in text
    assert 'Call it by this absolute path in `run.sh`' in text
    assert '`python3` on PATH =' not in text                          # the old, false wording
    assert ', '.join(E.DEFAULT_PACKAGES) in text


def test_verifier_unchanged():
    assert E.TEST_SH == f'#!/bin/bash\nset -u\nexec {E.VENV}/bin/python -I -B /tests/grade.py\n'
    assert runner.DEFAULT_PATH.startswith(f'{E.VENV}/bin:')
