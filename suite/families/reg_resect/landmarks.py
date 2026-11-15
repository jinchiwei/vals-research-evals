"""Landmark file formats for reg_resect.

Coordinate convention (verified on RESECT, see docs/research/suite/reg_resect.md):
every coordinate in this family is a WORLD position in millimetres in the RAS+ convention
(+x = patient Right, +y = Anterior, +z = Superior), which is the convention of the NIfTI sform/qform and of the MINC
.tag files RESECT ships. nibabel's `img.affine @ [i, j, k, 1]` gives RAS directly.
ITK/SimpleITK physical points are LPS: (x_lps, y_lps, z_lps) = (-x_ras, -y_ras, z_ras).

CSV format (both input and output):
    id,x,y,z
    L01,50.1644,-31.7197,34.8453
one header line exactly "id,x,y,z", one row per landmark, ids are short strings without commas.
"""
import csv
import io
import math
import re

import numpy as np

HEADER = ('id', 'x', 'y', 'z')
RAS_TO_LPS = np.array([-1.0, -1.0, 1.0])
MAX_CSV_BYTES = 1_000_000


def read_tag(path):
    """Parse a MINC .tag file with two volumes. Returns (points_vol1, points_vol2) as (N,3) arrays (RAS mm)."""
    text = open(path, encoding='utf-8', errors='replace').read()
    if 'Points' not in text:
        raise ValueError(f'{path}: no Points section')
    body = text.split('Points', 1)[1].split('=', 1)[1]
    rows = []
    for line in body.splitlines():
        line = line.split('"')[0].strip().rstrip(';')
        nums = re.findall(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?', line)
        if len(nums) >= 6:
            rows.append([float(v) for v in nums[:6]])
    a = np.asarray(rows, dtype=float)
    if a.ndim != 2 or a.shape[0] == 0:
        raise ValueError(f'{path}: no landmark rows')
    return a[:, :3], a[:, 3:6]


def format_csv(ids, points):
    points = np.asarray(points, dtype=float)
    out = io.StringIO()
    out.write(','.join(HEADER) + '\n')
    for i, p in zip(ids, points):
        out.write(f'{i},{p[0]:.4f},{p[1]:.4f},{p[2]:.4f}\n')
    return out.getvalue()


def write_csv(path, ids, points):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(format_csv(ids, points))


def parse_csv(raw):
    """Strict parser. raw: bytes or str. Returns (ids list, (N,3) float array).

    Raises ValueError with a human-readable reason on: wrong header, wrong column count,
    empty or duplicate id, non-numeric or non-finite coordinate, no rows.
    """
    if isinstance(raw, bytes):
        if len(raw) > MAX_CSV_BYTES:
            raise ValueError('file too large')
        raw = raw.decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(raw)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ValueError('empty file')
    header = tuple(c.strip().lower() for c in rows[0])
    if header != HEADER:
        raise ValueError(f'header must be exactly id,x,y,z (got {",".join(rows[0])[:80]!r})')
    ids, pts = [], []
    for n, r in enumerate(rows[1:], start=2):
        if len(r) != 4:
            raise ValueError(f'line {n}: expected 4 columns, got {len(r)}')
        lid = r[0].strip()
        if not lid:
            raise ValueError(f'line {n}: empty id')
        try:
            xyz = [float(c) for c in r[1:]]
        except ValueError:
            raise ValueError(f'line {n}: non-numeric coordinate') from None
        if not all(math.isfinite(v) for v in xyz):
            raise ValueError(f'line {n}: non-finite coordinate')
        ids.append(lid)
        pts.append(xyz)
    if not ids:
        raise ValueError('no landmark rows')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate landmark id')
    return ids, np.asarray(pts, dtype=float)


def read_csv(path):
    with open(path, 'rb') as handle:
        return parse_csv(handle.read())
