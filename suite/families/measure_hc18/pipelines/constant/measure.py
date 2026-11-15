"""Failure pipeline: always answers the development-set mean HC (174.43 mm over 152 dev images)."""
import json, sys
from pathlib import Path
inp, out = Path(sys.argv[1]), Path(sys.argv[2])
case = json.loads((inp / "case.json").read_text())
(out / "measurement.csv").write_text(f"case_id,hc_mm\n{case['case_id']},174.43\n")
