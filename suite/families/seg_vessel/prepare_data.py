"""Check, split and stage CHASE_DB1 for the seg_vessel family.

    ~/miniconda3/envs/vals-suite-seg_vessel/bin/python -m suite.families.seg_vessel.prepare_data

Reads DATA_ROOT/official/ (the 84 files of the official CHASEDB1.zip, extracted) and writes:
  DATA_ROOT/data_check.json         structure checks (28 images, 999 x 960, 14 children x L/R, both observers)
  DATA_ROOT/split.json              child-level split, seed 20261114, file hashes, task IDs, split hash
  DATA_ROOT/observer_agreement.json second observer vs first, per image (Dice, clDice, sens, spec)
  DATA_ROOT/staged/dev/<case>/      image.jpg, label_1stHO.png, label_2ndHO.png (original bytes)
  DATA_ROOT/staged/hidden/<case>/   input/image.jpg; reference/label.png (1stHO), reference/bar.json
  DATA_ROOT/staged/hidden_2ndHO/<case>/mask.png   second observer for hidden images (local reference
                                    point only; never exported)
Refuses to overwrite an existing split (the split is fixed once).
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import grader

DATA_ROOT = Path('/home/jkwei/data/vals-suite/seg_vessel')
SEED = 20261114
N_DEV_CHILDREN = 10
NAME = re.compile(r'Image_(\d\d)([LR])(?:_(1stHO|2ndHO))?\.(jpg|png)')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(official):
    files = sorted(p.name for p in official.iterdir())
    images = {}
    for f in files:
        m = NAME.fullmatch(f)
        if not m:
            raise ValueError(f'unexpected file {f}')
        child, eye, obs, ext = m.groups()
        images.setdefault((child, eye), {})[obs or 'image'] = f
    problems, sizes, fractions = [], set(), {}
    for (child, eye), d in sorted(images.items()):
        if set(d) != {'image', '1stHO', '2ndHO'}:
            problems.append(f'{child}{eye}: has {sorted(d)}')
            continue
        with Image.open(official / d['image']) as im:
            sizes.add((im.size, im.mode, im.format))
        for obs in ('1stHO', '2ndHO'):
            with Image.open(official / d[obs]) as im:
                if im.size != (999, 960):
                    problems.append(f'{d[obs]} size {im.size}')
                arr = np.asarray(im.convert('L'))
                vals = set(np.unique(arr).tolist())
                if not vals <= {0, 255}:
                    problems.append(f'{d[obs]} values {sorted(vals)}')
                fractions[d[obs]] = float((arr > 0).mean())
    children = sorted({c for c, _ in images})
    out = {'n_files': len(files), 'n_images': len(images), 'children': children,
           'both_eyes_every_child': all((c, e) in images for c in children for e in 'LR'),
           'image_size_mode_format': sorted([list(s[0]), s[1], s[2]] for s in sizes),
           'vessel_fraction_1stHO_mean': float(np.mean([v for k, v in fractions.items() if '1stHO' in k])),
           'vessel_fraction_2ndHO_mean': float(np.mean([v for k, v in fractions.items() if '2ndHO' in k])),
           'problems': problems}
    ok = (out['n_files'] == 84 and out['n_images'] == 28 and len(children) == 14
          and out['both_eyes_every_child'] and not problems
          and out['image_size_mode_format'] == [[[999, 960], 'RGB', 'JPEG']])
    out['ok'] = ok
    return out, images


def load_bool(path):
    with Image.open(path) as im:
        return np.asarray(im.convert('L')) > 0


def main(data_root=DATA_ROOT):
    data_root = Path(data_root)
    official = data_root / 'official'
    if (data_root / 'split.json').exists():
        sys.exit('split.json exists; the split is fixed. Delete it only to rebuild from scratch on purpose.')
    report, images = check(official)
    (data_root / 'data_check.json').write_text(json.dumps(report, indent=1) + '\n')
    if not report['ok']:
        sys.exit(f'data check failed: {report}')

    # Observer agreement for every image (the anchor of the clinical bar).
    agreement = {}
    for (child, eye), d in sorted(images.items()):
        r, s = load_bool(official / d['1stHO']), load_bool(official / d['2ndHO'])
        m = grader.case_metrics(r, s)
        agreement[f'Image_{child}{eye}'] = {k: m[k] for k in ('dice', 'cldice', 'sensitivity', 'specificity', 'accuracy')}
    (data_root / 'observer_agreement.json').write_text(json.dumps(agreement, indent=1) + '\n')

    # Child-level split.
    children = sorted({c for c, _ in images})
    order = list(np.random.default_rng(SEED).permutation(children))
    dev_children, hidden_children = sorted(order[:N_DEV_CHILDREN]), sorted(order[N_DEV_CHILDREN:])
    rng_ids = np.random.default_rng(SEED + 1)
    ids = rng_ids.choice(np.arange(1000, 10000), size=28, replace=False)
    letters = {c: chr(ord('A') + i) for i, c in enumerate(dev_children)}  # child labels shown to the agent
    rows, k = [], 0
    for group, kids in (('dev', dev_children), ('hidden', hidden_children)):
        for c in kids:
            for eye in 'LR':
                d = images[(c, eye)]
                case = f'{"dev" if group == "dev" else "hid"}_{ids[k]}'
                k += 1
                rows.append({'case': case, 'group': group, 'source': f'Image_{c}{eye}', 'child': c, 'eye': eye,
                             'child_label': letters.get(c),
                             'sha256': {o: sha256(official / d[o]) for o in ('image', '1stHO', '2ndHO')}})
    staged = data_root / 'staged'
    if staged.exists():
        shutil.rmtree(staged)
    for row in rows:
        d = images[(row['child'], row['eye'])]
        if row['group'] == 'dev':
            dst = staged / 'dev' / row['case']
            dst.mkdir(parents=True)
            shutil.copyfile(official / d['image'], dst / 'image.jpg')
            shutil.copyfile(official / d['1stHO'], dst / 'label_1stHO.png')
            shutil.copyfile(official / d['2ndHO'], dst / 'label_2ndHO.png')
        else:
            dst = staged / 'hidden' / row['case']
            (dst / 'input').mkdir(parents=True)
            (dst / 'reference').mkdir(parents=True)
            shutil.copyfile(official / d['image'], dst / 'input' / 'image.jpg')
            shutil.copyfile(official / d['1stHO'], dst / 'reference' / 'label.png')
            a = agreement[row['source']]
            (dst / 'reference' / 'bar.json').write_text(json.dumps(
                {'dice_2ndHO': a['dice'], 'cldice_2ndHO': a['cldice']}) + '\n')
            o2 = staged / 'hidden_2ndHO' / row['case']
            o2.mkdir(parents=True)
            shutil.copyfile(official / d['2ndHO'], o2 / 'mask.png')
    body = {'seed': SEED, 'method': 'children 01-14 permuted with numpy default_rng(20261114); first 10 development, '
                                    'last 4 hidden; both eyes of a child stay together. Case IDs drawn with '
                                    'default_rng(20261115) from 1000-9999.',
            'dev_children': dev_children, 'hidden_children': hidden_children, 'cases': rows}
    body['split_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    (data_root / 'split.json').write_text(json.dumps(body, indent=1) + '\n')
    print(json.dumps({'dev_children': dev_children, 'hidden_children': hidden_children,
                      'split_sha256': body['split_sha256']}))


if __name__ == '__main__':
    main()
