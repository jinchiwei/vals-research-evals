"""Toy pipeline: threshold the bright sphere, write mask.nii.gz and measurements.json.

Usage: python3 segment.py INPUT_DIR OUTPUT_DIR [MODE]
MODE (baked into run.sh by suite/families/toy/pipelines.py):
  oracle          correct: mask on the input grid, volume in mL
  specialist      a deliberately cruder smoothed threshold (the precomputed baseline)
  slow            oracle outputs, then a fake timing.json claiming 0.01 s, then sleeps an hour
  wrong_geometry  correct voxels written with an identity affine (spacing/origin/orientation lost)
  wrong_units     correct mask, but reports volume in mm^3 under the key volume_ml
Needs only numpy, scipy and nibabel (all in /opt/benchmark-venv). Works offline.
"""
import json
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

inp, out = Path(sys.argv[1]), Path(sys.argv[2])
mode = sys.argv[3] if len(sys.argv) > 3 else 'oracle'
out.mkdir(parents=True, exist_ok=True)

image = nib.load(str(inp / 'image.nii.gz'))
data = np.asanyarray(image.dataobj).astype(np.float32)
if mode == 'specialist':
    data = ndimage.uniform_filter(data, size=3)
    mask = data > 60
else:
    mask = data > 50

affine = np.eye(4) if mode == 'wrong_geometry' else image.affine
result = nib.Nifti1Image(mask.astype(np.uint8), affine)
result.header.set_xyzt_units('mm')
nib.save(result, str(out / 'mask.nii.gz'))

voxel_mm3 = abs(float(np.linalg.det(image.affine[:3, :3])))
volume_mm3 = int(mask.sum()) * voxel_mm3
volume = volume_mm3 if mode == 'wrong_units' else volume_mm3 / 1000.0
(out / 'measurements.json').write_text(json.dumps({'volume_ml': volume}) + '\n')

if mode == 'slow':
    (out / 'timing.json').write_text(json.dumps({'wall_seconds': 0.01}) + '\n')
    time.sleep(3600)
