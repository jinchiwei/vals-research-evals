"""Family spec for the suite exporter (suite/core/export, when it lands) -> one Harbor task.

Audience of every file is explicit: 'agent' files go into environment/ (the agent image build
context); 'verifier' files go into tests/ only (separate verifier sandbox, root-only, never in the
agent image); nothing hidden goes into solution/.
"""
STAGED_DIR = '/home/jkwei/data/vals-suite/reg_resect/staged'

SPEC = {
    'family': 'reg_resect',
    'task_id': 'reg-resect-build-0001',
    'tier': 'build',
    'title': 'Pre-operative MRI to intra-operative ultrasound registration for brain shift (RESECT)',
    'dataset': 'RESECT v1 (NIRD doi:10.11582/2017.00004), CC BY 4.0',
    'grader_module': 'suite.families.reg_resect.grader',
    # Clinical and runtime limits (fixed before any agent run; see docs/research/suite/reg_resect.md)
    'clinical_threshold_mm': 2.0,
    'time_limit_seconds_per_case': 120.0,
    'cpus': 4,
    'memory_mb': 16384,
    'pipeline_memory_bytes': None,           # RLIMIT_AS off: SimpleITK/NumPy thread pools reserve large VA
    'grading_deadline_seconds': 6 * 120 * 2 + 300,
    'agent_timeout_sec': 2700.0,
    'verifier_timeout_sec': 6 * 120 * 2 + 600,
    # Inputs/outputs contract
    'input_files': ['mri_t1.nii.gz', 'mri_flair.nii.gz', 'us.nii.gz', 'landmarks_mri.csv'],
    'reference_files': ['landmarks_us.csv'],
    'required_outputs': ['landmarks_us.csv'],
    'optional_outputs': ['displacement_ras.nii.gz'],
    # Where things go
    'agent_files': {                          # destination in the agent image -> source
        '/workspace/README.md': 'suite/families/reg_resect/README_agent.md',
        '/workspace/data/dev/': f'{STAGED_DIR}/dev/',            # 4 cases, inputs + landmarks_us.csv
        '/workspace/data/LICENSE-DATA.md': 'suite/families/reg_resect/LICENSE-DATA.md',
    },
    'verifier_files': {                       # destination under tests/ -> source
        'hidden/': f'{STAGED_DIR}/hidden/',   # 6 cases: input/ (staged to the pipeline) + reference/ (never)
        'specialist/': 'WORK/tests/specialist/',  # baseline outputs + runtime.json from build.py
        'task_config.json': 'WORK/tests/task_config.json',
        'lib/suite/core/': 'suite/core/',
        'lib/suite/families/reg_resect/': ['__init__.py', 'grader.py', 'landmarks.py'],
    },
    'solution': 'specialist pipeline (pipelines.write_pipeline("specialist")); uses no hidden data',
    'artifacts': [{'source': '/workspace/output', 'exclude': ['*.tmp', '__pycache__']}],
    'pip': ['numpy==2.1.3', 'scipy==1.14.1', 'nibabel==5.3.2', 'SimpleITK==2.4.0', 'scikit-image==0.24.0',
            'scikit-learn==1.5.2'],
    # Image size estimate (measured file sizes; base + wheels are estimates, no Docker on teal)
    'image_size_estimate_mb': {'python:3.12-slim (estimate)': 130,
                               'venv: pinned wheels as installed on teal (measured, SimpleITK alone 263)': 664,
                               'dev data, 4 cases (measured)': 202, 'total': 1000},
    'verifier_upload_estimate_mb': {'hidden (6 cases)': 285, 'specialist outputs': 0.1},
    # Specialist configuration frozen after development-case tuning (see reg_resect.md)
    'specialist_config': {'spacing': 1.0, 'pre_sigma_mri': 1.0, 'search_mm': 16.0},
}


def _split_readme(text):
    """README_agent.md -> (clinical part for instruction.md, output-format part)."""
    head, rest = text.split('## What you must deliver', 1)
    body = head.split('\n', 1)[1].strip()               # drop the H1 (the exporter adds the title)
    fmt = rest.split('Rules for the pipeline:', 1)[0].strip()
    return body, fmt


def build_spec(work_dir, staged_dir=STAGED_DIR, specialist_results_dir=None):
    """FamilySpec for suite.core.export. specialist_results_dir: a build.py tests/specialist folder
    (precomputed outputs + runtime.json); if None the exporter runs the specialist pipeline itself."""
    import shutil
    from pathlib import Path

    from suite.core.export import FamilySpec

    from . import pipelines
    here = Path(__file__).resolve().parent
    work, staged = Path(work_dir), Path(staged_dir)
    public = work / 'public'
    for case in sorted(p.name for p in (staged / 'dev').iterdir()):
        src, dst = staged / 'dev' / case, public / 'dev' / case
        (dst / 'input').mkdir(parents=True)
        (dst / 'reference').mkdir(parents=True)
        for name in SPEC['input_files']:
            shutil.copyfile(src / name, dst / 'input' / name)
        shutil.copyfile(src / 'landmarks_us.csv', dst / 'reference' / 'landmarks_us.csv')
    text = (here / 'README_agent.md').read_text()
    (public / 'README.md').write_text(text)
    shutil.copyfile(here / 'LICENSE-DATA.md', public / 'LICENSE-DATA.md')
    readme, fmt = _split_readme(text)
    hidden = {p.name: p for p in sorted((staged / 'hidden').iterdir())}
    # Harbor oracle = the specialist pipeline (built from agent-visible material only; scores like the
    # specialist, not 1.0). The 1.0 lookup oracle in pipelines.py embeds hidden references: never export it.
    solution = pipelines.write_pipeline('specialist', work / 'pipelines' / 'solution', config=SPEC['specialist_config'])
    kw = {}
    if specialist_results_dir is not None:
        kw['specialist_results_dir'] = Path(specialist_results_dir)
    else:
        kw['specialist_pipeline_dir'] = pipelines.write_pipeline('specialist', work / 'pipelines' / 'specialist',
                                                                 config=SPEC['specialist_config'])
    return FamilySpec(family=SPEC['family'], task_id=SPEC['task_id'], title=SPEC['title'], readme_md=readme,
                      output_format_md=fmt, grader_module=SPEC['grader_module'], public_dir=public,
                      hidden_cases=hidden, oracle_pipeline_dir=solution,
                      specialist_name='MIND-feature rigid registration (classical, CPU)',
                      time_limit_seconds=SPEC['time_limit_seconds_per_case'], cpus=SPEC['cpus'],
                      memory_mb=SPEC['memory_mb'], agent_timeout_sec=SPEC['agent_timeout_sec'], tier=SPEC['tier'],
                      # solution/ ships the specialist: 4 of 6 hidden cases within 2 mm (reg_resect.md).
                      expected_solution_reward=4 / 6, scored=True,
                      metadata={'dataset': SPEC['dataset'], 'clinical_threshold_mm': SPEC['clinical_threshold_mm'],
                                'tags': ['registration', 'mri', 'ultrasound', 'intra-operative']}, **kw)
