"""Train the seg_vessel specialist U-Net on development images only (GPU if available).

    ~/miniconda3/envs/vals-suite-seg_vessel/bin/python -m suite.families.seg_vessel.specialist.train \
        --out suite/families/seg_vessel/specialist/pipeline

Development children are split again by child: 8 children (16 images) train, 2 children (4 images)
select the checkpoint and the probability threshold (mean of Dice and clDice vs the first observer).
Hidden images are never read. Writes weights.pt, params.json and train_log.json into --out.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / 'pipeline'))
from unet import UNet, preprocess  # noqa: E402

from .. import grader  # noqa: E402

DATA_ROOT = Path('/home/jkwei/data/vals-suite/seg_vessel')
SEED = 20261114


def load_dev(data_root):
    split = json.loads((data_root / 'split.json').read_text())
    cases = [r for r in split['cases'] if r['group'] == 'dev']
    out = []
    for r in cases:
        d = data_root / 'staged' / 'dev' / r['case']
        rgb = np.asarray(Image.open(d / 'image.jpg').convert('RGB'))
        lab = np.asarray(Image.open(d / 'label_1stHO.png').convert('L')) > 0
        out.append({'case': r['case'], 'child': r['child'], 'rgb': rgb, 'label': lab})
    return out


def full_prob(model, rgb, device):
    x = torch.from_numpy(preprocess(rgb))[None].to(device)
    h, w = x.shape[-2:]
    ph, pw = (-h) % 16, (-w) % 16
    x = F.pad(x, (0, pw, 0, ph), mode='reflect')
    with torch.no_grad():
        return torch.sigmoid(model(x))[0, 0, :h, :w].float().cpu().numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--iters', type=int, default=4000)
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--patch', type=int, default=256)
    ap.add_argument('--eval-every', type=int, default=250)
    args = ap.parse_args()
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    dev = load_dev(DATA_ROOT)
    children = sorted({c['child'] for c in dev})
    val_children = sorted(rng.choice(children, 2, replace=False).tolist())
    train = [c for c in dev if c['child'] not in val_children]
    val = [c for c in dev if c['child'] in val_children]
    X = torch.stack([torch.from_numpy(preprocess(c['rgb'])) for c in train]).to(device)
    Y = torch.stack([torch.from_numpy(c['label'].astype(np.float32))[None] for c in train]).to(device)
    model = UNet().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=args.iters, pct_start=0.1)
    H, W, P = X.shape[2], X.shape[3], args.patch
    log, best, t0 = [], None, time.time()
    for it in range(1, args.iters + 1):
        model.train()
        idx = torch.randint(0, len(train), (args.batch,))
        ys = torch.randint(0, H - P + 1, (args.batch,))
        xs = torch.randint(0, W - P + 1, (args.batch,))
        xb = torch.stack([X[i, :, y:y + P, x:x + P] for i, y, x in zip(idx, ys, xs)])
        yb = torch.stack([Y[i, :, y:y + P, x:x + P] for i, y, x in zip(idx, ys, xs)])
        if rng.random() < 0.5:
            xb, yb = xb.flip(-1), yb.flip(-1)
        if rng.random() < 0.5:
            xb, yb = xb.flip(-2), yb.flip(-2)
        k = int(rng.integers(0, 4))
        xb, yb = torch.rot90(xb, k, (-2, -1)), torch.rot90(yb, k, (-2, -1))
        xb = xb * (1 + 0.2 * (torch.rand(args.batch, 3, 1, 1, device=device) - 0.5)) \
            + 0.2 * (torch.rand(args.batch, 3, 1, 1, device=device) - 0.5)
        logits = model(xb)
        p = torch.sigmoid(logits)
        soft_dice = 1 - (2 * (p * yb).sum() + 1) / (p.sum() + yb.sum() + 1)
        loss = F.binary_cross_entropy_with_logits(logits, yb) + soft_dice
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if it % args.eval_every == 0 or it == args.iters:
            model.eval()
            probs = [full_prob(model, c['rgb'], device) for c in val]
            rows = []
            for thr in np.arange(0.30, 0.71, 0.05):
                d = [grader.dice(c['label'], p > thr) for c, p in zip(val, probs)]
                cl = [grader.cldice(c['label'], p > thr) for c, p in zip(val, probs)]
                rows.append((float(np.mean(d) / 2 + np.mean(cl) / 2), float(thr), float(np.mean(d)), float(np.mean(cl))))
            score, thr, d, cl = max(rows)
            entry = {'iter': it, 'loss': float(loss), 'val_score': score, 'thr': thr, 'val_dice': d,
                     'val_cldice': cl, 'sec': round(time.time() - t0, 1)}
            log.append(entry)
            print(json.dumps(entry), flush=True)
            if best is None or score > best[0]:
                best = (score, thr, it, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    args.out.mkdir(parents=True, exist_ok=True)
    torch.save(best[3], args.out / 'weights.pt')
    (args.out / 'params.json').write_text(json.dumps({'threshold': round(best[1], 2), 'base': 16, 'depth': 4}) + '\n')
    (args.out.parent / 'train_log.json').write_text(json.dumps({
        'device': torch.cuda.get_device_name(0) if device == 'cuda' else 'cpu', 'train_children': sorted(
            {c['child'] for c in train}), 'val_children': val_children, 'iters': args.iters, 'batch': args.batch,
        'patch': args.patch, 'best_iter': best[2], 'best_val_score': best[0], 'threshold': best[1],
        'seconds': round(time.time() - t0, 1), 'log': log}, indent=1) + '\n')
    print('best', best[:3])


if __name__ == '__main__':
    main()
