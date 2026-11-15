#!/bin/bash
# Specialist / oracle pipeline: cross-fitted doubly robust (AIPW) estimator of the SATT.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/opt/benchmark-venv/bin/python3
[ -x "$PY" ] || PY=python3
exec "$PY" "$HERE/estimate.py" dr_att "$1" "$2"
