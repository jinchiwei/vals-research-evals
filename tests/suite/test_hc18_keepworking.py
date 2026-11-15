"""Round-3 K variant of measure_hc18: one added instruction paragraph, nothing else changed."""
import hashlib
import importlib.util
from pathlib import Path
import re

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("export_hc18_keepworking", REPO / "scripts" / "export_hc18_keepworking.py")
kw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kw)

V3 = REPO / "dist" / "suite-tasks-v3" / "measure_hc18" / "measure-hc18-0001"
K1 = REPO / "dist" / "suite-tasks-k1" / "measure_hc18" / "measure-hc18-0001"


def test_paragraph_is_the_preregistered_text():
    prereg = (REPO / "docs" / "research" / "suite" / "round3-prereg.md").read_text()
    quoted = re.findall(r"^  > (.*)$", prereg, flags=re.M)
    assert quoted, "blockquote not found in round3-prereg.md"
    assert " ".join(quoted) == " ".join(kw.KEEP_WORKING_PARAGRAPH.split("\n")).strip()


def test_appended_as_last_paragraph_and_only_once():
    out = kw.add_keep_working("# Title\n\nBody text.\n")
    assert out == "# Title\n\nBody text.\n\n" + kw.KEEP_WORKING_PARAGRAPH
    with pytest.raises(ValueError):
        kw.add_keep_working(out)


def test_bar_is_stated_above_the_paragraph():
    text = kw.add_keep_working((V3 / "instruction.md").read_text()) if V3.exists() else None
    if text is None:
        pytest.skip("dist/suite-tasks-v3 not present")
    at = text.index("**Using your session time.**")
    assert "4.9 % of the reference HC" in text[:at]
    assert "at least 90 % of hidden images" in text[:at]


def _digests(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


@pytest.mark.skipif(not (V3.exists() and K1.exists()), reason="dist exports not present")
def test_k1_export_differs_from_v3_only_in_instruction():
    v3, k1 = _digests(V3), _digests(K1)
    assert set(v3) == set(k1)
    differ = sorted(name for name in v3 if v3[name] != k1[name])
    assert differ == ["instruction.md"]
    assert (K1 / "instruction.md").read_text() == kw.add_keep_working((V3 / "instruction.md").read_text())


# ---- addendum K2 (clock check), round3-prereg.md 02:15 EST
K2 = REPO / "dist" / "suite-tasks-k2" / "measure_hc18" / "measure-hc18-0001"


def test_clock_paragraph_is_the_preregistered_text():
    prereg = (REPO / "docs" / "research" / "suite" / "round3-prereg.md").read_text()
    section = prereg[prereg.index("## Addendum K2"):]
    quoted = re.findall(r"^> (.*)$", section, flags=re.M)
    assert quoted, "K2 blockquote not found"
    assert " ".join(quoted) == " ".join(kw.CLOCK_CHECK_PARAGRAPH.split("\n")).strip()


def test_clock_paragraph_follows_keep_working_paragraph():
    k = kw.add_keep_working("# Title\n\nBody.\n")
    out = kw.add_clock_check(k)
    assert out == k + "\n" + kw.CLOCK_CHECK_PARAGRAPH
    with pytest.raises(ValueError):
        kw.add_clock_check("# Title\n\nBody.\n")   # needs K first
    with pytest.raises(ValueError):
        kw.add_clock_check(out)


@pytest.mark.skipif(not (K1.exists() and K2.exists()), reason="dist exports not present")
def test_k2_export_differs_from_k1_only_in_instruction():
    k1, k2 = _digests(K1), _digests(K2)
    assert set(k1) == set(k2)
    assert sorted(n for n in k1 if k1[n] != k2[n]) == ["instruction.md"]
    assert (K2 / "instruction.md").read_text() == kw.add_clock_check((K1 / "instruction.md").read_text())
