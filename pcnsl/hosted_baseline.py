"""Fixed descriptive baseline using only the verified hosted release on FAC.

Patient-level inputs and predictions remain in process memory on the data host.
Only aggregate metrics are written. No model APIs, internal cohort or Box inputs.
"""
import argparse
from collections import defaultdict
import csv
import json
import math
import os
from pathlib import Path
import re
import sys
import time

try:
    from .inspect_hosted import SPATIAL_METRICS, sha, subject
except ImportError:
    from inspect_hosted import SPATIAL_METRICS, sha, subject


def load_hosted_rows(root):
    root=Path(root)
    mutation_paths=list(root.rglob('ucsf500_mutations.csv'))
    if len(mutation_paths)!=1:
        raise ValueError('Expected exactly one mutation table')
    grouped=defaultdict(list)
    with mutation_paths[0].open(newline='',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            key=subject(row.get('patientdurablekey'))
            if not key: raise ValueError('Missing patient key')
            grouped[key].append(row)
    features=defaultdict(list)
    for path in root.rglob('*_FLAIR_SummaryLesions.csv'):
        if path.is_symlink(): continue
        key=next((subject(p) for p in path.parts if re.fullmatch(r'sub-[A-Za-z0-9]+',p)),None)
        if key and 'lesions_SummaryLesions' in path.parts: features[key].append(path)
    matrix=[]; labels={gene:[] for gene in ['MYD88','CD79B','IRF4']}
    excluded=defaultdict(int)
    for key in sorted(grouped):
        records=grouped[key]
        dates={r.get('tumorcollecteddate','').strip() for r in records}
        if len(dates)!=1 or '' in dates:
            excluded['ambiguous_or_missing_collection_date']+=1;continue
        paths=features.get(key,[])
        if not paths:
            excluded['missing_flair_summary']+=1;continue
        if len(paths)!=1:
            raise ValueError('Ambiguous patient-to-scan feature mapping')
        values={}
        with paths[0].open(newline='',encoding='utf-8-sig') as stream:
            reader=csv.reader(stream);header=next(reader)
            if len(header)!=2 or header[0].strip().lower() not in {'label','metric','','unnamed: 0'} or header[1].strip().lower() not in {'value','0'}:
                raise ValueError('Unrecognized feature schema')
            for row in reader:
                if row and row[0] in SPATIAL_METRICS:
                    if len(row)!=2 or row[0] in values:raise ValueError('Malformed or duplicate feature')
                    values[row[0]]=float(row[1])
        if len(values)!=len(SPATIAL_METRICS) or not all(math.isfinite(v) for v in values.values()):
            excluded['incomplete_or_nonfinite_spatial_features']+=1;continue
        matrix.append([values[m] for m in SPATIAL_METRICS])
        for gene in labels:
            positive=any(gene in re.split(r'[;,|/\s]+',str(r.get('gene','')).strip().upper())
                         and str(r.get('reportedalteration','')).strip().lower()=='true'
                         and str(r.get('variantclassification','')).strip().lower() in {'pathogenic','likely pathogenic'}
                         and str(r.get('geneticorigin','')).strip().lower()!='not detected' for r in records)
            labels[gene].append(int(positive))
    summary={'subjects_with_mutation_records':len(grouped),'eligible_subjects':len(matrix),
             'exclusions':dict(excluded),'features':list(SPATIAL_METRICS),
             'mutation_table_sha256':sha(mutation_paths[0]),
             'clinical_scan_specimen_pairing_verified':False,
             'endpoint':'Reported qualifying alteration versus no qualifying report among mutation-record subjects. Not biological wild type or proof of complete assay coverage.'}
    return matrix,labels,summary


def evaluate_fixed(matrix, labels, seeds=(11,23,37)):
    import numpy as np
    import sklearn
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    X=np.asarray(matrix,dtype=float)
    if X.ndim!=2 or not len(X) or not np.isfinite(X).all():
        raise ValueError('Expected audited finite patient-level feature matrix')
    runs=[]; excluded={}
    for gene,raw in labels.items():
        y=np.asarray(raw,dtype=int)
        if len(y)!=len(X) or not set(y).issubset({0,1}):raise ValueError('Invalid labels')
        positive=int(y.sum()); negative=len(y)-positive
        if gene not in {'MYD88','CD79B'} or min(positive,negative)<5:
            excluded[gene]={'positive':positive,'no_qualifying_report':negative,
                            'reason':'Outside prespecified two-target run or fewer than five patients in one class'}
            continue
        for seed in seeds:
            predictions={name:np.full(len(y),np.nan) for name in ['training_prevalence','spatial_logreg']}
            seen=np.zeros(len(y),dtype=int)
            fold_sizes=[]
            for train,test in StratifiedKFold(n_splits=5,shuffle=True,random_state=seed).split(X,y):
                if set(train)&set(test) or len(np.unique(y[train]))!=2 or len(np.unique(y[test]))!=2:
                    raise ValueError('Invalid patient split')
                # Each row is one unique release patient; groups never span rows.
                seen[test]+=1
                predictions['training_prevalence'][test]=float(y[train].mean())
                model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),
                                    LogisticRegression(C=1.0,solver='liblinear',max_iter=1000,random_state=seed))
                model.fit(X[train],y[train])
                index=list(model[-1].classes_).index(1)
                predictions['spatial_logreg'][test]=model.predict_proba(X[test])[:,index]
                fold_sizes.append({'train':len(train),'test':len(test),'train_positive':int(y[train].sum()),'test_positive':int(y[test].sum())})
            if not np.all(seen==1):raise ValueError('Each patient must have exactly one out-of-fold prediction')
            for name,p in predictions.items():
                if not np.isfinite(p).all() or (p<0).any() or (p>1).any():raise ValueError('Invalid predictions')
                runs.append({'gene':gene,'seed':seed,'baseline':name,'patients':len(y),
                             'positive':positive,'no_qualifying_report':negative,
                             'pooled_oof_auroc':float(roc_auc_score(y,p)),
                             'pooled_oof_average_precision':float(average_precision_score(y,p)),
                             'pooled_oof_brier':float(brier_score_loss(y,p)),
                             'fold_sizes':fold_sizes})
    return {'runs':runs,'excluded_targets':excluded,'versions':{'numpy':np.__version__,'scikit_learn':sklearn.__version__},
            'design':{'seeds':list(seeds),'folds':5,'hyperparameter_search':False,
                      'features':len(X[0]),'unique_patient_row_unit':True,'train_fold_only_imputation_and_scaling':True,
                      'logreg':{'C':1.0,'solver':'liblinear','max_iter':1000}},
            'interpretation':'Fixed descriptive internal cross-validation. No confidence intervals, independent validation, clinical utility or frontier-model failure claim.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    os.umask(0o077)
    start=time.monotonic()
    try:
        X,labels,summary=load_hosted_rows(args.root)
        report=evaluate_fixed(X,labels)
        report.update(source_summary=summary,elapsed_seconds=time.monotonic()-start,
                      code_sha256=sha(Path(__file__)),source_kind='Actual hosted v1.0 release only; no Box or internal cohort inputs')
        with args.out.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
        print(json.dumps({'complete':True,'patients':summary['eligible_subjects'],'aggregate_runs':len(report['runs'])}))
    except Exception as exc:
        print(json.dumps({'complete':False,'error_type':type(exc).__name__}))
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
