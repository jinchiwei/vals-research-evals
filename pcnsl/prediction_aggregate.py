"""Pool Harbor agent submissions (one predictions.csv per fold task) into out-of-fold metrics.

Runs on the data host. Inputs are private: the source dataset, each fold's
public/gold/crosswalk JSON from ``prediction_export fold``, and the carried
``predictions.csv`` artifacts. Output is the aggregate-only report of
``prediction_eval.run_evaluation``; no row IDs, case IDs or probabilities.

- Integrity problems in *our* files (wrong gene or fold, crosswalk or gold that
  disagrees with ``make_folds`` and the source dataset, non-canonical features)
  raise ``ValueError``: nothing is scored.
- Problems in the *agent's* files (missing, malformed, wrong task's row IDs)
  are fold failures: per-fold metrics for the other folds, no pooled OOF.
- Submissions are matched to patients by case key through the crosswalk,
  never by row order. Comparator arms run on the same folds and are paired
  with the agent only if their inputs are the representation the agent saw.
"""
import argparse
import hashlib
import json
from pathlib import Path

from pcnsl import prediction_eval as ev
from pcnsl import prediction_export as px

MISSING = 'submission missing'


class SubmissionArm:
    """Replays validated agent probabilities into run_evaluation by case key."""
    safe_error_messages = True   # messages below never contain row IDs, case IDs or values

    def __init__(self, name, probabilities, problems, test_order):
        self.name = name
        self._probabilities = probabilities   # fold -> {case_id: probability}
        self._problems = problems             # fold -> reason
        self._test_order = test_order         # fold -> case_ids in run_evaluation's test order

    def availability(self):
        return {'available': True}

    def describe(self):
        return {'source': 'Harbor task predictions.csv, validated with the task grader parser, matched by case key'}

    def predict_fold(self, fold):
        if fold.fold in self._problems:
            raise ev.ArmError(self._problems[fold.fold])
        cases = self._test_order[fold.fold]
        if len(cases) != len(fold.test_X):
            raise ev.ArmError('fold size disagrees with the canonical split')
        return [self._probabilities[fold.fold][case] for case in cases]


def _check_bundle(dataset, gene, k, split, bundle, canonical):
    public, gold, crosswalk = bundle['public'], bundle['gold'], bundle['crosswalk']
    px._check_payloads(public, gold)
    if public['gene'] != gene or public['fold'] != k:
        raise ValueError(f'fold {k}: bundle is for {public["gene"]} fold {public["fold"]}')
    if list(public['feature_names']) != list(dataset['feature_names']):
        raise ValueError(f'fold {k}: bundle features differ from the source dataset')
    ids = dataset['case_ids']
    train_rows = [r['row_id'] for r in public['train']]
    test_rows = [r['row_id'] for r in public['test']]
    if set(crosswalk) != set(train_rows) | set(test_rows):
        raise ValueError(f'fold {k}: crosswalk does not cover exactly the bundle rows')
    if len(set(crosswalk.values())) != len(crosswalk):
        raise ValueError(f'fold {k}: crosswalk maps two rows to one case')
    index = {case: i for i, case in enumerate(ids)}
    if not set(crosswalk.values()) <= set(index):
        raise ValueError(f'fold {k}: crosswalk names cases absent from the source dataset')
    if ({crosswalk[r] for r in test_rows} != {ids[i] for i in split['test']}
            or {crosswalk[r] for r in train_rows} != {ids[i] for i in split['train']}):
        raise ValueError(f'fold {k}: rows do not match the canonical make_folds split')
    labels = dataset['labels'][gene]
    for row in public['train']:
        i = index[crosswalk[row['row_id']]]
        if row['label'] != labels[i] or row['x'] != list(canonical[i]):
            raise ValueError(f'fold {k}: a training row disagrees with the source dataset')
    for row in public['test']:
        i = index[crosswalk[row['row_id']]]
        if row['x'] != list(canonical[i]) or gold['labels'][row['row_id']] != labels[i]:
            raise ValueError(f'fold {k}: a held-out row or gold label disagrees with the source dataset')


def aggregate_submissions(dataset, gene, bundles, submissions, *, name='agent', comparators=(),
                          feature_group='all', seed=ev.DEFAULT_SEED, n_splits=ev.N_SPLITS,
                          min_class_count=ev.MIN_CLASS_COUNT, bootstrap=2000):
    """Aggregate-only report for one gene.

    bundles: {fold: {'public', 'gold', 'crosswalk'}} for every fold.
    submissions: {fold: predictions.csv text, or None if the task produced none}.
    comparators: names in prediction_eval.ARMS, run on the same folds.
    feature_group: the comparators' representation; they are paired with the
    agent only if it equals the columns the agent was given.
    """
    canonical = ev.validate_dataset(dataset)
    if set(bundles) != set(range(n_splits)):
        raise ValueError(f'need a bundle for each of folds 0..{n_splits - 1}')
    folds = ev.make_folds(dataset, gene, n_splits=n_splits, seed=seed, min_class_count=min_class_count)
    ids = list(dataset['case_ids'])
    y = dataset['labels'][gene]
    probabilities, problems, test_order, digests = {}, {}, {}, {}
    for k, split in enumerate(folds):
        bundle = bundles[k]
        _check_bundle(dataset, gene, k, split, bundle, canonical)
        _, key = ev.build_fold(ids, dataset['feature_names'], canonical, y, split, gene, k, seed, n_splits,
                               return_key=True)
        test_order[k] = [ids[i] for i in key]
        text = submissions.get(k)
        if text is None:
            problems[k] = MISSING
            continue
        digests[k] = hashlib.sha256(text.encode()).hexdigest()
        test_rows = [r['row_id'] for r in bundle['public']['test']]
        try:
            parsed = px.parse_predictions(text, test_rows)
        except px.SubmissionError as error:
            problems[k] = 'submission invalid: ' + str(error)
            continue
        probabilities[k] = {bundle['crosswalk'][row]: p for row, p in parsed.items()}

    groups = ev._feature_groups_arg(dataset, feature_group)
    comparator_names = [dataset['feature_names'][j] for j in ev.select_features(dataset, groups)]
    paired = comparator_names == list(dataset['feature_names'])
    arms = [SubmissionArm(name, probabilities, problems, test_order)]
    if comparators and paired:
        arms += [ev.ARMS[c]() for c in comparators]
    report = ev.run_evaluation(dataset, arms, seed=seed, n_splits=n_splits, min_class_count=min_class_count,
                               feature_groups=None, genes=[gene], bootstrap=bootstrap)
    arm = report['genes'][gene]['arms'][name]
    if problems and all(reason == MISSING for reason in problems.values()):
        arm['status'] = 'partial'
        arm['note'] = 'some folds have no submission; compare per_fold entries, not pooled scores'
    representation = ('matches comparator inputs' if paired else
                      f'not compared: comparators would use feature group {feature_group!r}, '
                      'the agent saw every column')
    report['agent_submissions'] = {
        'arm': name,
        'folds_valid': sorted(probabilities),
        'folds_missing': sorted(k for k, r in problems.items() if r == MISSING),
        'folds_invalid': sorted(k for k, r in problems.items() if r != MISSING),
        'predictions_sha256': {str(k): v for k, v in sorted(digests.items())},
        'matching': 'by case key through the private crosswalk; row order ignored',
        'representation': representation if comparators else 'no comparators requested',
    }
    json.dumps(report, allow_nan=False)
    return report


def load_bundles(private_dir, gene, n_splits=ev.N_SPLITS):
    """Read {gene}-fold{k}.{public,gold,crosswalk}.json as written by ``prediction_export fold``."""
    out = {}
    for k in range(n_splits):
        stem = Path(private_dir) / f'{gene.lower()}-fold{k}'
        out[k] = {part: json.loads(Path(f'{stem}.{part}.json').read_text()) for part in ('public', 'gold', 'crosswalk')}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--gene', required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--submission', action='append', default=[], metavar='FOLD=PATH',
                        help='carried predictions.csv for a fold; omit a fold whose task produced none')
    parser.add_argument('--comparator', action='append', default=[], choices=sorted(ev.ARMS))
    parser.add_argument('--feature-group', default='all')
    parser.add_argument('--bootstrap', type=int, default=2000)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error(f'{args.out} exists; refusing to overwrite')
    submissions = {}
    for item in args.submission:
        fold, _, path = item.partition('=')
        if not fold.isdigit() or int(fold) in submissions:
            parser.error(f'bad or repeated --submission {item!r}')
        submissions[int(fold)] = Path(path).read_text(encoding='utf-8-sig') if Path(path).is_file() else None
    report = aggregate_submissions(json.loads(args.dataset.read_text()), args.gene,
                                   load_bundles(args.private_dir, args.gene), submissions,
                                   comparators=args.comparator, feature_group=args.feature_group,
                                   bootstrap=args.bootstrap)
    with open(args.out, 'x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    arm = report['genes'][args.gene]['arms']['agent']
    print(f"{args.gene}: agent status {arm['status']}; wrote aggregate-only report {args.out}")


if __name__ == '__main__':
    main()
