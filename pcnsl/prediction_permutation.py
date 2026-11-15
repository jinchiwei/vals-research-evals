"""Label-permutation null for the fixed logistic-regression pipeline only.

For each prespecified gene, patient labels are permuted (class counts kept),
and the *whole* fixed pipeline is rerun through ``prediction_eval.run_evaluation``:
the same stratified split procedure recomputed on the permuted labels, train-only
imputation/scaling, the same L2 logistic regression, no tuning, no score flips.
Pooled out-of-fold AUROC (higher) and Brier (lower) of the real labels are
compared with the null using plus-one p-values, ties counted as extreme.

This calibrates that one pipeline. It is not a null for TabPFN, a direct LLM or
an agent. Run on the data host; the output is aggregate-only.
"""
import argparse
import hashlib
import json
import math
import platform
import random
from pathlib import Path

from pcnsl import prediction_eval as ev

PERMUTATION_SEED = 20261115
DEFAULT_GENES = ('MYD88', 'CD79B')
DEFAULT_PERMUTATIONS = 199
DEFAULT_ARM = ev.LogisticRegressionArm
SCHEMA = 'pcnsl-prediction-permutation/v1'


def plus_one_p(null, observed, higher):
    """(1 + #null at least as extreme) / (len(null) + 1); ties count as extreme."""
    extreme = sum(v >= observed for v in null) if higher else sum(v <= observed for v in null)
    return (1 + extreme) / (len(null) + 1)


def permuted_labels(y, gene, seed, index):
    """Permutation `index` of one gene's patient labels; class counts are preserved."""
    rng = random.Random(f'{seed}:{gene}:{index}')
    out = list(y)
    rng.shuffle(out)
    return out


def _pooled(dataset, gene, arm, feature_groups):
    report = ev.run_evaluation(dataset, [arm], feature_groups=feature_groups, genes=[gene], bootstrap=0)
    result = report['genes'][gene]['arms'][arm.name]
    if result['status'] == 'unavailable':
        raise RuntimeError(f"{arm.name} unavailable: {result.get('reason')}")
    return result


def _summary(values):
    s = sorted(values)
    mean = sum(s) / len(s)
    sd = math.sqrt(sum((v - mean) ** 2 for v in s) / (len(s) - 1)) if len(s) > 1 else 0.0
    return {'mean': mean, 'sd': sd, 'min': s[0], 'p2.5': ev._percentile(s, 0.025),
            'median': ev._percentile(s, 0.5), 'p97.5': ev._percentile(s, 0.975), 'max': s[-1]}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def permutation_null(dataset, genes=DEFAULT_GENES, permutations=DEFAULT_PERMUTATIONS, seed=PERMUTATION_SEED,
                     arm_factory=DEFAULT_ARM, feature_group='all'):
    """Aggregate-only report: observed metrics, null distributions and p-values per gene."""
    if not isinstance(permutations, int) or permutations < 1:
        raise ValueError('permutations must be a positive integer')
    ev.validate_dataset(dataset)
    groups = dataset.get('groups')
    if groups is not None and len(set(groups)) != len(groups):
        raise ValueError('patient-level permutation requires one row per patient; found repeated patients')
    unknown = [g for g in genes if g not in dataset['labels']]
    if unknown:
        raise ValueError(f'genes without labels: {unknown}')
    feature_groups = ev._feature_groups_arg(dataset, feature_group)
    feature_count = len(ev.select_features(dataset, feature_groups))
    report = {'schema': SCHEMA, 'genes': {}}
    describe = None
    for gene in genes:
        arm = arm_factory()   # one fixed pipeline instance per gene, refit on every fold of every run
        observed = _pooled(dataset, gene, arm, feature_groups)
        if describe is None and hasattr(arm, 'describe'):
            describe = arm.describe()
        y = dataset['labels'][gene]
        entry = {'status': 'complete', 'patients': len(y), 'positive': sum(y), 'permutations_requested': permutations,
                 'permutations_completed': 0, 'observed': None, 'null': None, 'null_summary': None,
                 'p_values': None, 'distinct_null_split_fingerprints': 0}
        report['genes'][gene] = entry
        if observed['status'] != 'complete':
            entry.update(status='error', failure='observed run did not complete')
            continue
        entry['observed'] = {'auroc': observed['pooled_oof']['auroc'], 'brier': observed['pooled_oof']['brier'],
                             'average_precision': observed['pooled_oof']['average_precision']}
        null = {'auroc': [], 'brier': []}
        prints = set()
        for index in range(permutations):
            permuted = dict(dataset, labels={gene: permuted_labels(y, gene, seed, index)})
            result = _pooled(permuted, gene, arm, feature_groups)
            if result['status'] != 'complete':
                entry.update(status='error', failure=f'permutation {index} did not complete')
                break
            null['auroc'].append(result['pooled_oof']['auroc'])
            null['brier'].append(result['pooled_oof']['brier'])
            prints.add(result['split_fingerprint'])
            entry['permutations_completed'] += 1
        entry['distinct_null_split_fingerprints'] = len(prints)
        if entry['status'] != 'complete':
            continue
        entry['null'] = null
        entry['null_summary'] = {metric: _summary(values) for metric, values in null.items()}
        entry['p_values'] = {
            'auroc_higher': plus_one_p(null['auroc'], entry['observed']['auroc'], higher=True),
            'brier_lower': plus_one_p(null['brier'], entry['observed']['brier'], higher=False)}
    metadata = dataset.get('metadata') if isinstance(dataset.get('metadata'), dict) else {}
    report['design'] = {
        'scope': 'fixed logistic regression pipeline only (prediction_eval.LogisticRegressionArm); '
                 'not a null for TabPFN, direct LLM prediction or agents, which need their own valid null or '
                 'paired comparison',
        'pipeline': describe,
        'genes': list(genes), 'permutations': permutations, 'permutation_seed': seed,
        'permutation_unit': 'patient (one row per patient required); class counts preserved',
        'split_seed': ev.DEFAULT_SEED, 'folds': ev.N_SPLITS,
        'splits': 'make_splits recomputed on each permuted label vector (same stratified procedure)',
        'preprocessing': 'imputation and scaling fitted inside each training fold',
        'feature_group': feature_group, 'feature_count': feature_count,
        'feature_rounding_significant_digits': ev.SIGNIFICANT_DIGITS,
        'statistic': 'pooled out-of-fold AUROC (one-sided, higher) and Brier score (one-sided, lower)',
        'p_value': '(1 + number of permutations at least as extreme, ties inclusive) / (permutations + 1)',
        'score_direction': ev.SCORE_DIRECTION, 'selection': 'genes and settings prespecified; none chosen on results',
        'multiple_comparisons': 'two genes x two metrics are reported without multiple-comparison adjustment; '
                                'p-values are per-test and conditional on this cohort',
        'source_hashes': metadata.get('source_hashes'),
        'code': {'prediction_eval_sha256': _sha(ev.__file__), 'prediction_permutation_sha256': _sha(__file__)},
        'versions': {'python': platform.python_version()},
        'patient_level_outputs': False,
    }
    json.dumps(report, allow_nan=False)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--permutations', type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument('--genes', nargs='+', default=list(DEFAULT_GENES))
    parser.add_argument('--seed', type=int, default=PERMUTATION_SEED)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error(f'{args.out} exists; refusing to overwrite')
    report = permutation_null(json.loads(args.dataset.read_text()), genes=args.genes,
                              permutations=args.permutations, seed=args.seed)
    report['design']['dataset_sha256'] = _sha(args.dataset)
    with open(args.out, 'x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    for gene, entry in report['genes'].items():
        print(gene, entry['status'], entry['p_values'])


if __name__ == '__main__':
    main()
