"""Check MSD Task09 Spleen, fix the split and stage anonymised task cases.

Usage (project env vals-suite-seg_spleen):
  python -I suite/families/seg_spleen/prepare_data.py \
      --src /home/jkwei/data/vals-suite/seg_spleen/extracted/Task09_Spleen \
      --out /home/jkwei/data/vals-suite/seg_spleen

Writes (outside Git):
  OUT/data_check.json                 per-case orientation, spacing, HU range, labels, volume (all 41)
  OUT/split.json                      seed, development / hidden source IDs, task IDs, SHA-256 per file
  OUT/staged/dev/<id>/{image,label}.nii.gz
  OUT/staged/hidden/<id>/{image,label}.nii.gz

Staging rule (identical for development and hidden cases; documented in seg_spleen.md):
  * Body crop: in-plane bounding box of the largest connected body component
    (HU > -500 after a 2D projection over z), plus a 10 mm margin; all slices kept.
    This removes table and air only. It is not spleen-dependent.
  * Image stored as int16 HU (source values are already integer HU); label as uint8 0/1.
  * Affine kept exactly (translated for the crop), qform = sform code 1, units mm,
    descrip/aux_file/intent_name blanked, source ID replaced by a re-drawn task ID.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

SEED = 20261114
N_DEV = 8
N_HIDDEN = 6
MARGIN_MM = 10.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_case(img_path: Path, lab_path: Path) -> dict:
    img, lab = nib.load(str(img_path)), nib.load(str(lab_path))
    a = np.asanyarray(img.dataobj)
    lbl = np.asanyarray(lab.dataobj)
    zooms = tuple(float(z) for z in img.header.get_zooms()[:3])
    vox_ml = abs(np.linalg.det(img.affine[:3, :3])) / 1000.0
    labels, counts = np.unique(lbl, return_counts=True)
    spleen = lbl > 0
    comp, ncomp = ndimage.label(spleen, structure=np.ones((3, 3, 3)))
    sizes = np.bincount(comp.ravel())[1:] if ncomp else np.array([])
    hu_in = a[spleen]
    return {
        "shape": list(img.shape),
        "dtype_on_disk": str(img.get_data_dtype()),
        "scl_slope": None if not np.isfinite(img.header["scl_slope"]) else float(img.header["scl_slope"]),
        "scl_inter": None if not np.isfinite(img.header["scl_inter"]) else float(img.header["scl_inter"]),
        "orientation": "".join(nib.aff2axcodes(img.affine)),
        "spacing_mm": [round(z, 4) for z in zooms],
        "xyz_unit": img.header.get_xyzt_units()[0],
        "qform_code": int(img.header["qform_code"]), "sform_code": int(img.header["sform_code"]),
        "label_same_grid": bool(lab.shape == img.shape and np.allclose(lab.affine, img.affine, atol=1e-3)),
        "label_values": {int(k): int(v) for k, v in zip(labels, counts)},
        "intensity_min": float(a.min()), "intensity_max": float(a.max()),
        "intensity_integer": bool(np.all(a == np.round(a))),
        "spleen_hu_p5_p50_p95": [round(float(x), 1) for x in np.percentile(hu_in, [5, 50, 95])],
        "spleen_components": int(ncomp),
        "spleen_largest_component_frac": float(sizes.max() / sizes.sum()) if ncomp else None,
        "spleen_volume_ml": round(float(spleen.sum() * vox_ml), 2),
        "spleen_z_extent_slices": [int(np.where(spleen.any((0, 1)))[0].min()),
                                   int(np.where(spleen.any((0, 1)))[0].max())] if spleen.any() else None,
    }


def body_box(a: np.ndarray, spacing) -> tuple[slice, slice, slice]:
    proj = (a > -500).any(axis=2)
    lab, n = ndimage.label(proj)
    if n == 0:
        return (slice(None),) * 3
    big = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    idx = np.argwhere(big)
    lo, hi = idx.min(0), idx.max(0) + 1
    m = [int(np.ceil(MARGIN_MM / spacing[i])) for i in range(2)]
    lo = [max(0, lo[i] - m[i]) for i in range(2)]
    hi = [min(a.shape[i], hi[i] + m[i]) for i in range(2)]
    return slice(lo[0], hi[0]), slice(lo[1], hi[1]), slice(None)


def clean_header(hdr_src_affine, data, dtype):
    out = nib.Nifti1Image(data.astype(dtype), hdr_src_affine)
    h = out.header
    h.set_xyzt_units("mm", "sec")
    out.set_qform(hdr_src_affine, code=1)
    out.set_sform(hdr_src_affine, code=1)
    h["descrip"] = b""
    h["aux_file"] = b""
    h["intent_name"] = b""
    h["db_name"] = b""
    return out


def stage(src: Path, cid: str, dst: Path) -> dict:
    img = nib.load(str(src / "imagesTr" / f"{cid}.nii.gz"))
    lab = nib.load(str(src / "labelsTr" / f"{cid}.nii.gz"))
    a = np.asanyarray(img.dataobj)
    lbl = np.asanyarray(lab.dataobj) > 0
    spacing = img.header.get_zooms()[:3]
    sl = body_box(a, spacing)
    crop_a, crop_l = a[sl], lbl[sl]
    assert crop_l.sum() == lbl.sum(), f"crop removed spleen voxels in {cid}"
    start = np.array([s.start or 0 for s in sl] + [1], float)
    aff = img.affine.copy()
    aff[:3, 3] = (img.affine @ start)[:3]
    assert np.all(np.abs(crop_a) < 32767)
    dst.mkdir(parents=True, exist_ok=True)
    nib.save(clean_header(aff, np.round(crop_a), np.int16), str(dst / "image.nii.gz"))
    nib.save(clean_header(aff, crop_l, np.uint8), str(dst / "label.nii.gz"))
    return {"crop_shape": list(crop_a.shape), "orig_shape": list(a.shape),
            "image_sha256": sha256(dst / "image.nii.gz"), "label_sha256": sha256(dst / "label.nii.gz"),
            "image_bytes": (dst / "image.nii.gz").stat().st_size,
            "label_bytes": (dst / "label.nii.gz").stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-check", action="store_true")
    args = ap.parse_args()
    ds = json.loads((args.src / "dataset.json").read_text())
    ids = sorted(Path(t["image"]).name.replace(".nii.gz", "") for t in ds["training"])
    assert len(ids) == 41, len(ids)

    if not args.skip_check:
        check = {cid: check_case(args.src / "imagesTr" / f"{cid}.nii.gz",
                                 args.src / "labelsTr" / f"{cid}.nii.gz") for cid in ids}
        (args.out / "data_check.json").write_text(json.dumps(check, indent=1))
        print("checked", len(check))

    # Split: sort source IDs numerically, permute with the suite seed, take the first
    # N_DEV as development and the next N_HIDDEN as hidden. Never move a case.
    ordered = sorted(ids, key=lambda s: int(s.split("_")[1]))
    rng = np.random.default_rng(SEED)
    perm = [ordered[i] for i in rng.permutation(len(ordered))]
    dev, hidden = perm[:N_DEV], perm[N_DEV:N_DEV + N_HIDDEN]
    # Re-drawn task IDs (not derivable from the source numbering).
    tag_rng = np.random.default_rng(SEED + 1)
    tags = [f"{x:04d}" for x in tag_rng.choice(10000, size=N_DEV + N_HIDDEN, replace=False)]
    split = {"seed": SEED, "method": "numpy default_rng(seed).permutation over 41 IDs sorted numerically; "
             "first 8 development, next 6 hidden; task IDs from default_rng(seed+1)",
             "development": {}, "hidden": {}, "unused": perm[N_DEV + N_HIDDEN:]}
    for group, members, prefix in (("development", dev, "dev"), ("hidden", hidden, "hid")):
        for cid in members:
            tid = f"{prefix}_{tags.pop(0)}"
            info = stage(args.src, cid, args.out / "staged" / ("dev" if prefix == "dev" else "hidden") / tid)
            info["source_id"] = cid
            info["source_image_sha256"] = sha256(args.src / "imagesTr" / f"{cid}.nii.gz")
            info["source_label_sha256"] = sha256(args.src / "labelsTr" / f"{cid}.nii.gz")
            split[group][tid] = info
            print(group, tid, cid, info["crop_shape"], info["image_bytes"] // 1024, "KiB")
    (args.out / "split.json").write_text(json.dumps(split, indent=1))


if __name__ == "__main__":
    main()
