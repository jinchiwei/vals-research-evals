"""Evaluate baseline configurations on DEVELOPMENT cases only (never hidden).

    python -I -m suite.families.reg_resect.tune_dev STAGED_DIR '{"feature":"gradmag"}' ['{...}' ...]
Prints per-case mean TRE and runtime for each configuration.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from . import landmarks as lm
from .pipeline_src import mind_reg, register


def evaluate(staged, cfg_over, cases=None):
    dev = Path(staged) / 'dev'
    rows = []
    for case in sorted(p.name for p in dev.iterdir()) if cases is None else cases:
        over = dict(cfg_over)
        mod = mind_reg if over.pop('method', 'mi') == 'mind' else register
        cfg = dict(mod.DEFAULTS, **over)
        with tempfile.TemporaryDirectory() as out:
            t0 = time.monotonic()
            mod.run(dev / case, out, cfg)
            sec = time.monotonic() - t0
            ids, pred = lm.read_csv(Path(out) / 'landmarks_us.csv')
        rids, ref = lm.read_csv(dev / case / 'landmarks_us.csv')
        _, mri = lm.read_csv(dev / case / 'landmarks_mri.csv')
        assert ids == rids
        rows.append({'case': case, 'initial': float(np.linalg.norm(mri - ref, axis=1).mean()),
                     'final': float(np.linalg.norm(pred - ref, axis=1).mean()), 'seconds': sec})
    return rows


def main():
    staged = sys.argv[1]
    for spec in sys.argv[2:]:
        rows = evaluate(staged, json.loads(spec))
        print(spec, ' | '.join(f"{r['case']} {r['initial']:.2f}->{r['final']:.2f} ({r['seconds']:.0f}s)" for r in rows),
              f"| mean {np.mean([r['final'] for r in rows]):.2f} pass {sum(r['final'] < 2 for r in rows)}/{len(rows)}",
              flush=True)


if __name__ == '__main__':
    main()
