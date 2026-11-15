#!/usr/bin/env bash
set -euo pipefail
exec python -I "$(dirname "$(readlink -f "$0")")/predict.py" "$1" "$2"
