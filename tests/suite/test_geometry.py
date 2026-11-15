"""NIfTI output validation against a reference grid."""
import os

import nibabel as nib
import numpy as np
import pytest

from suite.core import geometry as G

AFF = np.array([[-0.8, 0, 0, 20.0], [0, 0.9, 0, -15.0], [0, 0, 2.5, 7.0], [0, 0, 0, 1]])
SHAPE = (10, 12, 6)


def save(path, data, affine, unit='mm'):
    img = nib.Nifti1Image(data, affine)
    img.header.set_xyzt_units(unit)
    nib.save(img, str(path))
    return path


@pytest.fixture
def grid(tmp_path):
    return G.load_reference_grid(save(tmp_path / 'ref.nii.gz', np.zeros(SHAPE, np.float32), AFF))


def mask():
    m = np.zeros(SHAPE, np.uint8)
    m[2:5, 3:6, 1:3] = 1
    return m


def test_valid_mask_loads(tmp_path, grid):
    m, aff, prov = G.load_mask_on_grid(save(tmp_path / 'm.nii.gz', mask(), AFF), grid)
    assert m.sum() == 18 and np.allclose(aff, AFF) and prov['spatial_unit'] == 'mm'
    assert grid.describe()['orientation'] == 'LAS'
    assert np.allclose(grid.spacing, [0.8, 0.9, 2.5])


@pytest.mark.parametrize('affine, data, needle', [
    (np.eye(4), mask(), 'spacing'),
    (np.diag([0.8, 0.9, 2.5, 1.0]) @ np.eye(4), mask(), 'orientation'),
    (AFF, mask()[:, :, :5], 'shape'),
    (AFF + np.array([[0, 0, 0, 3.0], [0] * 4, [0] * 4, [0] * 4]), mask(), 'origin'),
])
def test_wrong_geometry_is_diagnosed(tmp_path, grid, affine, data, needle):
    with pytest.raises(G.GeometryError) as e:
        G.load_mask_on_grid(save(tmp_path / 'm.nii.gz', data, affine), grid)
    assert e.value.code == 'geometry' and needle in e.value.detail


def test_units_are_converted_and_checked(tmp_path, grid):
    metres = AFF.copy()
    metres[:3, :] /= 1000.0
    m, aff, _ = G.load_mask_on_grid(save(tmp_path / 'a.nii.gz', mask(), metres, 'meter'), grid)
    assert np.allclose(aff, AFF)                       # metres header, same physical grid: accepted
    with pytest.raises(G.GeometryError) as e:          # mm affine labelled as metres: 1000x too big
        G.load_mask_on_grid(save(tmp_path / 'b.nii.gz', mask(), AFF, 'meter'), grid)
    assert e.value.code == 'geometry' and 'spacing' in e.value.detail


def test_unknown_units_inherit_only_on_same_grid(tmp_path, grid):
    _, _, prov = G.load_mask_on_grid(save(tmp_path / 'a.nii.gz', mask(), AFF, 'unknown'), grid)
    assert prov['spatial_unit_source'].startswith('inherited')
    with pytest.raises(G.GeometryError) as e:
        G.load_mask_on_grid(save(tmp_path / 'b.nii.gz', mask(), np.eye(4), 'unknown'), grid)
    assert e.value.code == 'units'


def test_bad_values_and_files(tmp_path, grid):
    with pytest.raises(G.GeometryError) as e:
        G.load_mask_on_grid(save(tmp_path / 'f.nii.gz', mask() * 0.5, AFF), grid)
    assert e.value.code == 'values'
    with pytest.raises(G.GeometryError) as e:
        G.load_mask_on_grid(tmp_path / 'missing.nii.gz', grid)
    assert e.value.code == 'missing'
    (tmp_path / 'junk.nii.gz').write_bytes(b'not a nifti')
    with pytest.raises(G.GeometryError) as e:
        G.load_mask_on_grid(tmp_path / 'junk.nii.gz', grid)
    assert e.value.code == 'unreadable'


def test_symlink_to_reference_is_refused(tmp_path, grid):
    target = save(tmp_path / 'secret_reference.nii.gz', mask(), AFF)
    os.symlink(target, tmp_path / 'm.nii.gz')
    with pytest.raises(G.GeometryError) as e:
        G.load_mask_on_grid(tmp_path / 'm.nii.gz', grid)
    assert e.value.code == 'not_regular_file'


def test_size_cap(tmp_path):
    (tmp_path / 'big').write_bytes(b'x' * 2048)
    with pytest.raises(G.GeometryError) as e:
        G.read_regular_file(tmp_path / 'big', max_bytes=1024)
    assert e.value.code == 'too_large'
