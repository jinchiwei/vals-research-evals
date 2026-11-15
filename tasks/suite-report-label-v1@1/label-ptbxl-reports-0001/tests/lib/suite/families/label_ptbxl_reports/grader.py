"""Family-local verifier for label_ptbxl_reports (direct-answer contract).

The shared core (suite/core/grading.py) assumes the pipeline contract: it runs the agent's run.sh on
hidden inputs. This task gives the agent the hidden reports and asks for labels directly, so no agent
code runs in the verifier. This module reads /workspace/output/labels.json, scores it against the
hidden labels and writes the same seven reward keys through suite.core.reward (vendored in tests/lib).

Imports: standard library, numpy and suite.core.reward only.

Reward keys (each 0 or 1 except quality and vs_specialist):
  ran                    labels.json exists as a regular file (not a symlink)
  valid                  JSON object, keys exactly the hidden IDs, values lists of distinct class names
  within_time            = ran (the platform stops the session at its limit and carries
                         /workspace/output as found, so a present file was written inside the session)
  clinically_acceptable  valid and every gate part met (cohort rule, DESIGN.md)
  quality                macro F1 over the 5 classes (0 if invalid)
  vs_specialist          min(1, quality / specialist macro F1)
  reward                 suite.core.reward.scalar_reward
"""
import argparse
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np

from suite.core import reward as rw

CLASSES = ('NORM', 'MI', 'STTC', 'CD', 'HYP')
GATE_MIN_KAPPA = 0.60
GATE_MACRO_F1 = 0.80
CLINICAL_THRESHOLD = (f'Cohen kappa >= {GATE_MIN_KAPPA} in each of {", ".join(CLASSES)} and macro F1 >= '
                      f'{GATE_MACRO_F1} on the hidden reports (all parts)')
PRIMARY_METRIC = 'macro F1 over the 5 diagnostic superclasses'
MAX_BYTES = 5 * 1024 * 1024
SEED = 20261114
SHARED_SANDBOX_MARKERS = ('solution', 'bundle')
# Under tests/hidden/ so suite.core.export.check_no_leak protects it.
REFERENCE = Path('hidden') / 'cohort' / 'reference' / 'labels.json'
SPECIALIST = Path('specialist') / 'labels.json'


class InfrastructureError(RuntimeError):
    pass


# ---------------------------------------------------------------------------- parsing


def read_regular(path, max_bytes=MAX_BYTES):
    """Bytes of a regular file, refusing symlinks, special files and oversize files."""
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        raise ValueError('labels.json is a symlink')
    if not stat.S_ISREG(st.st_mode):
        raise ValueError('labels.json is not a regular file')
    if st.st_size > max_bytes:
        raise ValueError(f'labels.json is larger than {max_bytes} bytes')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as f:
        return f.read(max_bytes + 1)


def _reject_constant(token):
    raise ValueError(f'non-standard JSON constant {token}')


def parse_labels(data, hidden_ids):
    """Strict parse. Returns ({id: frozenset of classes}, None) or (None, reason)."""
    try:
        obj = json.loads(data.decode('utf-8'), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as error:
        return None, f'not valid UTF-8 JSON: {str(error)[:120]}'
    if not isinstance(obj, dict):
        return None, 'top level must be a JSON object {record_id: [classes]}'
    hidden = set(hidden_ids)
    missing, extra = hidden - set(obj), set(obj) - hidden
    if missing or extra:
        return None, (f'keys must be exactly the {len(hidden)} hidden record IDs: {len(missing)} missing '
                      f'(e.g. {sorted(missing)[:3]}), {len(extra)} unknown (e.g. {sorted(extra)[:3]})')
    out = {}
    for rid in sorted(obj):
        value = obj[rid]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            return None, f'{rid}: value must be a list of class names'
        if len(set(value)) != len(value):
            return None, f'{rid}: duplicate class name'
        bad = [v for v in value if v not in CLASSES]
        if bad:
            return None, f'{rid}: unknown class {bad[0]!r} (allowed: {", ".join(CLASSES)})'
        out[rid] = frozenset(value)
    return out, None


# ---------------------------------------------------------------------------- metrics


def to_matrix(labels, ids):
    return np.array([[c in labels[i] for c in CLASSES] for i in ids], dtype=bool)


def cohen_kappa(y, p):
    """Binary Cohen's kappa. 0.0 when undefined (expected agreement 1: both raters constant)."""
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    po = float(np.mean(y == p))
    pe = float(np.mean(y) * np.mean(p) + (1 - np.mean(y)) * (1 - np.mean(p)))
    return 0.0 if pe >= 1.0 else (po - pe) / (1.0 - pe)


def f1(y, p):
    """Binary F1; 0.0 when there are no positives in either."""
    tp = int(np.sum(y & p))
    fp, fn = int(np.sum(~y & p)), int(np.sum(y & ~p))
    return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)


def cohort_metrics(Y, P):
    per = {}
    for j, c in enumerate(CLASSES):
        y, p = Y[:, j], P[:, j]
        tp, fp, fn = int(np.sum(y & p)), int(np.sum(~y & p)), int(np.sum(y & ~p))
        per[c] = {'f1': f1(y, p), 'kappa': cohen_kappa(y, p), 'tp': tp, 'fp': fp, 'fn': fn,
                  'tn': int(np.sum(~y & ~p)), 'precision': tp / (tp + fp) if tp + fp else 0.0,
                  'recall': tp / (tp + fn) if tp + fn else 0.0, 'prevalence': float(np.mean(y))}
    kappas = [per[c]['kappa'] for c in CLASSES]
    return {'per_class': per, 'macro_f1': float(np.mean([per[c]['f1'] for c in CLASSES])),
            'min_kappa': float(min(kappas)), 'worst_kappa_class': CLASSES[int(np.argmin(kappas))],
            'macro_kappa': float(np.mean(kappas)), 'exact_match': float(np.mean(np.all(Y == P, axis=1))),
            'hamming_loss': float(np.mean(Y != P)), 'n': int(len(Y))}


def bootstrap(Y, P, n_boot=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    mf, mk = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, len(Y), len(Y))
        m = cohort_metrics(Y[idx], P[idx])
        mf.append(m['macro_f1'])
        mk.append(m['min_kappa'])
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]  # noqa: E731
    return {'macro_f1_ci95': q(mf), 'min_kappa_ci95': q(mk), 'n_boot': n_boot, 'seed': seed}


def gate(m):
    return {f'kappa_ge_{GATE_MIN_KAPPA}_every_class': m['min_kappa'] >= GATE_MIN_KAPPA,
            f'macro_f1_ge_{GATE_MACRO_F1}': m['macro_f1'] >= GATE_MACRO_F1}


def grade_labels(path, reference, with_ci=True):
    """Grade one labels.json against the reference {id: [classes]}. Never raises on bad agent output."""
    ids = sorted(reference)
    out = {'ran': False, 'valid': False, 'acceptable': False, 'quality': 0.0, 'reason': None,
           'gate': {}, 'metrics': {}}
    path = Path(path)
    if not os.path.lexists(path):
        out['reason'] = 'labels.json missing'
        return out
    try:
        data = read_regular(path)
    except (OSError, ValueError) as error:
        out['reason'] = f'unreadable: {error}'
        return out
    out['ran'] = True
    labels, reason = parse_labels(data, ids)
    if labels is None:
        out['reason'] = f'invalid: {reason}'
        return out
    ref = {i: frozenset(v) for i, v in reference.items()}
    Y, P = to_matrix(ref, ids), to_matrix(labels, ids)
    m = cohort_metrics(Y, P)
    if with_ci:
        m['bootstrap'] = bootstrap(Y, P)
    g = gate(m)
    out.update(valid=True, quality=float(m['macro_f1']), gate=g, acceptable=all(g.values()), metrics=m)
    if not out['acceptable']:
        out['reason'] = 'gate parts not met: ' + ', '.join(k for k, ok in g.items() if not ok)
    return out


def grade(labels_path, tests_dir):
    """(reward dict, metrics dict) for one submission, using tests/reference and tests/specialist."""
    tests_dir = Path(tests_dir)
    reference = json.loads((tests_dir / REFERENCE).read_text())
    config = json.loads((tests_dir / 'task_config.json').read_text())
    if sorted(reference) != sorted(config['hidden_ids']):
        raise InfrastructureError('reference IDs differ from task_config hidden_ids')
    agent = grade_labels(labels_path, reference)
    spec = grade_labels(tests_dir / SPECIALIST, reference)
    if not spec['valid']:
        raise InfrastructureError(f"stored specialist labels invalid: {spec['reason']}")
    ran = float(agent['ran'])
    reward = rw.build_reward(ran=ran, valid=float(agent['valid']), within_time=ran,
                             clinically_acceptable=float(agent['acceptable']), quality=agent['quality'],
                             specialist_quality=spec['quality'])
    metrics = {'schema': 'suite-metrics/1', 'family': config.get('family'), 'task_id': config.get('task_id'),
               'grading': 'direct_answer', 'clinical_threshold': CLINICAL_THRESHOLD,
               'primary_metric': PRIMARY_METRIC, 'n_hidden': len(reference),
               'within_time_rule': 'within_time = ran: the platform enforces the agent session limit',
               'agent': agent, 'gate': agent['gate'],
               'gate_fraction': (sum(agent['gate'].values()) / len(agent['gate'])) if agent['gate'] else 0.0,
               'specialist': {'name': config.get('specialist_name'), **spec,
                              'gate_fraction': sum(spec['gate'].values()) / len(spec['gate']),
                              'reward_if_on_time': float(spec['acceptable'])},
               'simple_comparator': config.get('simple_comparator_summary')}
    try:
        metrics['labels_mtime_epoch'] = os.lstat(labels_path).st_mtime
    except OSError:
        pass
    return reward, metrics


def summary_line(reward, metrics):
    a = metrics['agent']
    m = a.get('metrics') or {}
    return json.dumps({'reward': reward, 'reason': a['reason'], 'gate': a['gate'],
                       'macro_f1': m.get('macro_f1'), 'min_kappa': m.get('min_kappa'),
                       'per_class_f1': {c: round(v['f1'], 4) for c, v in (m.get('per_class') or {}).items()},
                       'per_class_kappa': {c: round(v['kappa'], 4) for c, v in (m.get('per_class') or {}).items()},
                       'specialist_macro_f1': metrics['specialist']['quality']}, allow_nan=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description='label_ptbxl_reports verifier (direct answer).')
    parser.add_argument('--tests', default='/tests')
    parser.add_argument('--labels', default='/workspace/output/labels.json')
    parser.add_argument('--logs', default='/logs/verifier')
    parser.add_argument('--sandbox-root', default='/', help="'none' disables the shared-sandbox check (local runs)")
    args = parser.parse_args(argv)
    try:
        if args.sandbox_root != 'none':
            found = [m for m in SHARED_SANDBOX_MARKERS if os.path.lexists(os.path.join(args.sandbox_root, m))]
            if found:
                raise InfrastructureError('refusing to score: verifier appears to share the agent sandbox')
        rw.write_provisional_zero(args.logs)
        reward, metrics = grade(args.labels, args.tests)
        rw.write_reward(args.logs, reward, metrics)
        print(summary_line(reward, metrics)[:18000])
    except InfrastructureError as error:
        print(json.dumps({'infrastructure_error': str(error)}))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
