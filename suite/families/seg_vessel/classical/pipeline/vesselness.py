"""Frangi vesselness on the CLAHE-enhanced green channel, inside a field-of-view mask."""
import numpy as np
from scipy import ndimage
from skimage import exposure, filters, morphology


def fov_mask(rgb):
    red = rgb[..., 0].astype(np.float32)
    m = red > 20
    m = ndimage.binary_opening(m, iterations=3)
    m = ndimage.binary_erosion(m, iterations=8)
    return m


def vesselness(rgb, sigmas=(1, 1.5, 2, 3, 4)):
    g = rgb[..., 1].astype(np.float32) / 255.0
    g = exposure.equalize_adapthist(g, clip_limit=0.01)
    v = filters.frangi(g, sigmas=sigmas, black_ridges=True, beta=0.5, gamma=None)
    v[~fov_mask(rgb)] = 0
    return v / (np.percentile(v[v > 0], 99.5) + 1e-12) if (v > 0).any() else v


def segment(rgb, params):
    v = vesselness(rgb)
    m = v > params['threshold']
    return morphology.remove_small_objects(m, min_size=int(params['min_size']))
