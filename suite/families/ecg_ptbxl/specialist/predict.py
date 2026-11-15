"""Specialist comparator: compact xresnet1d-style residual 1D CNN (CPU inference).

Pipeline usage (as the grader calls it):  bash run.sh INPUT_DIR OUTPUT_DIR
INPUT_DIR holds signals.npz (int16 microvolts, N x 1000 x 12, 100 Hz) and meta.csv (record_id, age, sex).
Writes OUTPUT_DIR/predictions.csv with record_id,NORM,MI,STTC,CD,HYP.
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

CLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]


def conv(ci, co, k, s=1):
    return nn.Sequential(nn.Conv1d(ci, co, k, s, k // 2, bias=False), nn.BatchNorm1d(co))


class Block(nn.Module):
    """xresnet-style basic block: two k=5 convs; shortcut uses avg-pool + 1x1 conv when shape changes."""

    def __init__(self, ci, co, stride):
        super().__init__()
        self.body = nn.Sequential(conv(ci, co, 5, stride), nn.ReLU(inplace=True), conv(co, co, 5))
        nn.init.zeros_(self.body[-1][1].weight)
        sc = []
        if stride > 1:
            sc.append(nn.AvgPool1d(stride, stride, ceil_mode=True))
        if ci != co:
            sc.append(conv(ci, co, 1))
        self.short = nn.Sequential(*sc)
        self.act = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.act(self.body(x) + self.short(x))


class XResNet1d(nn.Module):
    def __init__(self, n_in=12, n_out=5, widths=(64, 128, 192, 256), blocks=(2, 2, 2, 2), drop=0.3):
        super().__init__()
        self.stem = nn.Sequential(conv(n_in, 32, 7, 2), nn.ReLU(inplace=True), conv(32, 32, 5), nn.ReLU(inplace=True),
                                  conv(32, 64, 5), nn.ReLU(inplace=True), nn.MaxPool1d(3, 2, 1))
        layers, ci = [], 64
        for i, (w, b) in enumerate(zip(widths, blocks)):
            for j in range(b):
                layers.append(Block(ci, w, 2 if (j == 0 and i > 0) else 1))
                ci = w
        self.body = nn.Sequential(*layers)
        self.head = nn.Sequential(nn.BatchNorm1d(2 * ci), nn.Dropout(drop), nn.Linear(2 * ci, n_out))

    def forward(self, x):          # x: (B, 12, T) standardised
        h = self.body(self.stem(x))
        h = torch.cat([h.mean(-1), h.amax(-1)], 1)
        return self.head(h)


def standardise(sig_int16, norm):
    x = sig_int16.astype(np.float32) / 1000.0                       # microvolts -> mV
    x = (x - np.asarray(norm["mean"], np.float32)) / np.asarray(norm["std"], np.float32)
    return np.ascontiguousarray(x.transpose(0, 2, 1))              # (N, 12, T)


def calibrate(logits, calib):
    a, b = np.asarray(calib["a"]), np.asarray(calib["b"])
    return 1.0 / (1.0 + np.exp(-(a * logits + b)))


def load(model_dir):
    model_dir = Path(model_dir)
    meta = json.loads((model_dir / "model.json").read_text())
    m = XResNet1d(**meta["arch"])
    m.load_state_dict(torch.load(model_dir / "model.pt", map_location="cpu", weights_only=True))
    m.eval()
    return m, meta


@torch.no_grad()
def logits_of(model, x, batch=256):
    out = []
    for i in range(0, len(x), batch):
        out.append(model(torch.from_numpy(x[i:i + batch])).numpy())
    return np.concatenate(out).astype(np.float64)


def main(inp, outp):
    torch.set_num_threads(int(os.environ.get("TORCH_NUM_THREADS", os.environ.get("OMP_NUM_THREADS", "4"))))
    here = Path(__file__).resolve().parent
    model, meta = load(here)
    sig = np.load(Path(inp) / "signals.npz")["signals"]
    with open(Path(inp) / "meta.csv", newline="") as fh:
        ids = [r["record_id"] for r in csv.DictReader(fh)]
    P = calibrate(logits_of(model, standardise(sig, meta["norm"])), meta["calibration"])
    Path(outp).mkdir(parents=True, exist_ok=True)
    with open(Path(outp) / "predictions.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id"] + CLASSES)
        for rid, p in zip(ids, P):
            w.writerow([rid] + [f"{v:.6f}" for v in p])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
