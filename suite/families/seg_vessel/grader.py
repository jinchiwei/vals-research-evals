"""seg_vessel grader: retinal vessel mask vs the first human observer of CHASE_DB1.

Plug-in for suite.core.grading (per-case). Imports numpy, Pillow and scikit-image lazily
(all in the task image), so the same file runs in the verifier and in the family env.

Contract (task/README.md):
  run.sh INPUT_DIR OUTPUT_DIR
  INPUT_DIR/image.jpg      colour fundus photograph (999 x 960, original CHASE_DB1 JPEG bytes)
  OUTPUT_DIR/mask.png      single-channel PNG, same width and height, values {0,1} or {0,255};
                           nonzero = vessel

Hidden reference folder (verifier only):
  label.png                first human observer (1stHO), original 1-bit PNG
  bar.json                 {"dice_2ndHO": d, "cldice_2ndHO": c}: the second observer's agreement
                           with the first on this image, computed by prepare_data.py with the
                           functions below

Clinical rule (fixed 2026-11-15 before any comparator or agent run; docs/research/suite/seg_vessel.md):
an image is acceptable if Dice >= dice_2ndHO and clDice >= cldice_2ndHO on that image, i.e. the
pipeline agrees with the first observer at least as well as a second trained human did, on both
overlap and centreline (connectivity) overlap. quality = Dice.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

from suite.core.geometry import GeometryError, read_regular_file

REQUIRED_OUTPUTS = ('mask.png',)
PRIMARY_METRIC = 'Dice vs first observer'
CLINICAL_THRESHOLD = ('Dice and clDice (centreline Dice, Shit et al. CVPR 2021) vs the first observer each at least '
                      "the second observer's value on the same image")
MAX_MASK_BYTES = 20 * 1024 * 1024
MASK_MODES = ('1', 'L', 'P', 'I', 'I;16')


class SubmissionError(ValueError):
    """Output violates the task contract."""


# ------------------------------------------------------------------ metrics
def dice(ref, pred) -> float:
    import numpy as np
    r, p = np.asarray(ref, bool), np.asarray(pred, bool)
    total = int(r.sum()) + int(p.sum())
    if total == 0:
        return 1.0
    return 2.0 * int(np.logical_and(r, p).sum()) / total


def skeleton(mask):
    from skimage.morphology import skeletonize
    import numpy as np
    a = np.asarray(mask)
    m = (a.view(np.uint8) if a.dtype == bool else a) != 0   # canonical, writable 0/1 bools
    return skeletonize(m) if m.any() else m


def cldice(ref, pred) -> float:
    """Centreline Dice (Shit et al., CVPR 2021, eq. 1-3), hard version.

    Tprec = |S(pred) & ref| / |S(pred)|, Tsens = |S(ref) & pred| / |S(ref)|,
    clDice = 2 Tprec Tsens / (Tprec + Tsens). S = skimage skeletonize (2D).
    Both empty -> 1.0; exactly one empty -> 0.0.
    """
    import numpy as np
    r, p = np.asarray(ref, bool), np.asarray(pred, bool)
    if not r.any() and not p.any():
        return 1.0
    if not r.any() or not p.any():
        return 0.0
    sp, sr = skeleton(p), skeleton(r)
    tprec = float((sp & r).sum()) / max(int(sp.sum()), 1)
    tsens = float((sr & p).sum()) / max(int(sr.sum()), 1)
    if tprec + tsens == 0:
        return 0.0
    return 2.0 * tprec * tsens / (tprec + tsens)


def confusion(ref, pred) -> dict:
    import numpy as np
    r, p = np.asarray(ref, bool), np.asarray(pred, bool)
    tp = int((r & p).sum()); fp = int((~r & p).sum()); fn = int((r & ~p).sum()); tn = int((~r & ~p).sum())
    return {'sensitivity': tp / (tp + fn) if tp + fn else None,
            'specificity': tn / (tn + fp) if tn + fp else None,
            'accuracy': (tp + tn) / r.size,
            'vessel_fraction_pred': float(p.mean()), 'vessel_fraction_ref': float(r.mean())}


def case_metrics(ref, pred) -> dict:
    return {'dice': dice(ref, pred), 'cldice': cldice(ref, pred), **confusion(ref, pred)}


def acceptable(m: dict, bar: dict) -> bool:
    return m['dice'] >= bar['dice_2ndHO'] and m['cldice'] >= bar['cldice_2ndHO']


# ------------------------------------------------------------------ IO
def image_size(path) -> tuple[int, int]:
    """(width, height) of the input image."""
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def read_mask_png(data: bytes, expected_size):
    """Bytes of an agent mask.png -> bool array (H, W). Raises SubmissionError on any breach."""
    import numpy as np
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        fmt, mode, size = im.format, im.mode, im.size
        if fmt != 'PNG':
            raise SubmissionError(f'mask.png is not a PNG (format {fmt})')
        if mode not in MASK_MODES:
            raise SubmissionError(f'mask.png must be single-channel (mode {mode})')
        if tuple(size) != tuple(expected_size):
            raise SubmissionError(f'mask.png is {size[0]}x{size[1]}, input is {expected_size[0]}x{expected_size[1]}')
        if mode in ('P', '1'):
            # PIL's mode-1 -> numpy bool can carry 0/255 bytes, which crashes skimage's skeletonize.
            im = im.convert('L')
        arr = np.asarray(im)
    except SubmissionError:
        raise
    except Exception as error:  # noqa: BLE001
        raise SubmissionError(f'mask.png unreadable: {type(error).__name__}') from None
    if arr.ndim != 2:
        raise SubmissionError('mask.png is not 2D')
    vals = set(np.unique(arr).tolist())
    if not (vals <= {0, 1} or vals <= {0, 255}):
        raise SubmissionError(f'mask values must be {{0,1}} or {{0,255}}, found {sorted(vals)[:6]}')
    return arr > 0


def load_reference(reference_dir):
    import numpy as np
    from PIL import Image
    reference_dir = Path(reference_dir)
    with Image.open(reference_dir / 'label.png') as im:
        ref = np.asarray(im.convert('L')) > 0
    bar = json.loads((reference_dir / 'bar.json').read_text())
    for k in ('dice_2ndHO', 'cldice_2ndHO'):
        if not isinstance(bar.get(k), (int, float)) or not math.isfinite(bar[k]):
            raise ValueError(f'bar.json {k} missing or not finite')
    return ref, bar


# ------------------------------------------------------------------ core plug-in
def grade_case(output_dir, input_dir, reference_dir) -> dict:
    output_dir, input_dir = Path(output_dir), Path(input_dir)
    ref, bar = load_reference(reference_dir)
    size = image_size(input_dir / 'image.jpg')
    try:
        data = read_regular_file(output_dir / 'mask.png', MAX_MASK_BYTES)
        pred = read_mask_png(data, size)
    except GeometryError as error:
        return {'valid': False, 'acceptable': False, 'quality': 0.0,
                'reason': f'mask.png {error.code}', 'metrics': {}}
    except SubmissionError as error:
        return {'valid': False, 'acceptable': False, 'quality': 0.0, 'reason': str(error), 'metrics': {}}
    m = case_metrics(ref, pred)
    m.update(bar)
    m['dice_margin_vs_2ndHO'] = m['dice'] - bar['dice_2ndHO']
    m['cldice_margin_vs_2ndHO'] = m['cldice'] - bar['cldice_2ndHO']
    ok = acceptable(m, bar)
    reason = None
    if not ok:
        parts = []
        if m['dice'] < bar['dice_2ndHO']:
            parts.append(f"Dice {m['dice']:.4f} < 2nd observer {bar['dice_2ndHO']:.4f}")
        if m['cldice'] < bar['cldice_2ndHO']:
            parts.append(f"clDice {m['cldice']:.4f} < 2nd observer {bar['cldice_2ndHO']:.4f}")
        reason = '; '.join(parts)
    return {'valid': True, 'acceptable': ok, 'quality': float(min(1.0, max(0.0, m['dice']))),
            'reason': reason, 'metrics': m}
