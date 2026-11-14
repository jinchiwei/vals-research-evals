"""Artifact grading. This never executes a submitted analysis on the host."""
import json
import math
import sys
from pathlib import Path


def grade(expected, answer):
    if not isinstance(answer, dict) or not isinstance(answer.get('items'), list):
        return dict(score=0.0, resolved=False, errors=['Expected object with items array'])
    items = answer['items']
    if any(not isinstance(x, dict) or not isinstance(x.get('id'), str) for x in items):
        return dict(score=0.0, resolved=False, errors=['Each item needs a string id'])
    indexed = {x['id']: x for x in items}
    if len(indexed) != len(items) or set(indexed) != {x['id'] for x in expected['items']}:
        return dict(score=0.0, resolved=False, errors=['Missing, duplicate, or extra item ids'])
    errors, correct = [], 0
    for truth in expected['items']:
        got = indexed[truth['id']]
        bad = []
        for key, value in truth.items():
            candidate = got.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                valid = (type(candidate) in (int, float) and math.isfinite(candidate)
                         and abs(candidate - value) <= 1e-4)
            else:
                valid = type(candidate) is type(value) and candidate == value
            if not valid:
                bad.append(key)
        if bad:
            errors.append(truth['id'] + ': incorrect ' + ', '.join(bad))
        else:
            correct += 1
    score = correct / len(expected['items'])
    return dict(score=score, resolved=not errors, errors=errors)


def main():
    expected_path, answer_path, reward_dir = map(Path, sys.argv[1:4])
    expected = json.loads(expected_path.read_text())
    try:
        if answer_path.stat().st_size > 1_000_000:
            raise ValueError('Answer larger than 1 MB')
        answer = json.loads(answer_path.read_text())
        result = grade(expected, answer)
    except (OSError, ValueError) as exc:
        result = dict(score=0.0, resolved=False, errors=[str(exc)])
    reward_dir.mkdir(parents=True, exist_ok=True)
    (reward_dir / 'reward.txt').write_text(str(result['score']))
    (reward_dir / 'details.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
