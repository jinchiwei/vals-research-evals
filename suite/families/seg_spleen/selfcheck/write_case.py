"""Self-check helper: write a contract output for one case.

  write_case.py MODE INPUT_DIR OUTPUT_DIR
MODE: oracle (reference mask, mL), empty (all-zero mask, 0 mL),
      voxelcount (reference mask, volume reported as voxel count, i.e. wrong units).
oracle/voxelcount read the reference from $SEG_SPLEEN_ORACLE_REFS/<case>/label.nii.gz,
which only the grader self-check provides (never a task image).
"""
import json
import os
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

mode, in_dir, out_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
im = nib.load(str(in_dir / "image.nii.gz"))
if mode == "empty":
    mask = np.zeros(im.shape[:3], bool)
else:
    ref = Path(os.environ["SEG_SPLEEN_ORACLE_REFS"]) / in_dir.name / "label.nii.gz"
    mask = np.asanyarray(nib.load(str(ref)).dataobj) > 0
out_dir.mkdir(parents=True, exist_ok=True)
nib.save(nib.Nifti1Image(mask.astype(np.uint8), im.affine), str(out_dir / "mask.nii.gz"))
n = int(mask.sum())
ml = n * abs(np.linalg.det(im.affine[:3, :3])) / 1000.0
vol = float(n) if mode == "voxelcount" else ml
(out_dir / "volume.json").write_text(json.dumps({"spleen_volume_ml": vol}))
