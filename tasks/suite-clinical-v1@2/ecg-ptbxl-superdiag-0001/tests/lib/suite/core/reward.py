"""reward.json / metrics.json contract shared by every task of the suite.

reward.json is flat, finite, and has exactly REWARD_KEYS in every task, each in [0, 1] with
0 = failure (Valkyrie averages each key over tasks and counts a missing key as 0.0):

  reward                 the scalar; computed by scalar_reward() below (the one place to change it)
  ran                    fraction of hidden cases for which the pipeline left every required output file
  valid                  fraction of hidden cases whose outputs pass the family's format and geometry checks
  within_time            fraction of hidden cases whose outputs were produced inside the clinical
                         time limit (ran and not killed on timeout)
  clinically_acceptable  fraction of hidden cases meeting the family's stated clinical threshold
  quality                mean over hidden cases of the family's primary metric mapped to [0, 1]
                         (0 for a case without valid outputs), higher better
  vs_specialist          min(1, quality / specialist quality) on the same hidden cases

The case-level fractions make "ran == 1" mean "outputs for every hidden case".
Raw values in physical units (mm, mL, seconds) go only to metrics.json next to reward.json.
"""
import json
import math
import os
from pathlib import Path

REWARD_KEYS = ('reward', 'ran', 'valid', 'within_time', 'clinically_acceptable', 'quality', 'vs_specialist')
GATE_KEYS = ('ran', 'valid', 'within_time')


class RewardContractError(ValueError):
    pass


def scalar_reward(keys):
    """Default scalar: clinically_acceptable if ran, valid and within_time are all 1, else 0.

    `keys` holds the six non-scalar keys. Change the suite's headline rule here and only here.
    """
    if all(keys[k] == 1.0 for k in GATE_KEYS):
        return float(keys['clinically_acceptable'])
    return 0.0


def vs_specialist(quality, specialist_quality):
    """min(1, quality / specialist_quality). If the specialist scores 0, the ratio is undefined;
    we return 1.0 when the agent scores above 0 (it beat the specialist) and 0.0 otherwise."""
    if specialist_quality is None or specialist_quality <= 0:
        return 1.0 if quality > 0 else 0.0
    return min(1.0, quality / specialist_quality)


def build_reward(*, ran, valid, within_time, clinically_acceptable, quality, specialist_quality):
    """Assemble and validate the full reward dict (including the scalar)."""
    keys = {'ran': ran, 'valid': valid, 'within_time': within_time,
            'clinically_acceptable': clinically_acceptable, 'quality': quality,
            'vs_specialist': vs_specialist(quality, specialist_quality)}
    keys = {k: float(v) for k, v in keys.items()}
    keys['reward'] = scalar_reward(keys)
    out = {k: keys[k] for k in REWARD_KEYS}
    validate_reward(out)
    return out


def zero_reward():
    return {k: 0.0 for k in REWARD_KEYS}


def validate_reward(reward):
    """Refuse anything but exactly REWARD_KEYS mapped to finite real numbers in [0, 1]."""
    if not isinstance(reward, dict):
        raise RewardContractError('reward must be a dict')
    missing, extra = set(REWARD_KEYS) - set(reward), set(reward) - set(REWARD_KEYS)
    if missing or extra:
        raise RewardContractError(f'reward keys wrong: missing {sorted(missing)}, extra {sorted(extra)}')
    for k, v in reward.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise RewardContractError(f'{k} must be a number, got {type(v).__name__}')
        if not math.isfinite(v) or not 0.0 <= v <= 1.0:
            raise RewardContractError(f'{k} must be finite and in [0, 1], got {v!r}')


def json_safe(value, path='', replaced=None):
    """Convert numpy scalars/arrays to Python, and non-finite floats to None (paths recorded)."""
    replaced = [] if replaced is None else replaced
    if hasattr(value, 'tolist') and not isinstance(value, (str, bytes)):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(k): json_safe(v, f'{path}/{k}', replaced) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v, f'{path}/{i}', replaced) for i, v in enumerate(value)]
    if isinstance(value, float) and not math.isfinite(value):
        replaced.append(f'{path}={value!r}')
        return None
    return value


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def write_reward(logs_dir, reward, metrics=None):
    """Write reward.json (validated) and, if given, metrics.json next to it.

    metrics may hold anything JSON-able; non-finite numbers become null and are listed under
    '_nonfinite_to_null' (e.g. HD95 = inf for an empty prediction).
    """
    validate_reward(reward)
    logs = Path(logs_dir)
    if metrics is not None:
        replaced = []
        safe = json_safe(metrics, '', replaced)
        if replaced:
            safe['_nonfinite_to_null'] = replaced
        _atomic_write(logs / 'metrics.json', json.dumps(safe, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _atomic_write(logs / 'reward.json', json.dumps({k: float(reward[k]) for k in REWARD_KEYS}, allow_nan=False) + '\n')


def write_provisional_zero(logs_dir):
    """Written first by the grader so a crash or verifier timeout still scores 0, not an infra error."""
    write_reward(logs_dir, zero_reward(), {'status': 'provisional: grading did not finish'})
