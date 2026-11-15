"""Write the causal_ate development and hidden datasets (data side only; nothing here reaches the agent).

    python -m suite.families.causal_ate.datagen.prepare_data DATA_ROOT

Reads DATA_ROOT/covariates/pool_{dev,hidden}.csv (covariates.py) and writes
  DATA_ROOT/split/dev/input/<id>/data.csv, DATA_ROOT/split/dev/reference/truth.csv     (agent-visible)
  DATA_ROOT/split/hidden/input/<id>/data.csv, DATA_ROOT/split/hidden/reference/truth.csv (verifier only)
  DATA_ROOT/private/{dev,hidden}_oracle.json   (settings and oracle diagnostics; never exported)
  DATA_ROOT/split/manifest.json                (dataset ids and SHA-256 of every file)
Seed 20261114 (dgp.SEED); dev = 16 settings x 2 replications on set-A stays, hidden = 16 x 3 on set-B stays.
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

from . import dgp

N_REPS = {'dev': 2, 'hidden': 3}
SEED_OFFSET = {'dev': 1, 'hidden': 2}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(data_root):
    root = Path(data_root)
    split = root / 'split'
    if split.exists():
        raise SystemExit(f'{split} exists; refusing to overwrite')
    (root / 'private').mkdir(parents=True, exist_ok=True)
    manifest = {'seed': dgp.SEED, 'n_per_dataset': dgp.N_PER_DATASET, 'splits': {}}
    for name in ('dev', 'hidden'):
        pool = pd.read_csv(root / 'covariates' / f'pool_{name}.csv')
        rows, diags, files = [], {}, {}
        for did, data, satt, diag in dgp.generate_split(pool, N_REPS[name], SEED_OFFSET[name]):
            d = split / name / 'input' / did
            d.mkdir(parents=True)
            data.to_csv(d / 'data.csv', index=False, float_format='%.6g')
            files[f'input/{did}/data.csv'] = sha(d / 'data.csv')
            rows.append({'dataset_id': did, 'satt': satt})
            diags[did] = diag
        ref = split / name / 'reference'
        ref.mkdir(parents=True)
        pd.DataFrame(rows).sort_values('dataset_id').to_csv(ref / 'truth.csv', index=False, float_format='%.10g')
        files['reference/truth.csv'] = sha(ref / 'truth.csv')
        (root / 'private' / f'{name}_oracle.json').write_text(json.dumps(diags, indent=1, sort_keys=True) + '\n')
        manifest['splits'][name] = {'n_datasets': len(rows), 'pool': f'pool_{name}.csv',
                                    'ids': sorted(r['dataset_id'] for r in rows), 'sha256': files}
        print(name, len(rows))
    (split / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')


if __name__ == '__main__':
    main(sys.argv[1])
