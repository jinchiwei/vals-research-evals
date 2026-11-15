"""Specialist baseline for reg_resect: classical MRI -> intra-operative ultrasound registration.

    python3 register.py INPUT_DIR OUTPUT_DIR [--config JSON]

Method (SimpleITK only, CPU):
  1. Fixed = ultrasound, moving = MRI (FLAIR by default). Work in ITK physical space (LPS);
     input/output landmarks are RAS, converted with (x, y, z) -> (-x, -y, z).
  2. Ultrasound field-of-view mask = voxels > 0, eroded so the fan border is ignored.
  3. Features: the ultrasound is smoothed; the MRI is either used as intensity or mapped to its
     gradient magnitude (ultrasound echoes come from tissue interfaces, so MRI edges are the
     better-correlated channel).
  4. Rigid (Euler) registration, Mattes mutual information inside the mask, multi-resolution
     (shrink 4/2/1), regular-step gradient descent, initialised at identity (the navigation
     alignment that comes with the data). Optional coarse translation grid search first.
  5. Landmarks: the registration transform T maps ultrasound points to MRI points, so each MRI
     landmark p is mapped with T^-1(p).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import SimpleITK as sitk

RAS_TO_LPS = np.array([-1.0, -1.0, 1.0])
DEFAULTS = {
    'mri': 'flair',            # flair | t1
    'feature': 'gradmag',      # intensity | gradmag
    'work_spacing_mm': 1.0,
    'mri_sigma_mm': 1.5,
    'us_sigma_mm': 1.0,
    'mask_erode_mm': 4.0,
    'bins': 32,
    'sampling': 0.25,
    'shrink': [4, 2, 1],
    'smooth_mm': [2.0, 1.0, 0.0],
    'iterations': 200,
    'max_step_mm': 2.0,
    'grid_search_mm': 0.0,     # half-width of a coarse translation search before refinement (0 = off)
    'grid_step_mm': 2.0,
    'transform': 'rigid',      # rigid | affine
    'threads': 4,
    'seed': 20261114,
}


def read_landmarks(path):
    lines = [l.strip() for l in open(path, encoding='utf-8') if l.strip()]
    assert lines[0].lower() == 'id,x,y,z', lines[0]
    ids, pts = [], []
    for line in lines[1:]:
        i, x, y, z = line.split(',')
        ids.append(i)
        pts.append([float(x), float(y), float(z)])
    return ids, np.array(pts)


def write_landmarks(path, ids, pts):
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write('id,x,y,z\n')
        for i, p in zip(ids, pts):
            handle.write(f'{i},{p[0]:.4f},{p[1]:.4f},{p[2]:.4f}\n')


def resample_iso(img, spacing, sigma_mm):
    img = sitk.Cast(img, sitk.sitkFloat32)
    if sigma_mm > 0:
        img = sitk.SmoothingRecursiveGaussian(img, sigma_mm)
    size = [int(round(sz * sp / spacing)) for sz, sp in zip(img.GetSize(), img.GetSpacing())]
    return sitk.Resample(img, size, sitk.Transform(), sitk.sitkLinear, img.GetOrigin(), [spacing] * 3,
                         img.GetDirection(), 0.0, sitk.sitkFloat32)


def us_mask(us_raw, ref, erode_mm):
    m = sitk.Resample(sitk.Cast(us_raw > 0, sitk.sitkUInt8), ref, sitk.Transform(), sitk.sitkNearestNeighbor, 0)
    r = max(1, int(round(erode_mm / ref.GetSpacing()[0])))
    m = sitk.BinaryFillhole(m)
    return sitk.BinaryErode(m, [r] * 3)


def mri_feature(mri, cfg):
    img = sitk.Cast(mri, sitk.sitkFloat32)
    if cfg['feature'] == 'gradmag':
        img = sitk.GradientMagnitudeRecursiveGaussian(img, cfg['mri_sigma_mm'])
    else:
        img = sitk.SmoothingRecursiveGaussian(img, cfg['mri_sigma_mm'])
    return img


def register(fixed, moving, mask, cfg, initial):
    R = sitk.ImageRegistrationMethod()
    R.SetMetricAsMattesMutualInformation(numberOfHistogramBins=cfg['bins'])
    R.SetMetricFixedMask(mask)
    R.SetMetricSamplingStrategy(R.RANDOM)
    R.SetMetricSamplingPercentage(cfg['sampling'], cfg['seed'])
    R.SetInterpolator(sitk.sitkLinear)
    R.SetOptimizerAsRegularStepGradientDescent(learningRate=cfg['max_step_mm'], minStep=0.01,
                                               numberOfIterations=cfg['iterations'], relaxationFactor=0.6,
                                               gradientMagnitudeTolerance=1e-6)
    R.SetOptimizerScalesFromPhysicalShift()
    R.SetShrinkFactorsPerLevel(cfg['shrink'])
    R.SetSmoothingSigmasPerLevel(cfg['smooth_mm'])
    R.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    R.SetInitialTransform(initial, inPlace=False)
    out = R.Execute(fixed, moving)
    return out, R.GetMetricValue()


def grid_search(fixed, moving, mask, cfg, center):
    """Coarse exhaustive translation search (MI at shrink 4), returns the best Euler transform."""
    R = sitk.ImageRegistrationMethod()
    R.SetMetricAsMattesMutualInformation(numberOfHistogramBins=cfg['bins'])
    R.SetMetricFixedMask(mask)
    R.SetMetricSamplingStrategy(R.RANDOM)
    R.SetMetricSamplingPercentage(cfg['sampling'], cfg['seed'])
    R.SetInterpolator(sitk.sitkLinear)
    f = sitk.SmoothingRecursiveGaussian(fixed, 2.0)
    m = sitk.SmoothingRecursiveGaussian(moving, 2.0)
    shrink = [2] * 3
    f, mk = sitk.Shrink(f, shrink), sitk.Shrink(mask, shrink)
    R.SetMetricFixedMask(mk)
    best, best_t = None, (0.0, 0.0, 0.0)
    h, s = cfg['grid_search_mm'], cfg['grid_step_mm']
    steps = np.arange(-h, h + 1e-6, s)
    for tx in steps:
        for ty in steps:
            for tz in steps:
                t = sitk.Euler3DTransform(center, 0, 0, 0, (float(tx), float(ty), float(tz)))
                R.SetInitialTransform(t)
                try:
                    v = R.MetricEvaluate(f, m)
                except RuntimeError:
                    continue
                if best is None or v < best:
                    best, best_t = v, (float(tx), float(ty), float(tz))
    return sitk.Euler3DTransform(center, 0, 0, 0, best_t)


def run(input_dir, output_dir, cfg):
    t0 = time.monotonic()
    sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(int(cfg['threads']))
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    us_raw = sitk.ReadImage(str(input_dir / 'us.nii.gz'), sitk.sitkFloat32)
    mri = sitk.ReadImage(str(input_dir / ('mri_flair.nii.gz' if cfg['mri'] == 'flair' else 'mri_t1.nii.gz')),
                         sitk.sitkFloat32)
    fixed = resample_iso(us_raw, cfg['work_spacing_mm'], cfg['us_sigma_mm'])
    mask = us_mask(us_raw, fixed, cfg['mask_erode_mm'])
    moving = mri_feature(mri, cfg)
    stats = sitk.StatisticsImageFilter()
    stats.Execute(sitk.Mask(fixed, mask))
    center = fixed.TransformContinuousIndexToPhysicalPoint([(s - 1) / 2 for s in fixed.GetSize()])
    if cfg['grid_search_mm'] > 0:
        init = grid_search(fixed, moving, mask, cfg, center)
    else:
        init = sitk.Euler3DTransform(center, 0, 0, 0, (0, 0, 0))
    tx, metric = register(fixed, moving, mask, cfg, init)
    if cfg['transform'] == 'affine':
        aff = sitk.AffineTransform(3)
        aff.SetCenter(center)
        rig = sitk.Euler3DTransform(sitk.CompositeTransform(tx).GetNthTransform(0)) \
            if isinstance(tx, sitk.CompositeTransform) else sitk.Euler3DTransform(tx)
        aff.SetMatrix(rig.GetMatrix())
        aff.SetTranslation(rig.GetTranslation())
        tx, metric = register(fixed, moving, mask, dict(cfg, shrink=[2, 1], smooth_mm=[1.0, 0.0]), aff)
    if isinstance(tx, sitk.CompositeTransform):
        tx = tx.GetNthTransform(tx.GetNumberOfTransforms() - 1) if tx.GetNumberOfTransforms() == 1 else tx
    inverse = tx.GetInverse()
    ids, mri_ras = read_landmarks(input_dir / 'landmarks_mri.csv')
    mapped = np.array([inverse.TransformPoint(tuple(p * RAS_TO_LPS)) for p in mri_ras]) * RAS_TO_LPS
    output_dir.mkdir(parents=True, exist_ok=True)
    write_landmarks(output_dir / 'landmarks_us.csv', ids, mapped)
    return {'metric': metric, 'seconds': time.monotonic() - t0,
            'shift_mm': float(np.linalg.norm(mapped - mri_ras, axis=1).mean())}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('input_dir')
    p.add_argument('output_dir')
    p.add_argument('--config', default='{}')
    a = p.parse_args(argv)
    cfg = dict(DEFAULTS)
    here_cfg = Path(__file__).with_name('config.json')
    if here_cfg.is_file():
        cfg.update(json.loads(here_cfg.read_text()))
    cfg.update(json.loads(a.config))
    info = run(a.input_dir, a.output_dir, cfg)
    print(json.dumps(info), file=sys.stderr)


if __name__ == '__main__':
    main()
