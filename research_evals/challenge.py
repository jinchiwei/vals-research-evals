"""Second-round workflow complexity; the underlying scientific answers stay fixed."""
import copy
import random
from .cases import CONTRACT


def complicate(case):
    result = copy.deepcopy(case)
    original = result['public']
    rng = random.Random(case['seed'] + 733)
    family = original['family']
    result['id'] += '-workflow'
    data = dict(family=family, workflow=True)
    if family == 'audit':
        events, predictions, outcomes, training = [], [], [], []
        for r in original['rows']:
            patient = r['patient']
            if r['split'] == 'train':
                training.append(patient)
            for visit in range(2):
                event = f'{patient}-E{visit}'
                events.append(dict(event_id=event, patient_id=patient,
                                   exam_date='2025-01-02' if visit == 0 else '2026-01-02',
                                   acquisition=r['protocol'], cohort='evaluation'))
                predictions.append(dict(event_id=event,
                                        image_score=r['image_score'] if visit == 0 else r['label'],
                                        protocol_score=r['protocol_score']))
                # Two adjudications of one event are not two independent samples.
                for version in (1, 2):
                    label = r['label'] if version == 2 else 1 - r['label']
                    outcomes.append(dict(event_id=event, revision=version,
                                         diagnosis='Finding' if label else 'None'))
        predictions.extend(copy.deepcopy(predictions[:24]))
        for table in (events, predictions, outcomes):
            rng.shuffle(table)
        data.update(events=events, predictions=predictions, adjudications=outcomes,
                    training_snapshot=training)
        data['task'] = (
            'Audit a frozen predictor under the cohort contract below. The research claim is that image '
            'scores discriminate the target finding beyond acquisition protocol. These are synthetic scores. '
            'Cohort: never include anyone in training_snapshot, even if an event says evaluation; '
            'use the earliest eligible exam per remaining person. Predictions are keyed by event_id; '
            'identical repeated export rows represent one prediction. Diagnosis is the highest-revision '
            'adjudication of that selected event. The literal diagnosis "None" means negative, not missing. '
            'Finding means positive. Do not substitute a later visit\'s outcome or score. '
            'Return items with a single id=claim, global_auc (image scores), protocol_auc, controlled_auc '
            '(positive/negative concordance among same-acquisition pairs, pooled by pair count; ties half), '
            'and verdict supported iff controlled_auc >= .65, otherwise unsupported. '
            'All metrics refer to this exact cohort. This is a descriptive discrimination criterion, not '
            'a causal claim. Implement the cohort reconstruction and calculations in analysis.py.')
    elif family == 'change':
        scans, people = [], []
        for i, subject in enumerate(original['subjects']):
            baseline_age = 62 + 3 * i
            people.append(dict(id=subject['id'], baseline_age=baseline_age))
            for j, r in enumerate(subject['visits']):
                mean = 4000 - 20 * (baseline_age + r['year'] - 60)
                factor = 1000 if j % 2 else 1
                scans.append(dict(subject=subject['id'], elapsed_days=r['year'] * 365.25,
                                  scanner=r['scanner'], units='cm3' if factor == 1000 else 'mm3',
                                  volume=(mean + 200 * r['value']) / factor,
                                  measurement_sd=200 * r['sigma'] / factor))
        rng.shuffle(scans)
        data.update(people=people, scans=scans,
                    calibration_mm3={k: v * 200 for k, v in original['calibration'].items()},
                    norms=dict(reference_age=60, mean_at_reference_mm3=4000,
                               mean_change_per_year_mm3=-20, population_sd_mm3=200))
        data['task'] = (
            'Assess longitudinal change relative to the supplied age norms. Use all listed scans per person. '
            'The norms describe expected anatomical volume at each attained age; population SD is constant. '
            'Calibration gives known additive scanner offsets in mm3. measurement_sd is independent known '
            'Gaussian measurement noise in the scan\'s stated units. Time is elapsed_days/365.25 years. '
            'Report slope and se in age-normalized population-SD units per year, fitting an intercept and '
            'slope with the known measurement variances. Scanner offsets and normative parameters are '
            'treated as exact for this synthetic task. The artificial policy is decline if the entire '
            'two-sided 95% normal interval is below -.08/year; stable if its lower bound is >= -.08/year; '
            'otherwise insufficient. Use critical value 1.96. This is not a clinical policy. '
            'Output one item per person with id, slope, se, verdict. Implement conversions and analysis.py.')
    else:
        data.update(queries=original['queries'], reports=original['reports'])
        for q in data['queries']:
            # A later correction to a different finding does not retract the requested finding.
            original_doc = next(r for r in data['reports'] if r['subject'] == q['id']
                                and r['exam_date'] == '2026-04-05' and r['type'] == 'report')
            data['reports'].append(dict(id='sinus-' + q['id'], subject=q['id'],
                exam_date='2026-04-05', signed_at='2026-04-09T12:00:00', type='addendum',
                replaces=original_doc['id'], applies_to=['sinus disease'],
                text='Correction: sinus disease is absent. Other findings are unchanged.'))
        for r in data['reports']:
            if r['type'] == 'addendum' and 'applies_to' not in r:
                r['applies_to'] = [next(q['finding'] for q in data['queries'] if q['id'] == r['subject'])]
        rng.shuffle(data['reports'])
        data['task'] = original['task'].replace(
            'Within that exam, a signed addendum explicitly replacing a report is authoritative.',
            'Within that exam, an addendum supersedes the referenced report ONLY for the findings '
            'listed in applies_to. A correction to a different finding does not replace the requested '
            'finding. Use the latest applicable correction, retaining original findings otherwise.')
    result['public'] = data
    result['instruction'] = CONTRACT + '\n\n' + data['task']
    return result


def normalize(data):
    """Reference preprocessing. This module is only shipped with the oracle."""
    if not data.get('workflow'):
        return data
    family = data['family']
    if family == 'audit':
        excluded = set(data['training_snapshot'])
        selected = {}
        for e in data['events']:
            patient = e['patient_id']
            if patient in excluded or e['cohort'] != 'evaluation':
                continue
            if patient not in selected or e['exam_date'] < selected[patient]['exam_date']:
                selected[patient] = e
        scores = {r['event_id']: r for r in data['predictions']}
        labels = {}
        for row in data['adjudications']:
            key = row['event_id']
            if key not in labels or row['revision'] > labels[key]['revision']:
                labels[key] = row
        rows = []
        for patient, event in selected.items():
            ident = event['event_id']
            rows.append(dict(patient=patient, split='test', protocol=event['acquisition'],
                             label=int(labels[ident]['diagnosis'] == 'Finding'),
                             image_score=scores[ident]['image_score'],
                             protocol_score=scores[ident]['protocol_score']))
        return dict(family=family, rows=rows)
    if family == 'change':
        norms = data['norms']
        sd = norms['population_sd_mm3']
        subjects = []
        for person in data['people']:
            visits = []
            for r in data['scans']:
                if r['subject'] != person['id']:
                    continue
                t = r['elapsed_days'] / 365.25
                factor = 1000 if r['units'] == 'cm3' else 1
                age = person['baseline_age'] + t
                mean = norms['mean_at_reference_mm3'] + norms['mean_change_per_year_mm3'] * (age - norms['reference_age'])
                visits.append(dict(year=t, scanner=r['scanner'],
                                   value=(factor * r['volume'] - mean) / sd,
                                   sigma=factor * r['measurement_sd'] / sd))
            subjects.append(dict(id=person['id'], visits=visits))
        return dict(family=family, subjects=subjects,
                    calibration={k: v/sd for k, v in data['calibration_mm3'].items()})
    reports = []
    for q in data['queries']:
        reports.extend(r for r in data['reports'] if r['subject'] == q['id']
                       and (r['type'] != 'addendum' or q['finding'] in r['applies_to']))
    return dict(family=family, queries=data['queries'], reports=reports)
