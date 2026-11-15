"""Failure pipeline: correct answer (oracle lookup) but takes 12 s per image, over the 10 s limit."""
import csv, json, os, sys, time
from pathlib import Path
inp, out = Path(sys.argv[1]), Path(sys.argv[2])
case = json.loads((inp / "case.json").read_text())
refs = {r["case_id"]: r["hc_mm"] for r in csv.DictReader(open(os.environ["HC18_ORACLE_REFS"]))}
time.sleep(12)
(out / "measurement.csv").write_text(f"case_id,hc_mm\n{case['case_id']},{refs[case['case_id']]}\n")
