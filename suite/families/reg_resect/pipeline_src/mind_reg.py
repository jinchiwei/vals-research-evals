"""MIND-feature rigid registration of MRI to ultrasound (numpy/scipy/SimpleITK only).

    python3 mind_reg.py INPUT_DIR OUTPUT_DIR

1. Resample ultrasound (fixed) and MRI (moving, FLAIR by default) onto one grid aligned with the
   ultrasound volume at `spacing` mm (default 1.5 mm), MRI through the identity transform (the
   navigation alignment shipped with the data). Ultrasound field-of-view mask = voxels > 0, eroded.
2. MIND descriptors (Heinrich et al. 2012, six-neighbourhood, Gaussian patch) for both images: a
   modality-independent description of local self-similarity, so MRI and ultrasound become comparable.
3. Exhaustive translation search: masked SSD between the descriptor images for every integer shift
   within +-search_mm, computed with FFT correlations (all shifts in one pass), plus a small
   displacement prior so flat cost surfaces stay near the navigation alignment.
4. Rigid refinement (6 parameters) of the same masked cost with Powell's method, starting from the
   best translation.
5. The MRI landmarks are moved by the inverse of the found transform (the transform maps ultrasound
   grid points to MRI points); output RAS world mm.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import SimpleITK as sitk
from scipy import ndimage, optimize
from scipy.spatial.transform import Rotation

RAS_TO_LPS = np.array([-1.0, -1.0, 1.0])
DEFAULTS = {'mri': 'flair', 'spacing': 1.5, 'search_mm': 12.0, 'mind_sigma': 0.8, 'mind_dist': 1,
            'erode_mm': 3.0, 'pre_sigma_us': 0.75, 'pre_sigma_mri': 0.0, 'prior_weight': 0.0,
            'refine': True, 'rot_scale_deg': 2.0, 'threads': 4, 'trim_border_mm': 0.0}


def read_landmarks(path):
    lines = [l.strip() for l in open(path, encoding='utf-8') if l.strip()]
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


def mind(img, sigma, dist):
    """MIND with a six-neighbourhood. img: 3D float array. Returns (6, ...) descriptors."""
    shifts = [(dist, 0, 0), (-dist, 0, 0), (0, dist, 0), (0, -dist, 0), (0, 0, dist), (0, 0, -dist)]
    d = np.empty((6,) + img.shape, dtype=np.float32)
    for k, s in enumerate(shifts):
        diff = (img - ndimage.shift(img, s, order=0, mode='nearest')) ** 2
        d[k] = ndimage.gaussian_filter(diff, sigma, mode='nearest')
    v = d.mean(axis=0)
    v = np.clip(v, 1e-3 * v.mean() + 1e-12, 1e3 * v.mean() + 1e-12)
    d = np.exp(-d / v)
    d /= d.max(axis=0, keepdims=True) + 1e-12
    return d


def normalise(a, mask):
    vals = a[mask]
    lo, hi = np.percentile(vals, [1, 99]) if vals.size else (a.min(), a.max())
    return np.clip((a - lo) / (hi - lo + 1e-6), 0, 1).astype(np.float32)


def fft_ssd_translation(F, M, W, radius):
    """Masked SSD between fixed descriptors F and moving descriptors M for all integer shifts t:
       C(t) = sum_x W(x) * ||F(x) - M(x + t)||^2. M is given on a grid padded by `radius` voxels.
       Returns cost array of shape (2r+1,)*3 indexed by t + r."""
    from numpy.fft import rfftn, irfftn
    shape = M.shape[1:]
    pad = lambda a: np.pad(a, [(0, s - a.shape[i]) for i, s in enumerate(shape)])
    Wp = pad(W)
    fW = np.conj(rfftn(Wp))
    corr = lambda A, B: irfftn(np.conj(rfftn(A)) * rfftn(B), s=shape)   # sum_x A(x) B(x + t)
    total = np.zeros(shape)
    msq = (M ** 2).sum(axis=0)
    total += corr(Wp, msq)
    for c in range(F.shape[0]):
        total -= 2 * corr(pad(W * F[c]), M[c])
    total += (W * (F ** 2).sum(axis=0)).sum()
    n = 2 * radius + 1
    # shift t in [0, 2r] on the padded grid corresponds to physical shift (t - r)
    return total[:n, :n, :n] / max(W.sum(), 1)


def run(input_dir, output_dir, cfg):
    t0 = time.monotonic()
    sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(int(cfg['threads']))
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    us = sitk.ReadImage(str(input_dir / 'us.nii.gz'), sitk.sitkFloat32)
    mri = sitk.ReadImage(str(input_dir / ('mri_flair.nii.gz' if cfg['mri'] == 'flair' else 'mri_t1.nii.gz')),
                         sitk.sitkFloat32)
    sp = float(cfg['spacing'])
    r = int(np.ceil(cfg['search_mm'] / sp))
    size = [int(np.ceil(s * p / sp)) for s, p in zip(us.GetSize(), us.GetSpacing())]
    origin, direction = np.array(us.GetOrigin()), np.array(us.GetDirection()).reshape(3, 3)
    # fixed grid
    us_s = sitk.SmoothingRecursiveGaussian(us, cfg['pre_sigma_us']) if cfg['pre_sigma_us'] > 0 else us
    fixed_ref = sitk.Image(size, sitk.sitkFloat32)
    fixed_ref.SetSpacing([sp] * 3); fixed_ref.SetOrigin(tuple(origin)); fixed_ref.SetDirection(tuple(direction.ravel()))
    fx = sitk.GetArrayFromImage(sitk.Resample(us_s, fixed_ref, sitk.Transform(), sitk.sitkLinear, 0.0))
    fov = sitk.GetArrayFromImage(sitk.Resample(sitk.Cast(us > 0, sitk.sitkUInt8), fixed_ref, sitk.Transform(),
                                               sitk.sitkNearestNeighbor, 0)) > 0
    fov = ndimage.binary_fill_holes(fov)
    mask = ndimage.binary_erosion(fov, iterations=max(1, int(round(cfg['erode_mm'] / sp))))
    # moving grid: same axes, padded by r voxels on each side
    pad_ref = sitk.Image([s + 2 * r for s in size], sitk.sitkFloat32)
    pad_ref.SetSpacing([sp] * 3); pad_ref.SetDirection(tuple(direction.ravel()))
    pad_ref.SetOrigin(tuple(origin - direction @ (np.ones(3) * r * sp)))
    mri_s = sitk.SmoothingRecursiveGaussian(mri, cfg['pre_sigma_mri']) if cfg['pre_sigma_mri'] > 0 else mri
    mv = sitk.GetArrayFromImage(sitk.Resample(mri_s, pad_ref, sitk.Transform(), sitk.sitkLinear, 0.0))
    # arrays are (z, y, x); keep that order consistently
    F = mind(normalise(fx, mask), cfg['mind_sigma'], cfg['mind_dist'])
    M = mind(normalise(mv, mv > 0), cfg['mind_sigma'], cfg['mind_dist'])
    W = mask.astype(np.float32)
    cost = fft_ssd_translation(F, M, W, r)
    if cfg['prior_weight'] > 0:
        g = np.indices(cost.shape) - r
        cost = cost + cfg['prior_weight'] * (g ** 2).sum(axis=0) * sp * sp
    best = np.unravel_index(np.argmin(cost), cost.shape)
    t_vox_zyx = np.array(best) - r
    t_phys = direction @ (t_vox_zyx[::-1] * sp)        # ITK physical (LPS) translation, fixed -> moving
    centre = np.array(fixed_ref.TransformContinuousIndexToPhysicalPoint([(s - 1) / 2 for s in size]))
    params = np.array([0, 0, 0, *t_phys], dtype=float)
    if cfg['refine']:
        mov_feat = [sitk.GetImageFromArray(M[c]) for c in range(6)]
        for im in mov_feat:
            im.CopyInformation(pad_ref)
        idx = np.argwhere(mask)                        # (z,y,x)
        if len(idx) > 40000:
            idx = idx[np.random.default_rng(0).choice(len(idx), 40000, replace=False)]
        pts = origin + (idx[:, ::-1] * sp) @ direction.T   # physical points of fixed samples
        Fs = F[:, idx[:, 0], idx[:, 1], idx[:, 2]]
        inv_dir = np.linalg.inv(direction)
        porigin = np.array(pad_ref.GetOrigin())
        Marr = M

        def cost_fn(p):
            rot = Rotation.from_rotvec(np.deg2rad(p[:3]) * cfg['rot_scale_deg'] / cfg['rot_scale_deg']).as_matrix()
            q = (pts - centre) @ rot.T + centre + p[3:]
            vox = ((q - porigin) @ inv_dir.T) / sp           # x,y,z continuous index
            coords = vox[:, ::-1].T                           # z,y,x
            s = 0.0
            for c in range(6):
                m = ndimage.map_coordinates(Marr[c], coords, order=1, mode='nearest')
                s += ((Fs[c] - m) ** 2).sum()
            return s / len(pts)

        res = optimize.minimize(cost_fn, params, method='Powell',
                                options={'xtol': 0.05, 'ftol': 1e-5, 'maxfev': 600})
        if res.fun <= cost_fn(params):
            params = res.x
    rot = Rotation.from_rotvec(np.deg2rad(params[:3])).as_matrix()
    # fixed (US) point x -> moving (MRI) point y = R (x - c) + c + t ; inverse: x = R^T (y - c - t) + c
    ids, mri_ras = read_landmarks(input_dir / 'landmarks_mri.csv')
    y = mri_ras * RAS_TO_LPS
    x = (y - centre - params[3:]) @ rot + centre
    mapped = x * RAS_TO_LPS
    output_dir.mkdir(parents=True, exist_ok=True)
    write_landmarks(output_dir / 'landmarks_us.csv', ids, mapped)
    return {'seconds': time.monotonic() - t0, 'translation_mm': [float(v) for v in params[3:]],
            'rotation_deg': [float(v) for v in params[:3]], 'grid_best_shift_vox': [int(v) for v in t_vox_zyx]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cfg = dict(DEFAULTS)
    here_cfg = Path(__file__).with_name('config.json')
    if here_cfg.is_file():
        cfg.update(json.loads(here_cfg.read_text()))
    if len(argv) > 2:
        cfg.update(json.loads(argv[2]))
    print(json.dumps(run(argv[0], argv[1], cfg)), file=sys.stderr)


if __name__ == '__main__':
    main()
