"""run.sh INPUT_DIR OUTPUT_DIR: Frangi mask -> OUTPUT_DIR/mask.png (0/255)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vesselness import segment  # noqa: E402

rgb = np.asarray(Image.open(Path(sys.argv[1]) / 'image.jpg').convert('RGB'))
mask = segment(rgb, json.loads((HERE / 'params.json').read_text()))
Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)
Image.fromarray(mask.astype(np.uint8) * 255, mode='L').save(Path(sys.argv[2]) / 'mask.png')
