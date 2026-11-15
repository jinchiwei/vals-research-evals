"""reward.json contract: exactly seven keys, finite, in [0, 1]; raw units only in metrics.json."""
import json
import math

import pytest

from suite.core import reward as R

CONTRACT = {'reward', 'ran', 'valid', 'within_time', 'clinically_acceptable', 'quality', 'vs_specialist'}


def good(**kw):
    base = dict(ran=1.0, valid=1.0, within_time=1.0, clinically_acceptable=0.75, quality=0.9,
                specialist_quality=0.95)
    base.update(kw)
    return R.build_reward(**base)


def test_contract_keys_exact():
    assert set(R.REWARD_KEYS) == CONTRACT and len(R.REWARD_KEYS) == 7
    assert set(good()) == CONTRACT and set(R.zero_reward()) == CONTRACT


def test_default_scalar_rule():
    assert good()['reward'] == 0.75
    for gate in ('ran', 'valid', 'within_time'):
        r = good(**{gate: 2 / 3})
        assert r['reward'] == 0.0 and r['clinically_acceptable'] == 0.75
    assert R.scalar_reward({'ran': 1, 'valid': 1, 'within_time': 1, 'clinically_acceptable': 0.0}) == 0.0


def test_vs_specialist():
    assert good()['vs_specialist'] == pytest.approx(0.9 / 0.95)
    assert good(quality=1.0, specialist_quality=0.5)['vs_specialist'] == 1.0          # capped
    assert good(quality=0.2, specialist_quality=0.0)['vs_specialist'] == 1.0
    assert good(quality=0.0, specialist_quality=0.0)['vs_specialist'] == 0.0


@pytest.mark.parametrize('bad', [
    {'reward': math.nan}, {'reward': math.inf}, {'quality': 1.5}, {'valid': -0.1}, {'ran': True},
    {'within_time': '1'}, {'extra_mm': 0.3}])
def test_validation_refuses(bad):
    r = dict(R.zero_reward())
    r.update(bad)
    with pytest.raises(R.RewardContractError):
        R.validate_reward(r)
    missing = dict(R.zero_reward())
    del missing['vs_specialist']
    with pytest.raises(R.RewardContractError):
        R.validate_reward(missing)


def test_write_reward_and_metrics(tmp_path):
    R.write_reward(tmp_path, good(), {'hd95_mm': math.inf, 'nested': [1.0, math.nan], 'seconds': 2.5})
    reward = json.loads((tmp_path / 'reward.json').read_text())
    assert set(reward) == CONTRACT and all(isinstance(v, float) for v in reward.values())
    metrics = json.loads((tmp_path / 'metrics.json').read_text())
    assert metrics['hd95_mm'] is None and metrics['nested'] == [1.0, None] and metrics['seconds'] == 2.5
    assert len(metrics['_nonfinite_to_null']) == 2
    with pytest.raises(R.RewardContractError):
        R.write_reward(tmp_path / 'x', {'reward': 1.0})
    assert not (tmp_path / 'x' / 'reward.json').exists()


def test_provisional_zero(tmp_path):
    R.write_provisional_zero(tmp_path)
    assert json.loads((tmp_path / 'reward.json').read_text()) == R.zero_reward()
