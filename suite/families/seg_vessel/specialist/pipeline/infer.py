"""run.sh INPUT_DIR OUTPUT_DIR: INPUT_DIR/image.jpg -> OUTPUT_DIR/mask.png (0/255, same size)."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

from unet import UNet, predict  # noqa: E402


def main(in_dir, out_dir):
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    params = json.loads((HERE / 'params.json').read_text())
    model = UNet(base=params['base'], depth=params['depth'])
    model.load_state_dict(torch.load(HERE / 'weights.pt', map_location='cpu', weights_only=True))
    model.eval()
    rgb = np.asarray(Image.open(Path(in_dir) / 'image.jpg').convert('RGB'))
    prob = predict(model, rgb)
    mask = (prob > params['threshold']).astype(np.uint8) * 255
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, mode='L').save(Path(out_dir) / 'mask.png')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
