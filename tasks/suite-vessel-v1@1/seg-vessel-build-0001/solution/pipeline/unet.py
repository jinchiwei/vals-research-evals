"""Small 2D U-Net for retinal vessels (4 levels, base width 16, ~0.5 M parameters)."""
import torch
from torch import nn


def block(cin, cout):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                         nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))


class UNet(nn.Module):
    def __init__(self, cin=3, base=16, depth=4):
        super().__init__()
        widths = [base * 2 ** i for i in range(depth + 1)]
        self.down = nn.ModuleList([block(cin, widths[0])] + [block(widths[i], widths[i + 1]) for i in range(depth)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(widths[i + 1], widths[i], 2, stride=2) for i in reversed(range(depth))])
        self.dec = nn.ModuleList([block(widths[i] * 2, widths[i]) for i in reversed(range(depth))])
        self.head = nn.Conv2d(widths[0], 1, 1)
        self.pool = nn.MaxPool2d(2)
        self.multiple = 2 ** depth

    def forward(self, x):
        skips = []
        for i, d in enumerate(self.down):
            x = d(x if i == 0 else self.pool(x))
            skips.append(x)
        x = skips.pop()
        for up, dec in zip(self.up, self.dec):
            x = dec(torch.cat([up(x), skips.pop()], 1))
        return self.head(x)


def preprocess(rgb):
    """uint8 HxWx3 -> float32 3xHxW, per-image channel standardisation."""
    import numpy as np
    x = rgb.astype(np.float32) / 255.0
    m, s = x.reshape(-1, 3).mean(0), x.reshape(-1, 3).std(0) + 1e-6
    return ((x - m) / s).transpose(2, 0, 1).copy()


def predict(model, rgb, multiple=16):
    """Full-image probability map (H, W) on CPU, reflect-padded to a multiple of the stride."""
    import numpy as np
    import torch.nn.functional as F
    x = torch.from_numpy(preprocess(rgb))[None]
    h, w = x.shape[-2:]
    ph, pw = (-h) % multiple, (-w) % multiple
    x = F.pad(x, (0, pw, 0, ph), mode='reflect')
    with torch.no_grad():
        p = torch.sigmoid(model(x))[0, 0, :h, :w]
    return p.numpy()
