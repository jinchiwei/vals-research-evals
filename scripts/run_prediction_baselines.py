"""Run fixed public-data controls on the data host; write aggregate reports only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pcnsl import prediction_eval as pe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--genes', nargs='+')
    parser.add_argument('--groups', nargs='+', default=['all', 'clinical'])
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args()
    os.umask(0o077)
    # Exclusive directory prevents an accidental rerun from overwriting evidence.
    args.out.mkdir(parents=True, exist_ok=False)
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    manifest = {'source': dataset['metadata']['source_kind'],
                'dataset_sha256': hashlib.sha256(raw).hexdigest(),
                'evaluator_sha256': hashlib.sha256(Path(pe.__file__).read_bytes()).hexdigest(),
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'runs': [], 'frontier_calls': 0}
    for group in args.groups:
        if group not in dataset['feature_groups']:
            raise ValueError('Unknown feature group')
        start = time.monotonic()
        report = pe.run_evaluation(dataset, [pe.TrainingPrevalenceArm(), pe.LogisticRegressionArm()],
                                   feature_groups=[group], genes=args.genes,
                                   bootstrap=args.bootstrap)
        report['elapsed_seconds'] = time.monotonic() - start
        report['provenance'] = {k: v for k, v in manifest.items() if k not in {'runs'}}
        target = args.out / (group + '.aggregate.json')
        with target.open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
        manifest['runs'].append({'feature_group': group, 'genes': len(report['genes']),
                                 'elapsed_seconds': report['elapsed_seconds'],
                                 'report_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    with (args.out / 'manifest.json').open('x') as stream:
        json.dump(manifest, stream, indent=2)
    print(json.dumps({'complete': True, 'runs': manifest['runs'], 'frontier_calls': 0}))


if __name__ == '__main__':
    main()
