"""Self-contained comparator / failure pipeline for triage_pharyngitis.

    python3 predict.py INPUT_DIR OUTPUT_DIR

Reads model.json next to this file: {"kind": ..., ...fitted parameters as plain JSON numbers}.
Kinds: rule, symptoms, image, combined (fitted on development patients only), constant, overconfident,
slow, lookup (self-check oracle only; never exported). Writes OUTPUT_DIR/predictions.json in the task format. Uses numpy (+ torch/torchvision/Pillow for
image kinds). The ResNet-50 ImageNet weights are read from model.json's
weights_path (local self-check only), else $TRIAGE_WEIGHTS, else /workspace/data/models/resnet50_imagenet1k_v2.pth.
"""
import csv
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SYMPTOMS = ('feeling_cold', 'sore_throat', 'cephalalgia', 'myalgia', 'rhinorrhea', 'diarrhea', 'vomit', 'cough',
            'pyrexia', 'rigors', 'lethargy', 'sputum', 'abdominal_pain', 'vertigo', 'sternutation', 'eye_infection',
            'otalgia', 'nasal_congestion', 'asthma', 'anorexia')
DEFAULT_WEIGHTS = '/workspace/data/models/resnet50_imagenet1k_v2.pth'
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


def read_patients(input_dir):
    with open(Path(input_dir) / 'patients.csv', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def tabular(rows):
    """Symptom design: 20 symptoms, age/10, child (<15), age>=45, male. Same order everywhere."""
    out = []
    for r in rows:
        age = float(r['age'])
        out.append([float(r[s]) for s in SYMPTOMS] + [age / 10.0, float(age < 15), float(age >= 45),
                                                      float(r['sex'] == 'M')])
    return np.asarray(out, dtype=float)


def mcisaac_partial(rows):
    """McIsaac (1998) items available in this dataset: temperature > 38 C (pyrexia, +1), absence of cough
    (+1), age 3-14 (+1), age >= 45 (-1). Tonsillar swelling/exudate and tender anterior cervical nodes are
    not recorded and count 0. Range -1..3."""
    s = []
    for r in rows:
        age = float(r['age'])
        s.append(int(r['pyrexia']) + (1 - int(r['cough'])) + (1 if 3 <= age <= 14 else 0) - (1 if age >= 45 else 0))
    return np.asarray(s, dtype=int)


def image_features(paths, weights=None, batch=16, device='cpu'):
    """Frozen ImageNet ResNet-50 global-average-pooled features (2048-d). Resize short side 256, centre 224."""
    import torch
    import torchvision
    from PIL import Image
    torch.set_num_threads(max(1, int(os.environ.get('OMP_NUM_THREADS', '2'))))
    model = torchvision.models.resnet50()
    model.load_state_dict(torch.load(weights or os.environ.get('TRIAGE_WEIGHTS', DEFAULT_WEIGHTS),
                                     map_location='cpu', weights_only=True))
    model.fc = torch.nn.Identity()
    model.eval().to(device)
    tf = torchvision.transforms.Compose([
        torchvision.transforms.Resize(256), torchvision.transforms.CenterCrop(224),
        torchvision.transforms.ToTensor(), torchvision.transforms.Normalize(MEAN, STD)])
    feats = []
    with torch.inference_mode():
        for i in range(0, len(paths), batch):
            ims = []
            for p in paths[i:i + batch]:
                im = Image.open(p)
                im.draft('RGB', (512, 512))          # fast JPEG decode at reduced scale for huge photos
                ims.append(tf(im.convert('RGB')))
            feats.append(model(torch.stack(ims).to(device)).float().cpu().numpy())
    return np.concatenate(feats).astype(np.float64)


def linear_logit(x, params):
    x = (x - np.asarray(params['mean'])) / np.asarray(params['scale'])
    return x @ np.asarray(params['coef']) + float(params['intercept'])


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def predict(model, rows, input_dir):
    kind = model['kind']
    if kind == 'constant':
        return np.full(len(rows), float(model['probability']))
    if kind == 'lookup':                   # grader self-check only: probabilities keyed by case_id
        return np.asarray([float(model['probabilities'][r['case_id']]) for r in rows])
    if kind == 'rule':
        table = {int(k): v for k, v in model['probability_by_score'].items()}
        return np.asarray([table[int(s)] for s in mcisaac_partial(rows)], dtype=float)
    if kind in ('symptoms', 'overconfident', 'slow'):
        p = sigmoid(linear_logit(tabular(rows), model['symptoms']))
        if kind == 'overconfident':        # same ranking, probabilities pushed to the extremes
            p = sigmoid(float(model['temperature_multiplier']) * (np.log(p / (1 - p)) - math.log(
                model['centre'] / (1 - model['centre']))))
        if kind == 'slow':
            time.sleep(float(model['sleep_seconds']))
        return p
    paths = [Path(input_dir) / 'images' / f"{r['case_id']}.jpg" for r in rows]
    img_logit = linear_logit(image_features(paths, weights=model.get('weights_path')), model['image'])
    if kind == 'image':
        return sigmoid(img_logit)
    if kind == 'combined':
        x = np.column_stack([img_logit, tabular(rows)])
        return sigmoid(linear_logit(x, model['stacker']))
    raise ValueError(f'unknown kind {kind}')


def main(input_dir, output_dir):
    model = json.loads((HERE / 'model.json').read_text())
    rows = read_patients(input_dir)
    p = predict(model, rows, input_dir)
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    preds = [{'case': r['case_id'], 'probability': float(v)} for r, v in zip(rows, p)]
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / 'predictions.json').write_text(json.dumps({'predictions': preds}))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
