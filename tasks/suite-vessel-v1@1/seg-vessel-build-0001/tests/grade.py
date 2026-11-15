"""Generated verifier entry point; the procedure lives in suite/core/grading.py (vendored in lib/)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from suite.core.grading import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
