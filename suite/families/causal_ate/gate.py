"""The causal_ate gate, fixed on 2026-11-15 before any comparator was run on the hidden datasets and
before any agent attempt (docs/research/suite/causal_ate.md). Inputs to the choice: Dorie et al. 2019
(published ACIC 2016 results) and the comparators' results on the 32 development datasets only.

A .py module (not JSON) because the suite exporter vendors only the family's *.py files into tests/lib.
All error measures are in units of each dataset's observed outcome standard deviation (sd of y in the
input data), as in ACIC 2016, so that datasets with arbitrary outcome units can be pooled.
"""

N_HIDDEN = 48
SECONDS_PER_DATASET = 20

GATE = {
    'family': 'causal_ate',
    'fixed_on': '2026-11-15 01:15 EST, after the comparators were run on the 32 development datasets and '
                'before any comparator or agent was run on the 48 hidden datasets',
    'estimand': 'SATT: mean over the treated units of E[Y(1) - Y(0) | X] (the conditional SATT of ACIC 2016)',
    'time_limit_s': N_HIDDEN * SECONDS_PER_DATASET,
    'time_limit_reason': f'{SECONDS_PER_DATASET} s per 2,000-row dataset on 4 CPUs, for all {N_HIDDEN} hidden '
                         'datasets in one run. A re-runnable automated analysis should finish while the analyst '
                         'waits; the cross-fitted doubly robust specialist needs a few seconds per dataset, so '
                         'the limit is several times that and rejects only per-dataset tuning searches or MCMC '
                         'runs that would not be re-run routinely.',
    'coverage': {
        'min': 0.85,
        'rule': 'share of hidden datasets whose reported 95% interval contains the true SATT must be >= 0.85 '
                '(at least 41 of 48)',
        'source': 'Nominal 95%. Dorie et al. 2019 (Statistical Science 34(1):43-68, section 6.2, Fig. 3): '
                  'plain BART covered about 82% and was called disappointing; BART+TMLE was nearly nominal, BART '
                  'with the propensity score a little over 90%, SuperLearner+TMLE with BART about 92%. The bar '
                  'separates the disappointing group (<= 0.83) from near-nominal methods with binomial slack: '
                  'a method with true coverage 0.95 falls below 41/48 with probability about 0.003.'},
    'rmse': {
        'max': 0.10,
        'rule': 'root mean squared error of the point estimate over hidden datasets <= 0.10 outcome sd',
        'source': 'Dorie et al. 2019 section 6.2: most automated methods reached bias and RMSE at or below about '
                  '0.05 sd at n = 4,802. Scaled to n = 2,000 per dataset by sqrt(4802/2000) = 1.55 this is '
                  '0.077; 0.10 allows for a different covariate set and DGP. Development data: doubly robust '
                  'comparator 0.069, regression adjustment 0.082, naive difference 0.180.'},
    'bias': {
        'max_abs': 0.05,
        'rule': '|mean signed error| over hidden datasets <= 0.05 outcome sd',
        'source': 'Dorie et al. 2019 section 6.2 (bias at or below about 0.05 sd for most methods). Weak by '
                  'design here because confounding directions are random; reported because ACIC reports it.'},
    'interval_length': {
        'max_mean': 0.50,
        'rule': 'mean length of the 95% intervals <= 0.50 outcome sd (an interval must be informative, so '
                'coverage cannot be bought with very wide intervals)',
        'source': 'Dorie et al. 2019 section 6.2 single out CBPS for wide intervals (mean length 0.78 sd). '
                  'Our median |SATT| on development data is about 0.3 sd; an interval longer than 0.5 sd '
                  'cannot tell a small effect from none. Development data: doubly robust comparator 0.23.'},
    'decision_rule': 'Each part is judged on the hidden-set value; all four must hold (cohort rule, DESIGN.md).',
    'quality_rule': 'quality = clip(1 - RMSE / 0.5, 0, 1)',
}
