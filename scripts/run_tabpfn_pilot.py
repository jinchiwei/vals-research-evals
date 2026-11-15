"""Offline cached TabPFN comparator on SCS. Writes aggregate evidence only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ['TABPFN_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'
# -I -S avoids unrelated site startup hooks; dependencies remain in this conda env.
if sys.flags.no_site:
    sys.path.insert(0, str(Path(sys.executable).resolve().parents[1] / 'lib' /
                           f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pcnsl import prediction_eval as pe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    import torch
    torch.set_num_threads(2)
    arm = pe.TabPFNArm(model_path=args.checkpoint, device='cpu', offline=True)
    # Tiny invented-data fit first; no downloads or authenticated model service.
    status = arm.availability()
    print(json.dumps({'stage': 'availability', **status}), flush=True)
    if not status['available']:
        with (args.out / 'blocked.aggregate.json').open('x') as stream:
            json.dump(status, stream)
        return 1
    tiny = pe.synthetic_dataset(n=64, n_features=6)
    _, _, fold = next(pe.iter_folds(tiny, genes=['SYNTH_A']))
    start = time.monotonic()
    try:
        p = arm.predict_fold(fold)
        if len(p) != len(fold.test_ids):
            raise ValueError('Wrong smoke prediction count')
    except Exception as exc:
        result = {'stage': 'synthetic_smoke', 'status': 'blocked', 'error_type': type(exc).__name__}
        if isinstance(exc, pe.ArmError):
            result['error_code'] = str(exc)
        with (args.out / 'blocked.aggregate.json').open('x') as stream:
            json.dump(result, stream)
        print(json.dumps(result), flush=True)
        return 1
    print(json.dumps({'stage': 'synthetic_smoke', 'status': 'complete', 'seconds': time.monotonic()-start}), flush=True)
    for group in ('all', 'clinical'):
        report = pe.run_evaluation(dataset, [pe.TrainingPrevalenceArm(), pe.LogisticRegressionArm(), arm],
                                   genes=['MYD88', 'CD79B'], feature_groups=[group], bootstrap=2000)
        report['provenance'] = {'dataset_sha256': hashlib.sha256(raw).hexdigest(),
                                'evaluator_sha256': hashlib.sha256(Path(pe.__file__).read_bytes()).hexdigest(),
                                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                'torch': torch.__version__, 'device': 'cpu', 'threads': 2}
        with (args.out / f'{group}.aggregate.json').open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
        print(json.dumps({'stage': group, 'status': 'complete', 'summary': report['summary']}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
