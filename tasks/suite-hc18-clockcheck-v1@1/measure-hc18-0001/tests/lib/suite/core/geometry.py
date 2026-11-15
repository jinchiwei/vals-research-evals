"""Read and validate NIfTI outputs against a reference grid.

Reuses pcnsl/imaging_eval.py for unit conversion (validate_volume), unit inheritance for
masks whose header says 'unknown' (inherit_spatial_units) and the affine tolerance
(AFFINE_RTOL, AFFINE_ATOL, same_grid). This module adds:
- safe reading of agent-written files (regular file only, no symlinks, size cap), because the
  grader runs as root and a symlink planted by the pipeline could point at a hidden reference;
- header-first checks (shape before voxel data, so a decompression bomb is not inflated);
- a diagnosis of *why* a grid differs (shape, orientation, spacing, origin/direction).

All affines returned here are voxel-to-world in mm (NIfTI/RAS+ world as nibabel reports it).
"""
import gzip
import io
import os
import stat

import numpy as np

from pcnsl import imaging_eval as _ie

AFFINE_RTOL, AFFINE_ATOL = _ie.AFFINE_RTOL, _ie.AFFINE_ATOL
SPACING_ATOL_MM = 1e-4
MAX_OUTPUT_BYTES = 256 * 1024 * 1024        # compressed size cap for one agent-written file
MAX_VOXELS = 512 ** 3                        # refuse to inflate anything larger


class GeometryError(ValueError):
    """An output is unreadable or not on the reference grid. .code is a short stable reason."""

    def __init__(self, code, detail):
        super().__init__(f'{code}: {detail}')
        self.code, self.detail = code, detail


def read_regular_file(path, max_bytes=MAX_OUTPUT_BYTES):
    """Bytes of an agent-written file. Refuses symlinks (O_NOFOLLOW), non-regular files and
    files over max_bytes. Raises GeometryError('missing'|'not_regular_file'|'too_large')."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    except FileNotFoundError:
        raise GeometryError('missing', os.path.basename(path)) from None
    except OSError:
        # ELOOP for a symlink under O_NOFOLLOW, or any other refusal.
        raise GeometryError('not_regular_file', os.path.basename(path)) from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise GeometryError('not_regular_file', os.path.basename(path))
        if st.st_size > max_bytes:
            raise GeometryError('too_large', f'{os.path.basename(path)} is {st.st_size} bytes')
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise GeometryError('too_large', os.path.basename(path))
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        os.close(fd)


def spacing_mm(affine):
    """Voxel spacing (mm) per array axis = column norms of the affine's 3x3 block."""
    a = np.asarray(affine, dtype=float)
    return np.linalg.norm(a[:3, :3], axis=0)


def orientation(affine):
    """Axis codes such as ('L', 'P', 'S') via nibabel.aff2axcodes."""
    import nibabel as nib
    return tuple(nib.aff2axcodes(np.asarray(affine, dtype=float)))


def is_sheared(affine, tol=1e-4):
    """True if the affine's columns are not mutually orthogonal (distances would be approximate)."""
    a = np.asarray(affine, dtype=float)[:3, :3]
    d = a / np.linalg.norm(a, axis=0)
    return not np.allclose(d.T @ d, np.eye(3), atol=tol)


class Grid:
    """Shape + affine (mm) of a reference image, with its declared spatial unit."""

    def __init__(self, shape, affine_mm, unit='mm', raw_affine=None):
        self.shape = tuple(int(s) for s in shape)
        self.affine = np.asarray(affine_mm, dtype=float)
        self.unit = unit
        self.raw_affine = self.affine if raw_affine is None else np.asarray(raw_affine, dtype=float)

    @property
    def spacing(self):
        return spacing_mm(self.affine)

    def describe(self):
        return {'shape': list(self.shape), 'spacing_mm': [float(x) for x in self.spacing],
                'orientation': ''.join(orientation(self.affine)),
                'origin_mm': [float(x) for x in self.affine[:3, 3]]}


def _image_from_bytes(data, name):
    """nibabel image from bytes (.nii or .nii.gz), header parsed, voxel data still lazy."""
    import nibabel as nib
    if name.endswith('.gz'):
        try:
            data = _gunzip_capped(data)
        except (OSError, EOFError, ValueError) as error:
            raise GeometryError('unreadable', f'{name}: bad gzip ({type(error).__name__})') from None
    try:
        return nib.Nifti1Image.from_bytes(data)
    except Exception as error:   # nibabel raises several types for corrupt headers
        try:
            return nib.Nifti2Image.from_bytes(data)
        except Exception:
            raise GeometryError('unreadable', f'{name}: not a NIfTI image ({type(error).__name__})') from None


def _gunzip_capped(data, max_bytes=MAX_VOXELS * 8 + (1 << 20)):
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            if out.tell() > max_bytes:
                raise ValueError('decompressed size over cap')
    return out.getvalue()


def load_reference_grid(path):
    """Grid of a trusted reference image (spatial unit converted to mm; 'unknown' rejected)."""
    import nibabel as nib
    img = nib.load(str(path))
    unit = img.header.get_xyzt_units()[0]
    shape = img.shape[:3]
    _, mm = _ie.validate_volume(np.zeros((1, 1, 1)), img.affine, unit)
    return Grid(shape, mm, unit, raw_affine=img.affine)


def diagnose_grid(shape, affine_mm, grid):
    """List of human-readable differences between (shape, affine_mm) and grid; [] when equal
    within (AFFINE_RTOL, AFFINE_ATOL) on the affine, the same tolerance as imaging_eval."""
    problems = []
    shape = tuple(int(s) for s in shape)
    if shape != grid.shape:
        problems.append(f'shape {list(shape)} != reference {list(grid.shape)}')
    a = np.asarray(affine_mm, dtype=float)
    if orientation(a) != orientation(grid.affine):
        problems.append(f"orientation {''.join(orientation(a))} != reference {''.join(orientation(grid.affine))}")
    sp, rsp = spacing_mm(a), grid.spacing
    if not np.allclose(sp, rsp, rtol=AFFINE_RTOL, atol=SPACING_ATOL_MM):
        problems.append(f'spacing {np.round(sp, 5).tolist()} mm != reference {np.round(rsp, 5).tolist()} mm')
    if not problems and not _ie.same_grid(shape, a, grid.shape, grid.affine):
        problems.append('affine (origin or direction) differs from reference beyond tolerance')
    return problems


def load_mask_on_grid(path, grid, max_bytes=MAX_OUTPUT_BYTES):
    """Read an agent-written mask and require it to lie on the reference grid.

    Steps: safe read -> parse header -> resolve spatial units (a mask declaring 'unknown'
    inherits the reference unit only when its raw affine and shape match the reference,
    via imaging_eval.inherit_spatial_units) -> compare shape/orientation/spacing/affine ->
    only then read voxel data -> require finite, non-negative integer labels.
    Returns (bool mask array, affine_mm, provenance dict). Raises GeometryError with codes:
    missing, not_regular_file, too_large, unreadable, units, geometry, values.
    """
    name = os.path.basename(str(path))
    img = _image_from_bytes(read_regular_file(path, max_bytes), name)
    shape = img.shape
    if len(shape) == 4 and shape[3] == 1:
        shape = shape[:3]
    if len(shape) != 3:
        raise GeometryError('geometry', f'{name} must be 3D, got shape {list(img.shape)}')
    if int(np.prod(shape)) > MAX_VOXELS:
        raise GeometryError('too_large', f'{name} has {int(np.prod(shape))} voxels')
    unit = img.header.get_xyzt_units()[0]
    if unit not in _ie.SPATIAL_UNIT_TO_MM and unit != 'unknown':
        raise GeometryError('units', f'{name} declares unsupported spatial unit {unit!r}')
    if unit == 'unknown':
        if not _ie.same_grid(shape, img.affine, grid.shape, grid.raw_affine):
            raise GeometryError('units', f'{name} declares no spatial unit and is not on the reference grid')
        mm = grid.affine
        provenance = {'spatial_unit': grid.unit, 'spatial_unit_source': 'inherited from same-grid reference'}
    else:
        mm = np.array(img.affine, dtype=float)
        mm[:3, :] *= _ie.SPATIAL_UNIT_TO_MM[unit]
        provenance = {'spatial_unit': unit, 'spatial_unit_source': 'output header'}
    problems = diagnose_grid(shape, mm, grid)
    if problems:
        raise GeometryError('geometry', '; '.join(problems))
    try:
        data = np.asanyarray(img.dataobj)
    except Exception as error:
        raise GeometryError('unreadable', f'{name}: voxel data ({type(error).__name__})') from None
    data = data.reshape(shape)
    try:
        mask = _ie._binary_mask(data, name)
    except ValueError as error:
        raise GeometryError('values', str(error)) from None
    provenance['grid'] = grid.describe()
    return mask, mm, provenance


def load_volume(path, allow_unknown_units=False):
    """(array, affine in mm) of a trusted file via pcnsl.imaging_eval.load_nifti."""
    return _ie.load_nifti(path, allow_unknown_units)
