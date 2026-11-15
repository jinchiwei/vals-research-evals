"""Run the causal_ate comparators on a split, timed with the suite runner, and score them with the grader.

    python -m suite.families.causal_ate.comparators.run_comparators DATA_ROOT {dev,hidden}

Writes DATA_ROOT/results/<split>/<method>/{estimates.json,runtime.json,log.txt} and
DATA_ROOT/results/<split>/summary.json (gate parts and metrics per method; per-dataset errors omitted).
Methods: dr_att (specialist), ols (regression adjustment), naive (difference in means).
Threads are capped at 4, the task's CPU count.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

from suite.core import runner

from .. import grader

HERE = Path(__file__).resolve().parent
METHODS = ('dr_att', 'ols', 'naive')


def method_pipeline(method, tmp):
    """A pipeline folder whose run.sh calls estimate.py with the given method."""
    d = Path(tmp) / f'pipe_{method}'
    d.mkdir()
    (d / 'estimate.py').write_text((HERE / 'pipelines' / 'dr_att' / 'estimate.py').read_text())
    (d / 'run.sh').write_text('#!/bin/bash\nset -euo pipefail\nHERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
                              f'exec python3 "$HERE/estimate.py" {method} "$1" "$2"\n')
    (d / 'run.sh').chmod(0o755)
    return d


def main(data_root, split_name):
    root = Path(data_root).resolve()
    split = root / 'split' / split_name
    out_root = root / 'results' / split_name
    summary = {}
    path = os.path.dirname(sys.executable) + ':/usr/bin:/bin'
    with tempfile.TemporaryDirectory() as tmp:
        for method in METHODS:
            out = out_root / method
            if out.exists():
                raise SystemExit(f'{out} exists; refusing to overwrite')
            out.mkdir(parents=True)
            pipe = method_pipeline(method, tmp)
            home = Path(tmp) / f'home_{method}'
            home.mkdir()
            res = runner.run_pipeline(pipe, split / 'input', out, 3600, home_dir=home, log_path=out / 'log.txt',
                                      path=path, threads=4)
            (out / 'runtime.json').write_text(json.dumps({
                'wall_seconds': res.wall_seconds, 'exit_code': res.exit_code, 'timed_out': res.timed_out,
                'measured_on': 'teal (WSL2), suite.core.runner, thread caps 4'}, indent=2) + '\n')
            g = grader.grade_cohort(out, split / 'input', split / 'reference')
            m = {k: v for k, v in g['metrics'].items() if k != 'per_dataset'}
            summary[method] = {'valid': g['valid'], 'reason': g['reason'], 'gate': g['gate'],
                               'all_parts': bool(g['valid'] and g['gate'] and all(g['gate'].values())),
                               'quality': g['quality'], 'metrics': m, 'wall_seconds': res.wall_seconds}
            print(method, json.dumps(summary[method]))
    (out_root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
