"""Specialist comparator and oracle solution: TF-IDF character n-grams + one-vs-rest logistic regression.

Trained only on the development reports (agent-visible). C is chosen from {1, 10, 100} by 5-fold
cross-validated macro F1 on the development set; threshold 0.5. Deterministic (liblinear, fixed folds).

Usage: python label_tfidf.py DATA_DIR OUT_LABELS_JSON [CV_LOG_JSON]
  DATA_DIR holds dev_reports.csv (record_id, report, NORM, MI, STTC, CD, HYP) and hidden_reports.csv.
Standalone: standard library, numpy, scikit-learn.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import KFold
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import make_pipeline

CLASSES = ('NORM', 'MI', 'STTC', 'CD', 'HYP')
C_GRID = (1.0, 10.0, 100.0)
SEED = 20261114


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def model(c):
    return make_pipeline(
        TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 5), lowercase=True, sublinear_tf=True, min_df=2),
        OneVsRestClassifier(LogisticRegression(C=c, solver='liblinear', max_iter=1000, random_state=SEED)))


def main(data_dir, out_path, cv_log=None):
    data_dir = Path(data_dir)
    dev = read(data_dir / 'dev_reports.csv')
    hidden = read(data_dir / 'hidden_reports.csv')
    X = [r['report'] for r in dev]
    Y = np.array([[int(r[c]) for c in CLASSES] for r in dev])
    folds = list(KFold(5, shuffle=True, random_state=SEED).split(X))
    cv = {}
    for c in C_GRID:
        pred = np.zeros_like(Y)
        for tr, te in folds:
            m = model(c).fit([X[i] for i in tr], Y[tr])
            pred[te] = (m.predict_proba([X[i] for i in te]) >= 0.5).astype(int)
        cv[c] = float(f1_score(Y, pred, average='macro', zero_division=0))
    best = max(C_GRID, key=lambda c: (cv[c], -c))
    final = model(best).fit(X, Y)
    proba = final.predict_proba([r['report'] for r in hidden])
    labels = {r['record_id']: [c for j, c in enumerate(CLASSES) if proba[i, j] >= 0.5] for i, r in enumerate(hidden)}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(labels, indent=1, sort_keys=True) + '\n')
    if cv_log:
        Path(cv_log).write_text(json.dumps({'cv_macro_f1_by_C': {str(k): v for k, v in cv.items()},
                                            'chosen_C': best}, indent=1) + '\n')
    print(json.dumps({'cv_macro_f1_by_C': cv, 'chosen_C': best, 'n_hidden': len(labels)}))


if __name__ == '__main__':
    main(*sys.argv[1:])
