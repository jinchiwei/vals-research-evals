"""Seeded fixtures. Generator and answers NEVER enter agent environments."""
import hashlib
import random
from .metrics import audit, trajectory


CONTRACT = ('Write answer.json in the working directory and a reproducible analysis.py. '
            'Use only input.json. All data are synthetic; this is not clinical advice. '
            'Return JSON with an items array; match ids, use finite JSON numbers, and '
            'report numerical values to at least 5 decimal places. A narrative may be '
            'included in a separate summary field. Do not round intermediate calculations.')


def pack(family, seed, variant, public, expected):
    ident = hashlib.sha256(f'{family}:{seed}:{variant}'.encode()).hexdigest()[:12]
    public['family'] = family
    return dict(id=f'{family}-{ident}', family=family, seed=seed,
                instruction=CONTRACT + '\n\n' + public['task'], public=public, expected=expected)


def generate(seed):
    rng = random.Random(seed)
    cases = []
    for biological in (False, True):
        rows = []
        for i in range(480):
            protocol = rng.randrange(2)
            y = int(rng.random() < (.87 if protocol else .13))
            score = 1.8 * protocol + rng.gauss(0, .35) + (1.0 * y if biological else 0)
            rows.append(dict(patient=f'P{i:04}', split='train' if i < 160 else 'test',
                             protocol=f'Q{protocol}', label=y, image_score=round(score, 6),
                             protocol_score=.87 if protocol else .13))
        rng.shuffle(rows)
        task = ('Audit the claim: the image predictor provides discrimination beyond acquisition '
                'protocol. The supplied scores are frozen model predictions, not raw MRI embeddings. '
                'Use only test patients. Compute global_auc for image_score, protocol_auc for '
                'protocol_score, and controlled_auc: the fraction of correctly ordered positive/negative '
                'pairs among pairs sharing a protocol (ties count 0.5). Pool pair counts across protocols, '
                'not the unweighted mean of per-protocol AUCs. Under this benchmark\'s operational rule '
                'the claim is supported iff controlled_auc >= 0.65; otherwise unsupported. '
                'This rule is descriptive, not a statistical significance test or causal claim. '
                'Output one item with id=claim and keys global_auc, protocol_auc, controlled_auc, verdict.')
        public = dict(task=task, rows=rows)
        cases.append(pack('audit', seed, str(biological), public,
                          {'items': [dict(id='claim', **audit(rows))]}))

    offsets = {'scanner-a': 0.0, 'scanner-b': round(rng.uniform(-.95, -.65), 6)}
    subjects, expected = [], []
    variants = [(0, False, False), (-.20, False, False), (0, True, False), (-.15, True, True)]
    rng.shuffle(variants)
    for i, (slope, switch, short) in enumerate(variants):
        ident = f'S{i + 1}'
        sigma = .10 if short else .025
        rows = []
        for j in range(5):
            t = j * (.04 if short else 1.0)
            scanner = 'scanner-b' if switch and j >= 2 else 'scanner-a'
            rows.append(dict(year=t, scanner=scanner, sigma=sigma,
                             value=round(.3 + slope * t + offsets[scanner] + rng.gauss(0, sigma), 6)))
        rng.shuffle(rows)
        subjects.append(dict(id=ident, visits=rows))
        expected.append(dict(id=ident, **trajectory(rows, offsets)))
    task = ('Assess longitudinal change for each subject. Values are already age/sex-normalized. '
            'Calibration contains known additive scanner offsets; sigma is each visit\'s known independent '
            'Gaussian measurement SD. Fit an intercept and slope by weighted least squares after calibration. '
            'Use known measurement variances, not a residual-estimated variance. Report slope per year and '
            'its standard error se. The synthetic decision policy: decline when the entire two-sided '
            '95% interval (normal critical value 1.96) is below -0.08/year; stable when its lower bound '
            'is >= -0.08/year; otherwise insufficient. stable means no threshold-exceeding decline '
            'established under this artificial policy, not a clinical diagnosis. Output one item per '
            'subject with id, slope, se, verdict.')
    cases.append(pack('change', seed, 'panel', dict(task=task, subjects=subjects, calibration=offsets),
                      {'items': expected}))

    # Authored semantic gold labels, independent of the reference parser.
    templates = [
        ('Unchanged chronic microhemorrhage. No new hemorrhage.', 'present', 'persistent',
         'Unchanged chronic microhemorrhage.', 'microhemorrhage'),
        ('Previously described edema has resolved.', 'absent', 'resolved',
         'Previously described edema has resolved.', 'edema'),
        ('Possible new superficial siderosis; artifact cannot be excluded.', 'uncertain', 'unknown',
         'Possible new superficial siderosis; artifact cannot be excluded.', 'superficial siderosis'),
        ('History of edema. Current examination does not assess edema.', 'unassessed', 'unknown',
         'Current examination does not assess edema.', 'edema'),
        ('New edema is present.', 'present', 'new', 'New edema is present.', 'edema'),
        ('No edema is seen.', 'absent', 'unknown', 'No edema is seen.', 'edema'),
    ]
    rng.shuffle(templates)
    queries, reports, expected = [], [], []
    for i, (body, status, change, evidence, finding) in enumerate(templates):
        subject, report_id = f'R{i + 1}', f'doc-{rng.randrange(100000, 999999)}'
        prior_id = f'prior-{i}'
        reports.extend([
            dict(id=prior_id, subject=subject, exam_date='2025-01-02', signed_at='2025-01-03T12:00:00',
                 type='report', text=f'{finding.capitalize()} is present.'),
            dict(id=report_id, subject=subject, exam_date='2026-04-05', signed_at='2026-04-06T12:00:00',
                 type='report', text=body),
            # An older exam signed later must not overwrite a newer exam.
            dict(id=f'late-{i}', subject=subject, exam_date='2024-11-01', signed_at='2026-04-08T12:00:00',
                 type='report', text=f'No {finding} is seen.'),
        ])
        if change == 'new':
            # The prior finding has explicitly resolved before the current recurrence.
            next(r for r in reports if r['id'] == prior_id)['text'] = f'No {finding} is seen.'
        if i % 2 == 0:
            corrected = report_id + '-addendum'
            reports.append(dict(id=corrected, subject=subject, exam_date='2026-04-05',
                                signed_at='2026-04-07T12:00:00', type='addendum',
                                replaces=report_id, text=body))
            # A conflicting original report is superseded by the addendum.
            next(r for r in reports if r['id'] == report_id)['text'] = f'No {finding} is seen.'
            report_id = corrected
        queries.append(dict(id=subject, finding=finding))
        expected.append(dict(id=subject, status=status, change=change, source_id=report_id, evidence=evidence))
    rng.shuffle(reports)
    task = ('Reconcile the requested finding for each subject at their most recent EXAM date, '
            'not their most recent signing date. Within that exam, a signed addendum explicitly replacing '
            'a report is authoritative. status is present, absent, uncertain, or unassessed. '
            'change is new, persistent, resolved, or unknown. Only assert change when the current '
            'authoritative text establishes it; absence alone is not proof of resolution. A history '
            'mention does not establish current presence; no new finding does not negate a chronic '
            'one. Possible findings remain uncertain with change unknown. Quote the single complete '
            'sentence most directly establishing the current status, including punctuation. '
            'Output items with id, status, change, source_id, evidence. All reports are invented.')
    cases.append(pack('reports', seed, 'panel', dict(task=task, queries=queries, reports=reports),
                      {'items': expected}))
    return cases
