"""Comparator estimators for causal_ate: SATT with a 95% interval for every dataset under INPUT_DIR.

    python3 estimate.py METHOD INPUT_DIR OUTPUT_DIR      METHOD in {dr_att, ols, naive}

dr_att  doubly robust (augmented IPW) estimator of the effect on the treated with 5-fold cross-fitting;
        nuisance models: control outcome regression E[Y | X, Z=0] and propensity P(Z=1 | X), each the
        average of a gradient-boosted model and a linear model (ridge / logistic); influence-function
        standard error (Chernozhukov et al. 2018, Econometrics Journal 21:C1-C68, section 5.1, ATT score).
ols     linear regression of Y on Z and the covariates; robust (HC1) standard error of the Z coefficient.
naive   difference in mean outcome between treated and controls; Welch standard error.

Writes OUTPUT_DIR/estimates.json in the task's format. Uses numpy, pandas and scikit-learn only.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 20261114
Z95 = 1.959963984540054
CLIP = 0.99
LOG_HINT = ('bun', 'creatinine', 'glucose', 'platelets', 'wbc', 'urine')


def design(df):
    X = df.drop(columns=['z', 'y']).copy()
    for c in X.columns:
        if any(h in c for h in LOG_HINT):
            X[c] = np.log1p(X[c].clip(lower=0))
    if 'icu_type' in X:
        icu = X.pop('icu_type')
        for k in (2, 3, 4):
            X[f'icu{k}'] = (icu == k).astype(float)
    return X.to_numpy(float)


def dr_att(X, z, y):
    n = len(y)
    g0 = np.zeros(n)
    e = np.zeros(n)
    folds = StratifiedKFold(5, shuffle=True, random_state=SEED)
    for train, test in folds.split(X, z):
        ctrl = train[z[train] == 0]
        gb = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                           min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
        lin = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 13)))
        gb.fit(X[ctrl], y[ctrl])
        lin.fit(X[ctrl], y[ctrl])
        g0[test] = 0.5 * gb.predict(X[test]) + 0.5 * lin.predict(X[test])
        gc = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                            min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
        lc = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
        gc.fit(X[train], z[train])
        lc.fit(X[train], z[train])
        e[test] = 0.5 * gc.predict_proba(X[test])[:, 1] + 0.5 * lc.predict_proba(X[test])[:, 1]
    e = np.clip(e, 1 - CLIP, CLIP)
    p = z.mean()
    r = y - g0
    w = (1 - z) * e / (1 - e)
    theta = (np.sum(z * r) - np.sum(w * r)) / np.sum(z)
    psi = (z * (r - theta) - w * r) / p
    se = psi.std(ddof=1) / np.sqrt(n)
    return theta, se


def ols(X, z, y):
    D = np.column_stack([np.ones(len(y)), z, (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1)])
    beta, *_ = np.linalg.lstsq(D, y, rcond=None)
    resid = y - D @ beta
    bread = np.linalg.pinv(D.T @ D)
    meat = (D * resid[:, None] ** 2).T @ D
    cov = bread @ meat @ bread * len(y) / (len(y) - D.shape[1])
    return beta[1], np.sqrt(cov[1, 1])


def naive(X, z, y):
    a, b = y[z == 1], y[z == 0]
    return a.mean() - b.mean(), np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))


METHODS = {'dr_att': dr_att, 'ols': ols, 'naive': naive}


def main(method, input_dir, output_dir):
    fn = METHODS[method]
    results = {}
    for d in sorted(Path(input_dir).iterdir()):
        if not (d / 'data.csv').is_file():
            continue
        df = pd.read_csv(d / 'data.csv')
        z, y = df['z'].to_numpy(int), df['y'].to_numpy(float)
        est, se = fn(design(df), z, y)
        results[d.name] = {'estimate': float(est), 'ci_lower': float(est - Z95 * se), 'ci_upper': float(est + Z95 * se)}
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / 'estimates.json').write_text(json.dumps({'estimand': 'SATT', 'datasets': results}, indent=1) + '\n')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
