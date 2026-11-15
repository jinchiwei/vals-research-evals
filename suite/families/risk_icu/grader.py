"""suite/core plug-in for risk_icu: cohort grading (runs inside the verifier from tests/lib).

risk_icu is graded on the whole hidden cohort: the exported task has ONE hidden folder ("cohort")
whose input/ holds every hidden record file and whose reference/ holds outcomes.csv. suite.core.grading
runs the pipeline once on it under the cohort time limit (gate.GATE["time_limit_s"]) and calls
grade_cohort().

Required output: predictions.csv (header RecordID,risk; one finite risk in [0,1] per input file).
quality = clip(2*AUROC - 1, 0, 1). Gate parts: the four components of gate.GATE. Reward follows the
suite's cohort rule (DESIGN.md): clinically_acceptable = 1 only if all four are met; suite.core writes
each part and gate_fraction to metrics.json.
"""
import os
import stat
from pathlib import Path

from . import grade
from .gate import GATE

GRADING = 'cohort'
REQUIRED_OUTPUTS = ('predictions.csv',)
PRIMARY_METRIC = 'clip(2*AUROC - 1, 0, 1)'
N_BOOT = 500
CLINICAL_THRESHOLD = (
    f"on the hidden cohort: challenge event-1 >= {GATE['event1']['bar']} (SAPS-I + 0.05); calibration slope "
    f"{GATE['calibration']['slope_min']}-{GATE['calibration']['slope_max']} and |calibration-in-the-large| <= "
    f"{GATE['calibration']['citl_abs_max']}; net benefit at p_t={GATE['net_benefit']['threshold']} above treat-all "
    f"and treat-none; worst ICU-type/sex AUROC >= overall - {GATE['subgroup']['max_auroc_gap']}")


def grade_cohort(output_dir, input_dir, reference_dir):
    ids = sorted(int(p.stem) for p in Path(input_dir).glob('*.txt'))
    path = Path(output_dir) / 'predictions.csv'
    try:            # the grader runs as root: never follow a link planted by the pipeline
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return {'valid': False, 'quality': 0.0, 'reason': 'predictions.csv is not a regular file',
                    'gate': {}, 'metrics': {}}
    except FileNotFoundError:
        pass                                      # validate_predictions reports it
    try:
        pred = grade.validate_predictions(str(Path(output_dir) / 'predictions.csv'), ids)
    except grade.InvalidOutput as error:
        return {'valid': False, 'quality': 0.0, 'reason': str(error), 'gate': {}, 'metrics': {}}
    outcomes = grade.read_outcomes(str(Path(reference_dir) / 'outcomes.csv'))
    m = grade.score(pred, outcomes, GATE, n_boot=N_BOOT)
    gate = m.pop('gate')
    m.pop('clinically_acceptable', None)          # the family's fraction; suite.core writes gate_fraction
    failed = [k for k, ok in gate.items() if not ok]
    return {'valid': True, 'quality': grade.quality_from_auroc(m['auroc']), 'gate': gate,
            'reason': ('gate failed: ' + ', '.join(failed)) if failed else None, 'metrics': m}


def grade_case(output_dir, input_dir, reference_dir):
    """Per-case view of grade_cohort (kept for the family tests): acceptable = every part met."""
    g = grade_cohort(output_dir, input_dir, reference_dir)
    gate = g['gate']
    metrics = dict(g['metrics'], gate=gate)
    if g['valid']:
        metrics['gate_fraction'] = sum(gate.values()) / len(gate)
    return {'valid': g['valid'], 'acceptable': bool(g['valid'] and gate and all(gate.values())),
            'quality': g['quality'], 'reason': g['reason'], 'metrics': metrics}
