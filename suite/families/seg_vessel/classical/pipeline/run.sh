#!/bin/bash
# seg_vessel simple comparator: Frangi vesselness + threshold fitted on development images only.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/opt/benchmark-venv/bin/python3
[ -x "$PY" ] || PY=python3
exec "$PY" -I "$HERE/segment.py" "$1" "$2"
