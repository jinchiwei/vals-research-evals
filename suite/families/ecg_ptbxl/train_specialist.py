"""Train the specialist on PTB-XL folds 1-8, select the epoch on fold 9, fit per-class Platt calibration
on fold 9, and write a CPU pipeline (run.sh + predict.py + weights) to ROOT/work/specialist_pipeline/.

    conda run -n vals-suite-ecg_ptbxl python suite/families/ecg_ptbxl/train_specialist.py \
        --root /home/jkwei/data/vals-suite/ecg_ptbxl --epochs 40

Fold 10 is never touched here.
"""
import argparse
import importlib.util
import json
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ecg_specialist", HERE / "specialist" / "predict.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)
_gspec = importlib.util.spec_from_file_location("ecg_grade", HERE / "grade.py")
G = importlib.util.module_from_spec(_gspec)
_gspec.loader.exec_module(G)
SEED = 20261114


def fit_platt(logit, y, iters=100):
    """Per-class logistic recalibration p = sigmoid(a*logit + b), fitted by Newton steps."""
    X = np.c_[logit, np.ones_like(logit)]
    w = np.array([1.0, 0.0])
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-(X @ w)))
        H = X.T @ (X * (mu * (1 - mu))[:, None]) + 1e-6 * np.eye(2)
        step = np.linalg.solve(H, X.T @ (y - mu))
        w += step
        if np.abs(step).max() < 1e-9:
            break
    return float(w[0]), float(w[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-3)
    a = ap.parse_args()
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    work = a.root / "work"
    tr = np.load(work / "train18" / "arrays.npz")
    va = np.load(work / "fold9" / "arrays.npz")
    xs = tr["signals"].astype(np.float32) / 1000.0
    norm = {"mean": xs.reshape(-1, 12).mean(0).tolist(), "std": xs.reshape(-1, 12).std(0).tolist()}
    del xs
    Xtr, Ytr = S.standardise(tr["signals"], norm), tr["y"].astype(np.float32)
    Xva, Yva = S.standardise(va["signals"], norm), va["y"].astype(int)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    arch = {"widths": [64, 128, 192, 256], "blocks": [2, 2, 2, 2], "drop": 0.3}
    model = S.XResNet1d(**arch).to(dev)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    steps = a.epochs * int(np.ceil(len(Xtr) / a.batch))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.3)
    lossf = nn.BCEWithLogitsLoss()
    Xtr_t, Ytr_t = torch.from_numpy(Xtr), torch.from_numpy(Ytr)
    best = (-1, None, None)
    log = []
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    for ep in range(a.epochs):
        model.train()
        perm = torch.from_numpy(rng.permutation(len(Xtr)))
        tot = 0.0
        for i in range(0, len(perm), a.batch):
            idx = perm[i:i + a.batch]
            xb = Xtr_t[idx].to(dev, non_blocking=True)
            yb = Ytr_t[idx].to(dev, non_blocking=True)
            # light augmentation: amplitude scale and a random shift of up to 0.5 s (wrap-around)
            xb = xb * torch.empty(len(xb), 1, 1, device=dev).uniform_(0.9, 1.1)
            xb = torch.roll(xb, int(rng.integers(-50, 51)), dims=-1)
            loss = lossf(model(xb), yb)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            lv = np.concatenate([model(torch.from_numpy(Xva[i:i + 512]).to(dev)).float().cpu().numpy()
                                 for i in range(0, len(Xva), 512)])
        auc = G.macro_auroc(Yva, lv)
        log.append({"epoch": ep, "train_loss": tot / len(Xtr), "fold9_macro_auroc": auc, "elapsed_s": time.time() - t0})
        print(log[-1], flush=True)
        if auc > best[0]:
            best = (auc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}, lv.astype(np.float64))
    train_s = time.time() - t0
    auc9, state, lv = best
    calib = {"a": [], "b": []}
    for k in range(5):
        s, b = fit_platt(lv[:, k], Yva[:, k])
        calib["a"].append(s)
        calib["b"].append(b)
    P9 = 1 / (1 + np.exp(-(np.array(calib["a"]) * lv + np.array(calib["b"]))))
    out = work / "specialist_pipeline"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    torch.save(state, out / "model.pt")
    shutil.copy(HERE / "specialist" / "predict.py", out / "predict.py")
    shutil.copy(HERE / "specialist" / "run.sh", out / "run.sh")
    meta = {"arch": arch, "norm": norm, "calibration": calib, "calibration_method": "per-class Platt on fold 9 logits",
            "n_params": n_params, "train_records": int(len(Xtr)), "fold9_records": int(len(Xva)),
            "selected_epoch": int(np.argmax([r["fold9_macro_auroc"] for r in log])), "fold9_macro_auroc": auc9,
            "fold9_macro_ece_raw": float(np.mean([G.ece(Yva[:, k], 1 / (1 + np.exp(-lv[:, k]))) for k in range(5)])),
            "fold9_macro_ece_calibrated_in_sample": float(np.mean([G.ece(Yva[:, k], P9[:, k]) for k in range(5)])),
            "train_seconds": train_s, "device": str(dev),
            "gpu": torch.cuda.get_device_name(0) if dev.type == "cuda" else None, "torch": torch.__version__,
            "epochs": a.epochs, "batch": a.batch, "max_lr": a.lr, "log": log}
    (out / "model.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k not in ("log", "norm")}, indent=1))


if __name__ == "__main__":
    main()
