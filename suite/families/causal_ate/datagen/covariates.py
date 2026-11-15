"""Real covariate pools for causal_ate from PhysioNet/CinC 2012 (ODC-By 1.0), never shown to the agent as code.

Development pool: the 4,000 set-A stays. Hidden pool: the 4,000 set-B stays. No stay is in both.
Covariates are values available at ICU admission or within the 48-hour window (age, sex,
weight, ICU type, ventilation, first/min/max of routine vitals and labs), cleaned with the risk_icu
rules (suite/families/risk_icu/comparators/features.py) and median-imputed within each pool.
Outcomes of the challenge are not used.

    python -m suite.families.causal_ate.datagen.covariates RISK_ICU_EXTRACTED OUT_DIR
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'suite' / 'families' / 'risk_icu' / 'comparators'))
sys.path.insert(0, str(REPO / 'suite' / 'families' / 'risk_icu'))
from features import feature_matrix  # noqa: E402

COLUMNS = {
    'age': 'age', 'female': 'female', 'weight0': 'weight_kg',
    'mechvent_any': 'mech_vent',
    'HR_first': 'hr_first', 'HR_max': 'hr_max', 'NIMAP_first': 'map_first', 'NIMAP_min': 'map_min',
    'Temp_first': 'temp_first', 'Temp_max': 'temp_max', 'GCS_first': 'gcs_first', 'GCS_min': 'gcs_min',
    'BUN_first': 'bun_first', 'Creatinine_first': 'creatinine_first', 'Glucose_first': 'glucose_first',
    'HCO3_first': 'hco3_first', 'HCT_first': 'hct_first', 'K_first': 'potassium_first',
    'Na_first': 'sodium_first', 'Platelets_first': 'platelets_first', 'WBC_first': 'wbc_first',
    'Mg_first': 'magnesium_first', 'Urine_total': 'urine_total_ml',
}


def build_pool(record_dir):
    paths = sorted(str(p) for p in Path(record_dir).glob('*.txt'))
    ids, names, X = feature_matrix(paths)
    df = pd.DataFrame(X, columns=names)
    out = pd.DataFrame({'record_id': ids})
    for src, dst in COLUMNS.items():
        out[dst] = df[src].values
    icu = np.select([df['icu1'] == 1, df['icu2'] == 1, df['icu3'] == 1, df['icu4'] == 1], [1, 2, 3, 4], 0)
    out['icu_type'] = icu
    missing = out.isna().mean()
    for c in out.columns:
        if out[c].isna().any():
            out[c] = out[c].fillna(out[c].median())
    return out, missing


def main(extracted, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pool, sub in (('dev', 'set-a'), ('hidden', 'set-b')):
        df, missing = build_pool(Path(extracted) / sub)
        df.to_csv(out_dir / f'pool_{pool}.csv', index=False)
        missing.to_csv(out_dir / f'pool_{pool}_missing_fraction.csv', header=['missing_fraction'])
        print(pool, df.shape)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
