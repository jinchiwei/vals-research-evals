#!/usr/bin/env bash
# Correct output, but only after sleeping past the limit (SEG_SPLEEN_SLOW_SEC, default 400 s).
set -euo pipefail
sleep "${SEG_SPLEEN_SLOW_SEC:-400}"
exec python -I "$(dirname "$0")/../write_case.py" oracle "$1" "$2"
