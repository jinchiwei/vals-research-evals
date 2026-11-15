"""Small 2D U-Net (about 1.9 M parameters) for the fetal-skull ellipse region."""
import torch
import torch.nn as nn

H, W = 224, 320


def block(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                         nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class UNet(nn.Module):
    def __init__(self, c=16):
        super().__init__()
        ch = [c, 2 * c, 4 * c, 8 * c, 16 * c]
        self.enc = nn.ModuleList([block(1, ch[0])] + [block(ch[i], ch[i + 1]) for i in range(4)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(ch[i + 1], ch[i], 2, stride=2) for i in range(4)])
        self.dec = nn.ModuleList([block(2 * ch[i], ch[i]) for i in range(4)])
        self.head = nn.Conv2d(ch[0], 1, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        skips = []
        for i, e in enumerate(self.enc):
            x = e(x if i == 0 else self.pool(x))
            skips.append(x)
        for i in reversed(range(4)):
            x = self.dec[i](torch.cat([self.up[i](x), skips[i]], 1))
        return self.head(x)
