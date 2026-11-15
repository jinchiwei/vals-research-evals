"""Classical spleen segmentation (no deep learning): the build tier's reference pipeline.

Steps: body mask -> in-plane location prior (learned from development masks, in
body-bounding-box coordinates) -> HU window -> per-slice erosion to cut thin bridges
to neighbouring organs -> 3D components scored by mean prior -> geodesic regrowth
inside an adaptive HU window -> hole filling. Parameters live in params.json and
prior.npy next to this file (written by classical/fit.py from development cases).

  python -I segment.py INPUT_DIR OUTPUT_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent


def disk(radius_px_x, radius_px_y):
    rx, ry = max(int(round(radius_px_x)), 0), max(int(round(radius_px_y)), 0)
    x, y = np.ogrid[-rx:rx + 1, -ry:ry + 1]
    d = (x / max(rx, 1e-6)) ** 2 + (y / max(ry, 1e-6)) ** 2 <= 1.0 if rx and ry else np.ones((1, 1), bool)
    return d[:, :, None]


def body_mask(img):
    b = img > -500
    lab, n = ndimage.label(b)
    if n == 0:
        return b
    b = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    for z in range(b.shape[2]):
        b[:, :, z] = ndimage.binary_fill_holes(b[:, :, z])
    return b


def body_coords(body):
    """(u, v) grids in [0,1] over the body's in-plane bounding box (shape X x Y)."""
    idx = np.argwhere(body.any(axis=2))
    lo, hi = idx.min(0), idx.max(0) + 1
    u = (np.arange(body.shape[0]) - lo[0]) / max(hi[0] - lo[0], 1)
    v = (np.arange(body.shape[1]) - lo[1]) / max(hi[1] - lo[1], 1)
    return np.clip(u, 0, 0.9999), np.clip(v, 0, 0.9999)


def prior_volume(body, prior):
    u, v = body_coords(body)
    n = prior.shape[0]
    p2 = prior[(u * n).astype(int)[:, None], (v * n).astype(int)[None, :]]
    return p2


def segment(img, affine, prior, p):
    sx, sy, sz = np.sqrt((affine[:3, :3] ** 2).sum(0))
    body = body_mask(img)
    p2 = prior_volume(body, prior)                       # X x Y
    sm = ndimage.median_filter(img, size=(3, 3, 1)).astype(np.float32)
    region = body & (p2[:, :, None] >= p["prior_floor"])
    cand = (sm >= p["hu_lo"]) & (sm <= p["hu_hi"]) & region
    fp = disk(p["erode_mm"] / sx, p["erode_mm"] / sy)
    core = ndimage.binary_erosion(cand, structure=fp)
    lab, n = ndimage.label(core, structure=np.ones((3, 3, 3), bool))
    if n == 0:
        return np.zeros(img.shape, bool)
    vox_ml = sx * sy * sz / 1000.0
    sizes = np.bincount(lab.ravel())[1:]
    psum = ndimage.sum_labels(np.broadcast_to(p2[:, :, None], img.shape), lab, np.arange(1, n + 1))
    mean_p = psum / np.maximum(sizes, 1)
    ok = sizes * vox_ml >= p["min_core_ml"]
    if p.get("score", "sum") == "sum":   # prior mass: favours big components deep in the prior
        score = np.where(ok, psum, -1)
    else:
        score = np.where(ok, mean_p * np.log1p(sizes * vox_ml), -1)
    seed = lab == (int(np.argmax(score)) + 1)
    # adaptive window around this case's spleen intensity
    med = float(np.median(sm[seed]))
    win = (sm >= med - p["win_below"]) & (sm <= med + p["win_above"]) & region
    grown = seed.copy()
    for _ in range(p["grow_iters"]):
        nxt = ndimage.binary_dilation(grown, structure=fp) & win
        if nxt.sum() == grown.sum():
            break
        grown = nxt
    lab2, n2 = ndimage.label(grown, structure=np.ones((3, 3, 3), bool))
    if n2 > 1:
        grown = lab2 == (np.argmax(np.bincount(lab2.ravel())[1:]) + 1)
    for z in range(grown.shape[2]):
        if grown[:, :, z].any():
            grown[:, :, z] = ndimage.binary_fill_holes(
                ndimage.binary_closing(grown[:, :, z], structure=disk(2, 2)[:, :, 0]))
    return grown


def main():
    in_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    p = json.loads((HERE / "params.json").read_text())
    prior = np.load(HERE / "prior.npy")
    im = nib.load(str(in_dir / "image.nii.gz"))
    img = np.asanyarray(im.dataobj).astype(np.float32)
    mask = segment(img, im.affine, prior, p)
    out_dir.mkdir(parents=True, exist_ok=True)
    m = nib.Nifti1Image(mask.astype(np.uint8), im.affine)
    m.set_qform(im.affine, code=1)
    m.set_sform(im.affine, code=1)
    m.header.set_xyzt_units("mm", "sec")
    nib.save(m, str(out_dir / "mask.nii.gz"))
    ml = float(mask.sum()) * abs(np.linalg.det(im.affine[:3, :3])) / 1000.0
    (out_dir / "volume.json").write_text(json.dumps({"spleen_volume_ml": round(ml, 3)}))


if __name__ == "__main__":
    main()
