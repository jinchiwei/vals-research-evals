"""Fixed development / hidden / pool split of the HC18 labelled training set.

Usage: python -I split.py DATA_ROOT
Seed 20261114. Unit of assignment = filename prefix (NNN in NNN_HC.png, NNN_2HC.png, ...),
which groups repeat images of one examination; a prefix never straddles the split.
Stratified by head-size tertile (cut points from all 999 labelled images) because the
release has no per-image gestational age or trimester.

Writes (repo, no reference values): split/split.json with case lists and SHA-256 hashes.
Writes (data dir, outside Git):
  staged/visible/<case>/{image.png,case.json,annotation.png}  + staged/visible/references.csv
  staged/hidden/inputs/<case>/{image.png,case.json}
  staged/hidden/references.csv   (grader only)
  staged/pool_filenames.txt      (non-hidden images for training the specialist U-Net)
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

SEED = 20261114
N_HIDDEN_PER_STRATUM = (27, 27, 26)
N_DEV_PER_STRATUM = (50, 50, 50)
HERE = Path(__file__).resolve().parent
TERTILE_NAMES = ("hc_tertile_small", "hc_tertile_mid", "hc_tertile_large")


def hc_band(v: float) -> str:
    """Approximate trimester band from HC alone (no GA in the release); descriptive only."""
    return "band_lt100mm" if v < 100 else ("band_100to260mm" if v < 260 else "band_ge260mm")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def png_bytes(path: Path) -> bytes:
    """Re-encode as 8-bit greyscale PNG with no metadata (pixel values unchanged)."""
    im = Image.open(path)
    arr = np.asarray(im)
    if arr.ndim == 3:
        arr = arr[..., 0]
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8), mode="L").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main(root: Path) -> None:
    rng = np.random.default_rng(SEED)
    rows = list(csv.DictReader(open(root / "raw" / "training_set_pixel_size_and_HC.csv")))
    hc = np.array([float(r["head circumference (mm)"]) for r in rows])
    cuts = [float(np.percentile(hc, 100 / 3)), float(np.percentile(hc, 200 / 3))]
    groups = defaultdict(list)
    for r in rows:
        groups[re.match(r"(\d+)_", r["filename"]).group(1)].append(r)

    def stratum_of(v: float) -> int:
        return int(v >= cuts[0]) + int(v >= cuts[1])

    by_stratum = defaultdict(list)
    for g, rs in sorted(groups.items()):
        by_stratum[stratum_of(np.mean([float(r["head circumference (mm)"]) for r in rs]))].append(g)

    assign = {}
    for s in range(3):
        gs = list(by_stratum[s])
        rng.shuffle(gs)
        nh = nd = 0
        for g in gs:
            k = len(groups[g])
            if nh < N_HIDDEN_PER_STRATUM[s]:
                assign[g], nh = "hidden", nh + k
            elif nd < N_DEV_PER_STRATUM[s]:
                assign[g], nd = "dev", nd + k
            else:
                assign[g] = "pool"

    # Opaque case IDs drawn from one space for dev and hidden (no linkage to HC18 filenames).
    all_rows = [r for g in sorted(groups) for r in groups[g] if assign[g] != "pool"]
    ids = rng.choice(16 ** 6, size=len(all_rows), replace=False)
    order = rng.permutation(len(all_rows))
    st = root / "staged"
    if st.exists():
        shutil.rmtree(st)
    (st / "visible").mkdir(parents=True)
    (st / "hidden" / "inputs").mkdir(parents=True)
    tdir = root / "extracted" / "training_set"
    out = {"seed": SEED, "unit": "filename prefix (examination)", "strata": "HC tertile",
           "tertile_cuts_mm": cuts, "dev": [], "hidden": [], "pool": []}
    vis_refs, hid_refs = [], []
    for i in order:
        r = all_rows[i]
        g = re.match(r"(\d+)_", r["filename"]).group(1)
        side = assign[g]
        cid = f"case_{ids[i]:06x}"
        px = float(r["pixel size(mm)"])
        hcv = float(r["head circumference (mm)"])
        s = stratum_of(hcv)
        img = png_bytes(tdir / r["filename"])
        case = {"case_id": cid, "pixel_size_mm": px}
        if side == "dev":
            d = st / "visible" / cid
            d.mkdir()
            ann = png_bytes(tdir / r["filename"].replace(".png", "_Annotation.png"))
            (d / "annotation.png").write_bytes(ann)
            vis_refs.append({"case_id": cid, "pixel_size_mm": px, "hc_mm": hcv, "stratum": TERTILE_NAMES[s], "band": hc_band(hcv)})
        else:
            d = st / "hidden" / "inputs" / cid
            d.mkdir()
            ann = None
            hid_refs.append({"case_id": cid, "hc_mm": hcv, "stratum": TERTILE_NAMES[s], "band": hc_band(hcv)})
        (d / "image.png").write_bytes(img)
        (d / "case.json").write_text(json.dumps(case) + "\n")
        out[side].append({"case_id": cid, "source_filename": r["filename"], "group": g,
                          "stratum": TERTILE_NAMES[s], "band": hc_band(hcv), "image_sha256": sha(img),
                          "case_json_sha256": sha((json.dumps(case) + "\n").encode()),
                          **({"annotation_sha256": sha(ann)} if ann else {})})
    for side in ("dev", "hidden"):
        out[side].sort(key=lambda x: x["case_id"])
    out["pool"] = sorted(r["filename"] for g in groups if assign[g] == "pool" for r in groups[g])
    out["counts"] = {k: len(out[k]) for k in ("dev", "hidden", "pool")}
    out["counts_by_stratum"] = {k: {t: sum(x["stratum"] == t for x in out[k]) for t in TERTILE_NAMES}
                                for k in ("dev", "hidden")}
    out["counts_by_band"] = {k: {b: sum(x["band"] == b for x in out[k]) for b in ("band_lt100mm", "band_100to260mm", "band_ge260mm")}
                             for k in ("dev", "hidden")}
    out["groups"] = {k: len({x["group"] for x in out[k]}) for k in ("dev", "hidden")}
    for path, recs in ((st / "visible" / "references.csv", vis_refs),
                       (st / "hidden" / "references.csv", hid_refs)):
        recs.sort(key=lambda x: x["case_id"])
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
            w.writeheader()
            w.writerows(recs)
    (st / "pool_filenames.txt").write_text("\n".join(out["pool"]) + "\n")
    out["hidden_references_sha256"] = sha((st / "hidden" / "references.csv").read_bytes())
    out["visible_references_sha256"] = sha((st / "visible" / "references.csv").read_bytes())
    (HERE / "split").mkdir(exist_ok=True)
    (HERE / "split" / "split.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("counts", "counts_by_stratum", "counts_by_band", "groups", "tertile_cuts_mm")}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
