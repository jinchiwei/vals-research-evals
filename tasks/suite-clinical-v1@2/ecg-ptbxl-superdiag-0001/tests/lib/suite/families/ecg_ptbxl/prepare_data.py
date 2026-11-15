"""PTB-XL checks and the fixed ecg_ptbxl split.

Run once (data outside Git):
    conda run -n vals-suite-ecg_ptbxl python -I suite/families/ecg_ptbxl/prepare_data.py \
        --root /home/jkwei/data/vals-suite/ecg_ptbxl

Reads   ROOT/extracted/ptb-xl-.../ (PhysioNet PTB-XL 1.0.3, 100 Hz records)
Writes  ROOT/work/data_checks.json        facts about labels, folds, demographics, signals
        ROOT/work/splits.json             record lists (ecg_id) per role, with SHA-256 of each list
        ROOT/work/crosswalk.csv           task id <-> ecg_id (never shipped)
        ROOT/work/dev/                    agent-visible development set
        ROOT/work/hidden/input/           hidden inputs (verifier only)
        ROOT/work/hidden/reference.csv    hidden labels + subgroups (verifier only)
        ROOT/work/fold9/, ROOT/work/train18/   our own training/selection arrays (never shipped)
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261114
CLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
N_DEV = 8000          # stratified subsample of folds 1-8 for the agent (about 150 MB compressed)
N_HIDDEN = 1000       # stratified sample of fold 10
AGE_BANDS = [(0, 55, "age<55"), (55, 70, "age55-69"), (70, 1000, "age>=70")]
N_SAMPLES, N_LEADS, GAIN = 1000, 12, 1000.0   # 10 s at 100 Hz, 12 leads, adc units per mV
LEADS = ["I", "II", "III", "AVR", "AVL", "AVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def find_dataset(root):
    hits = sorted((root / "extracted").glob("ptb-xl-*"))
    if len(hits) != 1:
        raise SystemExit(f"expected one extracted PTB-XL folder, found {hits}")
    return hits[0]


def superclass_labels(db, scp):
    """Benchmark rule (Strodthoff et al. 2021, utils.aggregate_diagnostic): every SCP code of the
    record that is a diagnostic statement maps to its diagnostic_class, whatever its likelihood."""
    diag = scp[scp["diagnostic"] == 1.0]
    out = np.zeros((len(db), len(CLASSES)), dtype=np.int8)
    for i, codes in enumerate(db["scp_codes"]):
        for code in ast.literal_eval(codes):
            if code in diag.index:
                out[i, CLASSES.index(diag.loc[code, "diagnostic_class"])] = 1
    return out


def read_signal(base, rel):
    """Format-16 interleaved int16, 12 leads, baseline 0, gain 1000/mV (checked against headers)."""
    raw = np.fromfile(base / (rel + ".dat"), dtype="<i2")
    return raw.reshape(N_SAMPLES, N_LEADS)


def check_header(base, rel):
    lines = (base / (rel + ".hea")).read_text().splitlines()
    first = lines[0].split()
    assert int(first[1]) == 12 and float(first[2]) == 100 and int(first[3]) == N_SAMPLES, first
    leads = []
    for line in lines[1:13]:
        parts = line.split()
        assert parts[1] == "16" and parts[2].startswith("1000.0") and parts[2].endswith("/mV"), parts
        assert parts[4] == "0", parts   # adc zero / baseline
        leads.append(parts[-1].upper())
    assert leads == LEADS, leads


def strat_key(y, sex, min_count):
    key = pd.Series(["".join(map(str, r)) + f"s{s}" for r, s in zip(y, sex)])
    counts = key.value_counts()
    rare = key.map(counts) < min_count
    key[rare] = "rare" + pd.Series(["".join(map(str, r)) for r in y])[rare].str[:2]
    counts = key.value_counts()
    key[key.map(counts) < min_count] = "rare"
    return key.to_numpy()


def stratified_sample(idx, keys, n, rng):
    """Proportional allocation per stratum (largest remainder), then a uniform draw inside each."""
    idx = np.asarray(idx)
    strata = pd.Series(keys).groupby(keys).indices
    total = len(idx)
    alloc = {k: n * len(v) / total for k, v in strata.items()}
    base = {k: int(np.floor(a)) for k, a in alloc.items()}
    short = n - sum(base.values())
    for k in sorted(alloc, key=lambda k: (-(alloc[k] - base[k]), k))[:short]:
        base[k] += 1
    chosen = []
    for k in sorted(strata):
        pos = np.sort(strata[k])
        chosen.extend(idx[rng.choice(pos, size=base[k], replace=False)])
    return np.sort(np.array(chosen))


def age_band(age):
    for lo, hi, name in AGE_BANDS:
        if lo <= age < hi:
            return name
    return "age_missing"


def list_hash(ids):
    return hashlib.sha256(",".join(str(int(i)) for i in ids).encode()).hexdigest()


def write_signals(path, signals):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, signals=signals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    base = find_dataset(args.root)
    work = args.root / "work"
    work.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)

    db = pd.read_csv(base / "ptbxl_database.csv", index_col="ecg_id")
    scp = pd.read_csv(base / "scp_statements.csv", index_col=0)
    y = superclass_labels(db, scp)
    db[CLASSES] = y
    has_label = y.sum(1) > 0

    # ---- facts
    facts = {"n_records": int(len(db)), "n_patients": int(db["patient_id"].nunique())}
    facts["n_without_superclass_label"] = int((~has_label).sum())
    facts["diagnostic_classes_in_scp_statements"] = sorted(scp.loc[scp["diagnostic"] == 1.0, "diagnostic_class"].dropna().unique().tolist())
    facts["n_diagnostic_statements"] = int((scp["diagnostic"] == 1.0).sum())
    lab = db[has_label]
    facts["prevalence_labelled"] = {c: round(float(lab[c].mean()), 4) for c in CLASSES}
    facts["labels_per_record"] = {str(k): int(v) for k, v in lab[CLASSES].sum(1).value_counts().sort_index().items()}
    pf = db.groupby("patient_id")["strat_fold"].nunique()
    facts["patients_in_more_than_one_fold"] = int((pf > 1).sum())
    facts["records_per_fold"] = {int(k): int(v) for k, v in db["strat_fold"].value_counts().sort_index().items()}
    facts["labelled_records_per_fold"] = {int(k): int(v) for k, v in lab["strat_fold"].value_counts().sort_index().items()}
    facts["validated_by_human_by_fold"] = {int(k): round(float(v), 4) for k, v in db.groupby("strat_fold")["validated_by_human"].mean().items()}
    facts["sex_counts"] = {str(k): int(v) for k, v in db["sex"].value_counts(dropna=False).items()}
    facts["sex_coding"] = "PTB-XL: 0 = male, 1 = female (dataset documentation)"
    facts["age_missing"] = int(db["age"].isna().sum())
    facts["age_eq_300"] = int((db["age"] == 300).sum())
    facts["age_range_excluding_300"] = [float(db.loc[db["age"] != 300, "age"].min()), float(db.loc[db["age"] != 300, "age"].max())]
    facts["age_quantiles"] = {q: float(db.loc[db["age"] != 300, "age"].quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    facts["height_missing_frac"] = round(float(db["height"].isna().mean()), 4)
    facts["weight_missing_frac"] = round(float(db["weight"].isna().mean()), 4)
    facts["pacemaker_noted"] = int(db["pacemaker"].notna().sum())

    # headers and signals: check every 100 Hz header, read every signal
    for rel in db["filename_lr"]:
        check_header(base, rel)
    facts["headers_checked"] = int(len(db))
    facts["header_format"] = "12 leads, 100 Hz, 1000 samples, format 16, gain 1000 adc/mV, baseline 0, lead order " + ",".join(LEADS)
    sig = np.stack([read_signal(base, rel) for rel in db["filename_lr"]])
    try:
        import wfdb
        rec = wfdb.rdrecord(str(base / db["filename_lr"].iloc[0]))
        facts["wfdb_crosscheck_max_abs_diff_mV"] = float(np.abs(rec.p_signal - sig[0] / GAIN).max())
        facts["wfdb_units"] = list(set(rec.units))
    except ImportError:
        facts["wfdb_crosscheck_max_abs_diff_mV"] = None
    amp = np.abs(sig.astype(np.int32))
    facts["signal_abs_uV_percentiles"] = {str(q): float(np.percentile(amp[::50], q)) for q in (50, 99, 99.99)}
    facts["records_with_any_int16_extreme"] = int(((sig == 32767) | (sig == -32768)).any(axis=(1, 2)).sum())
    facts["records_with_flat_lead"] = int((sig.std(axis=1) == 0).any(axis=1).sum())

    # ---- split (patient-level folds come from the dataset; we only subsample inside them)
    sex = db["sex"].to_numpy()
    pos = np.arange(len(db))
    keys = strat_key(y, sex, min_count=20)
    fold = db["strat_fold"].to_numpy()
    lab_mask = has_label.astype(bool)
    dev_pool = pos[lab_mask & (fold <= 8)]
    hid_pool = pos[lab_mask & (fold == 10)]
    dev_pos = stratified_sample(dev_pool, keys[dev_pool], N_DEV, rng)
    hid_pos = stratified_sample(hid_pool, keys[hid_pool], N_HIDDEN, rng)
    f9_pos = pos[lab_mask & (fold == 9)]
    tr_pos = pos[lab_mask & (fold <= 8)]
    ids = db.index.to_numpy()
    assert not set(db["patient_id"].iloc[dev_pos]) & set(db["patient_id"].iloc[hid_pos])

    def task_ids(prefix, n):
        draws = rng.choice(16 ** 7, size=n * 2, replace=False)[:n]
        return np.array([f"{prefix}{d:07x}" for d in draws])

    dev_ids, hid_ids = task_ids("d", len(dev_pos)), task_ids("h", len(hid_pos))
    # hidden order shuffled so ids/order carry nothing about the PTB-XL ordering
    hid_order = rng.permutation(len(hid_pos))
    hid_pos, hid_ids = hid_pos[hid_order], hid_ids
    pat_codes = {}
    for p in db["patient_id"].iloc[dev_pos]:
        pat_codes.setdefault(p, f"p{len(pat_codes):05d}")
    perm = rng.permutation(len(pat_codes))
    pat_map = {p: f"p{perm[i]:05d}" for i, p in enumerate(pat_codes)}

    def clean_age(a):
        return np.where(a == 300, 90, a)

    def meta(pos_, rid):
        d = db.iloc[pos_]
        return pd.DataFrame({"record_id": rid, "age": clean_age(d["age"].to_numpy()).astype(int),
                             "sex": np.where(d["sex"].to_numpy() == 1, "F", "M")})

    dev_meta = meta(dev_pos, dev_ids)
    dev_meta["patient_group"] = [pat_map[p] for p in db["patient_id"].iloc[dev_pos]]
    dev_meta["ptbxl_fold"] = fold[dev_pos]
    dev_lab = pd.DataFrame(y[dev_pos], columns=CLASSES)
    dev_lab.insert(0, "record_id", dev_ids)
    (work / "dev").mkdir(exist_ok=True)
    dev_meta.to_csv(work / "dev" / "meta.csv", index=False)
    dev_lab.to_csv(work / "dev" / "labels.csv", index=False)
    write_signals(work / "dev" / "signals.npz", sig[dev_pos])

    hid_meta = meta(hid_pos, hid_ids)
    (work / "hidden" / "input").mkdir(parents=True, exist_ok=True)
    hid_meta.to_csv(work / "hidden" / "input" / "meta.csv", index=False)
    write_signals(work / "hidden" / "input" / "signals.npz", sig[hid_pos])
    ref = pd.DataFrame(y[hid_pos], columns=CLASSES)
    ref.insert(0, "record_id", hid_ids)
    ref["sex"] = hid_meta["sex"].to_numpy()
    ref["age"] = hid_meta["age"].to_numpy()
    ref["age_band"] = [age_band(a) for a in hid_meta["age"]]
    ref.to_csv(work / "hidden" / "reference.csv", index=False)

    for name, p in (("fold9", f9_pos), ("train18", tr_pos)):
        (work / name).mkdir(exist_ok=True)
        np.savez(work / name / "arrays.npz", signals=sig[p], y=y[p], age=clean_age(db["age"].to_numpy()[p]),
                 sex=sex[p], ecg_id=ids[p])

    cross = pd.DataFrame({"record_id": np.concatenate([dev_ids, hid_ids]),
                          "ecg_id": np.concatenate([ids[dev_pos], ids[hid_pos]]),
                          "role": ["dev"] * len(dev_pos) + ["hidden"] * len(hid_pos)})
    cross.to_csv(work / "crosswalk.csv", index=False)

    splits = {"seed": SEED, "classes": CLASSES, "label_rule": "benchmark aggregate_diagnostic; records without a superclass label dropped",
              "roles": {}}
    for role, p in (("dev_folds1-8_subsample", dev_pos), ("hidden_fold10_sample", hid_pos),
                    ("specialist_validation_fold9", f9_pos), ("specialist_train_folds1-8", tr_pos)):
        e = np.sort(ids[p])
        splits["roles"][role] = {"n": int(len(e)), "n_patients": int(db.loc[e, "patient_id"].nunique()),
                                 "sha256_sorted_ecg_ids": list_hash(e), "ecg_ids": e.tolist(),
                                 "prevalence": {c: round(float(db.loc[e, c].mean()), 4) for c in CLASSES},
                                 "female_frac": round(float((db.loc[e, "sex"] == 1).mean()), 4)}
    hb = pd.Series(ref["age_band"]).value_counts().to_dict()
    splits["hidden_subgroups"] = {"sex": ref["sex"].value_counts().to_dict(), "age_band": hb,
                                  "positives_by_subgroup": {g: {c: int(ref.loc[ref[col] == g, c].sum()) for c in CLASSES}
                                                            for col in ("sex", "age_band") for g in ref[col].unique()}}
    (work / "splits.json").write_text(json.dumps(splits, indent=1))
    facts["files"] = {str(p.relative_to(work)): {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in sorted(work.rglob("*")) if p.is_file() and p.name != "data_checks.json"
                      and "arrays.npz" not in p.name}
    (work / "data_checks.json").write_text(json.dumps(facts, indent=1, default=str))
    summary = {k: v for k, v in facts.items() if k != "files"}
    print(json.dumps(summary, indent=1, default=str))
    print({r: (v["n"], v["n_patients"], v["prevalence"]) for r, v in splits["roles"].items()})
    print(splits["hidden_subgroups"])
    print("dev signals MB", (work / "dev" / "signals.npz").stat().st_size / 1e6)


if __name__ == "__main__":
    main()
