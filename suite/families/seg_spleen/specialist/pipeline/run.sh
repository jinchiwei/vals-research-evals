#!/usr/bin/env bash
# Specialist / toolbox-tier pipeline: TotalSegmentator (task "total", spleen ROI subset).
# run.sh INPUT_DIR OUTPUT_DIR. Needs TotalSegmentator on PATH and TOTALSEG_HOME_DIR with
# pre-fetched weights. SEG_SPLEEN_TS_MODE=full|fast, SEG_SPLEEN_TS_DEVICE=cpu|gpu.
set -euo pipefail
IN=$1; OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
THREADS=${OMP_NUM_THREADS:-4}
FAST=()
[ "${SEG_SPLEEN_TS_MODE:-full}" = fast ] && FAST=(--fast)
WORK=$(mktemp -d "${HOME:-/tmp}/ts.XXXXXX")
TotalSegmentator -i "$IN/image.nii.gz" -o "$WORK" --roi_subset spleen \
    -d "${SEG_SPLEEN_TS_DEVICE:-cpu}" -nr "$THREADS" -ns "$THREADS" -q "${FAST[@]}"
python -I "$HERE/finish.py" "$IN/image.nii.gz" "$WORK/spleen.nii.gz" "$OUT"
rm -rf "$WORK"
