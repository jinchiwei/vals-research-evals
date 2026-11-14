"""Transparent scripted controls, NOT frontier models or general NLP solutions."""
from .metrics import audit, trajectory


def solve(data, strategy='careful'):
    family = data['family']
    if family == 'audit':
        return {'items': [dict(id='claim', **audit(data['rows'], controlled=strategy != 'naive'))]}
    if family == 'change':
        offsets = data['calibration'] if strategy != 'naive' else dict.fromkeys(data['calibration'], 0)
        return {'items': [dict(id=s['id'], **trajectory(s['visits'], offsets, uncertainty=strategy == 'careful'))
                          for s in data['subjects']]}
    items = []
    for q in data['queries']:
        docs = [r for r in data['reports'] if r['subject'] == q['id']]
        latest = max(docs, key=lambda r: (r['signed_at'],) if strategy == 'naive'
                     else (r['exam_date'], r['signed_at']))
        body = latest['text']
        if 'does not assess' in body:
            status, change = 'unassessed', 'unknown'
            evidence = body.split('. ')[-1]
        elif body.startswith('Possible'):
            status, change, evidence = 'uncertain', 'unknown', body
        elif 'has resolved' in body:
            status, change, evidence = 'absent', 'resolved', body
        elif body.startswith('Unchanged'):
            status, change, evidence = 'present', 'persistent', body.split('. ')[0] + '.'
        elif body.startswith('New'):
            status, change, evidence = 'present', 'new', body
        elif body.startswith('No'):
            status, change, evidence = 'absent', 'unknown', body
        else:
            status, change, evidence = 'present', 'unknown', body
        items.append(dict(id=q['id'], status=status, change=change, source_id=latest['id'], evidence=evidence))
    return {'items': items}
