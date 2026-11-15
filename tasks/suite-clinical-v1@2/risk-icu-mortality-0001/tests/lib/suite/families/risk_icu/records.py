"""Parser for PhysioNet/CinC Challenge 2012 per-stay record files.

Format (one file per ICU stay, ``<RecordID>.txt``)::

    Time,Parameter,Value
    00:00,RecordID,132539
    00:00,Age,54
    00:00,Gender,0
    00:00,Height,-1
    00:00,ICUType,4
    00:00,Weight,-1
    00:07,GCS,15
    ...

``Time`` is elapsed ``HH:MM`` since ICU admission (00:00 to 48:00). The six
general descriptors appear at 00:00; ``-1`` means missing. ``Weight`` also
recurs later as a time series. Used by the grader, the comparators and tests;
stdlib only so it can run anywhere.
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, NamedTuple, Tuple

DESCRIPTORS = ("RecordID", "Age", "Gender", "Height", "ICUType", "Weight")
TIME_SERIES = (
    "Albumin", "ALP", "ALT", "AST", "Bilirubin", "BUN", "Cholesterol", "Creatinine",
    "DiasABP", "FiO2", "GCS", "Glucose", "HCO3", "HCT", "HR", "K", "Lactate", "Mg",
    "MAP", "MechVent", "Na", "NIDiasABP", "NIMAP", "NISysABP", "PaCO2", "PaO2", "pH",
    "Platelets", "RespRate", "SaO2", "SysABP", "Temp", "TroponinI", "TroponinT",
    "Urine", "WBC", "Weight",
)


class RecordFormatError(ValueError):
    pass


class Record(NamedTuple):
    record_id: int
    descriptors: Dict[str, float]          # -1 kept as NaN
    series: Dict[str, List[Tuple[int, float]]]  # parameter -> [(minute, value)]


def parse_time(text: str) -> int:
    parts = text.strip().split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise RecordFormatError(f"bad time {text!r}")
    hours, minutes = int(parts[0]), int(parts[1])
    if minutes >= 60:
        raise RecordFormatError(f"bad time {text!r}")
    return hours * 60 + minutes


def parse_record_text(text: str) -> Record:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or lines[0] != "Time,Parameter,Value":
        raise RecordFormatError("missing header 'Time,Parameter,Value'")
    descriptors: Dict[str, float] = {}
    series: Dict[str, List[Tuple[int, float]]] = {}
    for n, line in enumerate(lines[1:], start=2):
        fields = line.split(",")
        if len(fields) != 3:
            raise RecordFormatError(f"line {n}: expected 3 fields")
        minute = parse_time(fields[0])
        name = fields[1].strip()
        if name == "":
            continue  # tolerate blank parameter names
        try:
            value = float(fields[2])
        except ValueError as exc:
            raise RecordFormatError(f"line {n}: bad value {fields[2]!r}") from exc
        if minute == 0 and name in DESCRIPTORS and name not in descriptors:
            descriptors[name] = math.nan if (value == -1 and name != "RecordID") else value
            continue
        series.setdefault(name, []).append((minute, value))
    if "RecordID" not in descriptors:
        raise RecordFormatError("no RecordID descriptor")
    rid = descriptors.pop("RecordID")
    if rid != int(rid):
        raise RecordFormatError("non-integer RecordID")
    return Record(int(rid), descriptors, series)


def read_record(path: str) -> Record:
    with open(path, "r", encoding="utf-8") as handle:
        return parse_record_text(handle.read())


def list_records(input_dir: str) -> List[str]:
    """Record files in a folder, sorted; the file stem is the RecordID."""
    names = sorted(n for n in os.listdir(input_dir) if n.endswith(".txt"))
    return [os.path.join(input_dir, n) for n in names]


def replace_record_id(text: str, new_id: int) -> str:
    """Rewrite the RecordID descriptor line (used to pseudonymise hidden stays)."""
    out, done = [], False
    for line in text.splitlines():
        if not done and line.startswith("00:00,RecordID,"):
            out.append(f"00:00,RecordID,{int(new_id)}")
            done = True
        else:
            out.append(line)
    if not done:
        raise RecordFormatError("no RecordID line to replace")
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")
