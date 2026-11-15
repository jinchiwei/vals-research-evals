"""Bounded real-data direct-prediction pilot. Run only on FAC/SCS.

Four requests total, zero automatic retries. Output directory is exclusive;
response text and patient predictions remain in its private subdirectory.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pcnsl import prediction_eval as pe

MODELS = ('us.anthropic.claude-opus-5-5', 'gpt-5.2-2025-12-11')
GENES = ('MYD88', 'CD79B')
MAX_CHARS = 400_000


def prepare(dataset, max_chars=MAX_CHARS):
    jobs = []
    for gene in GENES:
        split = pe.make_folds(dataset, gene)[0]
        public, key = pe.build_public_payload(dataset, gene, **split, fold=0)
        request = json.dumps(public, allow_nan=False)
        if len(request) > max_chars:
            raise ValueError('Request exceeds prespecified size cap; no model calls allowed')
        for model in MODELS:
            jobs.append({'gene': gene, 'model': model, 'fold': 0, 'request': request,
                         'expected_ids': [r['case'] for r in public['test']],
                         'truth': [dataset['labels'][gene][i] for i in key],
                         'request_chars': len(request),
                         'rough_tokens_not_provider_verified': round(len(request) / 2.5),
                         'request_sha256': hashlib.sha256(request.encode()).hexdigest()})
    return jobs


def score(job, response):
    result = {k: job[k] for k in ('gene', 'model', 'fold', 'request_chars',
                                  'rough_tokens_not_provider_verified', 'request_sha256')}
    for key in ('model_reported', 'stop_reason', 'usage', 'latency_s', 'error_type', 'status_code'):
        if key in response:
            result[key] = response[key]
    if response.get('truncated') or response.get('stop_reason') in {'max_tokens', 'length'}:
        result['status'] = 'resource_limit'
    elif not response.get('ok'):
        result['status'] = 'model_refusal' if response.get('stop_reason') == 'refusal' else 'infrastructure_error'
    else:
        try:
            probabilities = pe.parse_predictions(response['text'], job['expected_ids'])
            result.update(status='scored', test_rows=len(job['truth']),
                          test_positive=sum(job['truth']),
                          metrics=pe.evaluate_probabilities(job['truth'], probabilities))
        except pe.ParseFailure as exc:
            result.update(status='response_format_error', parse_code=str(exc))
    return result


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, action='append', default=[])
    parser.add_argument('--run', action='store_true', help='Execute the four frozen requests; default is preflight only')
    args = parser.parse_args()
    os.umask(0o077)
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    jobs = prepare(dataset)
    manifest = {'version': 'public-prediction-pilot-v1', 'models': list(MODELS), 'genes': list(GENES),
                'fold': 0, 'max_calls': 4, 'automatic_retries': 0, 'output_token_cap': 8192,
                'timeout_seconds_per_call': 600, 'max_concurrent_calls': 2,
                'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'evaluator_sha256': hashlib.sha256(Path(pe.__file__).read_bytes()).hexdigest(),
                'client_sha256': hashlib.sha256(args.client.read_bytes()).hexdigest(),
                'feature_count': len(dataset['feature_names']),
                'feature_names_replaced': sum(a != b for a, b in zip(dataset['feature_names'], pe.safe_feature_names(dataset['feature_names']))),
                'context_limit': 'Gateway limit undisclosed; character cap checked; token estimates are not provider counts',
                'preflight': [{k: j[k] for k in ('gene', 'model', 'request_chars', 'rough_tokens_not_provider_verified')} for j in jobs],
                'interpretation': 'Single-fold engineering pilot, not a ranking, significance test or clinical validation'}
    args.out.mkdir(parents=True, exist_ok=False)
    write_new(args.out / 'manifest.json', manifest)
    if not args.run:
        print(json.dumps({'preflight': manifest['preflight'], 'calls': 0}))
        return
    spec = importlib.util.spec_from_file_location('pilot_versa_client', args.client)
    adapter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = adapter
    spec.loader.exec_module(adapter)
    for path in args.env_file:
        adapter.load_env_file(path)
    private = args.out / 'private'
    private.mkdir(mode=0o700)
    # Reserve every attempt before sending. A crash is not permission to repeat it.
    write_new(private / 'attempts.reserved.json', [{'gene': j['gene'], 'model': j['model']} for j in jobs])

    def execute(pair):
        index, job = pair
        write_new(private / f'{index}.request.json', json.loads(job['request']))
        client = adapter.VersaClient(timeout_s=600, max_retries=0, max_chars=200_000)
        extra = ({'output_config': {'effort': 'high'}} if 'anthropic' in job['model']
                 else {'reasoning_effort': 'high'})
        response = client.complete(job['model'], job['request'], max_output_tokens=8192, extra=extra).to_dict()
        write_new(private / f'{index}.response.json', response)
        result = score(job, response)
        write_new(args.out / f'{index}.aggregate.json', result)
        print(json.dumps({'attempt': index, 'gene': job['gene'], 'model': job['model'], 'status': result['status']}), flush=True)
        return result

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, enumerate(jobs)))
    write_new(args.out / 'summary.aggregate.json', {'manifest': manifest, 'attempts': results,
                                                    'elapsed_seconds': time.monotonic() - start})
    print(json.dumps({'complete': True, 'attempts': len(results)}), flush=True)


if __name__ == '__main__':
    main()
