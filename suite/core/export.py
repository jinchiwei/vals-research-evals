"""Write a Harbor/Valkyrie task folder from a family spec (packaging only; nothing is uploaded).

Layout written (platform-brief section 4):

  <task_id>/
    task.toml                 separate verifier, no-network verifier, model-API-only agent allowlist
    instruction.md            clinical task + data/output documentation + pipeline contract
    environment/Dockerfile    Python imaging deps in /opt/benchmark-venv; COPY data/
    environment/data/         public inputs: README, development cases (with references if the task has them)
    tests/test.sh             exec /opt/benchmark-venv/bin/python -I -B /tests/grade.py
    tests/grade.py            thin entry point -> suite.core.grading.main
    tests/task_config.json    cases, per-case time limit, grader module, threads, deadlines
    tests/lib/                vendored suite/core, the family package and pcnsl metric modules
    tests/hidden/<case>/input, tests/hidden/<case>/reference
    tests/specialist/<case>/  specialist outputs for the hidden cases + runtime.json
    solution/solve.sh         oracle: copies solution/pipeline to /workspace/output/pipeline
    solution/pipeline/        oracle pipeline (built from agent-visible material only)

Isolation: environment/ is the only Docker build context and instruction.md is the only other
agent-visible file. check_no_leak() fails the export if any hidden reference, hidden input or
specialist output (by byte hash, by gunzipped-content hash, or by its hex digest appearing in
a file) is present in environment/, instruction.md or solution/.
"""
import dataclasses
import gzip
import hashlib
import importlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import runner

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV = '/opt/benchmark-venv'
BASE_IMAGE = 'python:3.12-slim'
DEFAULT_PACKAGES = ('numpy==2.1.3', 'scipy==1.14.1', 'nibabel==5.3.2', 'SimpleITK==2.4.0',
                    'scikit-image==0.24.0', 'scikit-learn==1.5.2')
# The verifier (tests/lib: suite.core + pcnsl metrics) needs only these; every image must have them.
VERIFIER_PACKAGES = ('numpy', 'scipy')
IMPORT_NAMES = {'scikit-image': 'skimage', 'scikit-learn': 'sklearn', 'pillow': 'PIL',
                'totalsegmentator': 'totalsegmentator', 'simpleitk': 'SimpleITK'}
TASK_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,62}')
HOST = re.compile(r'[a-z0-9][a-z0-9.-]*')
ARTIFACT_LIMIT_TEXT = '512 MiB compressed and 20 000 files'
CORE_FILES = ('__init__.py', 'metrics.py', 'geometry.py', 'runner.py', 'reward.py', 'grading.py')
PCNSL_FILES = ('imaging_eval.py', 'prediction_eval.py')


class ExportLeakError(RuntimeError):
    """A hidden reference/input/specialist file is reachable from the agent's side of the task."""


class ExportError(RuntimeError):
    """The export would be wrong (e.g. specialist outputs missing, so the specialist would score 0)."""


@dataclass
class FamilySpec:
    family: str                         # family name, e.g. 'toy'
    task_id: str                        # lowercase letters, digits, hyphens
    title: str
    readme_md: str                      # clinical task description (agent-facing)
    output_format_md: str               # documentation of the files run.sh must write
    grader_module: str                  # e.g. 'suite.families.toy.grader'
    public_dir: Path                    # -> environment/data/ (dev cases, references if any, docs)
    hidden_cases: dict                  # case id -> dir holding input/ and reference/
    oracle_pipeline_dir: Path           # -> solution/pipeline/
    specialist_pipeline_dir: Path | None = None   # run at export time on hidden inputs, or:
    specialist_results_dir: Path | None = None    # precomputed: <case>/... + runtime.json
    specialist_name: str = 'specialist baseline'
    time_limit_seconds: float = 60.0    # per hidden case, enforced by the grader
    cpus: int = 2
    memory_mb: int = 4096
    gpus: int = 0
    gpu_types: tuple = ()
    agent_timeout_sec: float = 2700.0
    allowed_hosts: tuple = ('api.anthropic.com',)
    packages: tuple = DEFAULT_PACKAGES  # pip pins for this family's image (see family_packages())
    pip_extra_index_url: str | None = None   # e.g. the CPU torch wheel index
    threads: int | None = None          # thread caps for the pipeline (defaults to cpus)
    memory_limit_bytes: int | None = None
    metadata: dict = field(default_factory=dict)
    # Grading unit. 'per_case': run.sh once per hidden case, rewards are means over cases.
    # 'cohort': hidden_cases holds ONE folder with the whole hidden set; run.sh runs once on it;
    # the family grader defines grade_cohort() and the reward follows the cohort rule (grading.py).
    grading: str = 'per_case'
    cohort_size: int | None = None      # records in the cohort (instruction text only)
    hard_kill_seconds: float | None = None  # cohort: kill later than the limit (late = not within_time)
    # Bookkeeping for the suite manifest and the hosted oracle check (written to task.toml metadata).
    tier: str = 'build'
    expected_solution_reward: float | None = None   # reward the shipped solution/ must get
    scored: bool = True                 # False: kept as a worked example, excluded from scoring


def family_packages(family):
    """Image pins declared by a family in suite/families/<family>/image_requirements.txt.

    Lines are pip requirement pins; '# extra-index-url: URL' declares an extra wheel index.
    Returns (pins tuple, extra index URL or None).
    """
    path = REPO_ROOT / 'suite' / 'families' / family / 'image_requirements.txt'
    pins, index = [], None
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.lower().startswith('# extra-index-url:'):
            index = line.split(':', 1)[1].strip()
        elif line and not line.startswith('#'):
            pins.append(line)
    return tuple(pins), index


def _import_name(pin):
    name = re.split(r'[=<>!~\[ ;]', pin, maxsplit=1)[0].strip()
    return IMPORT_NAMES.get(name.lower(), name.replace('-', '_'))


# ---------------------------------------------------------------------------- file builders


VENV_PYTHON = f'{VENV}/bin/python3'
PROFILE_SCRIPT = '/etc/profile.d/00-benchmark-venv.sh'
# Shells the agent harness may use; every one must resolve python3 to the venv (checked at build time).
# 'env -i ... -l' is a login shell that inherits no ENV from the image, i.e. only /etc/profile applies.
PATH_CHECK_SHELLS = ('bash -lc', 'bash -c', 'sh -lc', 'sh -c', 'env -i bash -lc', 'env -i sh -lc')


def profile_snippet(venv=VENV):
    """One-line /etc/profile.d script: puts the benchmark venv first on PATH in login shells.

    Debian's /etc/profile (python:3.12-slim) resets PATH for login shells (`bash -lc`, as the registry
    Claude Code agent runs), which drops the Dockerfile's ENV PATH; it then sources /etc/profile.d/*.sh.
    """
    return f'export PATH="{venv}/bin:$PATH" VIRTUAL_ENV={venv}'


def python_env_rule(packages):
    """Agent-facing sentence naming the interpreter by absolute path (instruction.md, both modes)."""
    return (f'Use only the image\'s Python environment, `{VENV_PYTHON}`\n'
            f'  (packages: {", ".join(packages)}). Call it by this absolute path in `run.sh`; it is also\n'
            f'  first on `PATH` (login and non-login shells) here and in the grader. Use only that interpreter\n'
            f'  and files inside')


def dockerfile(spec):
    pins = [p for p in spec.packages if not p.startswith('-')]
    if len(pins) != len(spec.packages):
        raise ValueError('pip options do not belong in packages; use FamilySpec.pip_extra_index_url')
    missing = [m for m in VERIFIER_PACKAGES if m not in {_import_name(p) for p in pins}]
    if missing:
        raise ValueError(f'image packages must include the verifier dependencies {missing}')
    # One pip line (the local pilot runner reads the pins from it); the index is a single
    # '--opt=value' token so the pin list stays clean.
    index = f' --extra-index-url={spec.pip_extra_index_url}' if spec.pip_extra_index_url else ''
    modules = ', '.join(dict.fromkeys(_import_name(p) for p in pins))
    threads = spec.threads or spec.cpus
    return '\n'.join([
        f'FROM {BASE_IMAGE}',
        '# Every Python dependency lives in one virtualenv inside the image; nothing in system Python.',
        f'# Packages are this family\'s own declaration ({spec.family}).',
        f'RUN python3 -m venv {VENV} && {VENV}/bin/python -m pip install --no-cache-dir {" ".join(pins)}{index}',
        f'ENV PATH={VENV}/bin:$PATH VIRTUAL_ENV={VENV} PYTHONDONTWRITEBYTECODE=1 PIP_NO_INDEX=1 \\',
        f'    PIP_DISABLE_PIP_VERSION_CHECK=1 OMP_NUM_THREADS={threads} OPENBLAS_NUM_THREADS={threads} \\',
        f'    MKL_NUM_THREADS={threads} ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS={threads}',
        '# Fail the build (closed) if the declared runtime is incomplete.',
        f'RUN python3 -c "import sys; assert sys.prefix == \'{VENV}\', sys.prefix; import {modules}"',
        '# Login shells source /etc/profile, which resets PATH on Debian; put the venv first there too,',
        '# then fail the build unless every shell (login or not, with or without the image ENV) finds it.',
        f"RUN echo '{profile_snippet()}' > {PROFILE_SCRIPT} && chmod 0644 {PROFILE_SCRIPT}",
        'RUN for s in ' + ' '.join(f"'{s}'" for s in PATH_CHECK_SHELLS) + '; do '
        'p="$($s \'command -v python3\')"; '
        f'[ "$p" = {VENV_PYTHON} ] || {{ echo "$s resolves python3 to $p" >&2; exit 1; }}; done',
        'WORKDIR /workspace',
        'COPY data/ /workspace/data/',
        'RUN chmod -R a-w /workspace/data && mkdir -p /workspace/output && chmod 0777 /workspace/output',
    ]) + '\n'


def _hard_limit(spec):
    return max(spec.time_limit_seconds, spec.hard_kill_seconds or 0.0)


def verifier_timeout(spec, n_hidden):
    # Every case may use its full limit (or hard kill); plus copying, grading and the specialist pass.
    return float(int(n_hidden * _hard_limit(spec) * 1.5 + 300))


def task_toml(spec, n_hidden):
    for host in spec.allowed_hosts:
        if not HOST.fullmatch(host):
            raise ValueError(f'invalid allowed host {host!r}')
    if spec.allowed_hosts:
        agent_net = ['network_mode = "allowlist"', 'allowed_hosts = ' + json.dumps(list(spec.allowed_hosts))]
    else:
        agent_net = ['network_mode = "no-network"']
    gpu = []
    if spec.gpus:
        if not spec.gpu_types:
            raise ValueError('gpu_types is required when gpus > 0 (Modal)')
        gpu = [f'gpus = {int(spec.gpus)}', 'gpu_types = ' + json.dumps(list(spec.gpu_types))]
    meta = {'category': 'medical-imaging', 'family': spec.family, 'suite': 'vals-healthcare-suite',
            'tier': spec.tier, 'grading': spec.grading, 'scored': bool(spec.scored),
            'runtime_budget_sec_per_case': spec.time_limit_seconds, **spec.metadata}
    if spec.expected_solution_reward is not None:
        meta['oracle_expected_reward'] = round(float(spec.expected_solution_reward), 4)
    meta_lines = [f'{k} = {json.dumps(v)}' for k, v in meta.items()]
    return '\n'.join([
        'schema_version = "1.4"',
        '# Only the agent output folder is carried into the separate verifier sandbox.',
        'artifacts = [{ source = "/workspace/output", exclude = ["*.tmp", "__pycache__"] }]',
        '', '[metadata]', *meta_lines,
        '', '[agent]', f'timeout_sec = {float(spec.agent_timeout_sec)}', *agent_net,
        '', '[verifier]', f'timeout_sec = {verifier_timeout(spec, n_hidden)}',
        '# Hidden references in tests/ reach only a fresh verifier sandbox.',
        'environment_mode = "separate"', 'network_mode = "no-network"',
        '', '[verifier.environment]', '# Fixed, explicit timing machine (same image as the agent).',
        f'cpus = {int(spec.cpus)}', f'memory_mb = {int(spec.memory_mb)}', *gpu,
        '', '[environment]', f'cpus = {int(spec.cpus)}', f'memory_mb = {int(spec.memory_mb)}', *gpu,
        'storage_mb = 20480', 'workdir = "/workspace"', 'build_timeout_sec = 1500.0',
        'network_mode = "no-network"',
        'env = { CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1", PIP_NO_INDEX = "1" }',
    ]) + '\n'


def instruction(spec, n_hidden):
    if spec.grading == 'cohort':
        return _instruction_cohort(spec)
    hosts = ', '.join(spec.allowed_hosts) or 'none'
    return f"""# {spec.title}

{spec.readme_md.strip()}

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs per case

{spec.output_format_md.strip()}

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **one case**: it reads `INPUT_DIR` (laid out exactly like a development case's
input folder) and writes the required files into `OUTPUT_DIR`. After you finish, a separate
grader sandbox runs your pipeline on {n_hidden} hidden cases you have never seen and scores
the outputs against hidden references. Rules:

- **Time limit: {spec.time_limit_seconds:g} seconds of wall-clock time per case**, measured by the
  grader on {spec.cpus} CPU(s) and {spec.memory_mb} MB RAM. A case that exceeds it is killed and fails.
  Timing you report yourself is ignored.
- **Offline.** The grader has no network. {python_env_rule(spec.packages)}
  `/workspace/output/pipeline/`. Nothing else you create or install in this sandbox exists there.
- The pipeline runs as an unprivileged user with a fresh, empty `HOME`; write only to `OUTPUT_DIR`
  and `$TMPDIR`.
- Only `/workspace/output/` is carried to the grader; it must stay under {ARTIFACT_LIMIT_TEXT}.
  Optional diagnostics on development cases may go in `/workspace/output/visible_predictions/`;
  they are not scored.
- Network access in this sandbox is limited to the model API ({hosts}).

## How you are scored

Per hidden case the grader checks that the outputs exist, pass format and geometry checks, were
produced inside the time limit, and meet the clinical threshold stated above. The headline score
is the fraction of hidden cases meeting the clinical threshold, and it is 0 unless every hidden
case produced valid outputs inside the time limit. Your results are also compared with a
{spec.specialist_name} on the same hidden cases.
"""


def _instruction_cohort(spec):
    hosts = ', '.join(spec.allowed_hosts) or 'none'
    size = f'{spec.cohort_size:,} ' if spec.cohort_size else ''
    late = ''
    if spec.hard_kill_seconds and spec.hard_kill_seconds > spec.time_limit_seconds:
        late = (f' A run that finishes after the limit but before {spec.hard_kill_seconds:g} s is graded but does'
                f' not count as on time; at {spec.hard_kill_seconds:g} s it is killed.')
    return f"""# {spec.title}

{spec.readme_md.strip()}

## Data

Public material is in `/workspace/data/` (read-only). Start with `/workspace/data/README.md`.

## Required outputs

{spec.output_format_md.strip()}

## What you must leave behind: a pipeline

Write a self-contained pipeline to `/workspace/output/pipeline/` with an entry point

    bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR

that processes **the whole hidden set in one call**: `INPUT_DIR` holds all {size}hidden records,
laid out like the development input folder, and the pipeline writes the required files into
`OUTPUT_DIR`. After you finish, a separate grader sandbox runs your pipeline once on that hidden
set, which you have never seen, and scores the outputs against hidden references. Rules:

- **Time limit: {spec.time_limit_seconds:g} seconds of wall-clock time for the whole hidden set**, measured by
  the grader on {spec.cpus} CPU(s) and {spec.memory_mb} MB RAM.{late} Timing you report yourself is ignored.
- **Offline.** The grader has no network. {python_env_rule(spec.packages)}
  `/workspace/output/pipeline/`. Nothing else you create or install in this sandbox exists there.
- The pipeline runs as an unprivileged user with a fresh, empty `HOME`; write only to `OUTPUT_DIR`
  and `$TMPDIR`.
- Only `/workspace/output/` is carried to the grader; it must stay under {ARTIFACT_LIMIT_TEXT}.
  Optional diagnostics on development cases may go in `/workspace/output/visible_predictions/`;
  they are not scored.
- Network access in this sandbox is limited to the model API ({hosts}).

## How you are scored

The grader checks that the outputs exist, pass the format checks and were produced inside the
time limit, then computes the cohort metrics on the hidden set. The clinical gate has several
parts (stated above). The headline score is 1 only if the outputs are valid, on time, and meet
**every** part of the gate; otherwise it is 0. Meeting some parts earns no partial credit. Your
results are also compared with a {spec.specialist_name} on the same hidden set.
"""


GRADE_PY = '''"""Generated verifier entry point; the procedure lives in suite/core/grading.py (vendored in lib/)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from suite.core.grading import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
'''

TEST_SH = f'#!/bin/bash\nset -u\nexec {VENV}/bin/python -I -B /tests/grade.py\n'
SOLVE_SH = ('#!/bin/bash\n# Oracle: install the reference pipeline built only from agent-visible material.\n'
            'set -eu\nmkdir -p /workspace/output\nrm -rf /workspace/output/pipeline\n'
            'cp -r /solution/pipeline /workspace/output/pipeline\nchmod -R a+rX /workspace/output/pipeline\n')


# ---------------------------------------------------------------------------- helpers


def _copytree(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def vendor_library(spec, lib_dir):
    """Copy the exact modules the verifier imports into tests/lib/ (same package names as the repo)."""
    lib = Path(lib_dir)
    (lib / 'suite' / 'core').mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / 'suite' / '__init__.py', lib / 'suite' / '__init__.py')
    for name in CORE_FILES:
        shutil.copyfile(REPO_ROOT / 'suite' / 'core' / name, lib / 'suite' / 'core' / name)
    (lib / 'pcnsl').mkdir()
    for name in PCNSL_FILES:
        shutil.copyfile(REPO_ROOT / 'pcnsl' / name, lib / 'pcnsl' / name)
    parts = spec.grader_module.split('.')
    if parts[:2] != ['suite', 'families'] or len(parts) != 4:
        raise ValueError('grader_module must be suite.families.<family>.<module>')
    fam_src = REPO_ROOT / 'suite' / 'families' / parts[2]
    fam_dst = lib / 'suite' / 'families' / parts[2]
    fam_dst.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / 'suite' / 'families' / '__init__.py', lib / 'suite' / 'families' / '__init__.py')
    for py in sorted(fam_src.glob('*.py')):          # family package modules only, non-recursive
        shutil.copyfile(py, fam_dst / py.name)


def _resolved(spec):
    """Absolute copies of every path in the spec. The specialist pipeline runs with cwd = a fresh
    home directory, so a relative output path would land there and leave tests/specialist/ empty."""
    def r(p):
        return None if p is None else Path(p).expanduser().resolve()
    return dataclasses.replace(
        spec, public_dir=r(spec.public_dir), oracle_pipeline_dir=r(spec.oracle_pipeline_dir),
        specialist_pipeline_dir=r(spec.specialist_pipeline_dir), specialist_results_dir=r(spec.specialist_results_dir),
        hidden_cases={case: r(d) for case, d in spec.hidden_cases.items()})


def check_specialist_outputs(spec, specialist_dir, cases):
    """Fail loudly unless every hidden case has the family's required specialist outputs and a runtime."""
    specialist_dir = Path(specialist_dir)
    family = importlib.import_module(spec.grader_module)
    required = tuple(getattr(family, 'REQUIRED_OUTPUTS', ()))
    problems = []
    for case in cases:
        d = specialist_dir / case
        if not d.is_dir() or not any(d.iterdir()):
            problems.append(f'{case}: no specialist outputs')
            continue
        problems += [f'{case}: specialist output {name} missing' for name in required
                     if not (d / name).is_file() or (d / name).stat().st_size == 0]
    runtime = specialist_dir / 'runtime.json'
    seconds = json.loads(runtime.read_text()).get('wall_seconds', {}) if runtime.is_file() else {}
    problems += [f'{case}: specialist runtime missing from runtime.json' for case in cases if case not in seconds]
    if problems:
        raise ExportError('specialist outputs incomplete (the specialist would score 0): '
                          + '; '.join(problems[:20]) + (f' ... ({len(problems)} problems)' if len(problems) > 20 else ''))


def run_specialist(spec, out_dir):
    """Run the specialist pipeline on every hidden input with the suite runner; record wall time."""
    out_dir = Path(out_dir).resolve()
    seconds = {}
    with tempfile.TemporaryDirectory() as tmp:
        for case, case_dir in sorted(spec.hidden_cases.items()):
            dest = out_dir / case
            dest.mkdir(parents=True)
            result = runner.run_pipeline(spec.specialist_pipeline_dir, Path(case_dir) / 'input', dest,
                                         max(spec.time_limit_seconds, 600), home_dir=Path(tmp) / case,
                                         path=os.environ.get('SUITE_PIPELINE_PATH', runner.DEFAULT_PATH),
                                         threads=spec.threads or spec.cpus)
            if result.timed_out or result.exit_code != 0:
                raise RuntimeError(f'specialist failed on {case}: {result}')
            seconds[case] = result.wall_seconds
    (out_dir / 'runtime.json').write_text(json.dumps(
        {'name': spec.specialist_name, 'wall_seconds': seconds,
         'measured_on': 'export host via suite.core.runner (not the verifier machine)'}, indent=2) + '\n')


def _digests(path):
    """{sha256 of bytes, sha256 of gunzipped bytes for .gz} for one file."""
    data = Path(path).read_bytes()
    out = {hashlib.sha256(data).hexdigest()}
    if data[:2] == b'\x1f\x8b':
        try:
            out.add(hashlib.sha256(gzip.decompress(data)).hexdigest())
        except (OSError, EOFError):
            pass
    return out, data


def _files(root):
    root = Path(root)
    return [p for p in sorted(root.rglob('*')) if p.is_file()] if root.exists() else []


def check_no_leak(task_dir):
    """Raise ExportLeakError if protected verifier-only content is visible to the agent or oracle.

    Protected: tests/hidden/*/reference/**, tests/hidden/*/input/** and tests/specialist/**
    (non-empty files; runtime.json excluded as it holds only timings).
    Agent side: environment/** (the Docker build context), instruction.md, and solution/**.
    A leak is a byte-identical file, a file whose gunzipped content matches, or a file
    containing a protected file's SHA-256 hex digest.
    """
    task = Path(task_dir)
    protected = {}
    for sub in ('hidden', 'specialist'):
        for p in _files(task / 'tests' / sub):
            if p.name == 'runtime.json' or p.stat().st_size == 0:
                continue
            digests, _ = _digests(p)
            for d in digests:
                protected[d] = p.relative_to(task).as_posix()
    exposed = _files(task / 'environment') + _files(task / 'solution') + [task / 'instruction.md']
    leaks = []
    for p in exposed:
        if not p.is_file() or p.stat().st_size == 0:
            continue
        digests, data = _digests(p)
        rel = p.relative_to(task).as_posix()
        for d in digests & protected.keys():
            leaks.append(f'{rel} has the same content as {protected[d]}')
        text = data.lower()
        for d, src in protected.items():
            if d.encode() in text:
                leaks.append(f'{rel} contains the SHA-256 of {src}')
    if leaks:
        raise ExportLeakError('hidden material reachable by the agent: ' + '; '.join(sorted(set(leaks))))


def task_manifest(task_dir):
    """SHA-256 of every file tagged with its audience (agent / verifier / oracle / platform)."""
    task = Path(task_dir)
    rows = {}
    for p in _files(task):
        rel = p.relative_to(task).as_posix()
        audience = ('agent' if rel == 'instruction.md' or rel.startswith('environment/')
                    else 'verifier' if rel.startswith('tests/') else 'oracle' if rel.startswith('solution/')
                    else 'platform')
        rows[rel] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'audience': audience}
    return rows


# ---------------------------------------------------------------------------- main entry


def export_task(spec, out_dir):
    """Write <out_dir>/<task_id>/ atomically (staging dir + rename); refuse to overwrite."""
    if not TASK_ID.fullmatch(spec.task_id):
        raise ValueError('task_id must be lowercase letters, digits and hyphens')
    if not spec.hidden_cases:
        raise ValueError('need at least one hidden case')
    if (spec.specialist_pipeline_dir is None) == (spec.specialist_results_dir is None):
        raise ValueError('give exactly one of specialist_pipeline_dir or specialist_results_dir')
    if not (Path(spec.oracle_pipeline_dir) / 'run.sh').is_file():
        raise ValueError('oracle pipeline needs run.sh')
    if spec.grading not in ('per_case', 'cohort'):
        raise ValueError(f'unknown grading mode {spec.grading!r}')
    if spec.grading == 'cohort' and len(spec.hidden_cases) != 1:
        raise ValueError('cohort grading needs exactly one hidden folder holding the whole hidden set')
    spec = _resolved(spec)
    out_dir = Path(out_dir).expanduser().resolve()
    final = out_dir / spec.task_id
    if os.path.lexists(final):
        raise FileExistsError(f'{final} already exists; refusing to overwrite')
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / f'.{spec.task_id}.partial-{os.getpid()}'
    staging.mkdir()
    try:
        cases = sorted(spec.hidden_cases)
        n = len(cases)
        _copytree(spec.public_dir, staging / 'environment' / 'data')
        for case in cases:
            src = Path(spec.hidden_cases[case])
            for part in ('input', 'reference'):
                _copytree(src / part, staging / 'tests' / 'hidden' / case / part)
        if spec.specialist_results_dir is not None:
            _copytree(spec.specialist_results_dir, staging / 'tests' / 'specialist')
        else:
            run_specialist(spec, staging / 'tests' / 'specialist')
        check_specialist_outputs(spec, staging / 'tests' / 'specialist', cases)
        vendor_library(spec, staging / 'tests' / 'lib')
        _copytree(spec.oracle_pipeline_dir, staging / 'solution' / 'pipeline')
        config = {'schema': 'suite-task-config/1', 'family': spec.family, 'task_id': spec.task_id,
                  'grader_module': spec.grader_module, 'cases': cases, 'grading': spec.grading,
                  'time_limit_seconds': spec.time_limit_seconds, 'hard_kill_seconds': _hard_limit(spec),
                  'threads': spec.threads or spec.cpus,
                  'memory_bytes': spec.memory_limit_bytes, 'pipeline_path': runner.DEFAULT_PATH,
                  'grading_deadline_seconds': verifier_timeout(spec, n) - 120}
        files = {
            'task.toml': task_toml(spec, n),
            'instruction.md': instruction(spec, n),
            'environment/Dockerfile': dockerfile(spec),
            'tests/test.sh': TEST_SH,
            'tests/grade.py': GRADE_PY,
            'tests/task_config.json': json.dumps(config, indent=2) + '\n',
            'solution/solve.sh': SOLVE_SH,
        }
        for name, content in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        for name in ('tests/test.sh', 'solution/solve.sh'):
            (staging / name).chmod(0o755)
        check_no_leak(staging)
        if os.path.lexists(final):
            raise FileExistsError(f'{final} appeared during export; refusing to overwrite')
        os.rename(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final
