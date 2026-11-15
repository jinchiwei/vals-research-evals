"""risk_icu tests on synthetic patients (no real PhysioNet data needed).

Run: ~/miniconda3/envs/vals-suite-risk_icu/bin/python -m pytest tests/suite/test_risk_icu.py -q
"""
import csv
import math
import os
import stat

import numpy as np
import pytest

from suite.families.risk_icu import grade, grader, records
from suite.families.risk_icu.gate import GATE

SEED = 20261114


# ----------------------------------------------------------------------------- synthetic data
def synthetic_record(rid, age=60, gender=1, height=-1, icu=3, weight=80, hr=(80, 90), extra=()):
    lines = ["Time,Parameter,Value", f"00:00,RecordID,{rid}", f"00:00,Age,{age}", f"00:00,Gender,{gender}",
             f"00:00,Height,{height}", f"00:00,ICUType,{icu}", f"00:00,Weight,{weight}"]
    for i, v in enumerate(hr):
        lines.append(f"{i:02d}:30,HR,{v}")
    lines.extend(extra)
    return "\n".join(lines) + "\n"


def synthetic_cohort(tmp_path, n=400, seed=SEED):
    rng = np.random.default_rng(seed)
    inp = tmp_path / "input"
    inp.mkdir()
    rows = []
    for i in range(n):
        rid = 500000 + i
        sev = rng.normal()
        p = 1 / (1 + math.exp(-(-2.0 + 1.5 * sev)))
        y = int(rng.random() < p)
        icu = int(rng.integers(1, 5))
        sex = int(rng.integers(0, 2))
        hr = [int(80 + 15 * sev + rng.normal() * 5)] * 3
        (inp / f"{rid}.txt").write_text(synthetic_record(rid, gender=sex, icu=icu, hr=hr))
        rows.append({"RecordID": rid, "in_hospital_death": y, "saps1": 10, "sofa": 3, "icu_type": icu,
                     "gender": sex, "age": 60, "_p": p})
    ref = tmp_path / "reference"
    ref.mkdir()
    with open(ref / "outcomes.csv", "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=[k for k in rows[0] if k != "_p"])
        w.writeheader()
        w.writerows([{k: v for k, v in r.items() if k != "_p"} for r in rows])
    return inp, ref, rows


def write_preds(path, pairs, header="RecordID,risk"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "".join(f"{a},{b}\n" for a, b in pairs))
    return str(path)


# ----------------------------------------------------------------------------- record parsing
def test_parse_record_descriptors_and_series():
    rec = records.parse_record_text(synthetic_record(132539, height=-1, extra=["47:59,GCS,15", "48:00,Urine,30"]))
    assert rec.record_id == 132539
    assert math.isnan(rec.descriptors["Height"])  # -1 means missing
    assert rec.descriptors["Age"] == 60 and rec.descriptors["ICUType"] == 3
    assert rec.series["HR"] == [(30, 80.0), (90, 90.0)]
    assert rec.series["GCS"] == [(47 * 60 + 59, 15.0)]
    assert rec.series["Urine"] == [(2880, 30.0)]


def test_weight_recurs_as_time_series():
    rec = records.parse_record_text(synthetic_record(1, weight=70, extra=["12:00,Weight,72.5"]))
    assert rec.descriptors["Weight"] == 70
    assert rec.series["Weight"] == [(720, 72.5)]


@pytest.mark.parametrize("text", [
    "Time,Param,Value\n00:00,RecordID,1\n",
    "Time,Parameter,Value\n00:00,Age,50\n",
    "Time,Parameter,Value\n00:00,RecordID,1\n0:61,HR,80\n",
    "Time,Parameter,Value\n00:00,RecordID,1\n00:10,HR,abc\n",
])
def test_parse_record_rejects_malformed(text):
    with pytest.raises(records.RecordFormatError):
        records.parse_record_text(text)


def test_replace_record_id_only_touches_descriptor_line():
    text = synthetic_record(142675)
    new = records.replace_record_id(text, 777777)
    assert records.parse_record_text(new).record_id == 777777
    assert new.replace("777777", "142675") == text


# ----------------------------------------------------------------------------- strict output validation
def test_validate_accepts_exact_output(tmp_path):
    p = write_preds(tmp_path / "p.csv", [(1, 0.1), (2, 0.0), (3, 1.0)])
    assert grade.validate_predictions(p, [1, 2, 3]) == {1: 0.1, 2: 0.0, 3: 1.0}


@pytest.mark.parametrize("pairs,header", [
    ([(1, 0.1), (2, 0.2)], "RecordID,risk"),                       # missing id 3
    ([(1, 0.1), (2, 0.2), (3, 0.3), (4, 0.4)], "RecordID,risk"),   # extra id
    ([(1, 0.1), (1, 0.2), (3, 0.3)], "RecordID,risk"),             # duplicate
    ([(1, "nan"), (2, 0.2), (3, 0.3)], "RecordID,risk"),           # NaN
    ([(1, "inf"), (2, 0.2), (3, 0.3)], "RecordID,risk"),           # inf
    ([(1, 1.2), (2, 0.2), (3, 0.3)], "RecordID,risk"),             # > 1
    ([(1, -0.01), (2, 0.2), (3, 0.3)], "RecordID,risk"),           # < 0
    ([(1, "0.1,x"), (2, 0.2), (3, 0.3)], "RecordID,risk"),         # extra column
    ([("a1", 0.1), (2, 0.2), (3, 0.3)], "RecordID,risk"),          # non-integer id
    ([(1, 0.1), (2, 0.2), (3, 0.3)], "RecordID,prob"),             # wrong header
    ([(1, "high"), (2, 0.2), (3, 0.3)], "RecordID,risk"),          # not a number
])
def test_validate_rejects(tmp_path, pairs, header):
    p = write_preds(tmp_path / "p.csv", pairs, header)
    with pytest.raises(grade.InvalidOutput):
        grade.validate_predictions(p, [1, 2, 3])


def test_validate_rejects_missing_file(tmp_path):
    with pytest.raises(grade.InvalidOutput):
        grade.validate_predictions(str(tmp_path / "none.csv"), [1])


# ----------------------------------------------------------------------------- metrics
def test_auroc_basic_and_ties():
    assert grade.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert grade.auroc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert grade.auroc([0, 1, 0, 1], [0.5] * 4) == 0.5
    assert grade.auroc([0, 1, 1, 0], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.5)


def test_calibration_recovers_truth_and_flags_overconfidence():
    rng = np.random.default_rng(1)
    lp = rng.normal(-1.8, 1.2, 20000)
    p = 1 / (1 + np.exp(-lp))
    y = (rng.random(len(p)) < p).astype(int)
    slope, citl = grade.calibration_slope_intercept(y, p)
    assert slope == pytest.approx(1.0, abs=0.06) and abs(citl) < 0.05
    over = 1 / (1 + np.exp(-3 * lp))
    slope3, _ = grade.calibration_slope_intercept(y, over)
    assert slope3 == pytest.approx(1 / 3, abs=0.03)
    slope_c, citl_c = grade.calibration_slope_intercept(y, np.full(len(y), y.mean()))
    assert math.isnan(slope_c) and abs(citl_c) < 1e-6  # constant risk: slope undefined


def test_event1_uses_expected_death_count():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.2, 0.6, 0.1, 0.05, 0.05, 0.05, 0.02, 0.02, 0.01])  # sum = 2.0 -> flag top 2
    e = grade.event1(y, p)
    assert e["k_expected"] == 2 and e["n_flagged"] == 2
    assert e["se"] == 0.5 and e["ppv"] == 0.5 and e["event1"] == 0.5
    const = grade.event1(y, np.full(10, 0.2))  # ties: everyone flagged
    assert const["n_flagged"] == 10 and const["event1"] == pytest.approx(0.2)
    assert grade.event1(y, np.zeros(10))["event1"] == 0.0


def test_net_benefit_formula():
    y = np.array([1, 1, 0, 0, 0])
    p = np.array([0.9, 0.1, 0.3, 0.1, 0.1])
    nb, nb_all = grade.net_benefit(y, p, 0.2)
    assert nb == pytest.approx(1 / 5 - (1 / 5) * 0.25)
    assert nb_all == pytest.approx(2 / 5 - (3 / 5) * 0.25)


def test_hosmer_lemeshow_matches_score_c_shape():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.01, 0.6, 4000)
    y = (rng.random(4000) < p).astype(int)
    assert grade.hosmer_lemeshow_event2(y, p) < grade.hosmer_lemeshow_event2(y, np.clip(p * 1.8, 0, 1))


# ----------------------------------------------------------------------------- gate components
def _metrics(**over):
    m = {"event1": 0.45, "cal_slope": 1.0, "cal_intercept_citl": 0.0, "net_benefit": 0.05,
         "net_benefit_treat_all": -0.07, "auroc": 0.85, "worst_subgroup_auroc": 0.80}
    m.update(over)
    return m


@pytest.mark.parametrize("over,failed", [
    ({}, set()),
    ({"event1": GATE["event1"]["bar"] - 1e-3}, {"event1_vs_saps"}),
    ({"event1": GATE["event1"]["bar"]}, set()),
    ({"cal_slope": 0.79}, {"calibration"}),
    ({"cal_slope": 1.21}, {"calibration"}),
    ({"cal_slope": float("nan")}, {"calibration"}),
    ({"cal_intercept_citl": 0.21}, {"calibration"}),
    ({"cal_intercept_citl": -0.21}, {"calibration"}),
    ({"net_benefit": 0.0}, {"net_benefit"}),
    ({"net_benefit": 0.01, "net_benefit_treat_all": 0.02}, {"net_benefit"}),
    ({"worst_subgroup_auroc": 0.74}, {"worst_subgroup"}),
    ({"worst_subgroup_auroc": 0.75}, set()),
])
def test_gate_components(over, failed):
    comps = grade.gate_components(_metrics(**over), GATE)
    assert {k for k, ok in comps.items() if not ok} == failed


def test_gate_constants_are_the_fixed_ones():
    assert GATE["event1"]["bar"] == 0.321
    assert (GATE["calibration"]["slope_min"], GATE["calibration"]["slope_max"]) == (0.8, 1.2)
    assert GATE["calibration"]["citl_abs_max"] == 0.2
    assert GATE["net_benefit"]["threshold"] == 0.2
    assert GATE["subgroup"]["max_auroc_gap"] == 0.10
    assert GATE["time_limit_s"] == 300


# ----------------------------------------------------------------------------- reward
def test_reward_keys_and_gating():
    m = {"clinically_acceptable": 0.75, "auroc": 0.8}
    r = grade.reward_from(True, True, True, m, specialist_auroc=0.9)
    assert set(r) == set(grade.REWARD_KEYS) and all(0 <= v <= 1 for v in r.values())
    assert r["reward"] == 0.75 and r["quality"] == pytest.approx(0.6) and r["vs_specialist"] == pytest.approx(0.75)
    assert grade.reward_from(True, True, False, m, 0.9)["reward"] == 0.0
    assert grade.reward_from(True, False, True, None, 0.9) == {**{k: 0.0 for k in grade.REWARD_KEYS},
                                                               "ran": 1.0, "within_time": 1.0}


# ----------------------------------------------------------------------------- end to end
def _pipeline(tmp_path, name, body):
    d = tmp_path / name
    d.mkdir()
    (d / "run.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body)
    os.chmod(d / "run.sh", stat.S_IRWXU)
    return str(d)


def test_end_to_end_separates_pipelines(tmp_path, monkeypatch):
    inp, ref, rows = synthetic_cohort(tmp_path, n=2000)
    truth = tmp_path / "truth.csv"
    write_preds(truth, [(r["RecordID"], f"{r['_p']:.6f}") for r in rows])
    good = _pipeline(tmp_path, "good", f'mkdir -p "$2"; cp {truth} "$2/predictions.csv"\n')
    const = _pipeline(tmp_path, "const", 'mkdir -p "$2"; { echo RecordID,risk; for f in "$1"/*.txt; do '
                                         'b="${f##*/}"; echo "${b%.txt},0.14"; done; } > "$2/predictions.csv"\n')
    slow = _pipeline(tmp_path, "slow", f'sleep 30; cp {truth} "$2/predictions.csv"\n')
    crash = _pipeline(tmp_path, "crash", "exit 3\n")
    gate = dict(GATE, subgroup=dict(GATE["subgroup"], min_events_per_class=3))
    res = {}
    for name, pipe in (("good", good), ("const", const), ("slow", slow), ("crash", crash)):
        res[name] = grade.grade(pipe, str(inp), str(ref / "outcomes.csv"), gate, str(tmp_path / f"w_{name}"),
                                limit=5.0, specialist_auroc=None, n_boot=0)
    g = res["good"]
    assert g["reward"]["ran"] == g["reward"]["valid"] == g["reward"]["within_time"] == 1.0
    assert g["metrics"]["gate"]["calibration"] and g["metrics"]["gate"]["net_benefit"]
    assert g["reward"]["quality"] > 0.4
    c = res["const"]
    assert c["reward"]["valid"] == 1.0 and c["metrics"]["auroc"] == 0.5 and c["reward"]["quality"] == 0.0
    assert not c["metrics"]["gate"]["calibration"] and not c["metrics"]["gate"]["net_benefit"]
    assert c["reward"]["reward"] < g["reward"]["reward"]
    s = res["slow"]
    assert s["run"]["timed_out"] and s["run"]["wall_s"] < 15 and s["reward"]["reward"] == 0.0
    assert res["crash"]["reward"]["ran"] == 0.0 and res["crash"]["reward"]["reward"] == 0.0


def test_core_plugin_grade_case(tmp_path):
    inp, ref, rows = synthetic_cohort(tmp_path, n=300)
    out = tmp_path / "out"
    write_preds(out / "predictions.csv", [(r["RecordID"], f"{r['_p']:.6f}") for r in rows])
    g = grader.grade_case(out, inp, ref)
    assert g["valid"] and 0 < g["quality"] <= 1 and 0 <= g["metrics"]["gate_fraction"] <= 1
    assert g["acceptable"] == (g["metrics"]["gate_fraction"] == 1.0)
    write_preds(out / "predictions.csv", [(r["RecordID"], "nan") for r in rows])
    bad = grader.grade_case(out, inp, ref)
    assert not bad["valid"] and not bad["acceptable"] and bad["quality"] == 0.0
    assert grader.REQUIRED_OUTPUTS == ("predictions.csv",)
