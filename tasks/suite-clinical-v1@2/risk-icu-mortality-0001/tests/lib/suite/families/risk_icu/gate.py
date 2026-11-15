"""The risk_icu clinical gate, fixed on 2026-11-14 before any agent result (see docs/research/suite/risk_icu.md).

A .py module (not JSON) because the suite exporter vendors only the family's *.py files into tests/lib.
"""

GATE = {'family': 'risk_icu',
 'fixed_on': '2026-11-14, after the SAPS-I comparator was scored on the hidden set and before the '
             'gradient-boosted comparator or any agent was scored on it',
 'time_limit_s': 300,
 'time_limit_reason': 'Scores the whole hidden cohort of 4,000 stays in one run on 4 CPUs: 75 ms '
                      'per stay. A 48-hour risk refresh for every ICU bed must be ready well '
                      'inside the time between data close and a ward round; 5 minutes for 4,000 '
                      'stays is generous (the specialist pipeline needs well under a minute), so '
                      'the limit rejects only pipelines that would hold up a round or an admission '
                      'decision, e.g. retraining a large model or per-patient model fits at '
                      'prediction time.',
 'event1': {'bar': 0.321,
            'rule': 'min(Se, PPV) with the K = round(sum of risks) highest-risk stays flagged must '
                    'be >= SAPS-I comparator event-1 on the same hidden stays (0.2711) + 0.05',
            'source': 'Challenge event-1 definition and the SAPS-I sample-entry baseline 0.3125 '
                      '(Silva et al., Predicting in-hospital mortality of ICU patients: The '
                      'PhysioNet/Computing in Cardiology Challenge 2012, CinC 2012;39:245-248; '
                      'score.c v1.4). The +0.05 margin (5 more deaths in 100 caught at equal PPV) '
                      'is our convention: a new model must beat the free score units already '
                      'compute; the bar 0.321 also sits just above the published SAPS-I baseline '
                      '0.3125.'},
 'calibration': {'slope_min': 0.8,
                 'slope_max': 1.2,
                 'citl_abs_max': 0.2,
                 'source': 'Weak calibration (intercept 0, slope 1): Van Calster et al., J Clin '
                           'Epidemiol 2016;74:167-176 and BMC Med 2019;17:230 (Calibration: the '
                           'Achilles heel of predictive analytics); Steyerberg, Clinical '
                           'Prediction Models, 2nd ed. 2019. The 0.8-1.2 slope window and '
                           '|calibration-in-the-large| <= 0.2 logit (about +/-20% relative error '
                           'in the expected death count at 14% mortality) are conventions we fix '
                           'here; the literature gives the ideal values, not a tolerance.'},
 'net_benefit': {'threshold': 0.2,
                 'margin': 0.0,
                 'rule': 'net benefit at p_t = 0.20 must exceed both treat-all and treat-none (0)',
                 'source': 'Vickers and Elkin, Med Decis Making 2006;26:565-574; Vickers et al., '
                           'Diagn Progn Res 2019;3:18. Clinical argument: at 48 h a flag triggers '
                           'a senior intensivist review and a goals-of-care / escalation '
                           'discussion; accepting about 4 unnecessary reviews per patient who will '
                           'die (odds 1:4, p_t = 0.2) is the trade-off we assume; the threshold is '
                           'fixed, not tuned.'},
 'subgroup': {'max_auroc_gap': 0.1,
              'min_events_per_class': 10,
              'groups': ['icu_CCU', 'icu_CSRU', 'icu_MICU', 'icu_SICU', 'sex_female', 'sex_male'],
              'rule': 'worst subgroup AUROC >= overall AUROC - 0.10 over ICU type (1 CCU, 2 CSRU, '
                      '3 MICU, 4 SICU) and sex; subgroups with fewer than 10 deaths or survivors '
                      'are skipped; sex = -1 (missing, 5 hidden stays) is not a subgroup',
              'source': 'Subgroup performance reporting per TRIPOD+AI (Collins et al., BMJ '
                        '2024;385:e078378, item on performance in key subgroups). The 0.10 AUROC '
                        'gap is our convention (roughly one band on the Hosmer-Lemeshow '
                        '0.7/0.8/0.9 discrimination scale, Applied Logistic Regression 3rd ed. '
                        '2013).'},
 'decision_rule': 'Each component is judged on the hidden-set point estimate; bootstrap intervals '
                  '(1,000 patient resamples, seed 20261114) are reported, not used to pass or '
                  'fail.',
 'quality_rule': "quality = clip(2*AUROC - 1, 0, 1) (Somers' D)",
 'vs_specialist_rule': 'clip((AUROC_agent - 0.5) / (AUROC_specialist - 0.5), 0, 1), specialist = '
                       'gradient-boosted comparator on the same hidden stays'}
