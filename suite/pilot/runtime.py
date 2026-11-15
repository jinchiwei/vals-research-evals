"""Per-task Python runtime: a conda env holding exactly the task image's pip pins.

The exported environment/Dockerfile installs its packages with one
`pip install --no-cache-dir <pins>` line into /opt/benchmark-venv. We build
`vals-suite-rt-<family>` (python 3.12 + pip, conda-forge with nodefaults, everything else via pip,
as suite/environment.yml does) from those pins and bind it at /opt/benchmark-venv in both
sandboxes. If the Dockerfile has no pins, the suite core requirements are used (minus pytest).
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONDA = Path(os.path.expanduser('~/miniconda3/bin/conda'))
ENVS = Path(os.path.expanduser('~/miniconda3/envs'))
MARKER = '.vals-suite-rt.json'
PIP_LINE = re.compile(r'pip install (?:--no-cache-dir )?(.+?)\s*$')


def _norm(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def task_requirements(task_dir):
    """(list of pins, source description) for an exported task."""
    dockerfile = Path(task_dir) / 'environment' / 'Dockerfile'
    if dockerfile.is_file():
        for line in dockerfile.read_text().splitlines():
            if line.startswith('RUN') and 'pip install' in line:
                m = PIP_LINE.search(line)
                if m:
                    pins = [p for p in m.group(1).split() if not p.startswith('-')]
                    if pins:
                        return pins, 'environment/Dockerfile pip install line'
    core = [ln.strip() for ln in (REPO / 'suite' / 'requirements.txt').read_text().splitlines()
            if ln.strip() and not ln.startswith('#') and not ln.lower().startswith('pytest')]
    return core, 'suite/requirements.txt (fallback; task has no pins)'


def requirements_sha(pins):
    return hashlib.sha256('\n'.join(sorted(pins)).encode()).hexdigest()


def env_name(family):
    if not re.fullmatch(r'[a-z0-9_]+', family):
        raise ValueError(f'bad family name {family!r}')
    return f'vals-suite-rt-{family}'


def check_env(prefix, pins):
    """Return the list of pins missing from the env's pip freeze (empty = OK)."""
    python = Path(prefix) / 'bin' / 'python'
    out = subprocess.run([str(python), '-m', 'pip', 'list', '--format=json', '--disable-pip-version-check'],
                         capture_output=True, text=True, timeout=120, check=True).stdout
    have = {_norm(p['name']): p['version'] for p in json.loads(out)}
    missing = []
    for pin in pins:
        name, _, version = pin.partition('==')
        if have.get(_norm(name)) != version:
            missing.append(pin)
    return missing


def ensure_env(family, pins, *, build=True, log=print):
    """Use or create ~/miniconda3/envs/vals-suite-rt-<family>; returns (prefix, info)."""
    name = env_name(family)
    prefix = ENVS / name
    sha = requirements_sha(pins)
    marker = prefix / MARKER
    if prefix.exists():
        recorded = json.loads(marker.read_text()) if marker.is_file() else {}
        if recorded.get('requirements_sha256') != sha:
            raise RuntimeError(f'{prefix} exists but was built from different requirements; remove it with '
                               f'`{CONDA} env remove -n {name}` and rerun')
        missing = check_env(prefix, pins)
        if missing:
            raise RuntimeError(f'{prefix} is missing pins {missing}')
        return prefix, {'name': name, 'prefix': str(prefix), 'requirements_sha256': sha, 'pins': pins, 'created': False}
    if not build:
        raise RuntimeError(f'{prefix} does not exist (build disabled)')
    with tempfile.TemporaryDirectory(prefix='vals-suite-rt-') as tmp:
        (Path(tmp) / 'requirements.txt').write_text('\n'.join(pins) + '\n')
        (Path(tmp) / 'environment.yml').write_text(
            f'name: {name}\nchannels:\n  - conda-forge\n  - nodefaults\ndependencies:\n  - python=3.12\n'
            '  - pip\n  - pip:\n      - -r requirements.txt\n')
        log(f'creating conda env {name} from {len(pins)} pins')
        subprocess.run([str(CONDA), 'env', 'create', '-n', name, '-f', str(Path(tmp) / 'environment.yml')],
                       check=True, cwd=tmp, timeout=3600)
    missing = check_env(prefix, pins)
    if missing:
        raise RuntimeError(f'new env {prefix} is missing pins {missing}')
    marker.write_text(json.dumps({'requirements_sha256': sha, 'pins': pins}, indent=2) + '\n')
    return prefix, {'name': name, 'prefix': str(prefix), 'requirements_sha256': sha, 'pins': pins, 'created': True}
