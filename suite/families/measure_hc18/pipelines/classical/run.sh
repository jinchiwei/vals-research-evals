#!/usr/bin/env bash
set -euo pipefail
exec python3 -I "$(dirname "$0")/measure.py" "$1" "$2"
