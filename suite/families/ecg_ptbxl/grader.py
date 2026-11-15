"""suite/core plug-in for ecg_ptbxl: cohort grading (runs inside the verifier from tests/lib).

The hidden set is ONE folder (tests/hidden/cohort/): input/ holds signals.npz and meta.csv for every
hidden ECG, reference/ holds reference.csv (labels, sex, age band). suite.core.grading runs the
pipeline once on it under TIME_RULE (60 s + 0.5 s per ECG, hard kill at 2x) and calls grade_cohort().

All metrics, the strict parser and the gate come unchanged from grade.py (the family's original
self-contained grader, numpy only). The reward follows the suite's cohort rule (DESIGN.md):
clinically_acceptable = 1 only if all three gate parts are met. grade.py's conditional fraction
(parts 2 and 3 count only with part 1) stays in metrics as gate_fraction_met; suite.core writes the
plain fraction as gate_fraction.
"""
import os
import stat
from pathlib import Path

from . import grade as G

GRADING = 'cohort'
REQUIRED_OUTPUTS = ('predictions.csv',)
N_BOOT = G.N_BOOT
PRIMARY_METRIC = 'clip((macro AUROC - 0.5) / (0.928 - 0.5), 0, 1)'
CLINICAL_THRESHOLD = (
    f"on the hidden ECGs, all of: MI sensitivity >= {G.GATE['min_sensitivity']} at specificity "
    f"{G.GATE['operating_specificity']}; mean 5-class ECE <= {G.GATE['max_macro_ece']}; overall macro AUROC minus "
    f"worst sex/age-band macro AUROC <= {G.GATE['max_subgroup_gap']}")


def time_limit_seconds(n_ecgs):
    return G.time_budget(n_ecgs)


def hard_kill_seconds(n_ecgs):
    return G.time_budget(n_ecgs) * G.TIME_RULE['hard_kill_factor']


def _invalid(reason):
    return {'valid': False, 'quality': 0.0, 'reason': reason, 'gate': {}, 'metrics': {}}


def grade_cohort(output_dir, input_dir, reference_dir):
    ids, Y, groups = G.load_reference(Path(reference_dir) / 'reference.csv')
    path = Path(output_dir) / 'predictions.csv'
    try:            # the grader runs as root: never follow a link planted by the pipeline
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return _invalid('predictions.csv is not a regular file')
    except FileNotFoundError:
        return _invalid('predictions.csv missing')
    try:
        P = G.parse_predictions(path, ids)
    except G.InvalidOutput as error:
        return _invalid(str(error))
    rep = G.full_report(Y, P, groups, n_boot=N_BOOT)
    return {'valid': True, 'quality': G.quality_score(rep['macro_auroc']), 'reason': None,
            'gate': rep['gate'], 'metrics': rep}
