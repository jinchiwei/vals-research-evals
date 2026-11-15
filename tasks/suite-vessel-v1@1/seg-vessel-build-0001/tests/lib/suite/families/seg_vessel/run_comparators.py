"""Run a comparator pipeline on staged cases through the suite runner and grade it.

    taskset -c 0-3 ~/miniconda3/envs/vals-suite-seg_vessel/bin/python -m suite.families.seg_vessel.run_comparators \
        --pipeline suite/families/seg_vessel/specialist/pipeline --name unet --group hidden

Writes DATA_ROOT/specialist/<name>_<group>/<case>/mask.png and DATA_ROOT/specialist/<name>_<group>.json
(per-image Dice, clDice, bar, acceptable, grader-measured wall time). --name second_observer grades the
second observer's stored masks (no pipeline run). Development images are graded against label_1stHO
with the second observer's agreement on that image as the bar, exactly as hidden ones.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from suite.core.runner import run_pipeline

from . import grader

DATA_ROOT = Path('/home/jkwei/data/vals-suite/seg_vessel')
LIMIT = 60.0


def case_dirs(group, tmp):
    """(case, input_dir, reference_dir) for the group, building dev references on the fly."""
    split = json.loads((DATA_ROOT / 'split.json').read_text())
    agree = json.loads((DATA_ROOT / 'observer_agreement.json').read_text())
    out = []
    for r in split['cases']:
        if r['group'] != group:
            continue
        if group == 'hidden':
            base = DATA_ROOT / 'staged' / 'hidden' / r['case']
            out.append((r['case'], base / 'input', base / 'reference'))
        else:
            src = DATA_ROOT / 'staged' / 'dev' / r['case']
            inp, ref = Path(tmp) / r['case'] / 'input', Path(tmp) / r['case'] / 'reference'
            inp.mkdir(parents=True); ref.mkdir(parents=True)
            shutil.copyfile(src / 'image.jpg', inp / 'image.jpg')
            shutil.copyfile(src / 'label_1stHO.png', ref / 'label.png')
            a = agree[r['source']]
            (ref / 'bar.json').write_text(json.dumps({'dice_2ndHO': a['dice'], 'cldice_2ndHO': a['cldice']}))
            out.append((r['case'], inp, ref))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pipeline', type=Path)
    ap.add_argument('--name', required=True)
    ap.add_argument('--group', choices=('dev', 'hidden'), default='hidden')
    args = ap.parse_args()
    out_root = DATA_ROOT / 'specialist' / f'{args.name}_{args.group}'
    if out_root.exists():
        shutil.rmtree(out_root)
    path = f'{Path(sys.executable).parent}:/usr/local/bin:/usr/bin:/bin'
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for case, inp, ref in case_dirs(args.group, tmp):
            dest = out_root / case
            dest.mkdir(parents=True)
            rec = {'case': case}
            if args.name == 'second_observer':
                if args.group == 'hidden':
                    shutil.copyfile(DATA_ROOT / 'staged' / 'hidden_2ndHO' / case / 'mask.png', dest / 'mask.png')
                else:
                    shutil.copyfile(DATA_ROOT / 'staged' / 'dev' / case / 'label_2ndHO.png', dest / 'mask.png')
                rec['wall_seconds'] = None
            else:
                res = run_pipeline(args.pipeline.resolve(), inp, dest, LIMIT, home_dir=Path(tmp) / f'home-{case}',
                                   log_path=Path(tmp) / f'{case}.log', path=path, threads=4)
                rec.update(wall_seconds=round(res.wall_seconds, 3), exit_code=res.exit_code, timed_out=res.timed_out)
            g = grader.grade_case(dest, inp, ref)
            rec.update(valid=g['valid'], acceptable=g['acceptable'], reason=g['reason'],
                       **{k: g['metrics'].get(k) for k in ('dice', 'cldice', 'dice_2ndHO', 'cldice_2ndHO',
                                                          'sensitivity', 'specificity')})
            rows.append(rec)
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()
                              if k != 'reason'}), flush=True)
    n = len(rows)
    summary = {'name': args.name, 'group': args.group, 'n': n,
               'clinically_acceptable': sum(r['acceptable'] for r in rows) / n,
               'mean_dice': sum(r['dice'] or 0 for r in rows) / n,
               'mean_cldice': sum(r['cldice'] or 0 for r in rows) / n,
               'measured_on': f'teal (WSL2), suite.core.runner, 4 threads, cores pinned with taskset '
                              f'(affinity {sorted(os.sched_getaffinity(0))})',
               'cases': rows}
    (DATA_ROOT / 'specialist' / f'{args.name}_{args.group}.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
