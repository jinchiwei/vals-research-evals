"""Train the specialist U-Net on non-hidden HC18 images (pool = train, dev = validation).

Usage: python -I train.py DATA_ROOT OUT_DIR [EPOCHS]
Hidden images are never read: the pool list and the dev folder come from split.py.
"""
import csv, json, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from measure_hc18.geometry import filled_ellipse, fit_ellipse_points, outline_points  # noqa: E402
from measure_hc18.unet.model import H, W, UNet  # noqa: E402


def load(img_path, ann_path):
    im = np.asarray(Image.open(img_path))
    if im.ndim == 3:
        im = im[..., 0]
    a = np.asarray(Image.open(ann_path))
    a = a[..., 0] if a.ndim == 3 else a
    cx, cy, ra, rb, th = fit_ellipse_points(outline_points(a > 0))
    m = filled_ellipse(im.shape, cx, cy, ra, rb, th)
    x = np.asarray(Image.fromarray(im).resize((W, H), Image.BILINEAR), np.float32) / 255.0
    y = np.asarray(Image.fromarray(m * 255).resize((W, H), Image.NEAREST), np.float32) / 255.0
    return x, y


def main(root, out, epochs):
    out.mkdir(parents=True, exist_ok=True)
    tdir = root / "extracted" / "training_set"
    pool = [l for l in (root / "staged" / "pool_filenames.txt").read_text().split() if l]
    Xtr, Ytr = zip(*[load(tdir / f, tdir / f.replace(".png", "_Annotation.png")) for f in pool])
    vis = root / "staged" / "visible"
    dev = sorted(p for p in vis.iterdir() if p.is_dir())
    Xva, Yva = zip(*[load(d / "image.png", d / "annotation.png") for d in dev])
    Xtr, Ytr = torch.tensor(np.stack(Xtr))[:, None], torch.tensor(np.stack(Ytr))[:, None]
    Xva, Yva = torch.tensor(np.stack(Xva))[:, None], torch.tensor(np.stack(Yva))[:, None]
    print("train", Xtr.shape, "val", Xva.shape, flush=True)
    torch.manual_seed(20261114)
    dev_ = torch.device("cuda")
    net = UNet().to(dev_)
    opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    steps = epochs * ((len(Xtr) + 15) // 16)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=steps)
    best, t0 = 0, time.time()
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), 16):
            idx = perm[i:i + 16]
            x, y = Xtr[idx].to(dev_), Ytr[idx].to(dev_)
            if torch.rand(1) < 0.5:
                x, y = x.flip(3), y.flip(3)
            if torch.rand(1) < 0.5:
                x, y = x.flip(2), y.flip(2)
            x = (x * (0.8 + 0.4 * torch.rand(len(x), 1, 1, 1, device=dev_))).clamp(0, 1)
            lo = net(x)
            p = torch.sigmoid(lo)
            dice = 1 - (2 * (p * y).sum((1, 2, 3)) + 1) / (p.sum((1, 2, 3)) + y.sum((1, 2, 3)) + 1)
            loss = F.binary_cross_entropy_with_logits(lo, y) + dice.mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
        net.eval()
        with torch.no_grad():
            p = torch.cat([torch.sigmoid(net(Xva[i:i + 32].to(dev_))).cpu() for i in range(0, len(Xva), 32)]) > 0.5
            d = (2 * (p * Yva).sum((1, 2, 3)) / (p.sum((1, 2, 3)) + Yva.sum((1, 2, 3)) + 1e-6)).mean().item()
        print(f"epoch {ep} loss {loss.item():.4f} val_dice {d:.4f} t {time.time()-t0:.0f}s", flush=True)
        if d >= best:
            best = d
            torch.save(net.state_dict(), out / "unet.pt")
    (out / "train_log.json").write_text(json.dumps({"best_val_dice": best, "epochs": epochs,
                                                    "n_train": len(Xtr), "n_val": len(Xva),
                                                    "seconds": time.time() - t0}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 40)
