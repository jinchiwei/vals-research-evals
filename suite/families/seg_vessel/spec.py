"""Build the seg_vessel FamilySpec for suite.core.export (build tier).

    from suite.families.seg_vessel.spec import build_spec
    from suite.core.export import export_task
    export_task(build_spec('/abs/work'), '/abs/dist/suite-tasks-vessel-v1/seg_vessel')

Agent side (environment/data/): README.md (task/README.md filled), dev/<case>/{image.jpg,
label_1stHO.png, label_2ndHO.png} for the 20 development images, dev/cases.csv, the CC BY 4.0 licence
and ATTRIBUTION.md. Verifier side (tests/): hidden/<case>/input/image.jpg and
hidden/<case>/reference/{label.png (1stHO), bar.json (2nd observer's Dice and clDice)} for the 8
hidden images; specialist/<case>/mask.png = the stored U-Net outputs (DATA_ROOT/specialist/unet_hidden)
with grader-measured CPU wall times. solution/pipeline = the U-Net specialist itself (weights trained on
development images only), so the hosted oracle exercises CPU torch inference under the time limit.
Second-observer masks of hidden images are never exported.
"""
import csv
import json
import shutil
from pathlib import Path

from suite.core.export import DEFAULT_PACKAGES, FamilySpec

HERE = Path(__file__).resolve().parent
DATA_ROOT = Path('/home/jkwei/data/vals-suite/seg_vessel')
TASK_ID = 'seg-vessel-build-0001'
TIME_LIMIT_SEC = 60.0
CPUS, MEMORY_MB, AGENT_TIMEOUT_SEC = 4, 8192, 3600.0
TORCH_PIN, TORCH_INDEX = 'torch==2.15.0+cpu', 'https://download.pytorch.org/whl/cpu'
PACKAGES = DEFAULT_PACKAGES + ('pillow==11.0.0', 'pandas==2.2.3', TORCH_PIN)
SPECIALIST_RUN = 'unet_hidden'
LICENCE_FILE = 'LICENSE-CC-BY-4.0.txt'
ATTRIBUTION = """# Attribution

CHASE_DB1 retinal vessel reference dataset. Barman S, Hoppe A, Remagnino P, Fraz MM, Uyyanonvara B,
Rudnicka AR, Owen CG. Kingston University London, with St George's, University of London, 2012.
https://researchinnovation.kingston.ac.uk/en/datasets/chasedb1-retinal-vessel-reference-dataset-4/
Reference paper: Fraz MM et al. An ensemble classification-based approach applied to retinal blood
vessel segmentation. IEEE Trans Biomed Eng 2012;59(9):2538-2548. doi:10.1109/TBME.2012.2205687

Licence: Creative Commons Attribution 4.0 International (LICENSE-CC-BY-4.0.txt).

Modifications for this benchmark: a subset (20 of 28 images); files renamed to opaque case IDs;
image and label bytes otherwise unchanged; cases.csv added (child grouping and inter-observer agreement
computed by us).
"""


def _fill(text, values):
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', str(value))
    if '{{' in text:
        raise ValueError('unfilled placeholder in task/README.md')
    return text


def _split_readme(text):
    body = text.split('\n', 1)[1]
    head, rest = body.split('## What to deliver', 1)
    deliver, scoring = rest.split('## How it is scored', 1)
    scoring = scoring.split('## Licence', 1)[0]
    fmt = deliver.split('Your pipeline must write:', 1)[1].split('Rules for the pipeline:', 1)[0]
    return head.strip() + '\n\n## How it is scored\n' + scoring.rstrip() + '\n', \
        'The pipeline must write:\n' + fmt.strip() + '\n'


def readme(data_root=DATA_ROOT):
    data_root = Path(data_root)
    split = json.loads((data_root / 'split.json').read_text())
    agree = json.loads((data_root / 'observer_agreement.json').read_text())
    dev = [r for r in split['cases'] if r['group'] == 'dev']
    d2 = [agree[r['source']]['dice'] for r in dev]
    c2 = [agree[r['source']]['cldice'] for r in dev]
    values = {'N_DEV': len(dev), 'N_DEV_CHILDREN': len(split['dev_children']),
              'N_HIDDEN': len(split['cases']) - len(dev), 'N_HIDDEN_CHILDREN': len(split['hidden_children']),
              'LIMIT': int(TIME_LIMIT_SEC), 'CPUS': CPUS, 'MEM_GB': MEMORY_MB // 1024,
              'TORCH_LINE': ', and CPU-only PyTorch with no pretrained weights',
              'DICE2_MIN': f'{min(d2):.3f}', 'DICE2_MAX': f'{max(d2):.3f}', 'DICE2_MEAN': f'{sum(d2) / len(d2):.3f}',
              'CL2_MIN': f'{min(c2):.3f}', 'CL2_MAX': f'{max(c2):.3f}', 'CL2_MEAN': f'{sum(c2) / len(c2):.3f}'}
    return _fill((HERE / 'task' / 'README.md').read_text(), values), split, agree


def build_spec(work_dir, data_root=DATA_ROOT, expected_solution_reward=None):
    work, data = Path(work_dir).resolve(), Path(data_root)
    text, split, agree = readme(data)
    staged = data / 'staged'
    public = work / 'public'
    rows = []
    for r in split['cases']:
        if r['group'] != 'dev':
            continue
        dst = public / 'dev' / r['case']
        dst.mkdir(parents=True)
        for name in ('image.jpg', 'label_1stHO.png', 'label_2ndHO.png'):
            shutil.copyfile(staged / 'dev' / r['case'] / name, dst / name)
        a = agree[r['source']]
        rows.append((r['case'], r['child_label'], r['eye'], f"{a['dice']:.4f}", f"{a['cldice']:.4f}"))
    with open(public / 'dev' / 'cases.csv', 'w', newline='') as f:
        csv.writer(f).writerows([('case', 'child', 'eye', 'dice_2ndHO', 'cldice_2ndHO'), *rows])
    (public / 'README.md').write_text(text)
    shutil.copyfile(data / LICENCE_FILE, public / LICENCE_FILE)
    (public / 'ATTRIBUTION.md').write_text(ATTRIBUTION)

    hidden = {}
    for case_dir in sorted((staged / 'hidden').iterdir()):
        d = work / 'hidden' / case_dir.name
        shutil.copytree(case_dir, d)
        hidden[case_dir.name] = d

    run = json.loads((data / 'specialist' / f'{SPECIALIST_RUN}.json').read_text())
    spec_dir = work / 'specialist'
    for case in hidden:
        (spec_dir / case).mkdir(parents=True)
        shutil.copyfile(data / 'specialist' / SPECIALIST_RUN / case / 'mask.png', spec_dir / case / 'mask.png')
    (spec_dir / 'runtime.json').write_text(json.dumps({
        'name': 'small U-Net (trained on the 20 development images), CPU inference',
        'wall_seconds': {c['case']: c['wall_seconds'] for c in run['cases']},
        'measured_on': run['measured_on']}, indent=2) + '\n')
    if expected_solution_reward is None:
        expected_solution_reward = run['clinically_acceptable']
    task_text, fmt = _split_readme(text)
    return FamilySpec(
        family='seg_vessel', task_id=TASK_ID,
        title='Retinal vessel segmentation from fundus photographs (CHASE_DB1)',
        readme_md=task_text, output_format_md=fmt, grader_module='suite.families.seg_vessel.grader',
        public_dir=public, hidden_cases=hidden, oracle_pipeline_dir=HERE / 'specialist' / 'pipeline',
        specialist_results_dir=spec_dir,
        specialist_name='small U-Net specialist trained on the development images',
        time_limit_seconds=TIME_LIMIT_SEC, cpus=CPUS, memory_mb=MEMORY_MB, agent_timeout_sec=AGENT_TIMEOUT_SEC,
        threads=CPUS, packages=PACKAGES, pip_extra_index_url=TORCH_INDEX, tier='build',
        expected_solution_reward=expected_solution_reward, scored=True,
        metadata={'dataset': 'CHASE_DB1 (Kingston University, CC BY 4.0)', 'family_kind': 'segmentation',
                  'n_dev': len(rows), 'n_hidden': len(hidden),
                  'clinical_bar': 'per image Dice and clDice vs 1st observer >= 2nd observer on that image',
                  'tags': ['segmentation', 'retina', 'fundus', 'vessels', 'inter-observer']})
