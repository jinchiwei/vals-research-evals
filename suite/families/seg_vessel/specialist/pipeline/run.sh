#!/bin/bash
# seg_vessel specialist: small U-Net trained on the 20 development images only; CPU inference.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/opt/benchmark-venv/bin/python3
[ -x "$PY" ] || PY=python3
exec "$PY" -I "$HERE/infer.py" "$1" "$2"
