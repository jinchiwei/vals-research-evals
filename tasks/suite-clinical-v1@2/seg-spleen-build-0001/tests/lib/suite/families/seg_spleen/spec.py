"""Build the seg_spleen FamilySpec (build tier) for suite.core.export, from family.json.

    from suite.families.seg_spleen.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec('/abs/work'), '/abs/dist/suite-tasks/seg_spleen')

Agent side (environment/data/): README.md (task/README.md, placeholders filled for the tier), dev/<case>/
{image,label}.nii.gz for the 8 development cases, dev/volumes.csv, the CC BY-SA licence and ATTRIBUTION.md.
Verifier side (tests/): hidden/<case>/input/image.nii.gz and hidden/<case>/reference/label.nii.gz for the 6
hidden cases; specialist/<case>/{mask.nii.gz,volume.json} = the stored TotalSegmentator outputs
(DATA_ROOT/specialist/ts_gpu_full_hidden, the run summarised in specialist/summary_hidden.json) with their
measured wall times. solution/pipeline = the classical reference (fitted on development cases only).

Only the build tier is built here. The toolbox tier (TotalSegmentator + weights in the image) is not:
see docs/research/suite/integration.md for what it would still need.
"""
import csv
import json
import shutil
from pathlib import Path

from suite.core.export import FamilySpec

HERE = Path(__file__).resolve().parent
FAMILY = json.loads((HERE / 'family.json').read_text())
DATA_ROOT = Path(FAMILY['data_root'])
SPECIALIST_RUN = 'ts_gpu_full_hidden'
TASK_IDS = {'build': 'seg-spleen-build-0001'}


def _fill(text, values):
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', str(value))
    if '{{' in text:
        raise ValueError('unfilled placeholder in task/README.md')
    return text


def _split_readme(text):
    """Full README -> (task description for instruction.md, output-format section)."""
    body = text.split('\n', 1)[1]                                 # the exporter adds the title
    head, rest = body.split('## What to deliver', 1)
    deliver, scoring = rest.split('## How it is scored', 1)
    fmt = deliver.split('Your pipeline must write:', 1)[1].split('Rules for the pipeline:', 1)[0]
    return head.strip() + '\n\n## How it is scored\n' + scoring, 'The pipeline must write:\n' + fmt.strip() + '\n'


def _volume_ml(label_path):
    import nibabel as nib
    import numpy as np
    img = nib.load(str(label_path))
    return float((np.asanyarray(img.dataobj) > 0).sum()) * abs(float(np.linalg.det(img.affine[:3, :3]))) / 1000.0


def build_spec(work_dir, tier='build', data_root=DATA_ROOT):
    if tier != 'build':
        raise NotImplementedError('only the build tier is exported (toolbox tier: see integration.md)')
    cfg = FAMILY['tiers'][tier]
    work, data = Path(work_dir), Path(data_root)
    staged = data / 'staged'
    readme = _fill((HERE / 'task' / 'README.md').read_text(), cfg['readme_fill'])

    public = work / 'public'
    rows = []
    for case_dir in sorted((staged / 'dev').iterdir()):
        dst = public / 'dev' / case_dir.name
        dst.mkdir(parents=True)
        for name in ('image.nii.gz', 'label.nii.gz'):
            shutil.copyfile(case_dir / name, dst / name)
        rows.append((case_dir.name, f'{_volume_ml(case_dir / "label.nii.gz"):.2f}'))
    if len(rows) != cfg['readme_fill']['N_DEV']:
        raise ValueError(f'expected {cfg["readme_fill"]["N_DEV"]} development cases, found {len(rows)}')
    with open(public / 'dev' / 'volumes.csv', 'w', newline='') as f:
        csv.writer(f).writerows([('case', 'spleen_volume_ml'), *rows])
    (public / 'README.md').write_text(readme)
    shutil.copyfile(data / FAMILY['source']['licence_file'], public / FAMILY['source']['licence_file'])
    (public / 'ATTRIBUTION.md').write_text('# Attribution\n\n' + FAMILY['source']['attribution'] + '\n\nSource: '
                                           + FAMILY['source']['dataset'] + ', ' + FAMILY['source']['url'] + '\n')

    hidden = {}
    for case_dir in sorted((staged / 'hidden').iterdir()):
        d = work / 'hidden' / case_dir.name
        (d / 'input').mkdir(parents=True)
        (d / 'reference').mkdir(parents=True)
        shutil.copyfile(case_dir / 'image.nii.gz', d / 'input' / 'image.nii.gz')
        shutil.copyfile(case_dir / 'label.nii.gz', d / 'reference' / 'label.nii.gz')
        hidden[case_dir.name] = d

    run = json.loads((data / 'specialist' / f'{SPECIALIST_RUN}.json').read_text())
    spec_dir = work / 'specialist'
    for case in hidden:
        shutil.copytree(data / 'specialist' / SPECIALIST_RUN / case, spec_dir / case)
    (spec_dir / 'runtime.json').write_text(json.dumps({
        'name': 'TotalSegmentator 2.18.0 (task total, --roi_subset spleen, full 1.5 mm model)',
        'wall_seconds': {c['case']: c['wall_sec'] for c in run['cases']},
        'measured_on': 'teal, RTX 3060 GPU for the masks (CPU 4-thread full-model median 32 s per case, '
                       'specialist/ts_cpu4_full_hidden.json); indicative only'}, indent=2) + '\n')

    pins = list(cfg['pip'])
    index = None
    if cfg.get('include_torch') and cfg.get('pip_extra_index'):
        pins += cfg['pip_extra_index']['packages']
        index = cfg['pip_extra_index']['url']
    toml = cfg['task_toml']
    text, fmt = _split_readme(readme)
    return FamilySpec(
        family='seg_spleen', task_id=TASK_IDS[tier], title=FAMILY['title'], readme_md=text, output_format_md=fmt,
        grader_module='suite.families.seg_spleen.grader', public_dir=public, hidden_cases=hidden,
        oracle_pipeline_dir=HERE / 'classical' / 'pipeline', specialist_results_dir=spec_dir,
        specialist_name='TotalSegmentator specialist (not trained on these cases)',
        time_limit_seconds=float(cfg['grading']['case_time_limit_sec']), cpus=toml['environment']['cpus'],
        memory_mb=toml['environment']['memory_mb'], agent_timeout_sec=toml['agent']['timeout_sec'],
        threads=cfg['grading']['threads'], packages=tuple(pins), pip_extra_index_url=index, tier=tier,
        # Shipped solution = classical reference: 0 of 6 hidden cases acceptable (mean Dice 0.409).
        expected_solution_reward=0.0, scored=True,
        metadata={'dataset': FAMILY['source']['dataset'] + ' (CC BY-SA 4.0)', 'n_dev': len(rows),
                  'n_hidden': len(hidden), 'tags': ['segmentation', 'volumetry', 'ct', 'spleen']})
