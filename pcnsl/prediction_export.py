"""Export one held-out fold as a Harbor/Valkyrie *prediction* task.

The evaluated agent receives labeled training rows and unlabeled test rows and
must write held-out probabilities. A trusted verifier scores AUROC (reward),
average precision and Brier score. Packaging only: nothing here uploads,
launches runs, contacts a network, or reads patient data. Callers pass a
dataset dict (see ``build_fold``); tests use synthetic fixtures.

Isolation model (see docs/research/prediction-harbor.md):
- ``environment/`` (the Docker build context) and ``instruction.md`` are the
  only agent-visible inputs; neither contains held-out labels.
- ``tests/gold.json`` holds held-out labels. ``task.toml`` requests Valkyrie's
  *separate* verifier, so ``tests/`` is uploaded only into a fresh verifier
  sandbox; only ``/workspace/output`` is carried over from the agent sandbox.
- The verifier refuses to score (no reward, nonzero exit) if it sees evidence
  that it is running inside the agent's sandbox.
"""
import argparse
import csv
import hashlib
import inspect
import io
import json
import math
import os
import random
import re
import shutil
from pathlib import Path

from pcnsl.prediction_eval import DEFAULT_SEED, SIGNIFICANT_DIGITS, canonical_matrix, make_folds

PUBLIC_SCHEMA = 'pcnsl-prediction-public/1'
GOLD_SCHEMA = 'pcnsl-prediction-gold/1'
DEFAULT_BASE_IMAGE = 'python:3.12-slim'
# Installed at image build time only (the agent runtime gets no package index).
VENV = '/opt/benchmark-venv'
DEFAULT_PACKAGES = ('numpy==2.1.3', 'scipy==1.14.1', 'pandas==2.2.3', 'scikit-learn==1.5.2')
ENDPOINT = ('1 = a reported pathogenic/likely pathogenic qualifying alteration in the gene; '
            '0 = genomically profiled with no qualifying alteration reported. '
            '0 does not assert biological wild type or complete assay coverage.')
TASK_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,62}')
GENE = re.compile(r'[A-Z0-9][A-Z0-9-]{0,15}')
FEATURE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _.()%+-]{0,159}')
GROUP_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
FORBIDDEN_TOKENS = {'id', 'ids', 'mrn', 'accession', 'date', 'dob', 'birthdate', 'path', 'filename',
                    'uid', 'uuid', 'timestamp', 'datetime', 'patient', 'name', 'dicom'}
DATE_LIKE = re.compile(r'\d{4}[-_/]?\d{2}[-_/]?\d{2}|\d{8,}')
AGENT_TIMEOUT_SEC = 1800.0
VERIFIER_TIMEOUT_SEC = 120.0


# ---------------------------------------------------------------------------
# Scoring and submission validation. Standard library only: these functions
# are copied verbatim into each task's tests/grade.py, so offline aggregation
# and in-task grading use identical code.
# ---------------------------------------------------------------------------

class SubmissionError(ValueError):
    """The agent's prediction file violates the documented contract."""


def _check_binary(y, p):
    if len(y) != len(p) or not y:
        raise ValueError('labels and probabilities must be nonempty and aligned')
    if any(v not in (0, 1) or isinstance(v, bool) for v in y):
        raise ValueError('labels must be 0/1 integers')
    if not (0 < sum(y) < len(y)):
        raise ValueError('metric undefined: both classes are required')


def auroc(y, p):
    """Mann-Whitney AUROC; ties count one half. Never flipped below 0.5."""
    _check_binary(y, p)
    pos = [s for s, t in zip(p, y) if t == 1]
    neg = [s for s, t in zip(p, y) if t == 0]
    wins = 0.0
    for a in pos:
        for b in neg:
            wins += 1.0 if a > b else 0.5 if a == b else 0.0
    return wins / (len(pos) * len(neg))


def average_precision(y, p):
    """Step-wise AP over distinct thresholds (no interpolation), as in sklearn."""
    _check_binary(y, p)
    order = sorted(range(len(p)), key=lambda i: -p[i])
    total_pos = sum(y)
    tp = fp = 0
    ap = prev_recall = 0.0
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and p[order[j]] == p[order[i]]:
            tp += y[order[j]]
            fp += 1 - y[order[j]]
            j += 1
        recall = tp / total_pos
        ap += (recall - prev_recall) * (tp / (tp + fp))
        prev_recall = recall
        i = j
    return ap


def brier(y, p):
    """Mean squared error of probabilities against 0/1 outcomes."""
    if len(y) != len(p) or not y:
        raise ValueError('labels and probabilities must be nonempty and aligned')
    return sum((q - t) ** 2 for q, t in zip(p, y)) / len(y)


def parse_predictions(text, expected_ids):
    """Strictly parse ``row_id,probability`` CSV; no clipping, rescaling or repair."""
    expected = set(expected_ids)
    rows = list(csv.reader(io.StringIO(text, newline='')))
    if not rows or rows[0] != ['row_id', 'probability']:
        raise SubmissionError('header must be exactly: row_id,probability')
    found = {}
    for number, row in enumerate(rows[1:], start=2):
        if len(row) != 2:
            raise SubmissionError(f'line {number}: expected 2 fields, got {len(row)}')
        row_id, raw = row
        if row_id not in expected:
            raise SubmissionError(f'line {number}: unknown row_id')
        if row_id in found:
            raise SubmissionError(f'line {number}: duplicate row_id')
        try:
            value = float(raw)
        except ValueError:
            raise SubmissionError(f'line {number}: probability is not a number') from None
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise SubmissionError(f'line {number}: probability must be finite and within [0, 1]')
        found[row_id] = value
    missing = expected - set(found)
    if missing:
        raise SubmissionError(f'{len(missing)} test row_id(s) have no prediction')
    return found


def score_submission(gold_labels, text):
    """Return (valid, metrics) for one fold. Invalid submissions get no metrics."""
    ids = sorted(gold_labels)
    metrics = {'n_test': len(ids), 'n_test_positive': sum(gold_labels[k] for k in ids),
               'auroc': None, 'average_precision': None, 'brier': None, 'submission_error': None}
    try:
        if text is None:
            raise SubmissionError('prediction file is missing')
        predictions = parse_predictions(text, ids)
    except SubmissionError as error:
        metrics['submission_error'] = str(error)
        return False, metrics
    y = [gold_labels[k] for k in ids]
    p = [predictions[k] for k in ids]
    metrics.update(auroc=auroc(y, p), average_precision=average_precision(y, p), brier=brier(y, p))
    return True, metrics


SCORING_FUNCTIONS = (SubmissionError, _check_binary, auroc, average_precision, brier,
                     parse_predictions, score_submission)

GRADER_MAIN = r'''

MAX_BYTES = 1_000_000
# Paths that exist in the agent sandbox but not in a fresh separate-verifier
# sandbox (oracle solution upload, installed agent bundles). See prediction-harbor.md.
SHARED_SANDBOX_MARKERS = ('solution', 'bundle')


class InfrastructureError(RuntimeError):
    pass


def read_submission(path):
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(status.st_mode):
        raise SubmissionError('prediction file must be a regular file, not a link or directory')
    if status.st_size > MAX_BYTES:
        raise SubmissionError('prediction file exceeds 1 MB')
    with open(path, 'rb') as handle:
        data = handle.read(MAX_BYTES + 1)
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise SubmissionError('prediction file is not UTF-8') from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='/workspace/output')
    parser.add_argument('--gold', default='/tests/gold.json')
    parser.add_argument('--logs', default='/logs/verifier')
    parser.add_argument('--sandbox-root', default='/')
    args = parser.parse_args()
    logs = Path(args.logs)
    try:
        found = [m for m in SHARED_SANDBOX_MARKERS if os.path.lexists(os.path.join(args.sandbox_root, m))]
        if found:
            raise InfrastructureError(
                'refusing to score: verifier appears to share the agent sandbox (found /'
                + ', /'.join(found) + '); this task requires [verifier] environment_mode = "separate"')
        try:
            gold = json.loads(Path(args.gold).read_text())
            labels = gold['labels']
            if gold.get('schema') != GOLD_SCHEMA or not labels:
                raise ValueError('bad gold schema')
        except (OSError, ValueError, KeyError) as error:
            raise InfrastructureError('gold labels unavailable: ' + type(error).__name__) from None
        try:
            text = read_submission(os.path.join(args.output_dir, 'predictions.csv'))
            valid, metrics = score_submission(labels, text)
            digest = None if text is None else hashlib.sha256(text.encode()).hexdigest()
        except SubmissionError as error:
            valid, metrics = score_submission(labels, None)
            metrics['submission_error'] = str(error)
            digest = None
    except InfrastructureError as error:
        print(json.dumps({'infrastructure_error': str(error)}))
        print(str(error), file=sys.stderr)
        sys.exit(2)
    metrics.update(valid_submission=valid, gene=gold.get('gene'), fold=gold.get('fold'),
                   predictions_sha256=digest)
    rewards = {'reward': metrics['auroc'] if valid else 0.0, 'valid_submission': 1.0 if valid else 0.0}
    logs.mkdir(parents=True, exist_ok=True)
    (logs / 'metrics.json').write_text(json.dumps(metrics, indent=2, sort_keys=True) + '\n')
    (logs / 'reward.json').write_text(json.dumps(rewards) + '\n')
    print(json.dumps(metrics, sort_keys=True))


if __name__ == '__main__':
    main()
'''

ORACLE = r'''"""Reference plumbing check: predicts training prevalence for every test row.

This verifies the task end to end (expected reward 0.5). It is not a
performance target and never reads hidden labels.
"""
import csv
import sys
from pathlib import Path

data, out = Path(sys.argv[1]), Path(sys.argv[2])
with open(data / 'train.csv', newline='') as handle:
    labels = [int(row['label']) for row in csv.DictReader(handle)]
with open(data / 'test.csv', newline='') as handle:
    ids = [row['row_id'] for row in csv.DictReader(handle)]
rate = sum(labels) / len(labels)
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, 'w', newline='') as handle:
    writer = csv.writer(handle, lineterminator='\n')
    writer.writerow(['row_id', 'probability'])
    writer.writerows([row_id, repr(rate)] for row_id in ids)
'''


def grader_source():
    parts = ['"""Trusted verifier for one prediction fold. Generated; do not edit."""',
             'import argparse', 'import csv', 'import hashlib', 'import io', 'import json',
             'import math', 'import os', 'import stat', 'import sys', 'from pathlib import Path',
             '', f'GOLD_SCHEMA = {GOLD_SCHEMA!r}', '']
    parts += [inspect.getsource(item) for item in SCORING_FUNCTIONS]
    return '\n\n'.join(parts) + GRADER_MAIN


# ---------------------------------------------------------------------------
# Building one fold's public payload and private gold.
# ---------------------------------------------------------------------------

def _check_feature_name(name):
    if not isinstance(name, str) or not FEATURE_NAME.fullmatch(name):
        raise ValueError(f'unsafe feature name {name!r}: letters, digits, space, _.()%+- only')
    tokens = set(re.findall(r'[a-z]+', name.lower()))
    if tokens & FORBIDDEN_TOKENS or DATE_LIKE.search(name):
        raise ValueError(f'feature name {name!r} looks like an identifier, date or path')


def _check_dataset(dataset, gene):
    for key in ('case_ids', 'feature_names', 'X', 'labels', 'feature_groups'):
        if key not in dataset:
            raise ValueError(f'dataset is missing {key!r}')
    case_ids, names, X = dataset['case_ids'], dataset['feature_names'], dataset['X']
    if not isinstance(gene, str) or not GENE.fullmatch(gene):
        raise ValueError('gene must be an uppercase symbol')
    if gene not in dataset['labels']:
        raise ValueError(f'gene {gene!r} has no labels (not eligible?)')
    labels = dataset['labels'][gene]
    if not (len(case_ids) == len(X) == len(labels)) or not case_ids:
        raise ValueError('case_ids, X and labels must be nonempty and aligned')
    if len(set(case_ids)) != len(case_ids):
        raise ValueError('duplicate case_ids')
    if not names or len(set(names)) != len(names):
        raise ValueError('feature_names must be nonempty and unique')
    for name in names:
        _check_feature_name(name)
    for row in X:
        if not isinstance(row, list) or len(row) != len(names):
            raise ValueError('every X row must be a list aligned with feature_names')
        for value in row:
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('features must be finite numbers or null')
    if any(isinstance(v, bool) or v not in (0, 1) for v in labels):
        raise ValueError('labels must be 0/1 integers')
    groups = dataset['feature_groups']
    if not isinstance(groups, dict):
        raise ValueError('feature_groups must be a dict')
    known = set(names)
    for group, members in groups.items():
        if not isinstance(group, str) or not GROUP_NAME.fullmatch(group):
            raise ValueError(f'unsafe feature group name {group!r}')
        if not isinstance(members, list) or not set(members) <= known:
            raise ValueError(f'feature group {group!r} names unknown features')


def build_fold(dataset, gene, test_indices, *, seed, fold):
    """Split one fold into (public payload, private gold, private crosswalk).

    ``test_indices`` come from the caller's prespecified fold assignment. Row
    IDs are fresh per (seed, gene, fold) and row order is shuffled independently
    of labels. The crosswalk (row_id -> dataset case_id) must stay with the
    caller on the data host; it is never written into a task.
    """
    _check_dataset(dataset, gene)
    n = len(dataset['case_ids'])
    if not isinstance(fold, int) or isinstance(fold, bool) or fold < 0:
        raise ValueError('fold must be a nonnegative integer')
    if (not test_indices or len(set(test_indices)) != len(test_indices)
            or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n for i in test_indices)):
        raise ValueError('test_indices must be unique in-range integers')
    test = set(test_indices)
    train_idx = [i for i in range(n) if i not in test]
    test_idx = sorted(test)
    labels = dataset['labels'][gene]
    for part, idx in (('training', train_idx), ('held-out', test_idx)):
        ys = [labels[i] for i in idx]
        if not (0 < sum(ys) < len(ys)):
            raise ValueError(f'{part} rows must contain both classes')
    rng = random.Random(f'{seed}:{gene}:{fold}')
    rng.shuffle(train_idx)
    rng.shuffle(test_idx)
    used, crosswalk = set(), {}

    def fresh(prefix, index):
        while True:
            row_id = f'{prefix}-{rng.getrandbits(48):012x}'
            if row_id not in used:
                used.add(row_id)
                crosswalk[row_id] = dataset['case_ids'][index]
                return row_id

    X = canonical_matrix(dataset['X'])  # identical values to every comparator arm
    train = [{'row_id': fresh('r', i), 'label': labels[i], 'x': list(X[i])} for i in train_idx]
    test_rows, gold = [], {}
    for i in test_idx:
        row_id = fresh('t', i)
        test_rows.append({'row_id': row_id, 'x': list(X[i])})
        gold[row_id] = labels[i]
    public = {'schema': PUBLIC_SCHEMA, 'gene': gene, 'fold': fold, 'endpoint': ENDPOINT,
              'significant_digits': SIGNIFICANT_DIGITS,
              'feature_names': list(dataset['feature_names']),
              'feature_groups': {k: list(v) for k, v in dataset['feature_groups'].items()},
              'train': train, 'test': test_rows}
    private = {'schema': GOLD_SCHEMA, 'gene': gene, 'fold': fold, 'labels': gold}
    return public, private, crosswalk


def build_eval_fold(dataset, gene, fold, *, seed=DEFAULT_SEED, **fold_options):
    """build_fold with the test rows from prediction_eval.make_folds, as every arm uses."""
    folds = make_folds(dataset, gene, seed=seed, **fold_options)
    return build_fold(dataset, gene, folds[fold]['test'], seed=seed, fold=fold)


def _check_payloads(public, gold):
    if public.get('schema') != PUBLIC_SCHEMA or gold.get('schema') != GOLD_SCHEMA:
        raise ValueError('unrecognized payload schema')
    if public['gene'] != gold['gene'] or public['fold'] != gold['fold']:
        raise ValueError('public payload and gold describe different folds')
    _check_dataset({'case_ids': [r['row_id'] for r in public['train'] + public['test']],
                    'feature_names': public['feature_names'],
                    'X': [r['x'] for r in public['train'] + public['test']],
                    'labels': {public['gene']: [r['label'] for r in public['train']] + [0] * len(public['test'])},
                    'feature_groups': public['feature_groups']}, public['gene'])
    if public.get('significant_digits') != SIGNIFICANT_DIGITS:
        raise ValueError('payload was not built with the shared feature rounding')
    rows = [r['x'] for r in public['train'] + public['test']]
    if [list(r) for r in canonical_matrix(rows)] != rows:
        raise ValueError('feature values must already be canonical (prediction_eval.canonical_matrix)')
    if any(set(r) != {'row_id', 'x'} for r in public['test']):
        raise ValueError('public test rows may contain only row_id and x')
    if any(set(r) != {'row_id', 'label', 'x'} for r in public['train']):
        raise ValueError('public training rows must contain exactly row_id, label and x')
    test_ids = [r['row_id'] for r in public['test']]
    if set(gold['labels']) != set(test_ids):
        raise ValueError('gold labels must cover exactly the public test rows')
    ys = list(gold['labels'].values())
    if any(isinstance(v, bool) or v not in (0, 1) for v in ys) or not 0 < sum(ys) < len(ys):
        raise ValueError('gold labels must be 0/1 with both classes present')
    for row_id in [r['row_id'] for r in public['train']] + test_ids:
        if not re.fullmatch(r'[rt]-[0-9a-f]{12}', row_id):
            raise ValueError('row_ids must be exporter-generated anonymous IDs')


# ---------------------------------------------------------------------------
# Writing the Harbor task folder.
# ---------------------------------------------------------------------------

def _csv(header, rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(header)
    for row in rows:
        writer.writerow(['' if v is None else repr(v) if isinstance(v, float) else v for v in row])
    return out.getvalue()


def _instruction(public, tabpfn_checkpoint, cpus, memory_mb, agent_allowed_hosts):
    n_train = len(public['train'])
    n_pos = sum(r['label'] for r in public['train'])
    tools = 'Python 3.12 with numpy, scipy, pandas and scikit-learn'
    if agent_allowed_hosts:
        network = ('Outbound network is limited to the model API host(s) your harness uses ('
                   + ', '.join(agent_allowed_hosts) + '); there is no package index.')
    else:
        network = 'The sandbox has no network access.'
    if tabpfn_checkpoint:
        tools = (f'{tools}, plus the `tabpfn` package with a local model checkpoint at '
                 f'`{tabpfn_checkpoint}` (TabPFN cannot download weights here)')
    return f"""# Predict {public['gene']} alteration status for held-out patients

You are given tabular data from a primary central nervous system lymphoma
cohort: numeric MRI-derived lesion/radiomic summaries and clinical variables.
Each row is one patient. Your job is to estimate, for every held-out patient,
the probability that the label is 1.

**Label.** {public['endpoint']}

## Data (read-only, in `/workspace/data/`)

- `/workspace/data/train.csv`: `row_id`, `label`, then {len(public['feature_names'])} feature columns.
  {n_train} patients, {n_pos} with label 1.
- `/workspace/data/test.csv`: `row_id` and the same feature columns, no label.
  {len(public['test'])} patients.
- `/workspace/data/feature_groups.json`: named, overlapping groups of feature columns.
- `/workspace/data/README.md`: data dictionary.

Missing values are empty cells. Row order and `row_id` values are random and carry
no information. Held-out labels are not present anywhere in this environment.

## Deliverable

Write `/workspace/output/predictions.csv` with header `row_id,probability` and exactly
one row per `row_id` in `test.csv`. Each probability must be a finite number in [0, 1]
(not a percentage). Rows may be in any order. Missing, duplicated, extra, non-numeric
or out-of-range entries make the whole submission invalid; nothing is clipped or repaired.

## Scoring

The reward is held-out AUROC of your probabilities (0.5 is chance; no pass threshold).
Average precision and Brier score are also recorded, so calibrated probabilities matter.
An invalid or missing file is recorded as an invalid submission with reward 0.

## Environment

{tools}. The sandbox has {cpus:g} CPU(s) and {memory_mb} MB of memory. {network}
Work with what is installed; do not try to install software or download models.
You may write scratch files anywhere under `/workspace`.
"""


def _data_readme(public):
    groups = '\n'.join(f'- `{k}`: {len(v)} features' for k, v in public['feature_groups'].items())
    return f"""# Data dictionary

- One row per patient; `row_id` is a random identifier for this task only.
- `label` (train only): {public['endpoint']}
- Feature columns are numeric, rounded to {public['significant_digits']} significant digits; empty cells are missing values.
- Training rows: {len(public['train'])}; test rows: {len(public['test'])}; features: {len(public['feature_names'])}.

## Feature groups (overlapping; see feature_groups.json)

{groups}
"""


def _dockerfile(base_image, tabpfn_checkpoint):
    lines = [f'FROM {base_image}']
    if base_image == DEFAULT_BASE_IMAGE:
        # Dependencies go into a project virtualenv, never the image's system Python.
        # Installed at build time only; the agent runtime gets PIP_NO_INDEX and no package network.
        lines += [f'RUN python3 -m venv {VENV} && {VENV}/bin/python -m pip install --no-cache-dir '
                  + ' '.join(DEFAULT_PACKAGES),
                  f'ENV PATH={VENV}/bin:$PATH VIRTUAL_ENV={VENV}']
    # A custom base image must already put its own venv/conda environment first on PATH.
    lines += ['ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \\',
              '    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TABPFN_DISABLE_TELEMETRY=1']
    checks = ("import sys; assert sys.prefix not in ('/usr', '/usr/local'), "
              "'python3 on PATH must be a project environment, not system Python'; "
              'import numpy, scipy, pandas, sklearn')
    if tabpfn_checkpoint:
        lines.append(f'ENV TABPFN_MODEL_CACHE_DIR={os.path.dirname(tabpfn_checkpoint)}')
        checks += '; import tabpfn, os; assert os.path.isfile(' + repr(tabpfn_checkpoint) + ')'
    # Fail the image build (closed) if the declared runtime is incomplete.
    lines.append(f'RUN python3 -c "{checks}"')
    lines += ['WORKDIR /workspace', 'COPY data/ /workspace/data/',
              'RUN chmod -R a-w /workspace/data && mkdir -p /workspace/output && chmod 0777 /workspace/output']
    return '\n'.join(lines) + '\n'


def _task_toml(public, cpus, memory_mb, agent_allowed_hosts):
    agent = [f'timeout_sec = {AGENT_TIMEOUT_SEC}']
    if not agent_allowed_hosts:
        # Fail closed: an in-sandbox harness then cannot reach its model API either.
        agent.append('network_mode = "no-network"')
    else:
        for host in agent_allowed_hosts:
            if not re.fullmatch(r'[a-z0-9.-]+', host):
                raise ValueError(f'invalid allowed host {host!r}')
        agent += ['network_mode = "allowlist"', 'allowed_hosts = ' + json.dumps(list(agent_allowed_hosts))]
    return '\n'.join([
        'schema_version = "1.4"',
        '# Only the agent output folder is carried into the separate verifier sandbox.',
        'artifacts = ["/workspace/output"]',
        '',
        '[metadata]',
        'category = "scientific-prediction"',
        f'tags = ["pcnsl", "tabular", "mutation-prediction", "{public["gene"].lower()}"]',
        f'gene = "{public["gene"]}"',
        f'fold = {public["fold"]}',
        '',
        '[agent]', *agent,
        '',
        '[verifier]',
        f'timeout_sec = {VERIFIER_TIMEOUT_SEC}',
        '# Held-out labels in tests/ reach only a fresh verifier sandbox, never the agent sandbox.',
        'environment_mode = "separate"',
        'network_mode = "no-network"',
        '',
        '[environment]',
        f'cpus = {cpus}',
        f'memory_mb = {memory_mb}',
        'storage_mb = 4096',
        'workdir = "/workspace"',
        'build_timeout_sec = 1200.0',
    ]) + '\n'


def export_task(public, gold, out_dir, *, task_id=None, base_image=DEFAULT_BASE_IMAGE,
                tabpfn_checkpoint=None, agent_allowed_hosts=None, cpus=2, memory_mb=4096):
    """Write one task folder under ``out_dir``; refuse to overwrite. Returns its Path."""
    _check_payloads(public, gold)
    if tabpfn_checkpoint is not None:
        if base_image == DEFAULT_BASE_IMAGE:
            raise ValueError('TabPFN requires a prebuilt base_image containing tabpfn and its checkpoint')
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', tabpfn_checkpoint) or '..' in tabpfn_checkpoint:
            raise ValueError('tabpfn_checkpoint must be an absolute path inside the image')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:@-]*', base_image):
        raise ValueError('invalid base image reference')
    task_id = task_id or f"pcnsl-{public['gene'].lower()}-fold{public['fold']}"
    if not TASK_ID.fullmatch(task_id):
        raise ValueError('task_id must be lowercase letters, digits and hyphens')
    out_dir = Path(out_dir)
    final = out_dir / task_id
    if os.path.lexists(final):
        raise FileExistsError(f'{final} already exists; refusing to overwrite')
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / f'.{task_id}.partial-{os.getpid()}'
    if os.path.lexists(staging):
        raise FileExistsError(f'{staging} already exists; remove the stale partial export first')
    staging.mkdir()
    try:
        names = public['feature_names']
        files = {
            'instruction.md': _instruction(public, tabpfn_checkpoint, cpus, memory_mb, agent_allowed_hosts),
            'task.toml': _task_toml(public, cpus, memory_mb, agent_allowed_hosts),
            'environment/Dockerfile': _dockerfile(base_image, tabpfn_checkpoint),
            'environment/data/train.csv': _csv(['row_id', 'label', *names],
                                               ([r['row_id'], r['label'], *r['x']] for r in public['train'])),
            'environment/data/test.csv': _csv(['row_id', *names], ([r['row_id'], *r['x']] for r in public['test'])),
            'environment/data/feature_groups.json': json.dumps(public['feature_groups'], indent=2) + '\n',
            'environment/data/README.md': _data_readme(public),
            'tests/gold.json': json.dumps(gold, indent=2, sort_keys=True) + '\n',
            'tests/grade.py': grader_source(),
            'tests/test.sh': '#!/bin/bash\nset -u\nexec python3 -I /tests/grade.py\n',
            'solution/prevalence_baseline.py': ORACLE,
            'solution/solve.sh': ('#!/bin/bash\nset -eu\n'
                                  'python3 -I /solution/prevalence_baseline.py /workspace/data '
                                  '/workspace/output/predictions.csv\n'),
        }
        for name, content in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        for name in ('tests/test.sh', 'solution/solve.sh'):
            (staging / name).chmod(0o755)
        if os.path.lexists(final):
            raise FileExistsError(f'{final} appeared during export; refusing to overwrite')
        os.rename(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


def task_manifest(task):
    """SHA-256 of every file, split by who may see it (for provenance records)."""
    task = Path(task)
    rows = {}
    for path in sorted(task.rglob('*')):
        if path.is_file():
            rel = path.relative_to(task).as_posix()
            audience = ('agent' if rel == 'instruction.md' or rel.startswith('environment/')
                        else 'verifier' if rel.startswith('tests/') else 'oracle' if rel.startswith('solution/')
                        else 'platform')
            rows[rel] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'audience': audience}
    return rows


def _write_new(path, payload):
    path = Path(path)
    with open(path, 'x', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    fold = sub.add_parser('fold', help='split a dataset JSON into public/gold/crosswalk JSON (data host only)')
    fold.add_argument('--dataset', type=Path, required=True)
    fold.add_argument('--gene', required=True)
    fold.add_argument('--fold', type=int, required=True)
    fold.add_argument('--seed', type=int, default=DEFAULT_SEED)
    fold.add_argument('--private-dir', type=Path, required=True)
    task = sub.add_parser('task', help='write a Harbor task folder from public + gold JSON')
    task.add_argument('--public', type=Path, required=True)
    task.add_argument('--gold', type=Path, required=True)
    task.add_argument('--out', type=Path, required=True)
    task.add_argument('--task-id')
    task.add_argument('--base-image', default=DEFAULT_BASE_IMAGE)
    task.add_argument('--tabpfn-checkpoint')
    task.add_argument('--agent-allowed-host', action='append', dest='hosts')
    args = parser.parse_args(argv)
    if args.command == 'fold':
        dataset = json.loads(args.dataset.read_text())
        public, gold, crosswalk = build_eval_fold(dataset, args.gene, args.fold, seed=args.seed)
        args.private_dir.mkdir(parents=True, exist_ok=True)
        stem = f'{args.gene.lower()}-fold{args.fold}'
        for suffix, payload in (('public', public), ('gold', gold), ('crosswalk', crosswalk)):
            _write_new(args.private_dir / f'{stem}.{suffix}.json', payload)
        print(f'Wrote {stem} public/gold/crosswalk to {args.private_dir}; keep gold and crosswalk private.')
    else:
        path = export_task(json.loads(args.public.read_text()), json.loads(args.gold.read_text()), args.out,
                           task_id=args.task_id, base_image=args.base_image,
                           tabpfn_checkpoint=args.tabpfn_checkpoint, agent_allowed_hosts=args.hosts)
        print(f'Exported {path}; no upload or hosted run performed.')


if __name__ == '__main__':
    main()
