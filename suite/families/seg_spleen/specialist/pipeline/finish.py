"""Put a spleen mask on the input grid as uint8 0/1 and write volume.json in mL."""
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

image_path, mask_path, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
img = nib.load(image_path)
m = nib.load(mask_path)
data = np.asanyarray(m.dataobj) > 0
assert data.shape == img.shape[:3], (data.shape, img.shape)
assert np.allclose(m.affine, img.affine, atol=1e-3), "TotalSegmentator output not on input grid"
out.mkdir(parents=True, exist_ok=True)
mask = nib.Nifti1Image(data.astype(np.uint8), img.affine, img.header)
mask.set_data_dtype(np.uint8)
mask.header["scl_slope"], mask.header["scl_inter"] = 1, 0
nib.save(mask, str(out / "mask.nii.gz"))
ml = float(data.sum()) * abs(np.linalg.det(img.affine[:3, :3])) / 1000.0
(out / "volume.json").write_text(json.dumps({"spleen_volume_ml": round(ml, 3)}))
