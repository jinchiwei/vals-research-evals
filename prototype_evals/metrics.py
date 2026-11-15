"""Small, auditable numerical definitions; no third-party dependencies."""
import math


def auc(labels, scores):
    if len(labels) != len(scores) or any(y not in (0, 1) for y in labels):
        raise ValueError('Aligned binary labels required')
    if not all(math.isfinite(s) for s in scores):
        raise ValueError('Finite scores required')
    npos = sum(labels)
    nneg = len(labels) - npos
    if not npos or not nneg:
        raise ValueError('AUC requires both classes')
    ordered = sorted(zip(scores, labels))
    total = 0.0
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        total += sum(y for _, y in ordered[i:j]) * (i + 1 + j) / 2
        i = j
    return (total - npos * (npos + 1) / 2) / (npos * nneg)


def audit(rows, controlled=True):
    rows = [r for r in rows if r['split'] == 'test']
    overall = auc([r['label'] for r in rows], [r['image_score'] for r in rows])
    protocol = auc([r['label'] for r in rows], [r['protocol_score'] for r in rows])
    numer = denom = 0
    for group in sorted({r['protocol'] for r in rows}):
        subset = [r for r in rows if r['protocol'] == group]
        y = [r['label'] for r in subset]
        pairs = sum(y) * (len(y) - sum(y))
        if pairs:
            numer += pairs * auc(y, [r['image_score'] for r in subset])
            denom += pairs
    within = numer / denom
    verdict = 'supported' if (within if controlled else overall) >= .65 else 'unsupported'
    return dict(global_auc=overall, protocol_auc=protocol, controlled_auc=within, verdict=verdict)


def trajectory(rows, offsets, uncertainty=True):
    weights = [1 / r['sigma'] ** 2 for r in rows]
    sw = sum(weights)
    tbar = sum(w * r['year'] for w, r in zip(weights, rows)) / sw
    values = [r['value'] - offsets[r['scanner']] for r in rows]
    ybar = sum(w * v for w, v in zip(weights, values)) / sw
    sxx = sum(w * (r['year'] - tbar) ** 2 for w, r in zip(weights, rows))
    if sxx <= 0:
        raise ValueError('Distinct visit times required')
    slope = sum(w * (r['year'] - tbar) * (v - ybar)
                for w, r, v in zip(weights, rows, values)) / sxx
    se = 1 / math.sqrt(sxx)
    margin = 1.96 * se if uncertainty else 0
    verdict = ('decline' if slope + margin < -.08 else
               'stable' if slope - margin >= -.08 else 'insufficient')
    return dict(slope=slope, se=se, verdict=verdict)
