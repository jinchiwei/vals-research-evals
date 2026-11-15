"""Self-check oracle: looks up the reference HC (grader self-check only; reads HC18_ORACLE_REFS)."""
import csv, json, os, sys
from pathlib import Path
inp, out = Path(sys.argv[1]), Path(sys.argv[2])
case = json.loads((inp / "case.json").read_text())
refs = {r["case_id"]: r["hc_mm"] for r in csv.DictReader(open(os.environ["HC18_ORACLE_REFS"]))}
(out / "measurement.csv").write_text(f"case_id,hc_mm\n{case['case_id']},{refs[case['case_id']]}\n")
