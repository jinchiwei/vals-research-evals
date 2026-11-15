"""Failure pipeline: perfect geometry but reports the circumference in pixels (forgets pixel size)."""
import csv, json, os, sys
from pathlib import Path
inp, out = Path(sys.argv[1]), Path(sys.argv[2])
case = json.loads((inp / "case.json").read_text())
refs = {r["case_id"]: float(r["hc_mm"]) for r in csv.DictReader(open(os.environ["HC18_ORACLE_REFS"]))}
v = refs[case["case_id"]] / case["pixel_size_mm"]
(out / "measurement.csv").write_text(f"case_id,hc_mm\n{case['case_id']},{v:.3f}\n")
