"""Ellipse geometry for head circumference (HC).

HC is the perimeter of the ellipse a sonographer fits to the outer skull. We use
Ramanujan's second approximation, whose relative error is below 1e-9 for the
axis ratios of fetal heads (b/a > 0.5), so it is exact for our purposes.
"""
from __future__ import annotations

import math

import numpy as np


def ellipse_perimeter(a: float, b: float) -> float:
    """Perimeter of an ellipse with semi-axes a, b (any unit; result in the same unit)."""
    a, b = abs(float(a)), abs(float(b))
    if a + b == 0:
        return 0.0
    h = ((a - b) / (a + b)) ** 2
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


def fit_ellipse_points(xy: np.ndarray) -> tuple[float, float, float, float, float]:
    """Least-squares ellipse fit to points (N, 2) in (x, y). Returns cx, cy, a, b, theta (a >= b)."""
    from skimage.measure import EllipseModel

    m = EllipseModel()
    if len(xy) < 5 or not m.estimate(np.asarray(xy, dtype=float)):
        raise ValueError("ellipse fit failed")
    cx, cy, a, b, th = m.params
    if b > a:
        a, b, th = b, a, th + math.pi / 2
    return float(cx), float(cy), float(a), float(b), float(th)


def outline_points(mask: np.ndarray) -> np.ndarray:
    """(x, y) pixel coordinates of a drawn ellipse outline (nonzero pixels).

    The HC18 annotation images draw the outline a few pixels thick; the least-squares
    fit through the whole band lands on its centre line.
    """
    ys, xs = np.nonzero(mask)
    return np.stack([xs, ys], axis=1).astype(float)


def hc_from_outline(mask: np.ndarray, pixel_size_mm: float) -> float:
    """Head circumference in mm from an ellipse outline image and an isotropic pixel size."""
    _, _, a, b, _ = fit_ellipse_points(outline_points(mask))
    return ellipse_perimeter(a, b) * float(pixel_size_mm)


def draw_ellipse_outline(shape, cx, cy, a, b, theta, thickness=1.0) -> np.ndarray:
    """Rasterise an ellipse outline (for synthetic tests and the oracle-free self-check)."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    c, s = math.cos(theta), math.sin(theta)
    u = (xx - cx) * c + (yy - cy) * s
    v = -(xx - cx) * s + (yy - cy) * c
    r = np.sqrt((u / a) ** 2 + (v / b) ** 2)
    # approximate distance to the curve in pixels: |r - 1| * local radius
    rad = np.sqrt(u ** 2 + v ** 2) / np.maximum(r, 1e-9)
    return (np.abs(r - 1.0) * rad <= thickness / 2 + 1e-9).astype(np.uint8)


def filled_ellipse(shape, cx, cy, a, b, theta) -> np.ndarray:
    """Filled ellipse mask, same parametrisation as skimage EllipseModel / fit_ellipse_points."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    c, s = math.cos(theta), math.sin(theta)
    u = (xx - cx) * c + (yy - cy) * s
    v = -(xx - cx) * s + (yy - cy) * c
    return ((u / a) ** 2 + (v / b) ** 2 <= 1.0).astype(np.uint8)
