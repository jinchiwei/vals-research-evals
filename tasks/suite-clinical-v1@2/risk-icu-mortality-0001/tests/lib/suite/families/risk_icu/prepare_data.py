"""Fix the risk_icu split from the downloaded PhysioNet 2012 files.

development = all of set A (4,000 stays, outcomes public to the agent)
hidden      = all of set B (4,000 stays), RecordIDs re-drawn with seed 20261114
reserve     = set C, left untouched in extracted/set-c (never read here)

Usage: python -I prepare_data.py DATA_ROOT   (DATA_ROOT=/home/jkwei/data/vals-suite/risk_icu)
Writes DATA_ROOT/split/{dev,hidden}/ and DATA_ROOT/split/split.json. Idempotent:
refuses to overwrite a split whose recorded hashes differ.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from records import list_records, read_record, replace_record_id  # noqa: E402

SEED = 20261114
PSEUDO_RANGE = (300000, 999999)  # disjoint from original IDs (132539..163037)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return sha256_bytes(handle.read())


def list_hash(ids) -> str:
    return sha256_bytes(("\n".join(str(i) for i in ids) + "\n").encode())


def read_outcomes(path: str):
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {int(r["RecordID"]): r for r in rows}


def descriptor(rec, name):
    v = rec.descriptors.get(name)
    return "" if v is None or v != v else (int(v) if float(v).is_integer() else v)


def main(root: str) -> None:
    out = os.path.join(root, "split")
    if os.path.exists(os.path.join(out, "split.json")):
        print("split already exists; verifying instead of rewriting")
        verify(root)
        return
    dev_rec = os.path.join(out, "dev", "records")
    hid_rec = os.path.join(out, "hidden", "records")
    os.makedirs(dev_rec)
    os.makedirs(hid_rec)

    # Development: set A verbatim plus its public outcomes file verbatim.
    a_files = list_records(os.path.join(root, "extracted", "set-a"))
    a_out = read_outcomes(os.path.join(root, "raw", "Outcomes-a.txt"))
    dev_ids = []
    for path in a_files:
        rec = read_record(path)
        assert os.path.basename(path) == f"{rec.record_id}.txt"
        shutil.copyfile(path, os.path.join(dev_rec, os.path.basename(path)))
        dev_ids.append(rec.record_id)
    assert set(dev_ids) == set(a_out)
    shutil.copyfile(os.path.join(root, "raw", "Outcomes-a.txt"), os.path.join(out, "dev", "Outcomes-a.txt"))

    # Hidden: set B with re-drawn numeric IDs.
    b_files = list_records(os.path.join(root, "extracted", "set-b"))
    b_out = read_outcomes(os.path.join(root, "raw", "Outcomes-b.txt"))
    rng = random.Random(SEED)
    pseudo = rng.sample(range(*PSEUDO_RANGE), len(b_files))
    id_map, hidden_rows = [], []
    for path, new_id in zip(b_files, pseudo):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        rec = read_record(path)
        new_text = replace_record_id(text, new_id)
        with open(os.path.join(hid_rec, f"{new_id}.txt"), "w", encoding="utf-8") as handle:
            handle.write(new_text)
        o = b_out[rec.record_id]
        id_map.append({"hidden_id": new_id, "original_id": rec.record_id})
        hidden_rows.append({
            "RecordID": new_id,
            "in_hospital_death": int(o["In-hospital_death"]),
            "saps1": int(o["SAPS-I"]), "sofa": int(o["SOFA"]),
            "icu_type": descriptor(rec, "ICUType"), "gender": descriptor(rec, "Gender"),
            "age": descriptor(rec, "Age"),
        })
    hidden_rows.sort(key=lambda r: r["RecordID"])
    id_map.sort(key=lambda r: r["hidden_id"])
    _write_csv(os.path.join(out, "hidden", "outcomes.csv"), hidden_rows)
    _write_csv(os.path.join(out, "hidden_id_map.csv"), id_map)  # grader-side only, never in a task

    # Development outcomes table in the same shape (for the comparators' fitting).
    dev_rows = []
    for path in a_files:
        rec = read_record(path)
        o = a_out[rec.record_id]
        dev_rows.append({"RecordID": rec.record_id, "in_hospital_death": int(o["In-hospital_death"]),
                         "saps1": int(o["SAPS-I"]), "sofa": int(o["SOFA"]),
                         "icu_type": descriptor(rec, "ICUType"), "gender": descriptor(rec, "Gender"),
                         "age": descriptor(rec, "Age")})
    _write_csv(os.path.join(out, "dev", "outcomes.csv"), dev_rows)

    c_ids = sorted(int(n[:-4]) for n in os.listdir(os.path.join(root, "extracted", "set-c")) if n.endswith(".txt"))
    manifest = {
        "seed": SEED,
        "development": {"source": "set-a", "n": len(dev_ids), "deaths": sum(r["in_hospital_death"] for r in dev_rows),
                        "ids_sha256": list_hash(sorted(dev_ids)),
                        "outcomes_sha256": sha256_file(os.path.join(out, "dev", "Outcomes-a.txt"))},
        "hidden": {"source": "set-b (all 4000, RecordIDs re-drawn)", "n": len(hidden_rows),
                   "deaths": sum(r["in_hospital_death"] for r in hidden_rows),
                   "original_ids_sha256": list_hash(sorted(m["original_id"] for m in id_map)),
                   "hidden_ids_sha256": list_hash([r["RecordID"] for r in hidden_rows]),
                   "outcomes_sha256": sha256_file(os.path.join(out, "hidden", "outcomes.csv")),
                   "id_map_sha256": sha256_file(os.path.join(out, "hidden_id_map.csv"))},
        "reserve": {"source": "set-c (untouched)", "n": len(c_ids), "ids_sha256": list_hash(c_ids)},
        "records_sha256": {
            "dev": _dir_hash(dev_rec), "hidden": _dir_hash(hid_rec),
        },
    }
    for key in ("development", "hidden"):
        manifest[key]["prevalence"] = round(manifest[key]["deaths"] / manifest[key]["n"], 5)
    with open(os.path.join(out, "split.json"), "w") as handle:
        json.dump(manifest, handle, indent=1)
    with open(os.path.join(out, "dev_ids.txt"), "w") as handle:
        handle.write("\n".join(str(i) for i in sorted(dev_ids)) + "\n")
    with open(os.path.join(out, "hidden_ids.txt"), "w") as handle:
        handle.write("\n".join(str(r["RecordID"]) for r in hidden_rows) + "\n")
    print(json.dumps(manifest, indent=1))


def _dir_hash(folder: str) -> str:
    h = hashlib.sha256()
    for name in sorted(os.listdir(folder)):
        h.update(name.encode() + b"\0" + sha256_file(os.path.join(folder, name)).encode() + b"\n")
    return h.hexdigest()


def _write_csv(path, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify(root: str) -> None:
    out = os.path.join(root, "split")
    with open(os.path.join(out, "split.json")) as handle:
        manifest = json.load(handle)
    assert _dir_hash(os.path.join(out, "dev", "records")) == manifest["records_sha256"]["dev"]
    assert _dir_hash(os.path.join(out, "hidden", "records")) == manifest["records_sha256"]["hidden"]
    assert sha256_file(os.path.join(out, "hidden", "outcomes.csv")) == manifest["hidden"]["outcomes_sha256"]
    print("split verified:", manifest["development"]["n"], manifest["hidden"]["n"])


if __name__ == "__main__":
    main(sys.argv[1])
