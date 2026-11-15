"""Generated verifier entry point (direct answer); the procedure is in lib/suite/families/label_ptbxl_reports/grader.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from suite.families.label_ptbxl_reports.grader import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
