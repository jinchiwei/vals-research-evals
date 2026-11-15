"""Simple comparator: keyword rules (German, English, Swedish stems per superclass).

Written from domain knowledge and the development reports only (one refinement pass on development
errors, then frozen before any hidden scoring); no negation or hedge handling.
NORM is assigned when a 'normal ECG' phrase is present, or when no other class fires.

Usage: python label_keywords.py DATA_DIR OUT_LABELS_JSON [DEV_REPORT_JSON]
"""
import csv
import json
import re
import sys
from pathlib import Path

CLASSES = ('NORM', 'MI', 'STTC', 'CD', 'HYP')
RULES = {
    'NORM': [r'normales? ekg', r'normal ecg', r'normalt ekg', r'within normal limits', r'normal tracing'],
    'MI': [r'infarkt', r'infarct', r'myocardial infarction', r'\bami\b', r'\bimi\b', r'\basmi\b',
           r'r-progression', r'r wave progression', r'r-verlust', r'q-zacke', r'q waves?', r'narbe', r'nekrose', r'myokardschaden', r'myokardskada', r'myocardial damage',
           r'old (?:anterior|inferior|anteroseptal|lateral)'],
    'STTC': [r'st-senkung', r'st-hebung', r'st & t', r'st-t', r'st segments? (?:are |is )?(?:depressed|elevated)',
             r'st depression', r'st elevation', r't-negativ', r't-ver[aä]nderung', r't abnorm', r't waves? ',
             r'isch[aä]?emi', r'ischemi', r'ischaemi', r'repolari', r'st-s[aä]nkning', r'st-h[oö]jning',
             r't-f[oö]r[aä]ndring', r'myokardaffektion', r'non-?specific', r'unspezifisch', r'digitalis',
             r'qt', r'linksbelastung', r'strain'],
    'CD': [r'block', r'\blsb\b', r'\brsb\b', r'\blahb\b', r'\blphb\b', r'\bwpw\b', r'pr[aä]exzitation',
           r'leitungsst[oö]rung', r'conduction', r'\brbbb\b', r'\blbbb\b', r'\blafb\b', r'\blpfb\b',
           r'fascicular', r'faszikul', r'hemiblock', r'sk[aä]nkelblock', r'pre-?excitation'],
    'HYP': [r'hypertroph', r'hypertrofi', r'\blvh\b', r'\brvh\b', r'atrial enlargement', r'vorhofvergr',
            r'vorhofbelastung', r'p-?mitrale', r'p-?pulmonale', r'sokolow', r'voltages? (?:are )?high',
            r'high voltage', r'enlargement'],
}
COMPILED = {c: [re.compile(p, re.I) for p in pats] for c, pats in RULES.items()}


def label(text):
    found = [c for c in CLASSES if c != 'NORM' and any(p.search(text) for p in COMPILED[c])]
    if any(p.search(text) for p in COMPILED['NORM']) or not found:
        found = ['NORM'] + found
    return found


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main(data_dir, out_path, dev_report=None):
    data_dir = Path(data_dir)
    hidden = read(data_dir / 'hidden_reports.csv')
    labels = {r['record_id']: label(r['report']) for r in hidden}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(labels, indent=1, sort_keys=True) + '\n')
    if dev_report:
        dev = read(data_dir / 'dev_reports.csv')
        res = {}
        for c in CLASSES:
            tp = sum(1 for r in dev if r[c] == '1' and c in label(r['report']))
            fp = sum(1 for r in dev if r[c] == '0' and c in label(r['report']))
            fn = sum(1 for r in dev if r[c] == '1' and c not in label(r['report']))
            res[c] = round(2 * tp / (2 * tp + fp + fn), 4) if tp else 0.0
        Path(dev_report).write_text(json.dumps({'dev_f1': res}, indent=1) + '\n')
        print(json.dumps({'dev_f1': res}))


if __name__ == '__main__':
    main(*sys.argv[1:])
