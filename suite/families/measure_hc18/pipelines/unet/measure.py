"""U-Net HC measurement: segment the head, fit an ellipse to the 0.5 iso-contour, perimeter x pixel size."""
import json, math, os, sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from skimage.measure import EllipseModel, find_contours

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import H, W, UNet  # noqa: E402  (copy of measure_hc18/unet/model.py)

WEIGHTS = os.environ.get("HC18_UNET_WEIGHTS", "/home/jkwei/data/vals-suite/measure_hc18/comparators/unet/unet.pt")


def main(inp: Path, out: Path):
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    case = json.loads((inp / "case.json").read_text())
    im = np.asarray(Image.open(inp / "image.png"))
    im = im[..., 0] if im.ndim == 3 else im
    H0, W0 = im.shape
    x = np.asarray(Image.fromarray(im).resize((W, H), Image.BILINEAR), np.float32) / 255.0
    net = UNet()
    net.load_state_dict(torch.load(WEIGHTS, map_location="cpu", weights_only=True))
    net.eval()
    with torch.no_grad():
        p = torch.sigmoid(net(torch.from_numpy(x)[None, None]))[0, 0].numpy()
    p = np.pad(p, 1)  # closes contours touching the border
    cs = find_contours(p, 0.5)
    v = 174.4
    if cs:
        c = max(cs, key=len) - 1.0  # undo pad; (row, col)
        xs = (c[:, 1] + 0.5) * (W0 / W) - 0.5
        ys = (c[:, 0] + 0.5) * (H0 / H) - 0.5
        m = EllipseModel()
        if len(xs) >= 5 and m.estimate(np.stack([xs, ys], 1)):
            a, b = abs(m.params[2]), abs(m.params[3])
            hp = ((a - b) / (a + b)) ** 2
            v = math.pi * (a + b) * (1 + 3 * hp / (10 + math.sqrt(4 - 3 * hp))) * float(case["pixel_size_mm"])
    if not (math.isfinite(v) and 40.0 <= v <= 400.0):
        v = 174.4
    (out / "measurement.csv").write_text(f"case_id,hc_mm\n{case['case_id']},{v:.2f}\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
