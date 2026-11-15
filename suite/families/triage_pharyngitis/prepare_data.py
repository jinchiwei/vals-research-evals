"""Data checks, patient-level split and the prepared public/hidden trees for triage_pharyngitis.

    python -m suite.families.triage_pharyngitis.prepare_data [--data /home/jkwei/data/vals-suite/triage_pharyngitis]

Reads   DATA/extracted/excel.xlsx and DATA/extracted/data_image_pharyngitis_nature/
Writes  DATA/prepared/public/dev/{images/<case>.jpg, patients.csv, labels.csv}   (agent-visible)
        DATA/prepared/hidden/cohort/input/{images/<case>.jpg, patients.csv}      (verifier only)
        DATA/prepared/hidden/cohort/reference/labels.csv                         (verifier only)
        DATA/prepared/private/id_map.csv                                        (never exported)
        suite/families/triage_pharyngitis/split/{split.json, data_check.json}   (IDs, hashes, aggregates)

Split: seed 20261114, patient level (one image per patient), 180 hidden patients, stratified jointly by
primary label and capture device. Case IDs are re-drawn so they do not reveal the release's patient_ID.
All images are written without EXIF/XMP/comment metadata (216 release images carry GPS coordinates).
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from . import records

SEED = 20261114
N_HIDDEN = 180
DEFAULT_DATA = Path('/home/jkwei/data/vals-suite/triage_pharyngitis')
FAMILY_DIR = Path(__file__).resolve().parent
PATIENT_COLUMNS = ('case_id', 'age', 'sex', *records.SYMPTOM_COLUMNS)


def case_id(patient_id):
    return 'p' + hashlib.sha256(f'triage_pharyngitis-{SEED}-{patient_id}'.encode()).hexdigest()[:10]


def sha_list(items):
    return hashlib.sha256('\n'.join(map(str, items)).encode()).hexdigest()


def image_stats(path):
    from PIL import Image
    from scipy import ndimage
    im = Image.open(path)
    w, h = im.size
    g = np.asarray(im.convert('L').resize((256, max(1, round(256 * h / w)))), dtype=float)
    return {'width': w, 'height': h, 'format': im.format, 'mode': im.mode, 'bytes': Path(path).stat().st_size,
            'mean_luma': float(g.mean()), 'laplacian_var_256': float(ndimage.laplace(g).var())}


def q(values, ps=(0, 5, 25, 50, 75, 95, 100)):
    return {f'p{p}': float(np.percentile(values, p)) for p in ps}


def data_checks(table, stats, devices):
    import pandas as pd
    s = pd.DataFrame(stats).T
    t = table.loc[s.index]
    ct = {}
    for col in ('sex', 'age_band'):
        ct[col] = {str(k): {'n': int(v.size), 'bacterial_primary': int(t.loc[v.index, 'label'].sum())}
                   for k, v in t.groupby(col)['label']}
    dev = pd.Series(devices)
    ct['device'] = {k: {'n': int((dev == k).sum()), 'bacterial_primary': int(t.loc[dev[dev == k].index, 'label'].sum())}
                    for k in sorted(dev.unique())}
    return {
        'n_rows_spreadsheet': int(len(table)), 'n_images': int(len(s)),
        'patients_without_image': sorted(int(p) for p in set(table.index) - set(s.index)),
        'images_per_patient': 'exactly one (one folder per patient, one file per folder)',
        'image_formats': {str(k): int(v) for k, v in s['format'].value_counts().items()},
        'image_modes': {str(k): int(v) for k, v in s['mode'].value_counts().items()},
        'width_px': q(s['width'].astype(float)), 'height_px': q(s['height'].astype(float)),
        'min_side_lt_224': int((s[['width', 'height']].astype(float).min(axis=1) < 224).sum()),
        'file_bytes': q(s['bytes'].astype(float)), 'mean_luma_0_255': q(s['mean_luma'].astype(float)),
        'sharpness_laplacian_var_at_256px': q(s['laplacian_var_256'].astype(float)),
        'symptom_prevalence': {c: round(float(table[c].mean()), 4) for c in records.SYMPTOM_COLUMNS},
        'missing_values': {'symptoms': int(table[list(records.SYMPTOM_COLUMNS)].isna().sum().sum()),
                           'age': int(table['age'].isna().sum()), 'sex': int(table['sex'].isna().sum())},
        'age': {**q(table['age'].astype(float)), 'mean': float(table['age'].mean())},
        'sex_counts': {k: int(v) for k, v in table['sex'].value_counts().items()},
        'votes_per_patient': {str(k): int(v) for k, v in table['n_votes'].value_counts().sort_index().items()},
        'labels': {'bacterial_primary_ge_half': int(table['label'].sum()),
                   'bacterial_strict_gt_half': int(table['label_strict'].sum()),
                   'ties': int(table['tie'].sum()), 'unanimous': int(table['unanimous'].sum()),
                   'unanimous_bacterial': int((table['unanimous'] & table['label_strict']).sum()),
                   'n': int(len(table))},
        'subgroups_with_images': ct,
        'paper_discrepancies': {
            'unanimous_cases': f"paper: 182; file: {int(table['unanimous'].sum())}",
            'votes_per_patient': f"paper: 4 to 9; file: {int(table['n_votes'].min())} to {int(table['n_votes'].max())}",
            'images': f'paper: 742; release: {len(s)} (patient 666 has no image)',
            'ties': f"paper: discrepancies re-read by an extra physician; file: {int(table['tie'].sum())} exact ties",
        },
    }


def write_csv(df, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator='\n')


def main(argv=None):
    import pandas as pd
    from sklearn.model_selection import train_test_split
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=DEFAULT_DATA)
    args = ap.parse_args(argv)
    ext = args.data / 'extracted'
    table = records.load_table(ext / 'excel.xlsx')
    img_root = ext / 'data_image_pharyngitis_nature'
    stats, devices = {}, {}
    for pid in table.index:
        p = records.image_path(img_root, pid)
        if p.is_file():
            stats[pid] = image_stats(p)
            devices[pid] = records.device_from_exif(p)
    checks = data_checks(table, stats, devices)
    usable = table.loc[sorted(stats)].copy()
    usable['device'] = pd.Series(devices)
    strata = usable['label'].astype(str) + '_' + usable['device']
    dev_ids, hid_ids = train_test_split(list(usable.index), test_size=N_HIDDEN, random_state=SEED, stratify=strata)
    dev_ids, hid_ids = sorted(dev_ids), sorted(hid_ids)
    usable['case_id'] = [case_id(p) for p in usable.index]
    if usable['case_id'].duplicated().any():
        raise RuntimeError('case id collision')

    out = args.data / 'prepared'
    if out.exists():
        raise SystemExit(f'{out} exists; remove it to rebuild')
    actions = {}
    for part, ids in (('dev', dev_ids), ('hidden', hid_ids)):
        sub = usable.loc[ids].sort_values('case_id')
        base = out / 'public' / 'dev' if part == 'dev' else out / 'hidden' / 'cohort' / 'input'
        for pid, cid in zip(sub.index, sub['case_id']):
            actions[cid] = records.write_clean_image(records.image_path(img_root, pid), base / 'images' / f'{cid}.jpg')
        write_csv(sub[list(PATIENT_COLUMNS)], base / 'patients.csv')
        if part == 'dev':
            lab = sub[['case_id', 'label', 'n_votes', 'n_bacterial_votes']].rename(columns={'label': 'bacterial'})
            write_csv(lab, out / 'public' / 'dev' / 'labels.csv')
        else:
            ref = sub[['case_id', 'label', 'label_strict', 'bacterial_fraction', 'n_votes', 'sex', 'age_band',
                       'device']].rename(columns={'label': 'bacterial', 'label_strict': 'bacterial_strict'})
            write_csv(ref, out / 'hidden' / 'cohort' / 'reference' / 'labels.csv')
    write_csv(usable[['case_id', 'patient_id']].sort_values('patient_id'), out / 'private' / 'id_map.csv')

    def summary(ids):
        s = usable.loc[ids]
        return {'n': len(ids), 'bacterial_primary': int(s['label'].sum()),
                'prevalence_primary': round(float(s['label'].mean()), 4),
                'bacterial_strict': int(s['label_strict'].sum()), 'ties': int(s['tie'].sum()),
                'female': int((s['sex'] == 'F').sum()), 'child_lt15': int((s['age_band'] == 'child_lt15').sum()),
                'device': {k: int(v) for k, v in s['device'].value_counts().sort_index().items()},
                'patient_ids_sha256': sha_list(ids),
                'case_ids_sha256': sha_list(sorted(usable.loc[ids, 'case_id']))}
    split = {'schema': 'triage_pharyngitis-split/1', 'seed': SEED, 'unit': 'patient (one image each)',
             'stratified_by': 'primary label x capture device (EXIF Make)', 'excluded': checks['patients_without_image'],
             'paper_split': 'none fixed (3-fold CV); the paper suggests its 182 unanimous cases as a test set, '
                            'not used: the file has only 8 unanimous bacterial cases',
             'development': {**summary(dev_ids), 'patient_ids': dev_ids},
             'hidden': {**summary(hid_ids), 'patient_ids': hid_ids},
             'image_actions': {k: int(v) for k, v in pd.Series(actions).value_counts().items()},
             'source_zip_sha256': '2fa6d98cbc03d8be12d974f134fdd2c1466f40a0872dc9f67300e952ec28af7d'}
    (FAMILY_DIR / 'split').mkdir(exist_ok=True)
    for name, obj in (('split.json', split), ('data_check.json', checks)):
        text = json.dumps(obj, indent=1) + '\n'
        (FAMILY_DIR / 'split' / name).write_text(text)
        (args.data / name).write_text(text)
    print(json.dumps({k: v for k, v in split.items() if k not in ('development', 'hidden')}, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in split[k].items() if kk != 'patient_ids'} for k in ('development', 'hidden')}, indent=1))


if __name__ == '__main__':
    main()
