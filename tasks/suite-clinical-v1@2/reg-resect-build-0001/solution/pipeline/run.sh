#!/bin/bash
# Entry point contract: run.sh INPUT_DIR OUTPUT_DIR (one case). Offline; python3 from the image venv.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I "$HERE/mind_reg.py" "$1" "$2"
