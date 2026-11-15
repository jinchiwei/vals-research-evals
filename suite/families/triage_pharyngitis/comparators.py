"""Fit the four comparators on development patients only, write them as self-contained pipelines, run
them on the hidden cohort under suite.core.runner (grader-style wall clock, CPU, 2 threads) and grade.

    python -m suite.families.triage_pharyngitis.comparators [--data DATA] [--gpu]

(a) rule      partial McIsaac score (fever, no cough, age) -> development event rate per score (Laplace)
(b) symptoms  L2 logistic regression on 20 symptoms + age terms + sex; C by 5-fold CV log-loss
(c) image     frozen ImageNet ResNet-50 pooled features -> standardised L2 logistic regression; C by CV
(d) combined  out-of-fold image logit (5-fold within development) + symptom design -> L2 logistic stacker

Writes DATA/pipelines/<name>/ (run.sh, predict.py, model.json), DATA/comparators/<name>/{predictions.json,
metrics.json} and DATA/comparators/summary.json, plus an aggregate copy in the family's split/ folder.
Also writes the failure pipelines constant / overconfident / slow under DATA/pipelines/.
"""
import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

from . import grader
from .prepare_data import DEFAULT_DATA, FAMILY_DIR, SEED

SRC = FAMILY_DIR / 'pipeline_src'
sys.path.insert(0, str(SRC))
import predict as P  # noqa: E402

C_GRID = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0, 3.0)
RUN_SH = '''#!/bin/bash
# Entry point: run.sh INPUT_DIR OUTPUT_DIR (whole cohort). Offline; python3 from the task venv.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/predict.py" "$1" "$2"
'''


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_pipeline(dest, model):
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(SRC / 'predict.py', dest / 'predict.py')
    (dest / 'run.sh').write_text(RUN_SH)
    (dest / 'run.sh').chmod(0o755)
    (dest / 'model.json').write_text(json.dumps(model))
    return dest


def _lr_params(scaler, lr):
    return {'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(), 'coef': lr.coef_[0].tolist(),
            'intercept': float(lr.intercept_[0])}


def fit_lr(x, y, cv):
    """Standardise, choose C by CV log-loss, refit on all development rows. Returns params, C, OOF probs."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    best = None
    for c in C_GRID:
        pipe = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=5000))
        oof = cross_val_predict(pipe, x, y, cv=cv, method='predict_proba')[:, 1]
        eps = 1e-12
        ll = -np.mean(y * np.log(oof + eps) + (1 - y) * np.log(1 - oof + eps))
        if best is None or ll < best[0]:
            best = (ll, c, oof)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(C=best[1], max_iter=5000)).fit(x, y)
    return _lr_params(pipe[0], pipe[1]), best[1], best[2]


def internal_cv(y, oof):
    from suite.core import metrics as M
    return {'auroc': M.auroc(y, oof), 'brier': M.brier(y, oof), 'ece': M.expected_calibration_error(y, oof),
            'calibration': M.calibration_slope_intercept(y, oof),
            'specificity_at_sens_0_85': M.specificity_at_sensitivity(y, oof, 0.85)['specificity']}


def fit_all(data, use_gpu):
    from sklearn.model_selection import StratifiedKFold
    pub = data / 'prepared' / 'public' / 'dev'
    rows = sorted(read_csv(pub / 'patients.csv'), key=lambda r: r['case_id'])
    lab = {r['case_id']: int(r['bacterial']) for r in read_csv(pub / 'labels.csv')}
    y = np.asarray([lab[r['case_id']] for r in rows])
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    models, cvres = {}, {}

    score = P.mcisaac_partial(rows)
    table = {s: (int(y[score == s].sum()) + 1) / (int((score == s).sum()) + 2) for s in range(-1, 4)}
    models['rule'] = {'kind': 'rule', 'probability_by_score': {str(k): v for k, v in table.items()},
                      'score_counts': {str(s): int((score == s).sum()) for s in range(-1, 4)}}
    oof = np.zeros(len(y))
    for tr, te in cv.split(score, y):
        t = {s: (int(y[tr][score[tr] == s].sum()) + 1) / (int((score[tr] == s).sum()) + 2) for s in range(-1, 4)}
        oof[te] = [t[s] for s in score[te]]
    cvres['rule'] = internal_cv(y, oof)

    xt = P.tabular(rows)
    params, c, oof = fit_lr(xt, y, cv)
    models['symptoms'] = {'kind': 'symptoms', 'symptoms': params, 'C': c}
    cvres['symptoms'] = internal_cv(y, oof)

    feat_path = data / 'features' / 'dev_resnet50.npy'
    if feat_path.is_file():
        xi = np.load(feat_path)
    else:
        t0 = time.monotonic()
        xi = P.image_features([pub / 'images' / f"{r['case_id']}.jpg" for r in rows],
                              weights=str(data / 'models' / 'resnet50_imagenet1k_v2.pth'), batch=32,
                              device='cuda' if use_gpu else 'cpu')
        feat_path.parent.mkdir(exist_ok=True)
        np.save(feat_path, xi)
        print(f'dev features {xi.shape} in {time.monotonic() - t0:.1f}s', flush=True)
    params_i, ci, oof_i = fit_lr(xi, y, cv)
    models['image'] = {'kind': 'image', 'image': params_i, 'C': ci}
    cvres['image'] = internal_cv(y, oof_i)

    # Stacker: OOF image logit (inner CV with the chosen C) + symptom design. The stacker's own CV
    # estimate reuses those OOF logits, so it is slightly optimistic (C for the image head was chosen
    # on all development folds).
    img_logit_oof = np.log(oof_i / (1 - oof_i))
    xs = np.column_stack([img_logit_oof, xt])
    params_s, cs, oof_s = fit_lr(xs, y, cv)
    models['combined'] = {'kind': 'combined', 'image': params_i, 'stacker': params_s, 'C_image': ci, 'C_stacker': cs}
    cvres['combined'] = internal_cv(y, oof_s)

    prev = float(y.mean())
    models['constant'] = {'kind': 'constant', 'probability': prev}
    models['overconfident'] = {'kind': 'overconfident', 'symptoms': params, 'temperature_multiplier': 6.0,
                               'centre': prev}
    models['slow'] = {'kind': 'slow', 'symptoms': params, 'sleep_seconds': None}   # set per run
    return models, cvres, {'n': int(len(y)), 'n_bacterial': int(y.sum())}


def run_on_hidden(pipe_dir, data, work, time_limit, threads=2):
    from suite.core.runner import run_pipeline
    hidden = data / 'prepared' / 'hidden' / 'cohort'
    out = work / 'out'
    home = work / 'home'
    for d in (out, home):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    res = run_pipeline(pipe_dir, hidden / 'input', out, time_limit, home_dir=home, log_path=work / 'run.log',
                       path=str(Path(sys.executable).parent) + ':/usr/bin:/bin', threads=threads,
                       extra_env={'TRIAGE_WEIGHTS': str(data / 'models' / 'resnet50_imagenet1k_v2.pth')})
    grade = None
    if (out / 'predictions.json').exists():
        grade = grader.grade_case(out, hidden / 'input', hidden / 'reference')
    return res.to_dict(), grade, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=DEFAULT_DATA)
    ap.add_argument('--gpu', action='store_true')
    ap.add_argument('--only', nargs='*')
    args = ap.parse_args(argv)
    data = args.data
    models, cvres, dev = fit_all(data, args.gpu)
    n_hidden = len(read_csv(data / 'prepared' / 'hidden' / 'cohort' / 'input' / 'patients.csv'))
    limit = grader.time_limit_seconds(n_hidden)
    models['slow']['sleep_seconds'] = limit + 30
    summary = {'schema': 'triage_pharyngitis-comparators/1', 'development': dev, 'time_limit_seconds': limit,
               'n_hidden': n_hidden, 'threads': 2, 'hardware': 'teal (WSL2, CPU inference)',
               'internal_cv_development': cvres, 'hidden': {}}
    for name, model in models.items():
        if args.only and name not in args.only:
            continue
        pipe = write_pipeline(data / 'pipelines' / name, model)
        work = data / 'comparators' / name
        run_limit = 20.0 if name == 'slow' else limit       # slow: prove the kill without waiting minutes
        if name == 'slow':
            model['sleep_seconds'] = 60.0
            (pipe / 'model.json').write_text(json.dumps(model))
        run, grade, out = run_on_hidden(pipe, data, work, run_limit)
        entry = {'run': {k: run[k] for k in ('wall_seconds', 'timed_out', 'exit_code')},
                 'time_limit_seconds': run_limit, 'valid': bool(grade and grade['valid'])}
        if grade and grade['valid']:
            m = grade['metrics']
            entry.update({k: m[k] for k in ('auroc', 'quality', 'brier', 'ece', 'calibration', 'operating_point',
                                            'at_referral_threshold', 'net_benefit', 'worst_subgroup',
                                            'gate_components', 'gate_fraction', 'acceptable', 'bootstrap_95',
                                            'secondary_strict_majority_label', 'mean_probability')})
            entry['subgroup_auroc'] = {col: {g: v['auroc'] for g, v in s['groups'].items()}
                                       for col, s in m['subgroups'].items()}
            (work / 'metrics.json').write_text(json.dumps(m, indent=1, default=str))
            shutil.copyfile(out / 'predictions.json', work / 'predictions.json')
        elif grade:
            entry['reason'] = grade['reason']
        summary['hidden'][name] = entry
        print(name, json.dumps({k: entry.get(k) for k in ('run', 'auroc', 'gate_fraction', 'gate_components')},
                               default=str), flush=True)
    (data / 'comparators' / 'summary.json').write_text(json.dumps(summary, indent=1, default=str))
    (FAMILY_DIR / 'split' / 'comparators_summary.json').write_text(json.dumps(summary, indent=1, default=str))


if __name__ == '__main__':
    main()
