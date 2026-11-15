"""Fit the Frangi comparator's threshold and minimum component size on development images only.

    ~/miniconda3/envs/vals-suite-seg_vessel/bin/python -m suite.families.seg_vessel.classical.fit
Objective: mean over the 20 development images of (Dice + clDice) / 2 vs the first observer.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import morphology

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'pipeline'))
from vesselness import vesselness  # noqa: E402

from .. import grader  # noqa: E402

DATA_ROOT = Path('/home/jkwei/data/vals-suite/seg_vessel')


def main():
    split = json.loads((DATA_ROOT / 'split.json').read_text())
    dev = [r['case'] for r in split['cases'] if r['group'] == 'dev']
    data = []
    for c in dev:
        d = DATA_ROOT / 'staged' / 'dev' / c
        rgb = np.asarray(Image.open(d / 'image.jpg').convert('RGB'))
        data.append((vesselness(rgb), np.asarray(Image.open(d / 'label_1stHO.png').convert('L')) > 0))
    rows = []
    for thr in np.arange(0.01, 0.125, 0.01):
        for ms in (0, 100, 300):
            ds, cs = [], []
            for v, lab in data:
                m = morphology.remove_small_objects(v > thr, min_size=ms) if ms else v > thr
                ds.append(grader.dice(lab, m)); cs.append(grader.cldice(lab, m))
            rows.append({'threshold': round(float(thr), 3), 'min_size': ms, 'dice': float(np.mean(ds)),
                         'cldice': float(np.mean(cs)), 'score': float(np.mean(ds) / 2 + np.mean(cs) / 2)})
    best = max(rows, key=lambda r: r['score'])
    (HERE / 'pipeline' / 'params.json').write_text(json.dumps({'threshold': best['threshold'],
                                                               'min_size': best['min_size']}) + '\n')
    (HERE / 'fit_log.json').write_text(json.dumps({'best': best, 'grid': rows}, indent=1) + '\n')
    print(best)


if __name__ == '__main__':
    main()
