"""ecg_ptbxl grader and split tests on synthetic ECG-shaped data (no PTB-XL needed).

    conda run -n vals-suite-ecg_ptbxl python -m pytest tests/suite/test_ecg_ptbxl.py -q
"""
import csv
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

FAM = Path(__file__).resolve().parents[2] / "suite" / "families" / "ecg_ptbxl"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load("ecg_grade_t", FAM / "grade.py")
PREP = _load("ecg_prep_t", FAM / "prepare_data.py")
SIMPLE = _load("ecg_simple_t", FAM / "simple_ref" / "predict.py")
C = G.CLASSES


def synth(n=600, seed=0):
    rng = np.random.default_rng(seed)
    Y = (rng.random((n, 5)) < np.array([0.4, 0.25, 0.25, 0.22, 0.12])).astype(int)
    ids = [f"h{i:06x}" for i in range(n)]
    sex = np.where(rng.random(n) < 0.5, "M", "F")
    band = rng.choice(["age<55", "age55-69", "age>=70"], n)
    return ids, Y, {"sex": sex, "age_band": band}


def write_hidden(tmp, ids, Y, groups, n_samples=1000):
    hid = tmp / "hidden"
    (hid / "input").mkdir(parents=True)
    with open(hid / "reference.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id"] + C + ["sex", "age", "age_band"])
        for i, rid in enumerate(ids):
            w.writerow([rid, *Y[i], groups["sex"][i], 60, groups["age_band"][i]])
    with open(hid / "input" / "meta.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id", "age", "sex"])
        for i, rid in enumerate(ids):
            w.writerow([rid, 60, groups["sex"][i]])
    np.savez_compressed(hid / "input" / "signals.npz", signals=np.zeros((len(ids), n_samples, 12), np.int16))
    return hid


def write_preds(path, ids, P, header=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header or ["record_id"] + C)
        for rid, p in zip(ids, P):
            w.writerow([rid, *p])


def pipeline_from_probs(tmp, name, ids, P, sleep=0.0, exit_code=0):
    d = tmp / name
    d.mkdir()
    write_preds(d / "preds.csv", ids, P)
    (d / "run.sh").write_text("#!/usr/bin/env bash\n"
                              f"sleep {sleep}\n"
                              'cp "$(dirname "$0")/preds.csv" "$2/predictions.csv"\n'
                              f"exit {exit_code}\n")
    return d


# ------------------------------------------------------------------ metrics
def test_auroc_matches_pairwise_definition_with_ties():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 200)
    p = np.round(rng.random(200), 1)          # many ties
    pos, neg = p[y == 1], p[y == 0]
    want = ((pos[:, None] > neg[None]).sum() + 0.5 * (pos[:, None] == neg[None]).sum()) / (len(pos) * len(neg))
    assert G.auroc(y, p) == pytest.approx(want)
    assert math.isnan(G.auroc(np.zeros(5), np.arange(5)))


def test_sensitivity_at_specificity():
    y = np.array([0] * 10 + [1] * 10)
    p = np.r_[np.arange(10) / 10, np.arange(10) / 10 + 0.85]
    sens, spec, thr = G.sensitivity_at_specificity(y, p, 0.9)
    assert spec >= 0.9 and sens == 1.0
    sens_c, _, _ = G.sensitivity_at_specificity(y, np.full(20, 0.3), 0.9)
    assert sens_c == 0.0                   # constant scores cannot buy sensitivity with ties


def test_ece_and_slope():
    rng = np.random.default_rng(2)
    p = rng.random(20000)
    y = (rng.random(20000) < p).astype(int)
    assert G.ece(y, p) < 0.02
    slope, intercept = G.calibration_slope_intercept(y, p)
    assert slope == pytest.approx(1.0, abs=0.1) and intercept == pytest.approx(0.0, abs=0.1)
    sharp = 1 / (1 + np.exp(-5 * np.log(p / (1 - p))))
    assert G.ece(y, sharp) > 0.1


def test_quality_mapping():
    assert G.quality_score(0.5) == 0.0
    assert G.quality_score(0.928) == pytest.approx(1.0)
    assert G.quality_score(0.99) == 1.0 and G.quality_score(0.3) == 0.0
    assert G.quality_score(float("nan")) == 0.0
    assert G.vs_specialist_score(0.7, 0.9) == pytest.approx(0.5)


# ------------------------------------------------------------------ parser
def test_parser_strict(tmp_path):
    ids = ["a", "b"]
    good = tmp_path / "g.csv"
    write_preds(good, ids, [[0.1] * 5, [0.9] * 5])
    assert G.parse_predictions(good, ids).shape == (2, 5)
    cases = {
        "header": (["record_id", "MI", "NORM", "STTC", "CD", "HYP"], [[0.1] * 5, [0.2] * 5], ids),
        "nan": (None, [[0.1] * 5, [float("nan")] + [0.2] * 4], ids),
        "range": (None, [[0.1] * 5, [1.2] + [0.2] * 4], ids),
        "missing": (None, [[0.1] * 5], ["a"]),
        "dup": (None, [[0.1] * 5, [0.1] * 5], ["a", "a"]),
        "unknown": (None, [[0.1] * 5, [0.1] * 5], ["a", "z"]),
    }
    for name, (hdr, P, rid) in cases.items():
        f = tmp_path / f"{name}.csv"
        write_preds(f, rid, P, header=hdr)
        with pytest.raises(G.InvalidOutput):
            G.parse_predictions(f, ids)
    with pytest.raises(G.InvalidOutput):
        G.parse_predictions(tmp_path / "absent.csv", ids)


# ------------------------------------------------------------------ end-to-end grading
@pytest.fixture
def hidden(tmp_path):
    ids, Y, groups = synth()
    return tmp_path, ids, Y, groups, write_hidden(tmp_path, ids, Y, groups)


def _grade(tmp, pipe, hid, name):
    reward, metrics = G.grade(pipe, hid, tmp / f"logs_{name}", None, n_boot=50)
    on_disk = json.loads((tmp / f"logs_{name}" / "reward.json").read_text())
    assert set(on_disk) == set(G.REWARD_KEYS)
    assert all(isinstance(v, float) and 0.0 <= v <= 1.0 and math.isfinite(v) for v in on_disk.values())
    return reward, metrics


def test_grader_separates_pipelines(hidden):
    tmp, ids, Y, groups, hid = hidden
    rng = np.random.default_rng(3)
    oracle = Y.astype(float)
    const = np.tile(Y.mean(0), (len(ids), 1))
    noisy = 1 / (1 + np.exp(-(3 * (Y - 0.5) + rng.normal(0, 1.0, Y.shape))))     # fair ranking
    over = 1 / (1 + np.exp(-8 * np.log(noisy / (1 - noisy))))                     # same ranking, overconfident
    r_or, m_or = _grade(tmp, pipeline_from_probs(tmp, "oracle", ids, oracle), hid, "oracle")
    r_co, m_co = _grade(tmp, pipeline_from_probs(tmp, "const", ids, const), hid, "const")
    r_ov, m_ov = _grade(tmp, pipeline_from_probs(tmp, "over", ids, over), hid, "over")
    assert r_or["reward"] == 1.0 and r_or["quality"] == 1.0 and m_or["scores"]["gate_all_met"]
    assert r_co["valid"] == 1.0 and r_co["quality"] == 0.0 and not m_co["scores"]["gate"]["mi_operating_point"]
    assert r_co["reward"] == 0.0            # calibrated but useless earns nothing
    assert m_ov["scores"]["macro_auroc"] == pytest.approx(G.macro_auroc(Y, noisy))
    assert not m_ov["scores"]["gate"]["calibration"]
    assert r_ov["reward"] < r_or["reward"]


def test_grader_time_and_failures(hidden, monkeypatch):
    tmp, ids, Y, groups, hid = hidden
    monkeypatch.setitem(G.TIME_RULE, "startup_allowance_s", 0.5)
    monkeypatch.setitem(G.TIME_RULE, "per_ecg_s", 0.0)
    monkeypatch.setitem(G.TIME_RULE, "hard_kill_factor", 10.0)   # finishes late but before the hard kill
    slow = pipeline_from_probs(tmp, "slow", ids, Y.astype(float), sleep=1.5)
    r, m = _grade(tmp, slow, hid, "slow")
    assert r["ran"] == 1.0 and r["valid"] == 1.0 and r["within_time"] == 0.0 and r["reward"] == 0.0
    assert m["scores"]["macro_auroc"] == 1.0                     # still scored for diagnostics
    monkeypatch.setitem(G.TIME_RULE, "hard_kill_factor", 2.0)
    hang = pipeline_from_probs(tmp, "hang", ids, Y.astype(float), sleep=30)
    r, m = _grade(tmp, hang, hid, "hang")
    assert r["ran"] == 0.0 and r["reward"] == 0.0 and m["run"]["killed"]
    monkeypatch.setitem(G.TIME_RULE, "startup_allowance_s", 60)
    crash = pipeline_from_probs(tmp, "crash", ids, Y.astype(float), exit_code=3)
    r, _ = _grade(tmp, crash, hid, "crash")
    assert r["ran"] == 0.0 and r["reward"] == 0.0
    r, m = _grade(tmp, tmp / "does_not_exist", hid, "missing")
    assert r == {k: 0.0 for k in G.REWARD_KEYS}


def test_harbor_staging_does_not_follow_symlinks():
    src = (FAM / "grade.py").read_text()
    assert 'shutil.copytree(pipeline, eval_root / "pipeline", symlinks=True)' in src
    assert "kill_uid(NOBODY)" in src and '"pkill"' not in src


def test_gate_is_fraction_of_components(hidden):
    tmp, ids, Y, groups, hid = hidden
    m = G.full_report(Y, Y.astype(float), groups, n_boot=0)
    assert m["gate_fraction_met"] == 1.0
    m["macro_ece"] = 0.2
    g = G.gate_components(m)
    assert sum(g.values()) == 2 and G.gate_fraction(g) == pytest.approx(2 / 3)
    assert G.gate_fraction({"mi_operating_point": False, "calibration": True, "subgroup_gap": True}) == 0.0


# ------------------------------------------------------------------ split helpers and features
def test_stratified_sample_is_proportional_and_deterministic():
    keys = np.array(["a"] * 600 + ["b"] * 300 + ["c"] * 100)
    idx = np.arange(1000) + 5000
    s1 = PREP.stratified_sample(idx, keys, 100, np.random.default_rng(PREP.SEED))
    s2 = PREP.stratified_sample(idx, keys, 100, np.random.default_rng(PREP.SEED))
    assert np.array_equal(s1, s2) and len(np.unique(s1)) == 100
    got = {k: int(np.isin(s1, idx[keys == k]).sum()) for k in "abc"}
    assert got == {"a": 60, "b": 30, "c": 10}


def test_age_band_and_list_hash():
    assert [PREP.age_band(a) for a in (30, 55, 69, 70, 90)] == ["age<55", "age55-69", "age55-69", "age>=70", "age>=70"]
    assert PREP.list_hash([3, 1]) != PREP.list_hash([1, 3])


def test_simple_features_on_synthetic_ecg():
    t = np.arange(1000) / 100.0
    beat = np.zeros(1000)
    for c in np.arange(0.5, 10, 0.8):          # 75 bpm spikes
        beat += 1.2 * np.exp(-((t - c) / 0.02) ** 2)
    sig = (np.tile(beat[:, None], (1, 12)) * 1000).astype(np.int16)
    f = SIMPLE.features(sig, 60, 1.0)
    assert np.all(np.isfinite(f))
    hr = 60.0 / (np.diff(SIMPLE.r_peaks(sig / 1000.0)).mean() / 100)
    assert hr == pytest.approx(75, abs=3)
