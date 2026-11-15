#!/usr/bin/env bash
# Specialist comparator (b): small U-Net, CPU inference. Runs on teal in vals-suite-measure_hc18
# (needs torch; NOT part of the build-tier task image). Weights: HC18_UNET_WEIGHTS or the default path.
set -euo pipefail
exec python3 -I "$(dirname "$0")/measure.py" "$1" "$2"
