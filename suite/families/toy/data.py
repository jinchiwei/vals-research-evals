"""Synthetic cases for the toy family: one bright sphere in a noisy anisotropic volume.

Each case has a non-trivial affine (x flipped, anisotropic spacing that differs per case,
non-zero origin), so a pipeline must use the header to get geometry and volume right.
Reference mask = voxels whose centre lies within the sphere radius in world mm.
Image = smooth background (10..20) + 100 inside the sphere + Gaussian noise (sd 4), so a
threshold at 50 recovers the reference exactly; the task is a plumbing smoke test.
"""
import json
from pathlib import Path

import numpy as np

SHAPE = (40, 44, 18)
SPACINGS = ((0.8, 0.9, 2.5), (0.7, 0.7, 3.0), (1.0, 0.85, 2.0), (0.9, 0.75, 2.75))


def make_case(seed):
    rng = np.random.default_rng(seed)
    sx, sy, sz = SPACINGS[seed % len(SPACINGS)]
    affine = np.array([[-sx, 0, 0, 20.0 + seed], [0, sy, 0, -15.0], [0, 0, sz, 7.5 - seed], [0, 0, 0, 1]])
    ijk = np.indices(SHAPE).reshape(3, -1)
    world = (affine[:3, :3] @ ijk + affine[:3, 3:4]).T.reshape(SHAPE + (3,))
    centre_ijk = np.array(SHAPE) / 2 + rng.uniform(-3, 3, 3) * np.array([1, 1, 0.3])
    centre = affine[:3, :3] @ centre_ijk + affine[:3, 3]
    radius = float(rng.uniform(5.5, 8.0))
    mask = (np.linalg.norm(world - centre, axis=-1) <= radius).astype(np.uint8)
    background = 10.0 + 10.0 * np.indices(SHAPE)[0] / SHAPE[0]
    image = (background + 100.0 * mask + rng.normal(0, 4, SHAPE)).astype(np.float32)
    voxel_ml = abs(np.linalg.det(affine[:3, :3])) / 1000.0
    return {'image': image, 'mask': mask, 'affine': affine, 'volume_ml': float(mask.sum() * voxel_ml),
            'radius_mm': radius}


def _save(array, affine, path):
    import nibabel as nib
    img = nib.Nifti1Image(array, affine)
    img.header.set_xyzt_units('mm')
    img.set_qform(affine, code=1)
    img.set_sform(affine, code=1)
    nib.save(img, str(path))


def write_case(case, input_dir, reference_dir=None):
    """input_dir/image.nii.gz; reference_dir/{mask.nii.gz, measurements.json} if given."""
    Path(input_dir).mkdir(parents=True, exist_ok=True)
    _save(case['image'], case['affine'], Path(input_dir) / 'image.nii.gz')
    if reference_dir is not None:
        Path(reference_dir).mkdir(parents=True, exist_ok=True)
        _save(case['mask'], case['affine'], Path(reference_dir) / 'mask.nii.gz')
        (Path(reference_dir) / 'measurements.json').write_text(
            json.dumps({'volume_ml': case['volume_ml']}, indent=2) + '\n')
