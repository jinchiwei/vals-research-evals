"""Bounded experiment ledger. Scripted validation is separate from model evaluation."""
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from .cases import generate
from .grade import grade
from .solve import solve


def fingerprint():
    digest = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(p.name.encode() + p.read_bytes())
    return digest.hexdigest()


def evaluate(strategy, seeds):
    results = []
    for seed in seeds:
        for case in generate(seed):
            result = grade(case['expected'], solve(case['public'], strategy))
            results.append(dict(case=case['id'], family=case['family'], **result))
    families = defaultdict(list)
    for row in results:
        families[row['family']].append(row['score'])
    means = {k: sum(v) / len(v) for k, v in families.items()}
    return dict(score=sum(means.values()) / len(means), families=means, cases=results)


def smoke_loop(out, development, heldout):
    if set(development) & set(heldout) or not development or not heldout:
        raise ValueError('Nonempty disjoint seed splits required')
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'STOP').exists():
        return dict(status='stopped')
    ledger = out / 'experiments.jsonl'
    if ledger.exists():
        raise FileExistsError('Use a new output directory; preserve earlier experiments')
    history, best, best_score = [], None, -1
    hypotheses = {
        'naive': 'Global AUC, uncalibrated slopes and signing-date chronology can mislead.',
        'adjusted': 'Conditioning on protocol, correcting scanners and exam chronology fixes some failures.',
        'careful': 'Known measurement uncertainty also requires abstention on imprecise trajectories.',
    }
    for strategy in hypotheses:
        if (out / 'STOP').exists():
            return dict(status='stopped', iterations=history)
        result = evaluate(strategy, development)
        accepted = result['score'] > best_score
        if accepted:
            best, best_score = strategy, result['score']
        row = dict(strategy=strategy, hypothesis=hypotheses[strategy], accepted=accepted,
                   split='development', evidence='scripted-control', time=time.time(),
                   source_sha256=fingerprint(), **result)
        history.append(row)
        with ledger.open('a') as handle:
            handle.write(json.dumps(row) + '\n')
    held = evaluate(best, heldout)
    result = dict(status='complete', evidence='scripted-control; NOT frontier-model performance',
                  selection_split='development', development_seeds=development, heldout_seeds=heldout,
                  selected=best, iterations=history, heldout=held)
    (out / 'summary.json').write_text(json.dumps(result, indent=2))
    return result
