#!/usr/bin/env bash
set -euo pipefail
exec python -I "$(dirname "$0")/../write_case.py" voxelcount "$1" "$2"
