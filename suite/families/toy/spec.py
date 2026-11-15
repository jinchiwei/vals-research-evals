"""Build the toy family's FamilySpec (synthetic data generated into a work directory).

    from suite.families.toy.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec(work_dir), 'dist/suite-toy')

Development cases are seeds 1..n_dev, hidden cases seeds 101..; case IDs are random-looking
and unrelated between the public and hidden sets.
"""
import hashlib
import json
from pathlib import Path

from suite.core.export import FamilySpec

from . import data, grader, pipelines

README = f"""A synthetic phantom contains one bright sphere in a noisy 3D volume with anisotropic voxels
(spacing differs per case and the x axis is flipped). Segment the sphere and report its volume.

This is the suite's smoke task: it checks the plumbing (geometry, units, pipeline contract, timing),
not clinical skill. It contains no medical data.

Clinical threshold per case: {grader.CLINICAL_THRESHOLD}.
"""

OUTPUT_FORMAT = """Each case's `INPUT_DIR` contains `image.nii.gz` (float32, header spacing in mm).
`run.sh` must write into `OUTPUT_DIR`:

- `mask.nii.gz`: binary mask (0/1, integer type) on **exactly the input image grid**: same shape and the
  same affine (spacing, origin, orientation) as `image.nii.gz`, spatial units mm.
- `measurements.json`: `{"volume_ml": <number>}`, the sphere volume in **millilitres** (1 mL = 1000 mm^3).
"""


def _case_id(prefix, seed):
    return prefix + hashlib.sha256(f'toy-{seed}'.encode()).hexdigest()[:8]


def build_spec(work_dir, n_dev=2, n_hidden=3, time_limit_seconds=30.0, task_id='toy-sphere-volume-0001'):
    work = Path(work_dir)
    public = work / 'public'
    public.mkdir(parents=True)
    dev_ids = []
    for seed in range(1, n_dev + 1):
        cid = _case_id('dev-', seed)
        case_dir = public / 'dev' / cid
        data.write_case(data.make_case(seed), case_dir / 'input', case_dir / 'reference')
        dev_ids.append(cid)
    (public / 'README.md').write_text(
        README + '\n## Development cases\n\n'
        + '\n'.join(f'- `dev/{c}/input/image.nii.gz` with reference `dev/{c}/reference/mask.nii.gz` and '
                    f'`dev/{c}/reference/measurements.json`' for c in dev_ids)
        + '\n\n## Output format\n\n' + OUTPUT_FORMAT)
    (public / 'cases.json').write_text(json.dumps({'development_cases': dev_ids}, indent=2) + '\n')
    hidden = {}
    for i, seed in enumerate(range(101, 101 + n_hidden)):
        cid = _case_id('case-', seed)
        data.write_case(data.make_case(seed), work / 'hidden' / cid / 'input', work / 'hidden' / cid / 'reference')
        hidden[cid] = work / 'hidden' / cid
    oracle = pipelines.write_pipeline('oracle', work / 'pipelines' / 'oracle')
    specialist = pipelines.write_pipeline('specialist', work / 'pipelines' / 'specialist')
    return FamilySpec(family='toy', task_id=task_id, title='Toy smoke task: sphere segmentation and volume',
                      readme_md=README, output_format_md=OUTPUT_FORMAT, grader_module='suite.families.toy.grader',
                      public_dir=public, hidden_cases=hidden, oracle_pipeline_dir=oracle,
                      specialist_pipeline_dir=specialist, specialist_name='smoothed-threshold specialist',
                      time_limit_seconds=time_limit_seconds, cpus=2, memory_mb=4096,
                      expected_solution_reward=1.0, scored=False,
                      metadata={'dataset': 'synthetic', 'tags': ['smoke', 'synthetic']})
