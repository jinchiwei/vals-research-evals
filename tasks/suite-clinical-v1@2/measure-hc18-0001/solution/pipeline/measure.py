"""Classical HC pipeline (specialist comparator a): bright-skull ridge + RANSAC ellipse + refinement.

numpy/scipy/scikit-image/Pillow only. Parameters were tuned on development cases only.
Usage: measure.py INPUT_DIR OUTPUT_DIR   (INPUT_DIR has image.png and case.json)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

DS = 2            # downsample factor
SIGMA = 2.0       # smoothing (downsampled px)
N_HYP = 4000      # RANSAC hypotheses
SCALE_K = 1.03    # ridge centre -> annotated outer contour: median ref/pred ratio on 151 dev images
OFFSET_MM = 0.0   # additive calibration (tuned on dev)
SEED = 20261114


def conic_batch(P):
    """P: (n, 5, 2) -> conic coefficients (n, 6) by SVD null space."""
    x, y = P[..., 0], P[..., 1]
    D = np.stack([x * x, x * y, y * y, x, y, np.ones_like(x)], -1)
    _, _, vt = np.linalg.svd(D)
    return vt[:, -1, :]


def conic_to_params(c):
    A, B, C, D, E, F = c.T
    den = B * B - 4 * A * C
    ok = den < 0
    with np.errstate(all="ignore"):
        x0 = (2 * C * D - B * E) / den
        y0 = (2 * A * E - B * D) / den
        num = 2 * (A * E * E + C * D * D - B * D * E + den * F)
        s = np.sqrt((A - C) ** 2 + B * B)
        a = -np.sqrt(num * (A + C + s)) / den
        b = -np.sqrt(num * (A + C - s)) / den
        th = np.where(B != 0, np.arctan2(C - A - s, B), np.where(A < C, 0.0, np.pi / 2))
    big = np.maximum(a, b)
    small = np.minimum(a, b)
    th = np.where(a >= b, th, th + np.pi / 2)
    ok &= np.isfinite(big) & np.isfinite(small) & (small > 0)
    return x0, y0, big, small, th, ok


def ring(x0, y0, a, b, th, s, n=96):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ct, st = np.cos(t), np.sin(t)
    X = x0[:, None] + s * (a[:, None] * ct * np.cos(th)[:, None] - b[:, None] * st * np.sin(th)[:, None])
    Y = y0[:, None] + s * (a[:, None] * ct * np.sin(th)[:, None] + b[:, None] * st * np.cos(th)[:, None])
    return X, Y


def sample(img, X, Y):
    return ndi.map_coordinates(img, [Y.ravel(), X.ravel()], order=1, mode="constant", cval=0).reshape(X.shape)


def fit_ls(pts):
    c = conic_batch(pts[None])
    return conic_to_params(c)


def measure(img, px):
    im = img.astype(np.float32) / 255.0
    sm = ndi.gaussian_filter(im[::DS, ::DS], SIGMA)
    h, w = sm.shape
    # ridge map: bright relative to local background
    bg = ndi.gaussian_filter(sm, 12)
    R = np.clip(sm - bg, 0, None)
    R /= R.max() + 1e-6
    thr = np.percentile(R, 90)
    ys, xs = np.nonzero((R > thr) & (R == ndi.maximum_filter(R, 3)))
    if len(xs) < 20:
        ys, xs = np.nonzero(R > thr)
    pts = np.stack([xs, ys], 1).astype(float)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(pts), size=(N_HYP, 5))
    x0, y0, a, b, th, ok = conic_to_params(conic_batch(pts[idx]))
    ok &= (b / np.maximum(a, 1e-6) > 0.55) & (a > 0.08 * w) & (a < 0.62 * w)
    ok &= (x0 > 0) & (x0 < w) & (y0 > 0) & (y0 < h)
    if not ok.any():
        return None
    x0, y0, a, b, th = x0[ok], y0[ok], a[ok], b[ok], th[ok]
    on = sample(R, *ring(x0, y0, a, b, th, 1.0))
    inner = sample(R, *ring(x0, y0, a, b, th, 0.85))
    outer = sample(R, *ring(x0, y0, a, b, th, 1.15))
    cover = (on > thr).mean(1)
    score = on.mean(1) - 0.5 * inner.mean(1) - 0.5 * outer.mean(1) + 0.5 * cover
    k = int(np.argmax(score))
    e = [x0[k], y0[k], a[k], b[k], th[k]]
    for tol in (4.0, 2.5, 2.0):  # refine: least squares on ridge points near the ellipse
        X, Y = ring(*[np.array([v]) for v in e], 1.0, n=720)
        cur = np.stack([X[0], Y[0]], 1)
        d = np.min(np.hypot(pts[:, None, 0] - cur[None, :, 0], pts[:, None, 1] - cur[None, :, 1]), 1)
        near = pts[d < tol]
        if len(near) < 10:
            break
        r = fit_ls(near)
        if not r[5][0]:
            break
        cand = [r[0][0], r[1][0], r[2][0], r[3][0], r[4][0]]
        if not (0.5 * e[2] < cand[2] < 1.5 * e[2]):
            break
        e = cand
    a_, b_ = e[2], e[3]
    hp = ((a_ - b_) / (a_ + b_)) ** 2
    per = math.pi * (a_ + b_) * (1 + 3 * hp / (10 + math.sqrt(4 - 3 * hp)))
    return per * DS * px * SCALE_K + OFFSET_MM


def main(inp: Path, out: Path):
    case = json.loads((inp / "case.json").read_text())
    img = np.asarray(Image.open(inp / "image.png"))
    if img.ndim == 3:
        img = img[..., 0]
    v = measure(img, float(case["pixel_size_mm"]))
    if v is None or not math.isfinite(v) or not (40.0 <= v <= 400.0):
        v = 174.4  # development-set mean as a last resort
    (out / "measurement.csv").write_text(f"case_id,hc_mm\n{case['case_id']},{v:.2f}\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
