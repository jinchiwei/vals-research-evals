#!/usr/bin/env bash
# Classical reference pipeline (no deep learning). run.sh INPUT_DIR OUTPUT_DIR
set -euo pipefail
exec python -I "$(dirname "$0")/segment.py" "$1" "$2"
