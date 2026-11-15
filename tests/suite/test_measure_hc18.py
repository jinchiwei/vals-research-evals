"""measure_hc18 grader and geometry tests on synthetic ellipses (no real data needed)."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "suite" / "families"))
from measure_hc18 import geometry, grader  # noqa: E402


def numeric_perimeter(a, b, n=200000):
    t = np.linspace(0, 2 * np.pi, n + 1)
    x, y = a * np.cos(t), b * np.sin(t)
    return float(np.sum(np.hypot(np.diff(x), np.diff(y))))


@pytest.mark.parametrize("a,b", [(100, 100), (120, 90), (200, 110)])
def test_ramanujan_perimeter_matches_numeric(a, b):
    assert geometry.ellipse_perimeter(a, b) == pytest.approx(numeric_perimeter(a, b), rel=1e-6)


def test_known_ellipse_outline_gives_known_circumference_in_mm():
    a, b, px = 180.0, 140.0, 0.12
    mask = geometry.draw_ellipse_outline((540, 800), 400.3, 270.7, a, b, 0.4, thickness=3)
    expected = geometry.ellipse_perimeter(a, b) * px
    assert geometry.hc_from_outline(mask, px) == pytest.approx(expected, rel=0.003)


def refs3():
    return {"c1": {"hc_mm": 100.0, "stratum": "s"}, "c2": {"hc_mm": 180.0, "stratum": "m"},
            "c3": {"hc_mm": 300.0, "stratum": "l"}}


def runs_ok(refs, s=0.5):
    return {c: {"seconds": s, "exit_code": 0, "timed_out": False} for c in refs}


def test_perfect_answers_score_one():
    refs = refs3()
    rew, met = grader.score(refs, {c: r["hc_mm"] for c, r in refs.items()}, runs_ok(refs), specialist_quality=0.8)
    assert set(rew) == set(grader.REWARD_KEYS)
    assert all(rew[k] == 1.0 for k in grader.REWARD_KEYS)
    assert met["overall"]["mae_mm"] == 0.0


def test_pixel_unit_answers_are_flagged_invalid():
    refs = refs3()
    px = {"c1": 0.08, "c2": 0.12, "c3": 0.25}
    preds = {c: refs[c]["hc_mm"] / px[c] for c in refs}  # 1250, 1500, 1200 "mm"
    rew, met = grader.score(refs, preds, runs_ok(refs))
    assert rew["valid"] == 0.0 and rew["reward"] == 0.0
    assert met["n_invalid"] == 3


def test_centimetre_answers_are_flagged_invalid():
    refs = refs3()
    rew, _ = grader.score(refs, {c: r["hc_mm"] / 10 for c, r in refs.items()}, runs_ok(refs))
    assert rew["valid"] == 0.0 and rew["reward"] == 0.0


def test_missing_row_is_invalid(tmp_path):
    refs = refs3()
    preds = {"c1": 100.0, "c2": 180.0}  # c3 missing
    rew, met = grader.score(refs, preds, runs_ok(refs))
    assert rew["valid"] == pytest.approx(2 / 3) and rew["reward"] == 0.0
    assert rew["clinically_acceptable"] == pytest.approx(2 / 3)
    f = tmp_path / "measurement.csv"
    f.write_text("case_id,hc_mm\n")
    assert grader.read_output(f, "c1") == (None, "expected_1_row_got_0")
    assert grader.read_output(tmp_path / "absent.csv", "c1")[1] == "missing_file"


@pytest.mark.parametrize("text,reason", [
    ("hc,case\nc1,100\n", "bad_header"),
    ("case_id,hc_mm\nc1,100\nc1,101\n", "expected_1_row_got_2"),
    ("case_id,hc_mm\nc9,100\n", "wrong_case_id"),
    ("case_id,hc_mm\nc1,nan\n", "not_finite"),
    ("case_id,hc_mm\nc1,abc\n", "not_a_number"),
])
def test_output_parser_rejects_bad_files(tmp_path, text, reason):
    f = tmp_path / "m.csv"
    f.write_text(text)
    assert grader.read_output(f, "c1") == (None, reason)


def test_tolerance_is_relative_and_fixed():
    refs = {"c": {"hc_mm": 200.0, "stratum": "x"}}
    assert grader.score(refs, {"c": 209.7}, runs_ok(refs))[0]["clinically_acceptable"] == 1.0  # 4.85 %
    assert grader.score(refs, {"c": 210.0}, runs_ok(refs))[0]["clinically_acceptable"] == 0.0  # 5.0 %


def test_timeout_zeroes_reward():
    refs = refs3()
    runs = runs_ok(refs)
    runs["c2"] = {"seconds": grader.TIME_LIMIT_S + 0.1, "exit_code": None, "timed_out": True}
    rew, _ = grader.score(refs, {c: r["hc_mm"] for c, r in refs.items()}, runs)
    assert rew["within_time"] == pytest.approx(2 / 3) and rew["reward"] == 0.0 and rew["ran"] == 1.0


def test_quality_mapping():
    refs = {"c": {"hc_mm": 200.0, "stratum": "x"}}
    q = grader.score(refs, {"c": 200.0 + 3.63}, runs_ok(refs))[0]["quality"]
    assert q == pytest.approx(0.5, abs=1e-3)


def test_runner_end_to_end_on_synthetic_ellipse(tmp_path):
    """A pipeline measuring a drawn ellipse through the real runner gets the right HC in mm."""
    a, b, px = 150.0, 120.0, 0.1
    from PIL import Image
    case = tmp_path / "in" / "case_x"
    case.mkdir(parents=True)
    img = geometry.draw_ellipse_outline((540, 800), 400, 270, a, b, 0.2, thickness=3) * 255
    Image.fromarray(img.astype(np.uint8)).save(case / "image.png")
    (case / "case.json").write_text(json.dumps({"case_id": "case_x", "pixel_size_mm": px}))
    pipe = tmp_path / "pipe"
    pipe.mkdir()
    (pipe / "run.sh").write_text('exec python3 -I "$(dirname "$0")/m.py" "$1" "$2"\n')
    fam = Path(geometry.__file__).resolve().parents[1]
    (pipe / "m.py").write_text(
        "import sys, json, numpy as np\nfrom pathlib import Path\nfrom PIL import Image\n"
        f"sys.path.insert(0, {str(fam)!r})\nfrom measure_hc18.geometry import hc_from_outline\n"
        "i, o = Path(sys.argv[1]), Path(sys.argv[2])\nc = json.loads((i/'case.json').read_text())\n"
        "v = hc_from_outline(np.asarray(Image.open(i/'image.png')) > 0, c['pixel_size_mm'])\n"
        "(o/'measurement.csv').write_text(f\"case_id,hc_mm\\n{c['case_id']},{v}\\n\")\n")
    preds, runs = grader.run_pipeline(pipe, tmp_path / "in", tmp_path / "work", limit_s=60)
    assert runs["case_x"]["exit_code"] == 0
    assert preds["case_x"] == pytest.approx(geometry.ellipse_perimeter(a, b) * px, rel=0.003)


def test_core_grade_case_interface(tmp_path):
    inp, ref, out = tmp_path / "in", tmp_path / "ref", tmp_path / "out"
    for d in (inp, ref, out):
        d.mkdir()
    (inp / "case.json").write_text(json.dumps({"case_id": "c1", "pixel_size_mm": 0.1}))
    (ref / "reference.json").write_text(json.dumps({"hc_mm": 180.0}))
    (out / "measurement.csv").write_text("case_id,hc_mm\nc1,181.0\n")
    r = grader.grade_case(out, inp, ref)
    assert r["valid"] and r["acceptable"] and r["quality"] == pytest.approx(1 - 1 / 7.26)
    (out / "measurement.csv").write_text("case_id,hc_mm\nc1,1800\n")  # pixels
    r = grader.grade_case(out, inp, ref)
    assert not r["valid"] and "outside plausible" in r["reason"]
    (out / "measurement.csv").unlink()
    assert not grader.grade_case(out, inp, ref)["valid"]
