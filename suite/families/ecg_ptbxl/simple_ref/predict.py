"""Simple reference: hand-built ECG features + per-class gradient boosting (numpy/scipy/sklearn only).

    bash run.sh INPUT_DIR OUTPUT_DIR
"""
import csv
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

CLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
FS = 100
PRE, POST = 25, 45          # beat window: -0.25 s .. +0.45 s around the R peak


def r_peaks(x):
    """x: (T, 12) mV. Energy of the first difference summed over leads, smoothed; peaks >= 0.3 s apart."""
    e = np.abs(np.diff(x, axis=0)).sum(1)
    e = np.convolve(e, np.ones(5) / 5, mode="same")
    pk, _ = find_peaks(e, distance=30, height=0.35 * np.percentile(e, 99))
    # move each detection to the local absolute maximum of lead II within +-5 samples
    out = []
    for p in pk:
        lo, hi = max(0, p - 5), min(len(x), p + 6)
        out.append(lo + int(np.argmax(np.abs(x[lo:hi, 1]))))
    return np.unique(np.array(out, dtype=int))


def features(sig_int16, age, sex_f):
    x = sig_int16.astype(np.float32) / 1000.0
    x = x - np.median(x, axis=0, keepdims=True)
    feats = []
    q = np.percentile(x, [1, 5, 50, 95, 99], axis=0)
    d = np.diff(x, axis=0)
    feats += [x.std(0), np.ptp(x, 0), *q, np.abs(d).mean(0), d.std(0)]
    f = np.fft.rfft(x - x.mean(0), axis=0)
    pw = np.abs(f) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / FS)
    tot = pw[(fr >= 0.5) & (fr < 45)].sum(0) + 1e-9
    for lo, hi in ((0.5, 5), (5, 15), (15, 45)):
        feats.append(pw[(fr >= lo) & (fr < hi)].sum(0) / tot)
    pk = r_peaks(x)
    rr = np.diff(pk) / FS if len(pk) > 1 else np.array([1.0])
    hr = [60.0 / rr.mean(), rr.std() / rr.mean(), len(pk), np.abs(np.diff(rr)).mean() if len(rr) > 1 else 0.0]
    good = pk[(pk >= PRE) & (pk + POST <= len(x))]
    if len(good):
        beats = np.stack([x[p - PRE:p + POST] for p in good])
        tmpl = np.median(beats, axis=0)                           # (70, 12)
        tmpl = tmpl - tmpl[:8].mean(0, keepdims=True)              # PR-segment baseline
        resid = np.abs(beats - tmpl[None]).mean()
    else:
        tmpl, resid = np.zeros((PRE + POST, 12), np.float32), 0.0
    feats.append(tmpl[::2].reshape(-1))
    qrs = np.abs(np.diff(tmpl, axis=0)).sum(1)
    above = np.flatnonzero(qrs > 0.25 * qrs.max()) if qrs.max() > 0 else np.array([0])
    hr += [(above.max() - above.min()) / FS, resid]
    return np.concatenate([np.ravel(v) for v in feats] + [np.array(hr, np.float32), [age, sex_f]]).astype(np.float32)


def feature_matrix(sig, ages, sexes):
    return np.stack([features(s, a, 1.0 if g == "F" else 0.0) for s, a, g in zip(sig, ages, sexes)])


def read_meta(path):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [r["record_id"] for r in rows], [float(r["age"]) for r in rows], [r["sex"] for r in rows]


def main(inp, outp):
    here = Path(__file__).resolve().parent
    models = pickle.loads((here / "model.pkl").read_bytes())
    ids, ages, sexes = read_meta(Path(inp) / "meta.csv")
    X = feature_matrix(np.load(Path(inp) / "signals.npz")["signals"], ages, sexes)
    P = np.stack([m.predict_proba(X)[:, 1] for m in models], 1)
    Path(outp).mkdir(parents=True, exist_ok=True)
    with open(Path(outp) / "predictions.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id"] + CLASSES)
        for rid, p in zip(ids, P):
            w.writerow([rid] + [f"{v:.6f}" for v in p])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
